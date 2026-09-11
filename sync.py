import json
import re
import time
import os
import urllib.request
from html import unescape
from urllib.parse import urljoin, urlparse

BASE_URL = "https://apple-avenue.ru"

IMAGE_DIR = "images"

os.makedirs(IMAGE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# =========================================================
# IPHONE КАТЕГОРИИ
# =========================================================

IPHONE_CATEGORY_URLS = [
    f"{BASE_URL}/catalog/iphone_17_pro_max/",
    f"{BASE_URL}/catalog/iphone_17_pro/",
    f"{BASE_URL}/catalog/iphone_17/",
    f"{BASE_URL}/catalog/iphone_16_pro_max/",
    f"{BASE_URL}/catalog/iphone_16_pro/",
    f"{BASE_URL}/catalog/iphone_16/",
    f"{BASE_URL}/catalog/iphone_15_pro_max/",
    f"{BASE_URL}/catalog/iphone_15_pro/",
    f"{BASE_URL}/catalog/iphone_15/",
    f"{BASE_URL}/catalog/iphone_14/",
    f"{BASE_URL}/catalog/iphone_13/",
    f"{BASE_URL}/catalog/iphone_12/",
    f"{BASE_URL}/catalog/iphone_11/",
]

# =========================================================
# ANDROID БРЕНДЫ
# =========================================================

ANDROID_BRANDS = {
    "samsung": "Samsung",
    "xiaomi": "Xiaomi",
    "redmi": "Redmi",
    "honor": "Honor",
    "google": "Google",
    "pixel": "Google",
    "oneplus": "OnePlus",
    "huawei": "Huawei",
    "realme": "Realme",
    "nothing": "Nothing",
    "infinix": "Infinix",
    "motorola": "Motorola",
    "oppo": "OPPO",
    "vivo": "Vivo",
    "asus": "ASUS",
    "tecno": "Tecno",
    "sony": "Sony",
    "zte": "ZTE",
}

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
# URL
# =========================================================

def normalize_url(url):

    url = unescape(url)

    url = url.split("#")[0]

    return urljoin(
        BASE_URL,
        url
    )


# =========================================================
# BRAND FROM URL
# =========================================================

def get_brand_from_url(url):

    path = urlparse(url).path.lower()

    for key, brand in ANDROID_BRANDS.items():

        if key in path:
            return brand

    if "/iphone_" in path:
        return "Apple"

    return ""


# =========================================================
# IPHONE PRODUCT LINKS
# =========================================================

def get_iphone_product_links(html):

    links = re.findall(
        r'href=["\']([^"\']+)["\']',
        html,
        re.I
    )

    result = []

    category_names = [
        "iphone_17_pro_max",
        "iphone_17_pro",
        "iphone_17",
        "iphone_16_pro_max",
        "iphone_16_pro",
        "iphone_16",
        "iphone_15_pro_max",
        "iphone_15_pro",
        "iphone_15",
        "iphone_14",
        "iphone_13",
        "iphone_12",
        "iphone_11",
    ]

    for link in links:

        full_url = normalize_url(link)

        path = urlparse(
            full_url
        ).path.lower()

        if "/catalog/iphone_" not in path:
            continue

        parts = [
            x for x in path.split("/")
            if x
        ]

        if len(parts) < 3:
            continue

        last_part = parts[-1]

        # Не сама категория
        if last_part in category_names:
            continue

        # Товарный slug
        if not (
            "apple_iphone_" in last_part
            or last_part.startswith("iphone_")
        ):
            continue

        if full_url not in result:
            result.append(full_url)

    return result


# =========================================================
# ANDROID PRODUCT LINKS
# =========================================================

def get_android_product_links(html):

    links = re.findall(
        r'href=["\']([^"\']+)["\']',
        html,
        re.I
    )

    result = []

    for link in links:

        full_url = normalize_url(link)

        parsed = urlparse(
            full_url
        )

        path = parsed.path.lower()

        if "/catalog/" not in path:
            continue

        parts = [
            x for x in path.split("/")
            if x
        ]

        # Нужна структура:
        # /catalog/category/product/
        if len(parts) < 3:
            continue

        slug = parts[-1]

        # Не собираем страницы категорий
        if slug in (
            "catalog",
            "smartfony",
            "smartfony_i_telefony",
            "android",
        ):
            continue

        brand = get_brand_from_url(
            full_url
        )

        if not brand:
            continue

        # Дополнительная защита.
        # Настоящий товар обычно содержит модель
        # и характеристики в slug.
        product_words = [
            "galaxy",
            "samsung",
            "xiaomi",
            "redmi",
            "poco",
            "honor",
            "magic",
            "pixel",
            "google",
            "oneplus",
            "huawei",
            "realme",
            "nothing",
            "phone",
            "motorola",
            "edge",
            "razr",
            "infinix",
            "tecno",
            "oppo",
            "vivo",
            "asus",
            "rog",
            "zenfone",
            "sony",
            "xperia",
            "zte",
        ]

        if not any(
            word in slug
            for word in product_words
        ):
            continue

        if full_url not in result:
            result.append(full_url)

    return result


# =========================================================
# SEARCH ANDROID CATEGORIES
# =========================================================

def discover_android_categories():

    print(
        "\n🔎 Ищем Android-категории..."
    )

    urls = set()

    catalog_urls = [
        f"{BASE_URL}/catalog/",
        f"{BASE_URL}/catalog/smartfony/",
        f"{BASE_URL}/catalog/smartfony_i_telefony/",
    ]

    for catalog_url in catalog_urls:

        try:

            html = get_html(
                catalog_url
            )

        except Exception as error:

            print(
                "⚠️ Не удалось открыть:",
                catalog_url,
                error
            )

            continue

        links = re.findall(
            r'href=["\']([^"\']+)["\']',
            html,
            re.I
        )

        for link in links:

            full_url = normalize_url(
                link
            )

            path = urlparse(
                full_url
            ).path.lower()

            if "/catalog/" not in path:
                continue

            # Проверяем, относится ли ссылка
            # к Android-бренду
            if not any(
                brand in path
                for brand in ANDROID_BRANDS
            ):
                continue

            # Категория должна быть минимум
            # /catalog/xxxxx/
            parts = [
                x for x in path.split("/")
                if x
            ]

            if len(parts) != 2:
                continue

            urls.add(
                full_url
            )

        time.sleep(
            0.5
        )

    print(
        "📂 Android-категорий найдено:",
        len(urls)
    )

    for url in sorted(urls):

        print(
            "   •",
            url
        )

    return sorted(urls)


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

    images = re.findall(
        r'(?:src|data-src|data-original|href)=["\']([^"\']+)["\']',
        html,
        re.I
    )

    candidates = []

    for image in images:

        image = normalize_url(
            image
        )

        image_lower = image.lower()

        # Только настоящие картинки товаров
        if "/upload/iblock/" not in image_lower:
            continue

        if not re.search(
            r"\.(jpg|jpeg|png|webp)(?:\?|$)",
            image_lower,
            re.I
        ):
            continue

        bad_words = [
            "logo",
            "icon",
            "favicon",
            "avatar",
            "sprite",
            "loader",
            "loading",
            "nextype.alpha",
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

        bad_names = [
            "каталог техники",
            "appleavenue",
            "apple avenue",
            "интернет-магазин",
        ]

        if (
            name
            and not any(
                bad in name.lower()
                for bad in bad_names
            )
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

    # Сначала ищем в названии
    match = re.search(
        r"(\d+)\s*(TB|Tb|tb|GB|Gb|gb|ГБ|гб)",
        name,
        re.I
    )

    if match:

        number = int(
            match.group(1)
        )

        if "tb" in match.group(2).lower():

            number *= 1024

        return str(
            number
        ) + " ГБ"

    patterns = [

        r"Память\s*:?\s*([^<]{1,100})",

        r"Встроенная память\s*:?\s*([^<]{1,100})",

        r"Объем памяти\s*:?\s*([^<]{1,100})",

        r"Объём памяти\s*:?\s*([^<]{1,100})",

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

            return str(
                number
            ) + " ГБ"

    return ""


# =========================================================
# COLOR
# =========================================================

COLOR_MAP = {

    "черный": "Black",
    "чёрный": "Black",

    "белый": "White",

    "серебристый": "Silver",

    "синий": "Blue",

    "голубой": "Blue",

    "зеленый": "Green",
    "зелёный": "Green",

    "фиолетовый": "Purple",

    "розовый": "Pink",

    "желтый": "Yellow",
    "жёлтый": "Yellow",

    "красный": "Red",

    "золотой": "Gold",

    "серый": "Gray",

    "графит": "Graphite",

    "оранжевый": "Orange",

    "песочный": "Desert",

    "натуральный титан": "Natural Titanium",

    "черный титан": "Black Titanium",
    "чёрный титан": "Black Titanium",

    "белый титан": "White Titanium",

    "синий титан": "Blue Titanium",

    "песочный титан": "Desert Titanium",

    "натуральный": "Natural Titanium",

    "cosmic orange": "Cosmic Orange",
    "deep blue": "Deep Blue",
    "silver": "Silver",
    "black": "Black",
    "white": "White",
    "gold": "Gold",
    "blue": "Blue",
    "green": "Green",
    "purple": "Purple",
    "red": "Red",
    "yellow": "Yellow",
    "pink": "Pink",
    "space black": "Space Black",
    "space gray": "Space Gray",
    "natural titanium": "Natural Titanium",
    "white titanium": "White Titanium",
    "black titanium": "Black Titanium",
    "desert titanium": "Desert Titanium",

}


def get_color(
    html,
    name
):

    combined_text = (
        name
        + " "
        + clean_text(html)
    ).lower()

    # Сначала длинные названия
    # чтобы "титан" не перебивал
    for color in sorted(
        COLOR_MAP.keys(),
        key=len,
        reverse=True
    ):

        if color in combined_text:

            return COLOR_MAP[color]

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

    # Очень важный момент:
    # сначала ищем точные характеристики
    # Apple Avenue может писать:
    # физическая SIM + eSIM
    # только eSIM
    # nano+e-SIM

    if re.search(
        r"физическ\w*\s+sim\s*\+\s*esim",
        text,
        re.I
    ):

        return "SIM + eSIM"

    if re.search(
        r"nano\s*\+\s*e[\s-]*sim",
        text,
        re.I
    ):

        return "SIM + eSIM"

    if re.search(
        r"sim\s*\+\s*esim",
        text,
        re.I
    ):

        return "SIM + eSIM"

    if re.search(
        r"только\s+e[\s-]*sim",
        text,
        re.I
    ):

        return "eSIM"

    if re.search(
        r"только\s+esim",
        text,
        re.I
    ):

        return "eSIM"

    # Android часто пишет Dual SIM
    if re.search(
        r"dual\s*sim",
        text,
        re.I
    ):

        return "Dual SIM"

    if re.search(
        r"\be[\s-]*sim\b",
        text,
        re.I
    ):

        return "eSIM"

    if re.search(
        r"\bnano[\s-]*sim\b",
        text,
        re.I
    ):

        return "SIM"

    if re.search(
        r"физическ\w*\s+sim",
        text,
        re.I
    ):

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

    patterns = [

        r'id=["\']base-price["\'][^>]*value=["\']([^"\']+)["\']',

        r'id=["\']price-display["\'][^>]*>'
        r'\s*([\d\s]+)',

        r'class=["\'][^"\']*price[^"\']*["\'][^>]*>'
        r'\s*([\d\s]+)\s*(?:₽|руб)',

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

        if value < 1000:
            continue

        return value

    return 0


# =========================================================
# OLD PRICE
# =========================================================

def get_old_price(html):

    patterns = [

        r'class=["\'][^"\']*price-old[^"\']*["\']'
        r'[^>]*>(.*?)</',

        r'class=["\'][^"\']*old-price[^"\']*["\']'
        r'[^>]*>(.*?)</',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if not match:
            continue

        raw = clean_text(
            match.group(1)
        )

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

        if value >= 1000:
            return value

    return 0


# =========================================================
# PRODUCT CODE
# =========================================================

def get_product_code(html):

    patterns = [

        r"Код товара\s*:?\s*"
        r"([A-Za-z0-9_-]+)",

        r"Артикул\s*:?\s*"
        r"([A-Za-z0-9_-]+)",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
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
# VALIDATE PRODUCT
# =========================================================

def validate_product(
    name,
    price,
    image,
    brand
):

    if not name:
        return False

    if price < 1000:
        return False

    if not image:
        return False

    name_lower = name.lower()

    bad_words = [
        "каталог",
        "аксессуар",
        "чехол",
        "стекло",
        "зарядк",
        "кабель",
        "телевизор",
        "приставка",
        "наушник",
    ]

    if any(
        word in name_lower
        for word in bad_words
    ):
        return False

    # Проверяем бренд
    if brand == "Apple":

        if "iphone" not in name_lower:
            return False

    return True


# =========================================================
# PARSE PRODUCT
# =========================================================

def parse_product(
    url,
    forced_brand=None
):

    html = get_html(
        url
    )

    name = get_product_name(
        html
    )

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

    brand = (
        forced_brand
        or get_brand_from_url(url)
    )

    # Если бренд не определён,
    # пробуем определить по названию
    if not brand:

        name_lower = name.lower()

        for key, value in ANDROID_BRANDS.items():

            if key in name_lower:

                brand = value
                break

    if not brand:

        if "iphone" in name.lower():

            brand = "Apple"

    if not brand:

        raise Exception(
            "Бренд не определён"
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

    if not validate_product(
        name,
        price,
        image,
        brand
    ):

        raise Exception(
            "Страница не прошла проверку товара"
        )

    return {

        "name": name,

        "brand": brand,

        "description": description,

        "price": price,

        "old_price": old_price,

        "stock": stock,

        "image": image,

        "url": url,

        "product_code": product_code

    }


# =========================================================
# COLLECT IPHONE
# =========================================================

def collect_iphone_urls():

    print(
        "\n================================"
    )

    print(
        "🍎 ИЩЕМ IPHONE"
    )

    print(
        "================================"
    )

    urls = set()

    for category_url in IPHONE_CATEGORY_URLS:

        print(
            "\n🌐",
            category_url
        )

        try:

            html = get_html(
                category_url
            )

            links = get_iphone_product_links(
                html
            )

            print(
                "📦 Найдено:",
                len(links)
            )

            urls.update(
                links
            )

        except Exception as error:

            print(
                "⚠️ Ошибка категории:",
                error
            )

        time.sleep(
            0.4
        )

    print(
        "\n🍎 Всего iPhone:",
        len(urls)
    )

    return urls


# =========================================================
# COLLECT ANDROID
# =========================================================

def collect_android_urls():

    print(
        "\n================================"
    )

    print(
        "🤖 ИЩЕМ ANDROID"
    )

    print(
        "================================"
    )

    urls = set()

    category_urls = (
        discover_android_categories()
    )

    # Если категории нашли —
    # идём по ним
    for category_url in category_urls:

        print(
            "\n📂 Android категория:",
            category_url
        )

        try:

            html = get_html(
                category_url
            )

            links = get_android_product_links(
                html
            )

            print(
                "📱 Найдено товаров:",
                len(links)
            )

            urls.update(
                links
            )

        except Exception as error:

            print(
                "⚠️ Ошибка категории:",
                error
            )

        time.sleep(
            0.5
        )

    print(
        "\n🤖 Всего Android:",
        len(urls)
    )

    return urls


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
    "🍎 iPhone + 🤖 Android"
)

print(
    "================================"
)


products = []

seen_urls = set()


try:

    # =====================================================
    # IPHONE
    # =====================================================

    iphone_urls = collect_iphone_urls()

    # =====================================================
    # ANDROID
    # =====================================================

    android_urls = collect_android_urls()

    # Объединяем
    all_urls = []

    for url in iphone_urls:

        if url not in seen_urls:

            seen_urls.add(
                url
            )

            all_urls.append(
                url
            )

    for url in android_urls:

        if url not in seen_urls:

            seen_urls.add(
                url
            )

            all_urls.append(
                url
            )

    # =====================================================
    # ВСЕ ТОВАРЫ
    # =====================================================

    print(
        "\n================================"
    )

    print(
        "📦 ВСЕГО ССЫЛОК:",
        len(all_urls)
    )

    print(
        "================================"
    )

    # =====================================================
    # PARSE
    # =====================================================

    for index, url in enumerate(
        all_urls,
        start=1
    ):

        print(
            f"\n[{index}/{len(all_urls)}]"
        )

        print(
            url
        )

        try:

            brand = get_brand_from_url(
                url
            )

            product = parse_product(
                url,
                brand
            )

            products.append(
                product
            )

            print(
                "✅",
                product["brand"],
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
                "🖼 Фото есть"
            )

        except Exception as error:

            print(
                "❌ Пропущено:",
                error
            )

        time.sleep(
            0.5
        )

    # =====================================================
    # ПРОВЕРКА
    # =====================================================

    if not products:

        raise Exception(
            "Ни одного нормального товара не найдено. "
            "products.json НЕ изменён."
        )

    # =====================================================
    # СТАТИСТИКА
    # =====================================================

    apple_count = sum(
        1
        for product in products
        if product["brand"] == "Apple"
    )

    android_count = len(products) - apple_count

    print(
        "\n================================"
    )

    print(
        "📊 РЕЗУЛЬТАТ"
    )

    print(
        "================================"
    )

    print(
        "🍎 Apple:",
        apple_count
    )

    print(
        "🤖 Android:",
        android_count
    )

    print(
        "📱 Всего:",
        len(products)
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
        "🍎 Apple:",
        apple_count
    )

    print(
        "🤖 Android:",
        android_count
    )

    print(
        "📦 Всего товаров:",
        len(products)
    )

    print(
        "📄 products.json обновлён"
    )

    print(
        "🖼 Фото сохранены в:",
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
