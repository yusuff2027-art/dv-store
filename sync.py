import json
import re
import time
import os
import urllib.request
from html import unescape
from urllib.parse import urljoin

BASE_URL = "https://apple-avenue.ru"
CATEGORY_URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

IMAGE_DIR = "images"

os.makedirs(IMAGE_DIR, exist_ok=True)


# =========================================
# ЗАГРУЗКА СТРАНИЦЫ
# =========================================

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


# =========================================
# ОЧИСТКА ТЕКСТА
# =========================================

def clean_text(value):

    value = unescape(value)

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    # Убираем мусорные разделители
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
        r"-{3,}",
        " ",
        value
    )

    # Убираем конкретный мусор
    value = re.sub(
        r"/память/SIM\)?",
        " ",
        value,
        flags=re.I
    )

    value = re.sub(
        r"\+\s*плашки",
        " ",
        value,
        flags=re.I
    )

    value = re.sub(
        r"\bплашки\b",
        " ",
        value,
        flags=re.I
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip(
        " -,:;|/()"
    )


# =========================================
# ССЫЛКИ НА ТОВАРЫ
# =========================================

def get_product_links(html):

    pattern = (
        r'href=["\']'
        r'([^"\']*/catalog/iphone_17_pro_max/[^"\']+)'
        r'["\']'
    )

    links = re.findall(
        pattern,
        html,
        re.I
    )

    result = []

    for link in links:

        link = unescape(link)

        if "?" in link:
            continue

        if not link.endswith("/"):
            link += "/"

        if link == "/catalog/iphone_17_pro_max/":
            continue

        full_url = urljoin(
            BASE_URL,
            link
        )

        if full_url not in result:
            result.append(full_url)

    return result


# =========================================
# ПОЛУЧЕНИЕ ЗНАЧЕНИЯ
# =========================================

def get_value(html, pattern):

    match = re.search(
        pattern,
        html,
        re.I | re.S
    )

    if match:

        return clean_text(
            match.group(1)
        )

    return ""


# =========================================
# ИМЯ ФАЙЛА
# =========================================

def safe_filename(name):

    name = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+",
        "-",
        name
    )

    return name.strip(
        "-"
    ).lower()


# =========================================
# СКАЧИВАНИЕ ФОТО
# =========================================

def get_product_image(
    html,
    product_name
):

    images = re.findall(
        r'(?:src|data-src)=["\']([^"\']+)["\']',
        html,
        re.I
    )

    candidates = []

    for img in images:

        img = unescape(img)

        if img.startswith("/"):
            img = urljoin(
                BASE_URL,
                img
            )

        if not img.startswith(
            BASE_URL + "/upload/"
        ):
            continue

        if "/upload/iblock/" not in img:
            continue

        if re.search(
            r"\.(jpg|jpeg|png|webp)(?:\?|$)",
            img,
            re.I
        ):

            candidates.append(
                img
            )

    unique = []

    for img in candidates:

        if img not in unique:
            unique.append(img)

    if not unique:
        return ""

    image_url = unique[0]

    filename = safe_filename(
        product_name
    )

    extension = ".jpg"

    if ".png" in image_url.lower():
        extension = ".png"

    elif ".webp" in image_url.lower():
        extension = ".webp"

    local_path = (
        f"{IMAGE_DIR}/{filename}{extension}"
    )

    print(
        "🖼 Скачиваем фото:"
    )

    print(
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

            image_data = response.read()

        if len(image_data) < 1000:

            print(
                "⚠️ Файл слишком маленький"
            )

            return ""

        with open(
            local_path,
            "wb"
        ) as f:

            f.write(image_data)

        print(
            "✅ Фото сохранено:",
            local_path
        )

        return local_path

    except Exception as e:

        print(
            "❌ Ошибка загрузки фото:",
            e
        )

        return ""


# =========================================
# ПАМЯТЬ
# =========================================

def get_memory(
    html,
    name
):

    patterns = [

        r"Встроенная память\s*:?\s*([^<]{1,80})",

        r"Память\s*:?\s*([^<]{1,80})"

    ]

    for pattern in patterns:

        value = get_value(
            html,
            pattern
        )

        if value:

            match = re.search(
                r"(\d+)\s*(GB|Gb|гб|ГБ)",
                value,
                re.I
            )

            if match:

                return (
                    match.group(1)
                    + " ГБ"
                )

    # Если характеристика не найдена,
    # берём память из названия

    match = re.search(
        r"(\d+)\s*(GB|Gb|гб|ГБ)",
        name,
        re.I
    )

    if match:

        return (
            match.group(1)
            + " ГБ"
        )

    return ""


# =========================================
# ЦВЕТ
# =========================================

def get_color(
    html,
    name
):

    patterns = [

        r"Цвет\s*:?\s*([^<]{1,80})",

        r"Color\s*:?\s*([^<]{1,80})"

    ]

    for pattern in patterns:

        value = get_value(
            html,
            pattern
        )

        if value:

            value = clean_text(
                value
            )

            # Убираем мусор после цвета

            value = re.split(
                r"\b(?:память|memory|sim|eSIM|SIM)\b",
                value,
                flags=re.I
            )[0]

            value = value.strip(
                " -,:;|/()"
            )

            if value:

                return value


    # Если цвет указан в названии

    known_colors = [

        "Cosmic Orange",
        "Deep Blue",
        "Silver",
        "Black",
        "White",
        "Gold",

        "Natural Titanium",
        "Blue Titanium",
        "Black Titanium",
        "White Titanium"

    ]

    for color in known_colors:

        if color.lower() in name.lower():

            return color

    return ""


# =========================================
# SIM / ESIM
# =========================================

def get_sim_type(
    html,
    name
):

    # Сначала смотрим только на
    # характеристику страницы.

    patterns = [

        r"Тип SIM[-\s]*карты\s*:?\s*([^<]{1,100})",

        r"Тип SIM\s*:?\s*([^<]{1,100})",

        r"SIM[-\s]*карта\s*:?\s*([^<]{1,100})",

        r"SIM\s*:?\s*([^<]{1,100})",

        r"Поддержка SIM\s*:?\s*([^<]{1,100})"

    ]

    for pattern in patterns:

        value = get_value(
            html,
            pattern
        )

        if not value:
            continue

        value_lower = value.lower()

        has_esim = (
            "esim" in value_lower
            or "e-sim" in value_lower
            or "e sim" in value_lower
        )

        has_sim = bool(
            re.search(
                r"\bnano\s*sim\b|\bdual\s*sim\b|\bsim\s*\+\s*sim\b",
                value_lower
            )
        )

        if has_sim and has_esim:

            return "SIM + eSIM"

        if has_esim:

            return "eSIM"

        if has_sim:

            return "SIM"


    # ВАЖНО:
    #
    # Здесь специально НЕ смотрим на название товара.
    #
    # Потому что название:
    # "(eSim)" может означать конкретную
    # модификацию, но не гарантирует,
    # что на странице характеристика
    # заполнена так же.


    return ""


# =========================================
# КОД ТОВАРА
# =========================================

def get_product_code(html):

    return get_value(
        html,
        r"Код товара\s*:?\s*([A-Za-z0-9_-]+)"
    )


# =========================================
# ТОВАР
# =========================================

def parse_product(url):

    html = get_html(
        url
    )


    # НАЗВАНИЕ

    title = re.search(
        r"<title>(.*?)</title>",
        html,
        re.I | re.S
    )

    if title:

        name = clean_text(
            title.group(1)
        )

        name = re.sub(
            r"\s+купить.*$",
            "",
            name,
            flags=re.I
        )

    else:

        name = "Товар Apple"


    # ЦЕНА

    base_price = get_value(
        html,
        r'id=["\']base-price["\'][^>]*value=["\']([^"\']+)["\']'
    )

    if base_price:

        try:

            price_number = int(
                float(base_price)
            )

            price = (
                f"{price_number:,}"
                .replace(",", " ")
                + " ₽"
            )

        except:

            price = base_price

    else:

        price = "Цена по запросу"


    # СТАРАЯ ЦЕНА

    old_price = get_value(
        html,
        r'class=["\'][^"\']*price-old[^"\']*["\'][^>]*>(.*?)</'
    )


    # НАЛИЧИЕ

    if re.search(
        r"В наличии",
        html,
        re.I
    ):

        stock = "В наличии"

    elif re.search(
        r"Нет в наличии",
        html,
        re.I
    ):

        stock = "Нет в наличии"

    elif re.search(
        r"Под заказ",
        html,
        re.I
    ):

        stock = "Под заказ"

    else:

        stock = "Уточняйте наличие"


    # ХАРАКТЕРИСТИКИ

    memory = get_memory(
        html,
        name
    )

    color = get_color(
        html,
        name
    )

    sim_type = get_sim_type(
        html,
        name
    )


    # КОД

    product_code = get_product_code(
        html
    )


    # ФОТО

    image = get_product_image(
        html,
        name
    )


    # ОПИСАНИЕ

    description_parts = []


    if memory:

        description_parts.append(
            memory
        )


    if color:

        description_parts.append(
            color
        )


    if sim_type:

        description_parts.append(
            sim_type
        )


    description = " • ".join(
        description_parts
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


# =========================================
# ЗАПУСК
# =========================================

print(
    "================================"
)

print(
    "🚀 D&V STORE — СИНХРОНИЗАЦИЯ"
)

print(
    "================================"
)


try:

    print(
        "\n🌐 Загружаем каталог Apple Avenue..."
    )

    category_html = get_html(
        CATEGORY_URL
    )

    print(
        "✅ Каталог загружен"
    )

    print(
        "Размер:",
        len(category_html),
        "символов"
    )


    product_links = get_product_links(
        category_html
    )


    print(
        "\n📦 Найдено товаров:",
        len(product_links)
    )


    if not product_links:

        raise Exception(
            "Товары не найдены"
        )


    products = []


    for index, url in enumerate(
        product_links,
        start=1
    ):

        print(
            f"\n[{index}/{len(product_links)}] "
            "Загружаем товар..."
        )


        try:

            product = parse_product(
                url
            )

            products.append(
                product
            )


            print(
                "✅",
                product["name"]
            )

            print(
                "💰",
                product["price"]
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
                "🖼",
                "Есть"
                if product["image"]
                else "Нет"
            )


        except Exception as e:

            print(
                "❌ Ошибка:",
                e
            )


        time.sleep(1)


    if not products:

        raise Exception(
            "Не удалось получить товары. "
            "products.json не изменён."
        )


    with open(
        "products.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            products,
            f,
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


except Exception as e:

    print(
        "\n================================"
    )

    print(
        "❌ СИНХРОНИЗАЦИЯ ОСТАНОВЛЕНА"
    )

    print(
        "================================"
    )

    print(e)

    raise
