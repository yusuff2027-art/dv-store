import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# D&V STORE — APPLE AVENUE SCRAPER
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
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL + "/",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(HEADERS)


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


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", str(text)).strip()


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
        print(f"[ERROR] Не удалось открыть: {url}")
        print(error)
        return None


# ============================================================
# ЦЕНА
# ============================================================

def extract_price(text):
    if not text:
        return ""

    patterns = [
        r"(\d[\d\s]{2,})\s*(?:руб\.?|₽)",
        r"(\d[\d\s]{2,})\s*р\.",
        r"(\d[\d\s]{2,})\s*руб",
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


# ============================================================
# ПАМЯТЬ
# ============================================================

def detect_memory(text):

    if not text:
        return ""

    match = re.search(
        r"\b("
        r"32|64|128|256|512|1024|2048|"
        r"3072|4096"
        r")\s*"
        r"(ГБ|GB|ТБ|TB)"
        r"\b",
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


# ============================================================
# ЦВЕТ
# ============================================================

def detect_color(text):

    if not text:
        return ""

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
        "коричневый",
        "натуральный",
    ]

    lower = text.lower()

    for color in colors:

        if color in lower:
            return color.capitalize()

    return ""


# ============================================================
# НАЗВАНИЕ
# ============================================================

def get_product_name(soup):

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
        return clean_text(
            title.get_text(
                " ",
                strip=True,
            )
        )

    return ""


# ============================================================
# ПОИСК КАРТИНКИ
# ============================================================

def normalize_image_url(page_url, image_url):

    if not image_url:
        return ""

    image_url = str(image_url).strip()

    if not image_url:
        return ""

    # Убираем пробелы
    image_url = image_url.replace(" ", "%20")

    # Если это //site.ru/image.jpg
    if image_url.startswith("//"):
        image_url = "https:" + image_url

    # Относительная ссылка
    image_url = urljoin(
        page_url,
        image_url,
    )

    # Убираем query
    parsed = urlparse(image_url)

    clean_url = (
        f"{parsed.scheme}://"
        f"{parsed.netloc}"
        f"{parsed.path}"
    )

    return clean_url


def extract_from_srcset(srcset):

    if not srcset:
        return ""

    candidates = []

    for item in srcset.split(","):

        item = item.strip()

        if not item:
            continue

        parts = item.split()

        if not parts:
            continue

        url = parts[0]

        width = 0

        if len(parts) > 1:

            match = re.search(
                r"(\d+)",
                parts[1],
            )

            if match:
                width = int(
                    match.group(1)
                )

        candidates.append(
            (width, url)
        )

    if not candidates:
        return ""

    candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    return candidates[0][1]


def get_image_url(product_url, soup):

    if soup is None:
        return ""

    # --------------------------------------------------------
    # 1. OG IMAGE
    # --------------------------------------------------------

    meta = soup.find(
        "meta",
        property="og:image",
    )

    if meta:

        image = (
            meta.get("content")
            or meta.get("value")
        )

        image = normalize_image_url(
            product_url,
            image,
        )

        if image:
            print(
                "[IMAGE SOURCE] OG:",
                image,
            )

            return image

    # --------------------------------------------------------
    # 2. twitter:image
    # --------------------------------------------------------

    meta = soup.find(
        "meta",
        attrs={
            "name": "twitter:image"
        },
    )

    if meta:

        image = meta.get("content")

        image = normalize_image_url(
            product_url,
            image,
        )

        if image:
            print(
                "[IMAGE SOURCE] Twitter:",
                image,
            )

            return image

    # --------------------------------------------------------
    # 3. IMG ТЕГИ
    # --------------------------------------------------------

    candidates = []

    for img in soup.find_all("img"):

        possible_attributes = [
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-image",
            "data-url",
            "src",
        ]

        image = ""

        for attribute in possible_attributes:

            value = img.get(attribute)

            if value:
                image = value
                break

        # srcset
        if not image:

            srcset = img.get(
                "srcset"
            )

            image = extract_from_srcset(
                srcset
            )

        if not image:
            continue

        image = normalize_image_url(
            product_url,
            image,
        )

        if not image:
            continue

        lower = image.lower()

        # Не берем иконки и служебные изображения
        bad_words = [
            "logo",
            "icon",
            "favicon",
            "sprite",
            "banner",
            "avatar",
            "svg",
        ]

        if any(
            word in lower
            for word in bad_words
        ):
            continue

        # Приоритет большим изображениям
        score = 0

        if any(
            ext in lower
            for ext in [
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
            ]
        ):
            score += 10

        if any(
            word in lower
            for word in [
                "detail",
                "product",
                "catalog",
                "upload",
                "iblock",
            ]
        ):
            score += 10

        candidates.append(
            (score, image)
        )

    if candidates:

        candidates.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        image = candidates[0][1]

        print(
            "[IMAGE SOURCE] IMG:",
            image,
        )

        return image

    return ""


# ============================================================
# СКАЧИВАНИЕ КАРТИНКИ
# ============================================================

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
            ".gif",
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

        # Уже скачана
        if destination.exists():

            print(
                "[IMAGE EXISTS]",
                filename,
            )

            return f"images/{filename}"

        headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Referer": BASE_URL + "/",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }

        response = session.get(
            url,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        content = response.content

        if len(content) < 1000:

            print(
                "[IMAGE ERROR] Слишком маленький файл:",
                url,
            )

            return ""

        content_type = (
            response.headers
            .get(
                "content-type",
                "",
            )
            .lower()
        )

        if (
            "image" not in content_type
            and extension == ".jpg"
        ):

            # Иногда сервер неправильно
            # выставляет content-type.
            # Проверяем сигнатуру файла.

            if not (
                content.startswith(b"\xff\xd8")
                or content.startswith(b"\x89PNG")
                or content.startswith(b"RIFF")
            ):

                print(
                    "[IMAGE ERROR] Это не изображение:",
                    url,
                )

                return ""

        destination.write_bytes(
            content
        )

        print(
            "[IMAGE DOWNLOADED]",
            filename,
            f"({len(content)} bytes)",
        )

        return f"images/{filename}"

    except Exception as error:

        print(
            "[IMAGE ERROR]",
            url,
        )

        print(error)

        return ""


# ============================================================
# ТОВАР
# ============================================================

def parse_product(url, category):

    print()
    print(
        "[PRODUCT]",
        url,
    )

    soup = get_soup(url)

    if soup is None:
        return None

    name = get_product_name(
        soup
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
    lower_text = page_text.lower()

    unavailable_words = [
        "нет в наличии",
        "нет на складе",
        "под заказ",
        "товар закончился",
    ]

    available = not any(
        word in lower_text
        for word in unavailable_words
    )

    if "в наличии" in lower_text:
        available = True

    # Память
    memory = detect_memory(
        name + " " + page_text
    )

    # Цвет
    color = detect_color(
        name
    )

    if not color:
        color = detect_color(
            page_text
        )

    # Картинка
    image_url = get_image_url(
        url,
        soup,
    )

    product_id = make_id(
        name,
        url,
    )

    local_image = ""

    if image_url:

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

    print(
        "[RESULT]",
        name,
        "|",
        price,
        "| IMAGE:",
        bool(local_image),
    )

    return product


# ============================================================
# ПОЛУЧЕНИЕ ССЫЛОК
# ============================================================

def get_product_links(category_url):

    url = urljoin(
        BASE_URL,
        category_url,
    )

    print()
    print(
        "[CATEGORY]",
        url,
    )

    soup = get_soup(url)

    if soup is None:
        return []

    links = set()

    base_netloc = urlparse(
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

        if parsed.netloc != base_netloc:
            continue

        path = parsed.path

        if path in [
            "",
            "/",
        ]:
            continue

        excluded = [
            "/search/",
            "/compare/",
            "/favorite/",
            "/cart/",
            "/personal/",
            "/login/",
            "/register/",
        ]

        if any(
            item in path.lower()
            for item in excluded
        ):
            continue

        # Исключаем саму категорию
        if (
            path.rstrip("/")
            == category_url.rstrip("/")
        ):
            continue

        links.add(
            full_url
        )

    return sorted(
        links
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("D&V STORE — APPLE AVENUE SCRAPER")
    print("=" * 70)

    IMAGES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_products = []

    seen_urls = set()

    for category, urls in CATEGORY_URLS.items():

        print()
        print(
            "=" * 30,
            category,
            "=" * 30,
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

                # Небольшая пауза
                time.sleep(0.4)

    # ========================================================
    # УДАЛЯЕМ ДУБЛИКАТЫ
    # ========================================================

    unique = {}

    for product in all_products:

        unique[
            product["id"]
        ] = product

    all_products = list(
        unique.values()
    )

    all_products.sort(
        key=lambda item:
        item["name"].lower()
    )

    # ========================================================
    # СОХРАНЯЕМ
    # ========================================================

    OUTPUT_FILE.write_text(
        json.dumps(
            all_products,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ========================================================
    # СТАТИСТИКА
    # ========================================================

    total = len(
        all_products
    )

    with_images = sum(
        1
        for product in all_products
        if product.get("image")
    )

    with_prices = sum(
        1
        for product in all_products
        if product.get("price")
        and product.get("price")
        != "Цена уточняется"
    )

    print()
    print("=" * 70)
    print("ГОТОВО")
    print("=" * 70)

    print(
        f"Товаров в каталоге: {total}"
    )

    print(
        f"С фотографиями: {with_images}"
    )

    print(
        f"С ценами: {with_prices}"
    )

    print(
        f"Без фотографий: {total - with_images}"
    )

    print(
        f"Без цен: {total - with_prices}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
