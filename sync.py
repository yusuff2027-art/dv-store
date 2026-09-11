import json
import re
import time
import os
import urllib.request
from html import unescape
from urllib.parse import urljoin

BASE_URL = "https://apple-avenue.ru"

# ОБЩИЙ КАТАЛОГ IPHONE
CATEGORY_URL = "https://apple-avenue.ru/catalog/iphone/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}

IMAGE_DIR = "images"

os.makedirs(IMAGE_DIR, exist_ok=True)


# =========================================================
# ЗАГРУЗКА
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
# ОЧИСТКА ТЕКСТА
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

    # CSS / JS мусор
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
        r"-{3,}",
        " ",
        value
    )

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


# =========================================================
# ССЫЛКИ ТОВАРОВ
# =========================================================

def get_product_links(html):

    # Берём любые страницы товаров внутри /catalog/iphone/
    pattern = (
        r'href=["\']'
        r'([^"\']*/catalog/iphone/[^"\']+)'
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

        if "#" in link:
            continue

        if not link.endswith("/"):
            link += "/"

        # Не добавляем сам каталог
        if link == "/catalog/iphone/":
            continue

        # Не берём служебные ссылки
        if any(
            x in link.lower()
            for x in [
                "/filter/",
                "/compare/",
                "/search/",
                "/favorites/"
            ]
        ):
            continue

        full_url = urljoin(
            BASE_URL,
            link
        )

        if full_url not in result:

            result.append(
                full_url
            )

    return result


# =========================================================
# ФОТО
# =========================================================

def safe_filename(name):

    name = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+",
        "-",
        name
    )

    return name.strip(
        "-"
    ).lower()


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
                "⚠️ Фото слишком маленькое"
            )

            return ""

        with open(
            local_path,
            "wb"
        ) as file:

            file.write(
                image_data
            )

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
# ПАМЯТЬ
# =========================================================

def get_memory(
    html,
    name
):

    # Сначала название
    match = re.search(
        r"(\d+)\s*(?:GB|Gb|gb|ГБ|гб)",
        name,
        re.I
    )

    if match:

        return (
            match.group(1)
            + " ГБ"
        )

    # Потом характеристики
    patterns = [

        r"Встроенная память\s*:?\s*([^<]{1,80})",

        r"Память\s*:?\s*([^<]{1,80})"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if not match:
            continue

        value = clean_text(
            match.group(1)
        )

        memory_match = re.search(
            r"(\d+)\s*(?:GB|Gb|gb|ГБ|гб)",
            value,
            re.I
        )

        if memory_match:

            return (
                memory_match.group(1)
                + " ГБ"
            )

    return ""


# =========================================================
# ЦВЕТ
# =========================================================

def get_color(
    html,
    name
):

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
        "White Titanium",

        "Desert Titanium",
        "Titanium Gray",
        "Space Black",
        "Space Gray",

        "Rose Gold",
        "Midnight",
        "Starlight",

        "Purple",
        "Green",
        "Red",
        "Yellow",
        "Blue"

    ]

    # Сначала название
    for color in known_colors:

        if color.lower() in name.lower():

            return color

    # Потом характеристики
    patterns = [

        r"Цвет\s*:?\s*([^<]{1,80})",

        r"Color\s*:?\s*([^<]{1,80})"

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

            for color in known_colors:

                if color.lower() in value.lower():

                    return color

    return ""


# =========================================================
# SIM / ESIM
# =========================================================

def get_sim_type(
    html,
    name
):

    patterns = [

        r"Тип SIM[-\s]*карты\s*:?\s*([^<]{1,150})",

        r"Тип SIM\s*:?\s*([^<]{1,150})",

        r"SIM[-\s]*карта\s*:?\s*([^<]{1,150})",

        r"Поддержка SIM\s*:?\s*([^<]{1,150})",

        r"SIM\s*:?\s*([^<]{1,150})"

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

            if not value:
                continue

            lower = value.lower()

            # Нормализуем варианты eSIM
            normalized = lower.replace(
                "e-sim",
                "esim"
            ).replace(
                "e sim",
                "esim"
            )

            has_esim = "esim" in normalized

            # Убираем слово esim,
            # чтобы оно не считалось обычной SIM
            without_esim = re.sub(
                r"e\s*-?\s*sim",
                "",
                normalized,
                flags=re.I
            )

            # Ищем физическую SIM
            has_physical_sim = bool(
                re.search(
                    r"\bnano[\s-]*sim\b"
                    r"|\bphysical[\s-]*sim\b"
                    r"|\bdual[\s-]*sim\b"
                    r"|\bsim\s*\+\s*sim\b"
                    r"|\bsim\b",
                    without_esim,
                    re.I
                )
            )

            # Главное:
            # если есть и физическая SIM,
            # и eSIM
            if has_esim and has_physical_sim:

                return "SIM + eSIM"

            # Только eSIM
            if has_esim:

                return "eSIM"

            # Только физическая SIM
            if has_physical_sim:

                return "SIM"

    return ""


# =========================================================
# НАЛИЧИЕ
# =========================================================

def get_stock(html):

    if re.search(
        r"В наличии",
        html,
        re.I
    ):

        return "В наличии"

    if re.search(
        r"Нет в наличии",
        html,
        re.I
    ):

        return "Нет в наличии"

    if re.search(
        r"Под заказ",
        html,
        re.I
    ):

        return "Под заказ"

    return "Уточняйте наличие"


# =========================================================
# ЦЕНА
# =========================================================

def get_price(html):

    match = re.search(
        r'id=["\']base-price["\']'
        r'[^>]*value=["\']([^"\']+)["\']',
        html,
        re.I
    )

    if not match:

        return "Цена по запросу"

    value = match.group(1)

    try:

        number = int(
            float(value)
        )

        return (
            f"{number:,}"
            .replace(",", " ")
            + " ₽"
        )

    except:

        return value


# =========================================================
# СТАРАЯ ЦЕНА
# =========================================================

def get_old_price(html):

    match = re.search(
        r'class=["\'][^"\']*price-old[^"\']*["\']'
        r'[^>]*>(.*?)</',
        html,
        re.I | re.S
    )

    if not match:
        return ""

    return clean_text(
        match.group(1)
    )


# =========================================================
# КОД ТОВАРА
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
# ТОВАР
# =========================================================

def parse_product(url):

    html = get_html(
        url
    )

    # -----------------------------
    # НАЗВАНИЕ
    # -----------------------------

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

    # -----------------------------
    # ДАННЫЕ
    # -----------------------------

    price = get_price(
        html
    )

    old_price = get_old_price(
        html
    )

    stock = get_stock(
        html
    )

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

    product_code = get_product_code(
        html
    )

    image = get_product_image(
        html,
        name
    )

    # -----------------------------
    # ОПИСАНИЕ
    # -----------------------------

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


# =========================================================
# ЗАПУСК
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

try:

    print(
        "\n🌐 Загружаем общий каталог iPhone..."
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

        except Exception as error:

            print(
                "❌ Ошибка:",
                error
            )

        time.sleep(1)

    if not products:

        raise Exception(
            "Не удалось получить товары. "
            "products.json не изменён."
        )

    # =====================================================
    # СОХРАНЯЕМ
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
