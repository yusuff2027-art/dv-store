import json
import re
import time
import os
import urllib.request
from html import unescape
from urllib.parse import urljoin, urlparse

BASE_URL = "https://apple-avenue.ru"
CATEGORY_URL = "https://apple-avenue.ru/catalog/iphone/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    )
}

IMAGE_DIR = "images"

os.makedirs(IMAGE_DIR, exist_ok=True)


# =========================================================
# ЗАГРУЗКА HTML
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

    # CSS-мусор
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
# ССЫЛКИ НА ТОВАРЫ
# =========================================================

def get_product_links(html):

    # -----------------------------------------------------
    # Вариант 1:
    # Ищем ссылки на catalog в HTML
    # -----------------------------------------------------

    raw_links = re.findall(
        r'href\s*=\s*["\']([^"\']+)["\']',
        html,
        re.I
    )

    result = []

    for link in raw_links:

        link = unescape(link).strip()

        if not link:
            continue

        if link.startswith(
            ("#", "javascript:", "mailto:", "tel:")
        ):
            continue

        full_url = urljoin(
            BASE_URL,
            link
        )

        parsed = urlparse(
            full_url
        )

        # Только apple-avenue.ru
        if parsed.netloc.lower() != "apple-avenue.ru":
            continue

        path = parsed.path.rstrip("/")

        if not path:
            continue

        path_lower = path.lower()

        # Только каталог
        if not path_lower.startswith(
            "/catalog/"
        ):
            continue

        # Не берём фильтры и служебные страницы
        bad_parts = [
            "/filter/",
            "/compare/",
            "/search/",
            "/favorites/",
            "/basket/",
            "/order/",
            "/ajax/"
        ]

        if any(
            bad in path_lower
            for bad in bad_parts
        ):
            continue

        # Сам каталог iPhone не является товаром
        if path_lower == "/catalog/iphone":
            continue

        # Категории моделей тоже не нужны.
        # Их определяем по URL.
        category_names = [
            "iphone",
            "iphone_17",
            "iphone_17_pro",
            "iphone_17_pro_max",
            "iphone_17_air",
            "iphone_16",
            "iphone_16_pro",
            "iphone_16_pro_max",
            "iphone_16_plus",
            "iphone_16e",
            "iphone_15",
            "iphone_15_pro",
            "iphone_15_pro_max",
            "iphone_15_plus",
            "iphone_14",
            "iphone_14_pro",
            "iphone_14_pro_max",
            "iphone_13",
            "iphone_13_pro",
            "iphone_13_pro_max",
            "iphone_12",
            "iphone_12_pro",
            "iphone_12_pro_max",
            "iphone_11",
            "iphone_11_pro",
            "iphone_11_pro_max"
        ]

        last_part = path_lower.split("/")[-1]

        if last_part in category_names:
            continue

        # Ссылки с одинаковым URL не дублируем
        if full_url not in result:

            result.append(
                full_url
            )

    # -----------------------------------------------------
    # Вариант 2:
    # Иногда сайт содержит ссылки в data-href
    # -----------------------------------------------------

    data_links = re.findall(
        r'(?:data-href|data-url|data-link)\s*=\s*["\']([^"\']+)["\']',
        html,
        re.I
    )

    for link in data_links:

        link = unescape(link).strip()

        full_url = urljoin(
            BASE_URL,
            link
        )

        parsed = urlparse(
            full_url
        )

        if parsed.netloc.lower() != "apple-avenue.ru":
            continue

        if not parsed.path.lower().startswith(
            "/catalog/"
        ):
            continue

        if full_url not in result:

            result.append(
                full_url
            )

    return result


# =========================================================
# ИМЯ ФАЙЛА
# =========================================================

def safe_filename(name):

    name = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+",
        "-",
        name
    )

    name = name.strip(
        "-"
    ).lower()

    if not name:
        name = "product"

    return name[:180]


# =========================================================
# ФОТО
# =========================================================

def get_product_image(
    html,
    product_name
):

    images = re.findall(
        r'(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']',
        html,
        re.I
    )

    candidates = []

    for img in images:

        img = unescape(
            img
        ).strip()

        if not img:
            continue

        img = urljoin(
            BASE_URL,
            img
        )

        if "/upload/" not in img:
            continue

        if not re.search(
            r"\.(jpg|jpeg|png|webp)(?:\?|$)",
            img,
            re.I
        ):
            continue

        if img not in candidates:

            candidates.append(
                img
            )

    if not candidates:

        # Пробуем og:image
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.I
        )

        if match:

            img = urljoin(
                BASE_URL,
                unescape(
                    match.group(1)
                )
            )

            candidates.append(
                img
            )

    if not candidates:

        return ""

    image_url = candidates[0]

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

            file.write(
                data
            )

        print(
            "✅ Фото сохранено"
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

        r"Встроенная память\s*:?\s*([^<]{1,100})",

        r"Память\s*:?\s*([^<]{1,100})",

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

        r"Цвет\s*:?\s*([^<]{1,100})",

        r"Color\s*:?\s*([^<]{1,100})"

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

        r"SIM\s*:?\s*([^<]{1,150})",

        r"SIM[-\s]*карты\s*:?\s*([^<]{1,150})"

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

            normalized = (
                lower
                .replace(
                    "e-sim",
                    "esim"
                )
                .replace(
                    "e sim",
                    "esim"
                )
            )

            has_esim = (
                "esim" in normalized
            )

            # Временно убираем eSIM,
            # чтобы слово SIM внутри eSIM
            # не считалось физической SIM
            without_esim = re.sub(
                r"e\s*-?\s*sim",
                "",
                normalized,
                flags=re.I
            )

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

            # SIM + eSIM
            if (
                has_esim
                and has_physical_sim
            ):

                return "SIM + eSIM"

            # Только eSIM
            if has_esim:

                return "eSIM"

            # Только SIM
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

    # Основной способ
    match = re.search(
        r'id=["\']base-price["\']'
        r'[^>]*value=["\']([^"\']+)["\']',
        html,
        re.I
    )

    if match:

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
            pass

    # Запасной вариант
    patterns = [

        r'"price"\s*:\s*"?(\d+(?:\.\d+)?)',

        r'"PRICE"\s*:\s*"?(\d+(?:\.\d+)?)',

        r'data-price=["\'](\d+(?:\.\d+)?)["\']'

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I
        )

        if match:

            try:

                number = int(
                    float(
                        match.group(1)
                    )
                )

                return (
                    f"{number:,}"
                    .replace(",", " ")
                    + " ₽"
                )

            except:
                pass

    return "Цена по запросу"


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

    patterns = [

        r"Код товара\s*:?\s*([A-Za-z0-9_-]+)",

        r"Артикул\s*:?\s*([A-Za-z0-9_-]+)",

        r'"CODE"\s*:\s*"([^"]+)"'

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
# ПРОВЕРКА ЧТО ЭТО ТОВАР
# =========================================================

def looks_like_product(
    html,
    url
):

    lower = html.lower()

    # Должна присутствовать цена
    has_price = bool(
        re.search(
            r"base-price|price-old|₽|руб",
            lower,
            re.I
        )
    )

    # И хотя бы одна характеристика
    has_characteristic = bool(
        re.search(
            r"память|gb|гб|sim|esim|цвет|color",
            lower,
            re.I
        )
    )

    return (
        has_price
        and has_characteristic
    )


# =========================================================
# ТОВАР
# =========================================================

def parse_product(url):

    html = get_html(
        url
    )

    if not looks_like_product(
        html,
        url
    ):

        print(
            "⏭ Не похоже на карточку товара"
        )

        return None

    # -----------------------------------------------------
    # НАЗВАНИЕ
    # -----------------------------------------------------

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

        # Пробуем h1
        h1 = re.search(
            r"<h1[^>]*>(.*?)</h1>",
            html,
            re.I | re.S
        )

        if h1:

            name = clean_text(
                h1.group(1)
            )

        else:

            name = "Товар Apple"

    # -----------------------------------------------------
    # ДАННЫЕ
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # ОПИСАНИЕ
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # ССЫЛКИ
    # -----------------------------------------------------

    product_links = get_product_links(
        category_html
    )

    print(
        "\n📦 Найдено ссылок:",
        len(product_links)
    )

    if not product_links:

        raise Exception(
            "Товары не найдены"
        )

    products = []

    # -----------------------------------------------------
    # ОБРАБОТКА
    # -----------------------------------------------------

    for index, url in enumerate(
        product_links,
        start=1
    ):

        print(
            f"\n[{index}/{len(product_links)}]"
        )

        print(
            url
        )

        try:

            product = parse_product(
                url
            )

            if not product:

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
                "❌ Ошибка товара:",
                error
            )

        time.sleep(1)

    # -----------------------------------------------------
    # ПРОВЕРКА
    # -----------------------------------------------------

    if not products:

        raise Exception(
            "Не удалось получить ни одного товара. "
            "products.json НЕ изменён."
        )

    # -----------------------------------------------------
    # СОХРАНЕНИЕ
    # -----------------------------------------------------

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
        "Папка фото:",
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
