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
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

# Категории, которые хотим собирать
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


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_id(name, url):
    value = f"{name}-{url}"

    value = value.lower()

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

    # Ищем цену вида:
    # 75 550 руб.
    # 75550 руб.
    # 75 550 ₽

    match = re.search(
        r"(\d[\d\s]{2,})\s*(?:руб\.?|₽)",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    number = re.sub(r"\D", "", match.group(1))

    if not number:
        return ""

    return f"{int(number):,}".replace(",", " ") + " ₽"


def detect_memory(text):
    match = re.search(
        r"\b(64|128|256|512|1024|2048)\s*(?:ГБ|GB|Tb|TB|ТБ)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    value = match.group(1)
    unit = match.group(0).lower()

    if "tb" in unit or "тб" in unit:
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
    ]

    lower = text.lower()

    for color in colors:
        if color in lower:
            return color.capitalize()

    return ""


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


def get_image_url(product_url, soup):
    if soup is None:
        return ""

    # Сначала OG image
    meta = soup.find(
        "meta",
        property="og:image",
    )

    if meta and meta.get("content"):
        return urljoin(
            product_url,
            meta["content"],
        )

    # Потом обычные изображения
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

        src = urljoin(
            product_url,
            src,
        )

        if "apple-avenue.ru" in src:
            return src

    return ""


def download_image(url, product_id):
    if not url:
        return ""

    try:

        IMAGES_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        extension = ".jpg"

        parsed = urlparse(url)

        original_extension = Path(
            parsed.path
        ).suffix.lower()

        if original_extension in [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        ]:
            extension = original_extension

        filename = (
            product_id
            + extension
        )

        destination = (
            IMAGES_DIR
            / filename
        )

        if destination.exists():
            return f"images/{filename}"

        response = session.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

        if (
            "image" not in content_type
            and not original_extension
        ):
            print(
                "[WARNING] URL не похож на изображение:",
                url,
            )
            return ""

        destination.write_bytes(
            response.content
        )

        print(
            "[IMAGE]",
            filename,
        )

        return f"images/{filename}"

    except Exception as error:

        print(
            "[IMAGE ERROR]",
            url,
            error,
        )

        return ""


def parse_product(url, category):
    print(
        "[PRODUCT]",
        url,
    )

    soup = get_soup(url)

    if soup is None:
        return None

    # Название
    name = ""

    h1 = soup.find("h1")

    if h1:
        name = clean_text(
            h1.get_text(" ", strip=True)
        )

    if not name:

        meta = soup.find(
            "meta",
            property="og:title",
        )

        if meta:
            name = clean_text(
                meta.get("content", "")
            )

    if not name:
        return None

    page_text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    # Цена
    price = extract_price(
        page_text
    )

    if not price:
        price = "Цена уточняется"

    # Наличие
    available = (
        "В наличии" in page_text
        or "в наличии" in page_text
    )

    # Память
    memory = detect_memory(
        name + " " + page_text
    )

    # Цвет
    color = detect_color(
        name
    )

    # Если в названии цвет не нашли,
    # ищем на странице
    if not color:
        color = detect_color(
            page_text
        )

    # Фото
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

    product = {
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
            "%Y-%m-%d"
        ),
    }

    return product


def get_product_links(category_url):
    url = urljoin(
        BASE_URL,
        category_url,
    )

    soup = get_soup(url)

    if soup is None:
        return []

    links = set()

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

        if parsed.netloc != urlparse(
            BASE_URL
        ).netloc:
            continue

        path = parsed.path

        # Пропускаем служебные страницы
        if any(
            x in path.lower()
            for x in [
                "/search/",
                "/compare/",
                "/favorite/",
                "/cart/",
                "/personal/",
            ]
        ):
            continue

        # Только страницы товаров
        if path.rstrip("/") == category_url.rstrip("/"):
            continue

        # Не берем ссылки на корень
        if path in ["", "/"]:
            continue

        links.add(
            full_url
        )

    return sorted(links)


def load_existing():
    if not OUTPUT_FILE.exists():
        return []

    try:

        return json.loads(
            OUTPUT_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return []


def save_products(products):

    OUTPUT_FILE.write_text(
        json.dumps(
            products,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        f"[DONE] Сохранено товаров: {len(products)}"
    )


def main():

    print("=" * 60)
    print("D&V STORE — AppleAvenue scraper")
    print("=" * 60)

    all_products = []

    seen_urls = set()

    for category, urls in CATEGORY_URLS.items():

        print()
        print(
            f"========== {category} =========="
        )

        for category_url in urls:

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

                product = parse_product(
                    product_url,
                    category,
                )

                if product:

                    all_products.append(
                        product
                    )

                # Не создаём бешеную нагрузку
                time.sleep(0.5)

    # Удаляем дубликаты
    unique = {}

    for product in all_products:

        unique[
            product["id"]
        ] = product

    all_products = list(
        unique.values()
    )

    all_products.sort(
        key=lambda x: x["name"].lower()
    )

    save_products(
        all_products
    )


if __name__ == "__main__":
    main()
