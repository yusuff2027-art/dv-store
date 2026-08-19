import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://apple-avenue.ru"

OUTPUT_FILE = Path("products.json")
IMAGES_DIR = Path("images")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/",
}


CATEGORY_URLS = {
    "Apple": [
        "/catalog/iphone/",
        "/catalog/ipad/",
        "/catalog/macbook_air_1/",
        "/catalog/macbook_pro_1/",
        "/catalog/apple_watch/",
        "/catalog/airpods/",
    ],
    "Samsung": ["/catalog/samsung/"],
    "Xiaomi": ["/catalog/xiaomi/"],
    "Honor": ["/catalog/honor/"],
    "Google": ["/catalog/google/"],
    "OnePlus": ["/catalog/oneplus/"],
    "Huawei": ["/catalog/huawei/"],
    "Nothing": ["/catalog/nothing/"],
}


session = requests.Session()
session.headers.update(HEADERS)


def prepare_images_folder():
    """
    Создаём images.
    Если images случайно является файлом — удаляем его.
    """

    if IMAGES_DIR.exists() and not IMAGES_DIR.is_dir():
        print("[WARNING] images существует как файл. Удаляем...")
        IMAGES_DIR.unlink()

    IMAGES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_id(name, url):
    value = f"{name}-{url}".lower()

    value = re.sub(
        r"[^a-zа-я0-9]+",
        "-",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(r"-+", "-", value)

    return value.strip("-")[:120]


def extract_price(text):
    if not text:
        return ""

    patterns = [
        r"(\d[\d\s]{2,})\s*(?:руб\.?|₽)",
        r"(\d[\d\s]{2,})\s*р\.",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            number = re.sub(
                r"\D",
                "",
                match.group(1),
            )

            if number:
                return (
                    f"{int(number):,}"
                    .replace(",", " ")
                    + " ₽"
                )

    return ""


def detect_memory(text):

    match = re.search(
        r"\b(32|64|128|256|512|1024|2048)\s*"
        r"(ГБ|GB|ТБ|TB)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    value = match.group(1)
    unit = match.group(2).upper()

    if unit in ["TB", "ТБ"]:
        return f"{value} ТБ"

    return f"{value} ГБ"


def detect_color(text):

    colors = [
        "черный",
        "чёрный",
        "белый",
        "серебристый",
        "серебро",
        "синий",
        "голубой",
        "оранжевый",
        "зеленый",
        "зелёный",
        "фиолетовый",
        "розовый",
        "желтый",
        "жёлтый",
        "золотой",
        "титановый",
        "графитовый",
        "серый",
        "красный",
        "бежевый",
        "фиолетовый",
    ]

    lower = text.lower()

    for color in colors:

        if color in lower:
            return color.capitalize()

    return ""


def get_response(url):

    try:

        response = session.get(
            url,
            timeout=30,
            allow_redirects=True,
        )

        response.raise_for_status()

        return response

    except Exception as error:

        print(
            "[ERROR]",
            url,
            error,
        )

        return None


def get_soup(url):

    response = get_response(url)

    if response is None:
        return None

    return BeautifulSoup(
        response.text,
        "html.parser",
    )


def collect_image_urls(product_url, soup):

    if soup is None:
        return []

    result = []

    def add_url(value):

        if not value:
            return

        value = value.strip()

        if value.startswith("data:"):
            return

        value = urljoin(
            product_url,
            value,
        )

        if value not in result:
            result.append(value)

    # OG IMAGE
    for meta in soup.find_all(
        "meta",
        property="og:image",
    ):

        add_url(
            meta.get("content")
        )

    # Twitter image
    for meta in soup.find_all(
        "meta",
        attrs={"name": "twitter:image"},
    ):

        add_url(
            meta.get("content")
        )

    # IMG
    for img in soup.find_all("img"):

        attributes = [
            "src",
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-image",
            "data-fancybox",
        ]

        for attribute in attributes:

            value = img.get(attribute)

            if value:
                add_url(value)

    # srcset
    for img in soup.find_all("img"):

        srcset = img.get("srcset")

        if srcset:

            for item in srcset.split(","):

                value = item.strip().split(" ")[0]

                add_url(value)

    # LINK preload
    for link in soup.find_all(
        "link",
        rel="preload",
    ):

        if link.get("as") == "image":

            add_url(
                link.get("href")
            )

    # Оставляем только изображения
    image_urls = []

    for url in result:

        lower = url.lower()

        if any(
            extension in lower
            for extension in [
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".avif",
            ]
        ):

            if url not in image_urls:
                image_urls.append(url)

    return image_urls


def download_image(url, product_id):

    if not url:
        return ""

    prepare_images_folder()

    try:

        response = session.get(
            url,
            timeout=30,
            allow_redirects=True,
            headers={
                **HEADERS,
                "Referer": BASE_URL + "/",
            },
        )

        response.raise_for_status()

        content_type = (
            response.headers
            .get(
                "content-type",
                "",
            )
            .lower()
        )

        # Проверяем, действительно ли это картинка
        if not content_type.startswith("image/"):

            print(
                "[SKIP IMAGE]",
                url,
                content_type,
            )

            return ""

        extension = ".jpg"

        if "png" in content_type:
            extension = ".png"

        elif "webp" in content_type:
            extension = ".webp"

        elif "avif" in content_type:
            extension = ".avif"

        elif "jpeg" in content_type:
            extension = ".jpg"

        filename = (
            product_id
            + extension
        )

        destination = (
            IMAGES_DIR
            / filename
        )

        destination.write_bytes(
            response.content
        )

        print(
            "[IMAGE OK]",
            filename,
        )

        return (
            "images/"
            + filename
        )

    except Exception as error:

        print(
            "[IMAGE ERROR]",
            url,
            error,
        )

        return ""


def get_product_image(product_url, soup, product_id):

    image_urls = collect_image_urls(
        product_url,
        soup,
    )

    print(
        f"[IMAGES FOUND] {len(image_urls)}"
    )

    for image_url in image_urls:

        local_image = download_image(
            image_url,
            product_id,
        )

        if local_image:
            return local_image

    return ""


def parse_product(url, category):

    print()
    print(
        "[PRODUCT]",
        url,
    )

    soup = get_soup(url)

    if soup is None:
        return None

    # -------------------------
    # NAME
    # -------------------------

    name = ""

    h1 = soup.find("h1")

    if h1:

        name = clean_text(
            h1.get_text(
                " ",
                strip=True,
            )
        )

    if not name:

        meta = soup.find(
            "meta",
            property="og:title",
        )

        if meta:

            name = clean_text(
                meta.get(
                    "content",
                    "",
                )
            )

    if not name:
        return None

    # -------------------------
    # TEXT
    # -------------------------

    page_text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    # -------------------------
    # PRICE
    # -------------------------

    price = extract_price(
        page_text
    )

    if not price:

        # Попробуем meta
        price_meta = soup.find(
            "meta",
            property="product:price:amount",
        )

        if price_meta:

            value = price_meta.get(
                "content",
                "",
            )

            if value:

                try:

                    price = (
                        f"{float(value):,.0f}"
                        .replace(",", " ")
                        + " ₽"
                    )

                except Exception:
                    pass

    if not price:
        price = "Цена уточняется"

    # -------------------------
    # AVAILABLE
    # -------------------------

    lower_text = page_text.lower()

    unavailable_words = [
        "нет в наличии",
        "нет на складе",
        "под заказ",
        "распродан",
    ]

    available = not any(
        word in lower_text
        for word in unavailable_words
    )

    if "в наличии" in lower_text:
        available = True

    # -------------------------
    # MEMORY
    # -------------------------

    memory = detect_memory(
        name + " " + page_text
    )

    # -------------------------
    # COLOR
    # -------------------------

    color = detect_color(
        name
    )

    if not color:

        color = detect_color(
            page_text
        )

    # -------------------------
    # ID
    # -------------------------

    product_id = make_id(
        name,
        url,
    )

    # -------------------------
    # IMAGE
    # -------------------------

    image = get_product_image(
        url,
        soup,
        product_id,
    )

    # -------------------------
    # PRODUCT
    # -------------------------

    product = {

        "id": product_id,

        "name": name,

        "price": price,

        "brand": category,

        "category": category,

        "memory": memory,

        "color": color,

        "available": available,

        "image": image,

        "source": "AppleAvenue",

        "source_url": url,

        "updated": time.strftime(
            "%Y-%m-%d"
        ),
    }

    print(
        "[RESULT]",
        name,
        "|",
        price,
        "|",
        image or "NO IMAGE",
    )

    return product


def get_product_links(category_url):

    url = urljoin(
        BASE_URL,
        category_url,
    )

    print(
        "[CATEGORY]",
        url,
    )

    soup = get_soup(url)

    if soup is None:
        return []

    links = set()

    base_domain = urlparse(
        BASE_URL
    ).netloc

    for a in soup.find_all("a"):

        href = a.get("href")

        if not href:
            continue

        full_url = urljoin(
            url,
            href,
        )

        parsed = urlparse(
            full_url
        )

        if parsed.netloc != base_domain:
            continue

        path = parsed.path

        if path in [
            "",
            "/",
        ]:
            continue

        if any(
            blocked in path.lower()
            for blocked in [
                "/search/",
                "/compare/",
                "/favorite/",
                "/cart/",
                "/personal/",
                "/login/",
                "/register/",
            ]
        ):
            continue

        if (
            path.rstrip("/")
            ==
            category_url.rstrip("/")
        ):
            continue

        # Ссылка должна вести внутрь каталога
        if "/catalog/" not in path:
            continue

        links.add(
            full_url
        )

    return sorted(links)


def save_products(products):

    OUTPUT_FILE.write_text(
        json.dumps(
            products,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    photos = sum(
        1
        for product in products
        if product.get("image")
    )

    prices = sum(
        1
        for product in products
        if (
            product.get("price")
            and product.get("price")
            != "Цена уточняется"
        )
    )

    print()
    print("=" * 60)
    print(
        f"Товаров в каталоге: {len(products)}"
    )
    print(
        f"С фотографиями: {photos}"
    )
    print(
        f"С ценами: {prices}"
    )
    print("=" * 60)


def main():

    print("=" * 60)
    print(
        "D&V STORE — APPLE AVENUE SCRAPER"
    )
    print("=" * 60)

    # ВАЖНО:
    # Исправляет FileExistsError
    prepare_images_folder()

    all_products = []

    seen_urls = set()

    for category, category_urls in CATEGORY_URLS.items():

        print()
        print(
            "=" * 40
        )
        print(
            f"КАТЕГОРИЯ: {category}"
        )
        print(
            "=" * 40
        )

        for category_url in category_urls:

            links = get_product_links(
                category_url
            )

            print(
                f"{category_url}: "
                f"{len(links)} ссылок"
            )

            for product_url in links:

                if product_url in seen_urls:
                    continue

                seen_urls.add(
                    product_url
                )

                try:

                    product = parse_product(
                        product_url,
                        category,
                    )

                    if product:
                        all_products.append(
                            product
                        )

                except Exception as error:

                    print(
                        "[PRODUCT ERROR]",
                        product_url,
                    )

                    print(error)

                time.sleep(0.5)

    # -------------------------
    # DEDUPLICATION
    # -------------------------

    unique = {}

    for product in all_products:

        unique[
            product["id"]
        ] = product

    all_products = list(
        unique.values()
    )

    all_products.sort(
        key=lambda product:
        product["name"].lower()
    )

    save_products(
        all_products
    )


if __name__ == "__main__":
    main()
