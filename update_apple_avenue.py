import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# НАСТРОЙКИ
# ============================================================

BASE_URL = "https://apple-avenue.ru"

CATEGORY_URLS = [
    "https://apple-avenue.ru/catalog/iphone_18_pro/",
    "https://apple-avenue.ru/catalog/iphone_18_pro_max/",
]

PRODUCTS_FILE = Path("products.json")

# Наценка отсутствует
MARKUP = 0

# Только эти объёмы памяти
ALLOWED_MEMORY = {
    "256gb",
    "512gb",
    "1tb",
    "2tb",
}

REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


# ============================================================
# HTTP
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


def get(url):
    for attempt in range(3):
        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            if response.status_code == 200:
                return response

            print(
                f"[WARN] HTTP {response.status_code}: {url}",
                flush=True,
            )

        except requests.RequestException as exc:
            print(
                f"[WARN] Ошибка запроса ({attempt + 1}/3): "
                f"{url} -> {exc}",
                flush=True,
            )

        time.sleep(2)

    return None


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def clean_url(url):
    """
    Приводим URL к нормальному виду:
    - убираем query
    - убираем #fragment
    - убираем ?amp=Y
    - добавляем /
    """

    absolute = urljoin(BASE_URL, url)

    parsed = urlparse(absolute)

    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    if not clean.endswith("/"):
        clean += "/"

    return clean


def is_18_product_url(url):
    """
    Проверяем, что ссылка относится именно к iPhone 18 Pro
    или 18 Pro Max, а не к другой модели.
    """

    url = clean_url(url).lower()

    if "/catalog/iphone_18_pro_max/" in url:
        return True

    if "/catalog/iphone_18_pro/" in url:
        return True

    return False


def get_memory_from_url(url):
    value = url.lower()

    if "2tb" in value:
        return "2 ТБ"

    if "1tb" in value:
        return "1 ТБ"

    if "512gb" in value:
        return "512 ГБ"

    if "256gb" in value:
        return "256 ГБ"

    return ""


def is_allowed_memory(url):
    value = url.lower()

    return any(
        re.search(rf"(^|[_/-]){re.escape(memory)}([_/-]|$)", value)
        for memory in ALLOWED_MEMORY
    )


def normalize_price(text):
    """
    Из текста вроде:
    '179 950 руб.'
    получаем:
    179950
    """

    if not text:
        return 0

    text = text.replace("\xa0", " ")

    numbers = re.findall(r"\d[\d\s]*", text)

    if not numbers:
        return 0

    # Берём наиболее подходящее число.
    candidates = []

    for item in numbers:
        digits = re.sub(r"\D", "", item)

        if digits:
            value = int(digits)

            # Цена телефона обычно больше 10 000
            if value >= 10000:
                candidates.append(value)

    if not candidates:
        return 0

    return candidates[0]


def find_price(soup):
    """
    Ищем цену товара.

    Сначала ищем элементы с характерными классами/текстом,
    затем используем общий поиск по странице.
    """

    selectors = [
        ".price",
        ".product-price",
        ".price_value",
        ".product-detail-price",
        ".catalog-detail-price",
        "[itemprop='price']",
    ]

    for selector in selectors:
        elements = soup.select(selector)

        for element in elements:
            text = element.get_text(" ", strip=True)

            price = normalize_price(text)

            if price >= 10000:
                return price

    # Запасной вариант:
    # ищем текст возле "руб."
    text = soup.get_text(" ", strip=True)

    matches = re.findall(
        r"(\d[\d\s\xa0]{4,})\s*(?:руб\.?|₽)",
        text,
        flags=re.IGNORECASE,
    )

    for match in matches:
        price = normalize_price(match)

        if price >= 10000:
            return price

    return 0


def find_old_price(soup, current_price):
    """
    Пытаемся найти старую цену.

    Если её нет — возвращаем 0.
    """

    selectors = [
        ".old-price",
        ".price-old",
        ".old_price",
        ".product-price-old",
        ".discount-price-old",
        "del",
        "s",
    ]

    for selector in selectors:
        elements = soup.select(selector)

        for element in elements:
            price = normalize_price(
                element.get_text(" ", strip=True)
            )

            if price >= 10000 and price != current_price:
                return price

    return 0


def find_title(soup):
    selectors = [
        "h1",
        "[itemprop='name']",
        ".product-title",
        ".catalog-detail__title",
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if element:
            title = element.get_text(" ", strip=True)

            if len(title) > 5:
                return title

    if soup.title:
        title = soup.title.get_text(" ", strip=True)

        title = re.sub(
            r"\s+(купить|в Москве!).*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        return title.strip()

    return ""


def find_stock(soup):
    """
    AppleAvenue обычно пишет "В наличии".
    """

    text = soup.get_text(" ", strip=True).lower()

    unavailable_words = [
        "нет в наличии",
        "нет на складе",
        "под заказ",
        "товар закончился",
    ]

    for word in unavailable_words:
        if word in text:
            return "Нет в наличии"

    available_words = [
        "в наличии",
        "есть в наличии",
    ]

    for word in available_words:
        if word in text:
            return "В наличии"

    return "Уточнить наличие"


def find_product_code(soup):
    text = soup.get_text(" ", strip=True)

    patterns = [
        r"Код товара:\s*([A-Za-zА-Яа-я0-9_-]+)",
        r"Артикул:\s*([A-Za-zА-Яа-я0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1).strip()

    return ""


def find_image(soup, page_url):
    """
    Берём главное изображение товара.
    """

    candidates = []

    selectors = [
        "meta[property='og:image']",
        "meta[name='twitter:image']",
        "img[itemprop='image']",
        ".product-detail img",
        ".catalog-detail img",
        "img",
    ]

    for selector in selectors:
        for element in soup.select(selector):
            src = (
                element.get("content")
                or element.get("data-src")
                or element.get("data-original")
                or element.get("src")
            )

            if src:
                candidates.append(src)

    for src in candidates:
        src = src.strip()

        if not src:
            continue

        image_url = urljoin(page_url, src)

        low = image_url.lower()

        if any(
            bad in low
            for bad in [
                "logo",
                "icon",
                "favicon",
                "placeholder",
                "sprite",
            ]
        ):
            continue

        return image_url

    return ""


def find_sim_type(soup, url):
    """
    Определяем SIM по URL и тексту страницы.
    """

    url_lower = url.lower()
    text = soup.get_text(" ", strip=True).lower()

    if "_esim" in url_lower or "только esim" in text:
        # Но если URL физической версии — она приоритетнее.
        if "физическая sim + esim" in text:
            # Проверяем заголовок/URL.
            if "_esim" in url_lower:
                return "eSIM"
            return "SIM + eSIM"

        return "eSIM"

    if (
        "физическая sim + esim" in text
        or "физическая sim" in text
    ):
        return "SIM + eSIM"

    return ""


def build_description(title, memory, sim):
    parts = []

    if memory:
        parts.append(memory)

    if sim:
        parts.append(sim)

    return " • ".join(parts)


# ============================================================
# ПОИСК ТОВАРОВ В КАТЕГОРИЯХ
# ============================================================

def collect_product_urls():
    found = set()

    for category_url in CATEGORY_URLS:
        print(
            f"[INFO] Открываем категорию: {category_url}",
            flush=True,
        )

        response = get(category_url)

        if not response:
            continue

        soup = BeautifulSoup(
            response.text,
            "lxml",
        )

        for link in soup.select("a[href]"):
            href = link.get("href")

            if not href:
                continue

            url = clean_url(href)

            if not is_18_product_url(url):
                continue

            if not is_allowed_memory(url):
                continue

            found.add(url)

    return sorted(found)


# ============================================================
# ПАРСИНГ ТОВАРА
# ============================================================

def parse_product(url):
    print(
        f"[INFO] Загружаем: {url}",
        flush=True,
    )

    response = get(url)

    if not response:
        return None

    soup = BeautifulSoup(
        response.text,
        "lxml",
    )

    title = find_title(soup)

    if not title:
        print(
            f"[WARN] Не удалось определить название: {url}",
            flush=True,
        )
        return None

    price = find_price(soup)

    if price <= 0:
        print(
            f"[WARN] Не удалось определить цену: {url}",
            flush=True,
        )
        return None

    old_price = find_old_price(
        soup,
        price,
    )

    memory = get_memory_from_url(url)

    sim = find_sim_type(
        soup,
        url,
    )

    stock = find_stock(soup)

    image = find_image(
        soup,
        url,
    )

    code = find_product_code(soup)

    # Никакой наценки
    final_price = price + MARKUP

    product = {
        "name": title,
        "brand": "Apple",
        "description": build_description(
            title,
            memory,
            sim,
        ),
        "price": final_price,
        "old_price": old_price,
        "stock": stock,
        "image": image,
        "url": clean_url(url),
        "product_code": code,
        "source": "AppleAvenue",
        "source_url": clean_url(url),
        "memory": memory,
        "sim": sim,
    }

    return product


# ============================================================
# УДАЛЕНИЕ ДУБЛЕЙ
# ============================================================

def is_18_existing_product(product):
    """
    Определяем старые 18 Pro / 18 Pro Max в нашем JSON.
    """

    url = str(product.get("url", "")).lower()
    name = str(product.get("name", "")).lower()

    if (
        "/catalog/iphone_18_pro_max/" in url
        or "/catalog/iphone_18_pro/" in url
    ):
        return True

    if "iphone 18 pro max" in name:
        return True

    if "iphone 18 pro" in name:
        return True

    return False


def canonical_key(product):
    url = clean_url(
        str(product.get("url", ""))
    ).lower()

    return url


# ============================================================
# ОБНОВЛЕНИЕ PRODUCTS.JSON
# ============================================================

def update_products(new_products):
    if not PRODUCTS_FILE.exists():
        print(
            "[ERROR] products.json не найден!",
            flush=True,
        )
        sys.exit(1)

    try:
        with PRODUCTS_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            products = json.load(file)

    except Exception as exc:
        print(
            f"[ERROR] Не удалось прочитать products.json: {exc}",
            flush=True,
        )
        sys.exit(1)

    if not isinstance(products, list):
        print(
            "[ERROR] products.json должен содержать JSON-массив.",
            flush=True,
        )
        sys.exit(1)

    # Сохраняем ВСЕ товары кроме старых 18 Pro / 18 Pro Max.
    other_products = [
        product
        for product in products
        if not is_18_existing_product(product)
    ]

    # Дедупликация новых товаров по URL.
    unique_new = {}

    for product in new_products:
        key = canonical_key(product)

        if key:
            unique_new[key] = product

    new_products = list(unique_new.values())

    # Добавляем свежие 18 Pro / Pro Max.
    final_products = other_products + new_products

    # Сохраняем аккуратно.
    with PRODUCTS_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            final_products,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")

    print(
        f"[OK] products.json обновлён.",
        flush=True,
    )

    print(
        f"[OK] Было товаров: {len(products)}",
        flush=True,
    )

    print(
        f"[OK] Новых 18 Pro / Pro Max: {len(new_products)}",
        flush=True,
    )

    print(
        f"[OK] Всего товаров теперь: {len(final_products)}",
        flush=True,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("D&V STORE — AppleAvenue Auto Update")
    print("iPhone 18 Pro / 18 Pro Max")
    print("Наценка: 0 ₽")
    print("=" * 70)

    urls = collect_product_urls()

    print(
        f"[INFO] Найдено ссылок на варианты: {len(urls)}",
        flush=True,
    )

    if not urls:
        print(
            "[ERROR] AppleAvenue не вернул ни одного варианта.",
            flush=True,
        )
        print(
            "[ERROR] products.json НЕ будет изменён.",
            flush=True,
        )
        sys.exit(1)

    products = []

    for url in urls:
        product = parse_product(url)

        if product:
            products.append(product)

        time.sleep(REQUEST_DELAY)

    if not products:
        print(
            "[ERROR] Не удалось получить ни одного товара.",
            flush=True,
        )
        print(
            "[ERROR] products.json НЕ будет изменён.",
            flush=True,
        )
        sys.exit(1)

    # Защита от случайного неполного ответа сайта.
    if len(products) < 5:
        print(
            f"[ERROR] Получено подозрительно мало товаров: {len(products)}",
            flush=True,
        )
        print(
            "[ERROR] products.json НЕ будет изменён.",
            flush=True,
        )
        sys.exit(1)

    update_products(products)


if __name__ == "__main__":
    main()
