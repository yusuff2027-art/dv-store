import json
import re
import time
import os
import urllib.request
from html import unescape
from urllib.parse import urljoin, urlparse

BASE_URL = "https://apple-avenue.ru"

# Основные категории iPhone
CATEGORY_URLS = [
    "https://apple-avenue.ru/catalog/iphone_17_pro_max/",
    "https://apple-avenue.ru/catalog/iphone_17_pro/",
    "https://apple-avenue.ru/catalog/iphone_17/",
    "https://apple-avenue.ru/catalog/iphone_16_pro_max/",
    "https://apple-avenue.ru/catalog/iphone_16_pro/",
    "https://apple-avenue.ru/catalog/iphone_16/",
    "https://apple-avenue.ru/catalog/iphone_15_pro_max/",
    "https://apple-avenue.ru/catalog/iphone_15_pro/",
    "https://apple-avenue.ru/catalog/iphone_15/",
    "https://apple-avenue.ru/catalog/iphone_14/",
    "https://apple-avenue.ru/catalog/iphone_13/",
    "https://apple-avenue.ru/catalog/iphone_12/",
    "https://apple-avenue.ru/catalog/iphone_11/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

IMAGE_DIR = "images"

os.makedirs(IMAGE_DIR, exist_ok=True)


# =========================================================
# HTTP
# =========================================================

def get_html(url):

    req = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        req,
        timeout=30
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="ignore"
        )


# =========================================================
# TEXT
# =========================================================

def clean_text(value):

    if not value:
        return ""

    value = unescape(value)

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    # Убираем CSS
    value = re.sub(
        r"#(?:[0-9a-fA-F]{3,8});?",
        " ",
        value
    )

    value = re.sub(
        r"(?:font-family|font-size|font-weight|line-height)"
        r"\s*:[^;]+;?",
        " ",
        value,
        flags=re.I
    )

    value = re.sub(
        r"={2,}",
        " ",
        value
    )

    value = re.sub(
        r"_{2,}",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip(
        " \t\r\n-,:;|/"
    )


# =========================================================
# PRODUCT LINKS
# =========================================================

def get_product_links(html):

    links = re.findall(
        r'href=["\']([^"\']+)["\']',
        html,
        re.I
    )

    result = []

    for link in links:

        link = unescape(link)

        if "?" in link:
            continue

        full_url = urljoin(
            BASE_URL,
            link
        )

        parsed = urlparse(full_url)

        path = parsed.path.lower()

        # Только iPhone
        if "/catalog/iphone_" not in path:
            continue

        # Не сама категория
        if path.rstrip("/").endswith(
            (
                "/iphone_17_pro_max",
                "/iphone_17_pro",
                "/iphone_17",
                "/iphone_16_pro_max",
                "/iphone_16_pro",
                "/iphone_16",
                "/iphone_15_pro_max",
                "/iphone_15_pro",
                "/iphone_15",
                "/iphone_14",
                "/iphone_13",
                "/iphone_12",
                "/iphone_11"
            )
        ):
            continue

        # Ссылка должна быть товаром
        parts = [
            x for x in path.split("/")
            if x
        ]

        if len(parts) < 3:
            continue

        if full_url not in result:
            result.append(full_url)

    return result


# =========================================================
# FILENAME
# =========================================================

def safe_filename(name):

    name = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+",
        "_",
        name
    )

    name = re.sub(
        r"_+",
        "_",
        name
    )

    return name.strip(
        "_"
    ).lower()


# =========================================================
# IMAGE
# =========================================================

def get_product_image(
    html,
    product_name
):

    # Ищем реальные картинки из upload/iblock
    images = re.findall(
        r'(?:src|data-src|data-original|href)=["\']([^"\']+)["\']',
        html,
        re.I
    )

    candidates = []

    for image in images:

        image = unescape(
            image
        )

        image = urljoin(
            BASE_URL,
            image
        )

        image_lower = image.lower()

        # Только реальные картинки
        if "/upload/iblock/" not in image_lower:
            continue

        if not re.search(
            r"\.(jpg|jpeg|png|webp)(?:\?|$)",
            image_lower,
            re.I
        ):
            continue

        # Отбрасываем очевидные служебные картинки
        bad_words = [
            "logo",
            "icon",
            "favicon",
            "avatar",
            "sprite",
            "loader",
            "loading"
        ]

        if any(
            word in image_lower
            for word in bad_words
        ):
            continue

        if image not in candidates:
            candidates.append(
                image
            )

    if not candidates:
        return ""

    image_url = candidates[0]

    filename = safe_filename(
        product_name
    )

    extension_match = re.search(
        r"\.(jpg|jpeg|png|webp)(?:\?|$)",
        image_url,
        re.I
    )

    extension = ".jpg"

    if extension_match:
        extension = "." + extension_match.group(1).lower()

    local_path = (
        f"{IMAGE_DIR}/{filename}{extension}"
    )

    print(
        "🖼 Фото:",
        image_url
    )

    try:

        req = urllib.request.Request(
            image_url,
            headers=HEADERS
        )

        with urllib.request.urlopen(
            req,
            timeout=30
        ) as response:

            data = response.read()

        if len(data) < 1000:

            print(
                "⚠️ Фото слишком маленькое"
            )

            return ""

        with open(
            local_path,
            "wb"
        ) as file:

            file.write(data)

        print(
            "✅ Фото сохранено:",
            local_path
        )

        # Для GitHub Pages нужен относительный путь
        return local_path

    except Exception as error:

        print(
            "❌ Ошибка фото:",
            error
        )

        return ""


# =========================================================
# NAME
# =========================================================

def get_product_name(html):

    patterns = [

        r'<h1[^>]*>(.*?)</h1>',

        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',

        r'<title>(.*?)</title>'

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if not match:
            continue

        name = clean_text(
            match.group(1)
        )

        # Убираем название магазина
        name = re.sub(
            r"\s*[|–—-]\s*AppleAvenue.*$",
            "",
            name,
            flags=re.I
        )

        name = re.sub(
            r"\s+купить.*$",
            "",
            name,
            flags=re.I
        )

        name = clean_text(
            name
        )

        if (
            name
            and "каталог техники" not in name.lower()
            and "appleavenue" not in name.lower()
        ):

            return name

    return ""


# =========================================================
# MEMORY
# =========================================================

def get_memory(
    html,
    name
):

    match = re.search(
        r"(\d+)\s*(?:TB|Tb|tb|GB|Gb|gb|ГБ|гб)",
        name,
        re.I
    )

    if match:

        number = match.group(1)

        # TB переводим в ГБ
        if re.search(
            r"TB|Tb|tb",
            match.group(0),
            re.I
        ):

            return str(
                int(number) * 1024
            ) + " ГБ"

        return number + " ГБ"

    # Вторая попытка — характеристики
    patterns = [

        r"Память\s*:?\s*([^<]{1,100})",

        r"Встроенная память\s*:?\s*([^<]{1,100})",

        r"Объем памяти\s*:?\s*([^<]{1,100})"

    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.I | re.S
        )

        for value in matches:

            value = clean_text(
                value
            )

            match = re.search(
                r"(\d+)\s*(TB|Tb|tb|GB|Gb|gb|ГБ|гб)",
                value,
                re.I
            )

            if not match:
                continue

            number = int(
                match.group(1)
            )

            if "tb" in match.group(2).lower():

                number *= 1024

            return str(number) + " ГБ"

    return ""


# =========================================================
# COLOR
# =========================================================

KNOWN_COLORS = [

    "Cosmic Orange",
    "Deep Blue",
    "Silver",

    "Black",
    "White",
    "Gold",
    "Blue",
    "Green",
    "Purple",
    "Red",
    "Yellow",

    "Natural Titanium",
    "Blue Titanium",
    "Black Titanium",
    "White Titanium",

    "Desert Titanium",
    "Titanium Gray",
    "Space Black",
    "Space Gray",

    "Rose Gold",
    "Midnight",
    "Starlight"

]


def get_color(
    html,
    name
):

    for color in KNOWN_COLORS:

        if color.lower() in name.lower():

            return color

    patterns = [

        r"Цвет\s*:?\s*([^<]{1,100})",

        r"Color\s*:?\s*([^<]{1,100})"

    ]

    for pattern in patterns:

        values = re.findall(
            pattern,
            html,
            re.I | re.S
        )

        for value in values:

            value = clean_text(
                value
            )

            for color in KNOWN_COLORS:

                if color.lower() in value.lower():

                    return color

    return ""


# =========================================================
# SIM
# =========================================================

def get_sim_type(
    html,
    name
):

    text = clean_text(
        html
    ).lower()

    # Сначала ищем физическую SIM + eSIM
    physical_sim = bool(
        re.search(
            r"\bnano[\s-]*sim\b"
            r"|\bphysical[\s-]*sim\b"
            r"|\bфизическ\w*\s+sim\b"
            r"|\bsim\s*\+\s*esim\b"
            r"|\besim\s*\+\s*sim\b",
            text,
            re.I
        )
    )

    esim = bool(
        re.search(
            r"\besim\b"
            r"|\be-sim\b"
            r"|\be sim\b",
            text,
            re.I
        )
    )

    if physical_sim and esim:
        return "SIM + eSIM"

    # Если в названии явно eSIM
    if re.search(
        r"\(e\s*sim\)",
        name,
        re.I
    ):

        # Apple iPhone с физической SIM
        # и eSIM показываем как SIM + eSIM
        return "SIM + eSIM"

    if esim:
        return "eSIM"

    if physical_sim:
        return "SIM"

    return ""


# =========================================================
# STOCK
# =========================================================

def get_stock(html):

    text = clean_text(
        html
    )

    if re.search(
        r"Нет в наличии",
        text,
        re.I
    ):

        return "Нет в наличии"

    if re.search(
        r"Под заказ",
        text,
        re.I
    ):

        return "Под заказ"

    if re.search(
        r"В наличии",
        text,
        re.I
    ):

        return "В наличии"

    return "Уточняйте наличие"


# =========================================================
# PRICE
# =========================================================

def get_price(html):

    # Главная цена Apple Avenue
    patterns = [

        r'id=["\']base-price["\'][^>]*value=["\']([^"\']+)["\']',

        r'id=["\']price-display["\'][^>]*>'
        r'\s*([\d\s]+)',

        r'class=["\'][^"\']*price[^"\']*["\'][^>]*>'
        r'\s*([\d\s]+)\s*(?:₽|руб)'

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if not match:
            continue

        raw = match.group(1)

        digits = re.sub(
            r"[^\d]",
            "",
            raw
        )

        if not digits:
            continue

        value = int(
            digits
        )

        # Защита от мусорных значений
        if value < 1000:
            continue

        return value

    return 0


# =========================================================
# OLD PRICE
# =========================================================

def get_old_price(html):

    match = re.search(
        r'class=["\'][^"\']*price-old[^"\']*["\']'
        r'[^>]*>(.*?)</',
        html,
        re.I | re.S
    )

    if not match:
        return 0

    raw = clean_text(
        match.group(1)
    )

    digits = re.sub(
        r"[^\d]",
        "",
        raw
    )

    if not digits:
        return 0

    value = int(
        digits
    )

    if value < 1000:
        return 0

    return value


# =========================================================
# PRODUCT CODE
# =========================================================

def get_product_code(html):

    match = re.search(
        r"Код товара\s*:?\s*"
        r"([A-Za-z0-9_-]+)",
        html,
        re.I
    )

    if match:
        return match.group(1)

    return ""


# =========================================================
# DESCRIPTION
# =========================================================

def make_description(
    memory,
    color,
    sim
):

    parts = []

    if memory:
        parts.append(
            memory
        )

    if color:
        parts.append(
            color
        )

    if sim:
        parts.append(
            sim
        )

    return " • ".join(
        parts
    )


# =========================================================
# PARSE PRODUCT
# =========================================================

def parse_product(url):

    html = get_html(
        url
    )

    name = get_product_name(
        html
    )

    # Защита от страниц категорий
    if not name:
        raise Exception(
            "Название товара не найдено"
        )

    if (
        "каталог техники" in name.lower()
        or "appleavenue" in name.lower()
    ):

        raise Exception(
            "Это не страница товара"
        )

    memory = get_memory(
        html,
        name
    )

    color = get_color(
        html,
        name
    )

    sim = get_sim_type(
        html,
        name
    )

    price = get_price(
        html
    )

    old_price = get_old_price(
        html
    )

    stock = get_stock(
        html
    )

    product_code = get_product_code(
        html
    )

    image = get_product_image(
        html,
        name
    )

    description = make_description(
        memory,
        color,
        sim
    )

    return {

        "name": name,

        "brand": "Apple",

        "description": description,

        "price": price,

        "old_price": old_price,

        "stock": stock,

        "image": image,

        "url": url,

        "product_code": product_code

    }


# =========================================================
# MAIN
# =========================================================

print(
    "================================"
)

print(
    "🚀 D&V STORE — СИНХРОНИЗАЦИЯ"
)

print(
    "================================"
)


products = []

seen_urls = set()


try:

    # =====================================================
    # КАТЕГОРИИ
    # =====================================================

    for category_url in CATEGORY_URLS:

        print(
            "\n🌐 Категория:",
            category_url
        )

        try:

            category_html = get_html(
                category_url
            )

        except Exception as error:

            print(
                "⚠️ Категория недоступна:",
                error
            )

            continue

        links = get_product_links(
            category_html
        )

        print(
            "📦 Найдено ссылок:",
            len(links)
        )

        for url in links:

            if url in seen_urls:
                continue

            seen_urls.add(
                url
            )

    # =====================================================
    # ТОВАРЫ
    # =====================================================

    print(
        "\n================================"
    )

    print(
        "📦 ВСЕГО ТОВАРОВ:",
        len(seen_urls)
    )

    print(
        "================================"
    )

    for index, url in enumerate(
        seen_urls,
        start=1
    ):

        print(
            f"\n[{index}/{len(seen_urls)}]"
        )

        print(
            url
        )

        try:

            product = parse_product(
                url
            )

            # Цена обязательна
            if not product["price"]:

                print(
                    "⚠️ Цена не найдена — пропускаем"
                )

                continue

            # Фото обязательно
            if not product["image"]:

                print(
                    "⚠️ Фото не найдено — пропускаем"
                )

                continue

            products.append(
                product
            )

            print(
                "✅",
                product["name"]
            )

            print(
                "💰",
                product["price"],
                "₽"
            )

            print(
                "📦",
                product["stock"]
            )

            print(
                "📋",
                product["description"]
            )

            print(
                "🖼 Есть"
            )

        except Exception as error:

            print(
                "❌ Ошибка товара:",
                error
            )

        time.sleep(
            0.5
        )

    # =====================================================
    # НЕ ЗАТИРАЕМ СТАРЫЙ КАТАЛОГ ПУСТЫМ
    # =====================================================

    if not products:

        raise Exception(
            "Ни одного нормального товара не найдено. "
            "products.json НЕ изменён."
        )

    # =====================================================
    # SAVE
    # =====================================================

    with open(
        "products.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            products,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        "\n================================"
    )

    print(
        "🎉 СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА"
    )

    print(
        "================================"
    )

    print(
        "Товаров сохранено:",
        len(products)
    )

    print(
        "Файл: products.json"
    )

    print(
        "Фото:",
        IMAGE_DIR
    )

except Exception as error:

    print(
        "\n================================"
    )

    print(
        "❌ СИНХРОНИЗАЦИЯ ОСТАНОВЛЕНА"
    )

    print(
        "================================"
    )

    print(
        error
    )

    raise
