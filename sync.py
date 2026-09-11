import json
import re
import time
import os
import urllib.request
from html import unescape
from urllib.parse import urljoin, urlparse, parse_qs


# ============================================================
# D&V STORE — APPLE AVENUE IPHONE SYNC
# ============================================================

BASE_URL = "https://apple-avenue.ru"
CATEGORY_URL = "https://apple-avenue.ru/catalog/iphone/"

PRODUCTS_FILE = "products.json"
IMAGE_DIR = "images"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

os.makedirs(IMAGE_DIR, exist_ok=True)


# ============================================================
# HTTP
# ============================================================

def get_html(url):
    req = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()

    return data.decode("utf-8", errors="ignore")


def download_file(url, path):
    req = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()

    with open(path, "wb") as f:
        f.write(data)


# ============================================================
# TEXT
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = unescape(text)

    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)

    text = text.replace("&nbsp;", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# URL
# ============================================================

def normalize_url(url):
    url = urljoin(BASE_URL, url)

    parsed = urlparse(url)

    if parsed.netloc and parsed.netloc != "apple-avenue.ru":
        return ""

    # Убираем параметры и якоря
    url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    if not url.endswith("/"):
        url += "/"

    return url


# ============================================================
# ССЫЛКИ
# ============================================================

def extract_links(html):
    links = []

    for match in re.findall(
        r'href\s*=\s*["\']([^"\']+)["\']',
        html,
        flags=re.I
    ):
        url = normalize_url(match)

        if url:
            links.append(url)

    return list(dict.fromkeys(links))


# ============================================================
# IPHONE CATEGORY
# ============================================================

def is_iphone_category(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path.startswith("catalog/"):
        return False

    slug = path.split("/")[-1].lower()

    # Только категории iPhone
    if slug == "iphone":
        return True

    if re.fullmatch(r"iphone_[a-z0-9_]+", slug):
        return True

    return False


def get_iphone_categories(html):
    result = []

    for url in extract_links(html):

        if not is_iphone_category(url):
            continue

        result.append(url)

    # Убираем общий /iphone/
    result = [
        x for x in result
        if x.rstrip("/") != CATEGORY_URL.rstrip("/")
    ]

    return list(dict.fromkeys(result))


# ============================================================
# REAL PRODUCT URL
# ============================================================

def is_real_iphone_product(url):
    parsed = urlparse(url)

    path = parsed.path.strip("/")
    parts = path.split("/")

    # Должно быть:
    # catalog / iphone_17_pro_max / apple_iphone_17_pro_max_256gb...
    if len(parts) != 3:
        return False

    catalog = parts[0]
    model = parts[1]
    product = parts[2]

    if catalog != "catalog":
        return False

    # Категория должна быть iPhone
    if not model.startswith("iphone_"):
        return False

    # Сам товар должен начинаться с apple_iphone
    if not product.startswith("apple_iphone_"):
        return False

    # Защита от мусора
    bad_words = [
        "compare",
        "favorites",
        "basket",
        "search",
        "ajax",
        "filter",
    ]

    for bad in bad_words:
        if bad in product.lower():
            return False

    return True


def get_product_links_from_category(html):
    result = []

    for url in extract_links(html):

        if is_real_iphone_product(url):
            result.append(url)

    return list(dict.fromkeys(result))


# ============================================================
# PAGINATION
# ============================================================

def get_next_pages(html, category_url):
    result = []

    for url in extract_links(html):

        parsed = urlparse(url)

        if not parsed.path.rstrip("/") == urlparse(category_url).path.rstrip("/"):
            continue

        query = parse_qs(parsed.query)

        if "PAGEN_1" in query:
            result.append(url)

    return list(dict.fromkeys(result))


def crawl_category(category_url):
    """
    Загружает категорию iPhone.
    Собирает товары и страницы пагинации.
    """

    visited = set()
    queue = [category_url]
    products = set()

    max_pages = 50

    while queue and len(visited) < max_pages:

        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)

        print()
        print("📂 Категория:", url)

        try:
            html = get_html(url)

        except Exception as e:
            print("❌ Ошибка категории:", e)
            continue

        found = get_product_links_from_category(html)

        print("🛒 Товаров на странице:", len(found))

        for product in found:
            products.add(product)

        # Ищем следующие страницы
        next_pages = get_next_pages(html, category_url)

        for next_url in next_pages:
            if next_url not in visited:
                queue.append(next_url)

        # Дополнительный способ:
        # если сайт использует ?PAGEN_1=N
        current_page = 1

        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        if "PAGEN_1" in query:
            try:
                current_page = int(query["PAGEN_1"][0])
            except Exception:
                current_page = 1

        # Если нашли товары — пробуем следующие 20 страниц
        if found:
            for page in range(current_page + 1, current_page + 3):

                next_url = category_url

                separator = "&" if "?" in next_url else "?"

                next_url = (
                    next_url
                    + separator
                    + "PAGEN_1="
                    + str(page)
                )

                if next_url not in visited:
                    queue.append(next_url)

        time.sleep(0.5)

    return sorted(products)


# ============================================================
# TITLE
# ============================================================

def get_title(html):
    match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        flags=re.I | re.S
    )

    if not match:
        return ""

    title = clean_text(match.group(1))

    title = re.sub(
        r"\s+купить.*$",
        "",
        title,
        flags=re.I
    )

    title = re.sub(
        r"\s+\|\s*AppleAvenue.*$",
        "",
        title,
        flags=re.I
    )

    return title.strip()


# ============================================================
# MEMORY
# ============================================================

def get_memory(html, title):
    text = clean_text(html + " " + title)

    patterns = [
        r"(\d+)\s*TB",
        r"(\d+)\s*Tb",
        r"(\d+)\s*ТБ",
        r"(\d+)\s*GB",
        r"(\d+)\s*Gb",
        r"(\d+)\s*ГБ",
    ]

    # Сначала TB
    for pattern in patterns[:3]:
        match = re.search(pattern, text, flags=re.I)

        if match:
            tb = int(match.group(1))
            return str(tb * 1024) + " ГБ"

    # Потом GB
    for pattern in patterns[3:]:
        match = re.search(pattern, text, flags=re.I)

        if match:
            gb = int(match.group(1))
            return str(gb) + " ГБ"

    return ""


# ============================================================
# COLOR
# ============================================================

COLOR_MAP = {
    "серебристый": "Silver",
    "серебряный": "Silver",
    "серебро": "Silver",

    "черный": "Black",
    "чёрный": "Black",

    "белый": "White",

    "синий": "Blue",
    "голубой": "Blue",

    "зеленый": "Green",
    "зелёный": "Green",

    "розовый": "Pink",

    "фиолетовый": "Purple",

    "желтый": "Yellow",
    "жёлтый": "Yellow",

    "оранжевый": "Cosmic Orange",

    "натуральный титан": "Natural Titanium",
    "черный титан": "Black Titanium",
    "чёрный титан": "Black Titanium",
    "белый титан": "White Titanium",
    "синий титан": "Blue Titanium",
    "песочный титан": "Desert Titanium",

    "natural titanium": "Natural Titanium",
    "black titanium": "Black Titanium",
    "white titanium": "White Titanium",
    "blue titanium": "Blue Titanium",
    "desert titanium": "Desert Titanium",

    "cosmic orange": "Cosmic Orange",
    "deep blue": "Deep Blue",
    "silver": "Silver",
    "black": "Black",
    "white": "White",
    "blue": "Blue",
    "green": "Green",
    "pink": "Pink",
    "purple": "Purple",
    "yellow": "Yellow",
}


def get_color(html, title):
    text = clean_text(html + " " + title)

    # Сначала ищем поле "Цвет:"
    patterns = [
        r"Цвет\s*:\s*([A-Za-zА-Яа-яЁё\- ]{2,40})",
        r"Цвет\s*</[^>]+>\s*([^<]{2,40})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            flags=re.I
        )

        if match:
            raw = clean_text(match.group(1)).strip()

            raw_lower = raw.lower()

            for key, value in COLOR_MAP.items():

                if key in raw_lower:
                    return value

    # Затем ищем цвет в названии
    lower_title = title.lower()

    # Сначала длинные названия
    keys = sorted(
        COLOR_MAP.keys(),
        key=len,
        reverse=True
    )

    for key in keys:

        if key in lower_title:
            return COLOR_MAP[key]

    return ""


# ============================================================
# SIM
# ============================================================

def get_sim_type(html, title):
    text = clean_text(html + " " + title).lower()

    # Ищем именно поле Тип SIM
    sim_patterns = [
        r"тип\s+sim\s*:\s*([^|]{0,80})",
        r"тип\s+sim-карты\s*:\s*([^|]{0,80})",
        r"тип\s+sim[^<]{0,80}",
    ]

    sim_text = ""

    for pattern in sim_patterns:

        match = re.search(
            pattern,
            text,
            flags=re.I
        )

        if match:
            sim_text += " " + match.group(0)

    # Также название товара
    sim_text += " " + title.lower()

    # --------------------------------------------------------
    # Только eSIM
    # --------------------------------------------------------

    only_esim = [
        "только esim",
        "только e-sim",
        "esim only",
        "(esim)",
        "(e-sim)",
    ]

    for item in only_esim:

        if item in sim_text:
            return "eSIM"

    # --------------------------------------------------------
    # SIM + eSIM
    # --------------------------------------------------------

    physical_sim = (
        "физическая sim"
        in sim_text
        or
        "physical sim"
        in sim_text
        or
        "nano+e-sim"
        in sim_text
        or
        "nano + e-sim"
        in sim_text
        or
        "sim + esim"
        in sim_text
        or
        "sim+esim"
        in sim_text
        or
        "sim + e-sim"
        in sim_text
    )

    has_esim = (
        "esim" in sim_text
        or
        "e-sim" in sim_text
    )

    if physical_sim and has_esim:
        return "SIM + eSIM"

    # --------------------------------------------------------
    # Обычная SIM
    # --------------------------------------------------------

    if (
        "физическая sim"
        in sim_text
        or
        "nano-sim"
        in sim_text
        or
        "nano sim"
        in sim_text
    ):
        return "SIM"

    return ""


# ============================================================
# STOCK
# ============================================================

def get_stock(html):
    text = clean_text(html).lower()

    if "нет в наличии" in text:
        return "Нет в наличии"

    if "под заказ" in text:
        return "Под заказ"

    if "в наличии" in text:
        return "В наличии"

    return ""


# ============================================================
# PRICE
# ============================================================

def get_price(html):
    # Главный вариант Apple Avenue
    patterns = [
        r'id=["\']base-price["\'][^>]*value=["\']([^"\']+)["\']',
        r'value=["\']([^"\']+)["\'][^>]*id=["\']base-price["\']',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            flags=re.I
        )

        if match:
            raw = match.group(1)

            digits = re.sub(r"[^\d]", "", raw)

            if digits:
                return int(digits)

    # Запасной вариант
    text = clean_text(html)

    price_patterns = [
        r'(\d[\d\s]{3,})\s*руб',
        r'(\d[\d\s]{3,})\s*₽',
    ]

    for pattern in price_patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.I
        )

        for value in matches:

            digits = re.sub(r"\D", "", value)

            if digits:

                price = int(digits)

                # Защита от случайных чисел
                if 1000 <= price <= 1000000:
                    return price

    return 0


# ============================================================
# OLD PRICE
# ============================================================

def get_old_price(html):
    patterns = [
        r'class=["\'][^"\']*price-old[^"\']*["\'][^>]*>(.*?)</',
        r'class=["\'][^"\']*old-price[^"\']*["\'][^>]*>(.*?)</',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            flags=re.I | re.S
        )

        if match:

            text = clean_text(match.group(1))

            digits = re.sub(
                r"[^\d]",
                "",
                text
            )

            if digits:

                value = int(digits)

                if value > 0:
                    return value

    return 0


# ============================================================
# PRODUCT CODE
# ============================================================

def get_product_code(html):
    match = re.search(
        r"Код товара\s*:?\s*([A-Za-zА-Яа-я0-9\-_]+)",
        clean_text(html),
        flags=re.I
    )

    if match:
        return match.group(1)

    return ""


# ============================================================
# IMAGE
# ============================================================

def get_product_image(html, product_url):
    images = []

    # Основные изображения /upload/iblock/
    images += re.findall(
        r'https?://[^"\']+/upload/iblock/[^"\']+\.(?:jpg|jpeg|png|webp)',
        html,
        flags=re.I
    )

    # Относительные картинки
    relative_images = re.findall(
        r'["\']([^"\']*?/upload/iblock/[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
        html,
        flags=re.I
    )

    for image in relative_images:

        image_url = normalize_url(image)

        if image_url:
            images.append(image_url)

    # Уникальные
    unique = []

    for image in images:

        image = image.replace("\\/", "/")

        if image not in unique:
            unique.append(image)

    if not unique:
        return "", ""

    # Выбираем нормальную фотографию
    image_url = unique[0]

    # Имя файла
    parsed = urlparse(image_url)

    filename = os.path.basename(parsed.path)

    filename = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        filename
    )

    if not filename:
        filename = "product.jpg"

    # Чтобы одинаковые названия не перезаписывали друг друга
    code_match = re.search(
        r"apple_iphone_[^/]+",
        product_url,
        flags=re.I
    )

    if code_match:
        prefix = code_match.group(0)[:80]
        filename = prefix + "_" + filename

    local_path = os.path.join(
        IMAGE_DIR,
        filename
    )

    try:

        download_file(
            image_url,
            local_path
        )

        return image_url, local_path

    except Exception as e:

        print("❌ Ошибка скачивания фото:", e)

        return image_url, ""


# ============================================================
# PRODUCT PARSER
# ============================================================

def parse_product(url):
    print()
    print("----------------------------------------")
    print("📱", url)

    html = get_html(url)

    title = get_title(html)

    # Защита: если это НЕ товар — пропускаем
    if not title.lower().startswith("apple iphone"):
        raise Exception(
            "Это не страница товара iPhone"
        )

    price = get_price(html)

    # Если цены нет — пропускаем
    if price <= 0:
        raise Exception(
            "Цена не найдена"
        )

    old_price = get_old_price(html)

    stock = get_stock(html)

    memory = get_memory(
        html,
        title
    )

    color = get_color(
        html,
        title
    )

    sim = get_sim_type(
        html,
        title
    )

    product_code = get_product_code(
        html
    )

    image_url, local_image = get_product_image(
        html,
        url
    )

    # Если фото нет — всё равно товар сохраняем,
    # но image будет пустым.
    description_parts = []

    if memory:
        description_parts.append(memory)

    if color:
        description_parts.append(color)

    if sim:
        description_parts.append(sim)

    description = " • ".join(
        description_parts
    )

    print("🏷", title)
    print("💰 Цена:", price)
    print("💰 Старая:", old_price)
    print("📦", stock)
    print("📋", description)

    if local_image:
        print("🖼 Фото сохранено:", local_image)
    else:
        print("⚠️ Фото не скачано")

    return {
        "name": title,
        "brand": "Apple",
        "description": description,
        "price": price,
        "old_price": old_price,
        "stock": stock,
        "image": (
            "/" + local_image.replace("\\", "/")
            if local_image
            else ""
        ),
        "url": url,
        "product_code": product_code,
    }


# ============================================================
# MAIN
# ============================================================

print()
print("========================================")
print("🚀 D&V STORE — APPLE IPHONE SYNC")
print("========================================")
print()

print("🌐 Загружаем общий каталог iPhone...")

try:
    main_html = get_html(
        CATEGORY_URL
    )

except Exception as e:

    print("❌ Не удалось загрузить каталог:")
    print(e)

    raise


print("✅ Каталог iPhone загружен")
print("Размер:", len(main_html), "символов")
print()


# ============================================================
# FIND MODEL CATEGORIES
# ============================================================

print("🔎 Ищем категории iPhone...")

categories = get_iphone_categories(
    main_html
)

print(
    "📂 Найдено категорий:",
    len(categories)
)

for category in categories:
    print("   •", category)


if not categories:
    raise Exception(
        "Категории iPhone не найдены"
    )


# ============================================================
# FIND PRODUCTS
# ============================================================

all_products = set()

print()
print("🔎 Собираем реальные карточки товаров...")
print()

for index, category in enumerate(
    categories,
    start=1
):

    print(
        f"[{index}/{len(categories)}]"
    )

    products = crawl_category(
        category
    )

    print(
        "✅ Найдено товаров:",
        len(products)
    )

    for product in products:
        all_products.add(product)

    time.sleep(0.5)


print()
print("========================================")
print(
    "📦 ВСЕГО ТОВАРОВ:",
    len(all_products)
)
print("========================================")
print()


if not all_products:

    raise Exception(
        "Реальные товары iPhone не найдены"
    )


# ============================================================
# PARSE PRODUCTS
# ============================================================

products_data = []

product_list = sorted(
    all_products
)

for index, url in enumerate(
    product_list,
    start=1
):

    print()
    print(
        f"[{index}/{len(product_list)}]"
    )

    try:

        product = parse_product(
            url
        )

        products_data.append(
            product
        )

    except Exception as e:

        print(
            "❌ Пропущен товар:",
            e
        )

    time.sleep(0.3)


# ============================================================
# SAVE
# ============================================================

print()
print("========================================")
print("💾 СОХРАНЕНИЕ")
print("========================================")

if not products_data:

    raise Exception(
        "После обработки не осталось товаров"
    )


with open(
    PRODUCTS_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        products_data,
        f,
        ensure_ascii=False,
        indent=2
    )


print(
    "✅ Сохранено товаров:",
    len(products_data)
)

print(
    "📄 Файл:",
    PRODUCTS_FILE
)

print()
print("========================================")
print("🎉 СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА")
print("========================================")
