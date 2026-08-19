import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://apple-avenue.ru"
CATALOG_URL = "https://apple-avenue.ru/catalog/"

OUTPUT_FILE = Path("products.json")
IMAGES_DIR = Path("images")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL + "/",
}

session = requests.Session()
session.headers.update(HEADERS)


def clean(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def make_id(name, url):
    value = f"{name}-{url}".lower()
    value = re.sub(r"[^a-zа-я0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")[:150]


def get_soup(url):
    try:
        r = session.get(url, timeout=30)

        print(f"[HTTP {r.status_code}] {url}")

        if r.status_code != 200:
            return None

        return BeautifulSoup(r.text, "html.parser")

    except Exception as e:
        print("[REQUEST ERROR]", url, e)
        return None


def extract_price(text):
    if not text:
        return ""

    patterns = [
        r"(\d[\d\s]{2,})\s*руб\.?",
        r"(\d[\d\s]{2,})\s*₽",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.I)

        if m:
            number = re.sub(r"\D", "", m.group(1))

            if number:
                return f"{int(number):,}".replace(",", " ") + " ₽"

    return ""


def extract_memory(text):
    if not text:
        return ""

    m = re.search(
        r"\b(64|128|256|512|1024|2048)\s*(ГБ|GB|ТБ|TB)\b",
        text,
        re.I,
    )

    if not m:
        return ""

    value = m.group(1)
    unit = m.group(2).upper()

    if unit in ("TB", "ТБ"):
        unit = "ТБ"
    else:
        unit = "ГБ"

    return f"{value} {unit}"


def extract_color(text):
    colors = [
        "Deep Blue",
        "Cosmic Orange",
        "Black Titanium",
        "White Titanium",
        "Natural Titanium",
        "Blue Titanium",
        "Desert Titanium",
        "Midnight",
        "Starlight",
        "Black",
        "White",
        "Blue",
        "Green",
        "Pink",
        "Purple",
        "Yellow",
        "Red",
        "Orange",
        "Silver",
        "Grey",
        "Gray",
        "Черный",
        "Чёрный",
        "Белый",
        "Синий",
        "Зеленый",
        "Зелёный",
        "Розовый",
        "Фиолетовый",
        "Желтый",
        "Жёлтый",
        "Красный",
        "Оранжевый",
        "Серебристый",
        "Графитовый",
        "Титановый",
    ]

    lower = text.lower()

    for color in colors:
        if color.lower() in lower:
            return color

    return ""


def get_image(soup, product_url):
    if soup is None:
        return ""

    # 1. OpenGraph
    for prop in ["og:image", "og:image:url"]:

        meta = soup.find("meta", property=prop)

        if meta and meta.get("content"):
            return urljoin(
                product_url,
                meta["content"],
            )

    # 2. Twitter image
    meta = soup.find(
        "meta",
        attrs={"name": "twitter:image"},
    )

    if meta and meta.get("content"):
        return urljoin(
            product_url,
            meta["content"],
        )

    # 3. Картинки товара
    for img in soup.find_all("img"):

        src = (
            img.get("data-src")
            or img.get("data-original")
            or img.get("data-lazy")
            or img.get("src")
        )

        if not src:
            continue

        if src.startswith("data:"):
            continue

        full = urljoin(product_url, src)

        if "apple-avenue.ru" in full:
            return full

    return ""


def download_image(image_url, product_id):

    if not image_url:
        return ""

    try:

        IMAGES_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        parsed = urlparse(image_url)

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

        filename = product_id + extension

        destination = (
            IMAGES_DIR / filename
        )

        if destination.exists():
            return f"images/{filename}"

        r = session.get(
            image_url,
            timeout=30,
            headers={
                "Referer": BASE_URL + "/"
            },
        )

        if r.status_code != 200:
            return ""

        if len(r.content) < 1000:
            return ""

        destination.write_bytes(
            r.content
        )

        print(
            "[IMAGE]",
            filename,
        )

        return f"images/{filename}"

    except Exception as e:

        print(
            "[IMAGE ERROR]",
            image_url,
            e,
        )

        return ""


def looks_like_product(url, text):

    path = urlparse(url).path.lower()

    # Исключаем служебные страницы
    excluded = [
        "/search/",
        "/compare/",
        "/favorite/",
        "/cart/",
        "/personal/",
        "/catalog/compare",
        "/catalog/favorite",
    ]

    if any(x in path for x in excluded):
        return False

    # Ссылка должна быть внутри catalog
    if not path.startswith("/catalog/"):
        return False

    # Не сама категория
    if path.rstrip("/") in [
        "/catalog",
        "/catalog/iphone",
    ]:
        # iPhone здесь специально не исключаем ниже
        pass

    text = clean(text).lower()

    keywords = [
        "iphone",
        "ipad",
        "macbook",
        "airpods",
        "apple watch",
        "samsung galaxy",
        "xiaomi",
        "redmi",
        "poco",
        "huawei",
        "honor",
        "google pixel",
        "oneplus",
        "nothing phone",
    ]

    return any(
        keyword in text
        for keyword in keywords
    )


def get_product_links():

    print()
    print("=" * 60)
    print("ИЩЕМ ТОВАРЫ")
    print("=" * 60)

    links = set()

    # Реальные категории AppleAvenue
    catalog_pages = [
        "/catalog/iphone/",
        "/catalog/apple/",
        "/catalog/",
    ]

    for category in catalog_pages:

        url = urljoin(
            BASE_URL,
            category,
        )

        soup = get_soup(url)

        if not soup:
            continue

        print(
            f"[CATALOG] {url}"
        )

        for a in soup.find_all("a"):

            href = a.get("href")

            if not href:
                continue

            full = urljoin(
                url,
                href,
            )

            parsed = urlparse(full)

            if parsed.netloc != urlparse(
                BASE_URL
            ).netloc:
                continue

            text = clean(
                a.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            if looks_like_product(
                full,
                text,
            ):

                links.add(
                    full.split("?")[0]
                )

    print()
    print(
        f"[FOUND] Найдено ссылок: {len(links)}"
    )

    return sorted(links)


def parse_product(url):

    print(
        "[PRODUCT]",
        url,
    )

    soup = get_soup(url)

    if not soup:
        return None

    # Название
    name = ""

    h1 = soup.find("h1")

    if h1:
        name = clean(
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
            name = clean(
                meta.get(
                    "content",
                    "",
                )
            )

    if not name:
        return None

    # Весь текст
    text = clean(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    # Цена
    price = extract_price(
        text
    )

    if not price:
        return None

    # Характеристики
    memory = extract_memory(
        name + " " + text
    )

    color = extract_color(
        name
    )

    if not color:
        color = extract_color(
            text
        )

    # Фото
    image_url = get_image(
        soup,
        url,
    )

    product_id = make_id(
        name,
        url,
    )

    local_image = download_image(
        image_url,
        product_id,
    )

    # Бренд
    lower = name.lower()

    if "iphone" in lower or "ipad" in lower:
        brand = "Apple"

    elif "samsung" in lower:
        brand = "Samsung"

    elif (
        "xiaomi" in lower
        or "redmi" in lower
        or "poco" in lower
    ):
        brand = "Xiaomi"

    elif "huawei" in lower:
        brand = "Huawei"

    elif "honor" in lower:
        brand = "Honor"

    elif "pixel" in lower:
        brand = "Google"

    elif "oneplus" in lower:
        brand = "OnePlus"

    elif "nothing" in lower:
        brand = "Nothing"

    else:
        brand = "Другие"

    product = {
        "id": product_id,
        "name": name,
        "price": price,
        "brand": brand,
        "category": brand,
        "memory": memory,
        "color": color,
        "available": True,
        "image": local_image,
        "source": "AppleAvenue",
        "source_url": url,
        "updated": time.strftime(
            "%Y-%m-%d"
        ),
    }

    print(
        "[OK]",
        name,
        "|",
        price,
        "| image:",
        bool(local_image),
    )

    return product


def save(products):

    OUTPUT_FILE.write_text(
        json.dumps(
            products,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("ГОТОВО")
    print(
        "Товаров:",
        len(products),
    )

    print(
        "Фото:",
        sum(
            bool(x.get("image"))
            for x in products
        ),
    )

    print(
        "Цен:",
        sum(
            bool(x.get("price"))
            for x in products
        ),
    )

    print("=" * 60)


def main():

    print("=" * 60)
    print("D&V STORE — AppleAvenue")
    print("=" * 60)

    links = get_product_links()

    if not links:

        print()
        print(
            "ОШИБКА: товары не найдены."
        )

        # Создаём валидный JSON,
        # чтобы workflow показал проблему
        save([])

        return

    products = []

    # Ограничение убираем — собираем весь найденный каталог
    for number, url in enumerate(
        links,
        start=1,
    ):

        print(
            f"\n[{number}/{len(links)}]"
        )

        product = parse_product(
            url
        )

        if product:
            products.append(
                product
            )

        time.sleep(0.3)

    # Удаляем дубли
    unique = {}

    for product in products:
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

    save(products)


if __name__ == "__main__":
    main()
