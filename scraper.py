import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# D&V STORE — AppleAvenue scraper
# ============================================================

BASE_URL = "https://apple-avenue.ru"

OUTPUT_FILE = Path("products.json")
IMAGES_DIR = Path("images")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


# ============================================================
# КАТЕГОРИИ
# ============================================================

CATEGORY_URLS = {
    "Apple": [
        "/catalog/iphone/",
        "/catalog/ipad/",
        "/catalog/macbook_air_1/",
        "/catalog/macbook_pro_1/",
        "/catalog/apple_watch/",
        "/catalog/airpods/",
    ],

    "Samsung": [
        "/catalog/samsung/",
    ],

    "Xiaomi": [
        "/catalog/xiaomi/",
    ],

    "Honor": [
        "/catalog/honor/",
    ],

    "Google": [
        "/catalog/google/",
    ],

    "OnePlus": [
        "/catalog/oneplus/",
    ],

    "Huawei": [
        "/catalog/huawei/",
    ],

    "Nothing": [
        "/catalog/nothing/",
    ],
}


session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url):
    if not url:
        return ""

    url = url.split("#")[0]

    return url.rstrip("/")


def make_id(name, url):
    value = f"{name}-{url}".lower()

    value = re.sub(
        r"[^a-zа-я0-9]+",
        "-",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(r"-+", "-", value)

    return value.strip("-")[:150]


def get_soup(url):
    try:
        response = session.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        return BeautifulSoup(
            response.text,
            "html.parser",
        )

    except Exception as error:
        print(f"[ERROR] {url}")
        print(error)
        return None


# ============================================================
# ЦЕНА
# ============================================================

def extract_price(soup):
    if soup is None:
        return ""

    # Сначала ищем JSON-LD
    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):
        try:
            data = json.loads(
                script.string or script.get_text()
            )

            objects = (
                data
                if isinstance(data, list)
                else [data]
            )

            for obj in objects:

                if not isinstance(obj, dict):
                    continue

                offers = obj.get("offers")

                if isinstance(offers, dict):
                    price = offers.get("price")

                    if price:
                        return format_price(price)

        except Exception:
            pass

    # Потом ищем классы Bitrix
    selectors = [
        ".price",
        ".product-item-price-current",
        ".catalog-detail-price",
        ".price_value",
        ".product-price",
        ".detail_price",
    ]

    for selector in selectors:

        element = soup.select_one(selector)

        if element:

            text = clean_text(
                element.get_text(" ", strip=True)
            )

            price = extract_price_from_text(text)

            if price:
                return price

    # Последний вариант — весь текст
    text = clean_text(
        soup.get_text(" ", strip=True)
    )

    return extract_price_from_text(text)


def extract_price_from_text(text):

    if not text:
        return ""

    patterns = [
        r"(\d[\d\s]{2,})\s*(?:₽|руб\.?|рублей)",
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

                return format_price(
                    number
                )

    return ""


def format_price(value):

    value = str(value)

    value = re.sub(
        r"[^\d]",
        "",
        value,
    )

    if not value:
        return ""

    return f"{int(value):,}".replace(
        ",",
        " ",
    ) + " ₽"


# ============================================================
# НАЗВАНИЕ
# ============================================================

def extract_name(soup):

    if soup is None:
        return ""

    h1 = soup.find("h1")

    if h1:

        name = clean_text(
            h1.get_text(
                " ",
                strip=True,
            )
        )

        if name:
            return name

    meta = soup.find(
        "meta",
        property="og:title",
    )

    if meta:

        name = clean_text(
            meta.get("content", "")
        )

        if name:
            return name

    title = soup.find("title")

    if title:

        name = clean_text(
            title.get_text(
                " ",
                strip=True,
            )
        )

        name = re.sub(
            r"\s*купить.*$",
            "",
            name,
            flags=re.IGNORECASE,
        )

        return name.strip()

    return ""


# ============================================================
# ФОТО
# ============================================================

def get_image_url(product_url, soup):

    if soup is None:
        return ""

    # OG image
    meta = soup.find(
        "meta",
        property="og:image",
    )

    if meta:

        content = meta.get(
            "content"
        )

        if content:

            return urljoin(
                product_url,
                content,
            )

    # Twitter image
    meta = soup.find(
        "meta",
        attrs={
            "name": "twitter:image"
        },
    )

    if meta:

        content = meta.get(
            "content"
        )

        if content:

            return urljoin(
                product_url,
                content,
            )

    # Изображения товара
    selectors = [
        ".product-detail-image img",
        ".catalog-detail-image img",
        ".product-image img",
        ".detail-picture img",
        ".product-item-image img",
    ]

    for selector in selectors:

        img = soup.select_one(
            selector
        )

        if img:

            src = (
                img.get("data-src")
                or img.get("data-original")
                or img.get("src")
            )

            if src and not src.startswith("data:"):

                return urljoin(
                    product_url,
                    src,
                )

    # Последний вариант
    for img in soup.find_all("img"):

        src = (
            img.get("data-src")
            or img.get("data-original")
            or img.get("src")
        )

        if not src:
            continue

        if src.startswith("data:"):
            continue

        full = urljoin(
            product_url,
            src,
        )

        parsed = urlparse(full)

        if parsed.netloc == urlparse(
            BASE_URL
        ).netloc:

            return full

    return ""


def download_image(url, product_id):

    if not url:
        return ""

    try:

        IMAGES_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        parsed = urlparse(url)

        extension = Path(
            parsed.path
        ).suffix.lower()

        if extension not in [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        ]:
            extension = ".jpg"

        filename = (
            product_id
            + extension
        )

        destination = (
            IMAGES_DIR
            / filename
        )

        response = session.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        content_type = (
            response.headers
            .get("content-type", "")
            .lower()
        )

        if (
            "image" not in content_type
            and not url.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            )
        ):
            print(
                "[IMAGE SKIP]",
                url,
            )

            return ""

        destination.write_bytes(
            response.content
        )

        print(
            "[IMAGE OK]",
            filename,
        )

        return (
            f"images/{filename}"
        )

    except Exception as error:

        print(
            "[IMAGE ERROR]",
            url,
            error,
        )

        return ""


# ============================================================
# ПАМЯТЬ
# ============================================================

def detect_memory(text):

    if not text:
        return ""

    match = re.search(
        r"\b("
        r"64|128|256|512|1024|2048"
        r")\s*"
        r"(ГБ|GB|TB|ТБ)"
        r"\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    value = match.group(1)
    unit = match.group(2).lower()

    if unit in ["tb", "тб"]:
        return f"{value} ТБ"

    return f"{value} ГБ"


# ============================================================
# ЦВЕТ
# ============================================================

def detect_color(text):

    if not text:
        return ""

    colors = [
        "черный",
        "чёрный",
        "black",

        "белый",
        "white",

        "синий",
        "blue",

        "голубой",

        "красный",
        "red",

        "зеленый",
        "зелёный",
        "green",

        "оранжевый",
        "orange",

        "фиолетовый",
        "purple",

        "розовый",
        "pink",

        "желтый",
        "жёлтый",
        "yellow",

        "золотой",
        "gold",

        "серебристый",
        "silver",

        "серый",
        "gray",
        "grey",

        "титановый",
        "titanium",

        "графитовый",
        "graphite",
    ]

    lower = text.lower()

    for color in colors:

        if color in lower:

            return color.capitalize()

    return ""


# ============================================================
# ПРОВЕРКА — ЭТО ТОВАР ИЛИ НЕТ
# ============================================================

def looks_like_product(url, name):

    if not name:
        return False

    path = urlparse(url).path.lower()

    bad_parts = [
        "/catalog/",
        "/filter/",
        "/search/",
        "/compare/",
        "/favorite/",
        "/cart/",
        "/personal/",
        "/services/",
        "/news/",
        "/brands/",
    ]

    # Если это сама категория
    if path.endswith("/catalog/"):
        return False

    # Сама страница категории
    if path.count("/") <= 3:
        return False

    # Фильтры не товары
    if "/filter/" in path:
        return False

    # Название должно быть похожим
    product_words = [
        "iphone",
        "ipad",
        "macbook",
        "airpods",
        "apple watch",
        "samsung",
        "galaxy",
        "xiaomi",
        "redmi",
        "poco",
        "honor",
        "pixel",
        "oneplus",
        "huawei",
        "nothing",
    ]

    lower_name = name.lower()

    return any(
        word in lower_name
        for word in product_words
    )


# ============================================================
# ССЫЛКИ НА ТОВАРЫ
# ============================================================

def get_product_links(category_url):

    category_full_url = urljoin(
        BASE_URL,
        category_url,
    )

    soup = get_soup(
        category_full_url
    )

    if soup is None:
        return []

    links = set()

    domain = urlparse(
        BASE_URL
    ).netloc

    for a in soup.find_all("a"):

        href = a.get("href")

        if not href:
            continue

        full_url = normalize_url(
            urljoin(
                category_full_url,
                href,
            )
        )

        parsed = urlparse(
            full_url
        )

        if parsed.netloc != domain:
            continue

        if "/filter/" in parsed.path:
            continue

        if any(
            bad in parsed.path.lower()
            for bad in [
                "/search/",
                "/compare/",
                "/favorite/",
                "/cart/",
                "/personal/",
            ]
        ):
            continue

        # Не добавляем саму категорию
        if normalize_url(
            full_url
        ) == normalize_url(
            category_full_url
        ):
            continue

        # Берём только ссылки, где текст похож
        link_text = clean_text(
            a.get_text(
                " ",
                strip=True,
            )
        )

        href_lower = parsed.path.lower()

        product_hint = (
            any(
                word in href_lower
                for word in [
                    "iphone",
                    "ipad",
                    "macbook",
                    "airpods",
                    "watch",
                    "samsung",
                    "galaxy",
                    "xiaomi",
                    "redmi",
                    "poco",
                    "honor",
                    "pixel",
                    "oneplus",
                    "huawei",
                    "nothing",
                ]
            )
            or len(link_text) > 8
        )

        if product_hint:

            links.add(
                full_url
            )

    return sorted(links)


# ============================================================
# ПАРСИНГ ТОВАРА
# ============================================================

def parse_product(url, category):

    print(
        "[PRODUCT]",
        url,
    )

    soup = get_soup(url)

    if soup is None:
        return None

    name = extract_name(
        soup
    )

    if not looks_like_product(
        url,
        name,
    ):
        return None

    text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    price = extract_price(
        soup
    )

    if not price:
        price = "Цена уточняется"

    memory = detect_memory(
        name + " " + text
    )

    color = detect_color(
        name
    )

    if not color:

        color = detect_color(
            text
        )

    image_url = get_image_url(
        url,
        soup,
    )

    product_id = make_id(
        name,
        url,
    )

    local_image = download_image(
        image_url,
        product_id,
    )

    available = (
        "в наличии" in text.lower()
        or "есть в наличии" in text.lower()
    )

    return {
        "id": product_id,
        "name": name,
        "price": price,
        "brand": category,
        "category": category,
        "memory": memory,
        "color": color,
        "available": available,
        "image": local_image,
        "source": "AppleAvenue",
        "source_url": url,
        "updated": time.strftime(
            "%Y-%m-%d %H:%M"
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("D&V STORE — APPLE AVENUE SCRAPER")
    print("=" * 70)

    all_products = []
    seen_urls = set()

    for category, category_urls in CATEGORY_URLS.items():

        print()
        print(
            f"========== {category} =========="
        )

        for category_url in category_urls:

            links = get_product_links(
                category_url
            )

            print(
                f"[CATEGORY] {category_url}"
            )

            print(
                f"[LINKS] найдено: {len(links)}"
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
                        error,
                    )

                time.sleep(0.5)

    # Убираем дубликаты
    unique = {}

    for product in all_products:

        unique[
            product["id"]
        ] = product

    products = list(
        unique.values()
    )

    products.sort(
        key=lambda x:
        x["name"].lower()
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            products,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print(
        f"ГОТОВО! ТОВАРОВ: {len(products)}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
