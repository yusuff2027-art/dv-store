import json
import re
import time
import urllib.request
from html import unescape
from urllib.parse import urljoin

BASE_URL = "https://apple-avenue.ru"
CATEGORY_URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}


def get_html(url):
    req = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def clean_text(value):
    value = unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def get_product_links(html):
    pattern = r'href=["\']([^"\']*/catalog/iphone_17_pro_max/[^"\']+)["\']'

    links = re.findall(pattern, html, re.I)

    result = []

    for link in links:
        link = unescape(link)

        if "?" in link:
            continue

        if not link.endswith("/"):
            link += "/"

        # Исключаем сам каталог
        if link == "/catalog/iphone_17_pro_max/":
            continue

        full_url = urljoin(BASE_URL, link)

        if full_url not in result:
            result.append(full_url)

    return result


def get_value(html, pattern):
    match = re.search(pattern, html, re.I | re.S)

    if match:
        return clean_text(match.group(1))

    return ""


def parse_product(url):
    html = get_html(url)

    # -------------------------
    # НАЗВАНИЕ
    # -------------------------

    title = re.search(
        r"<title>(.*?)</title>",
        html,
        re.I | re.S
    )

    if title:
        name = clean_text(title.group(1))
        name = re.sub(
            r"\s+купить.*$",
            "",
            name,
            flags=re.I
        )
    else:
        name = "Товар Apple"

    # -------------------------
    # ЦЕНА
    # -------------------------

    base_price = get_value(
        html,
        r'id=["\']base-price["\'][^>]*value=["\']([^"\']+)["\']'
    )

    if base_price:
        try:
            price_number = int(float(base_price))
            price = f"{price_number:,}".replace(",", " ") + " ₽"
        except:
            price = base_price
    else:
        price = "Цена по запросу"

    # -------------------------
    # СТАРАЯ ЦЕНА
    # -------------------------

    old_price = get_value(
        html,
        r'class=["\'][^"\']*price-old[^"\']*["\'][^>]*>(.*?)</'
    )

    # -------------------------
    # НАЛИЧИЕ
    # -------------------------

    if re.search(r"В наличии", html, re.I):
        stock = "В наличии"
    elif re.search(r"Нет в наличии", html, re.I):
        stock = "Нет в наличии"
    elif re.search(r"Под заказ", html, re.I):
        stock = "Под заказ"
    else:
        stock = "Уточняйте наличие"

    # -------------------------
    # ПАМЯТЬ
    # -------------------------

    memory = get_value(
        html,
        r"Встроенная память\s*:?\s*</?[^>]*>\s*([^<]{1,50})"
    )

    if not memory:
        memory = get_value(
            html,
            r"Встроенная память\s*:?\s*([^<]{1,50})"
        )

    # -------------------------
    # ЦВЕТ
    # -------------------------

    color = get_value(
        html,
        r"Цвет\s*:?\s*([^<]{1,50})"
    )

    # -------------------------
    # КОД ТОВАРА
    # -------------------------

    product_code = get_value(
        html,
        r"Код товара\s*:?\s*([A-Za-z0-9_-]+)"
    )

    # -------------------------
    # ГЛАВНАЯ КАРТИНКА
    # -------------------------

    images = re.findall(
        r'(?:src|data-src)=["\']([^"\']+)["\']',
        html,
        re.I
    )

    image = ""

    for img in images:

        img = unescape(img)

        if img.startswith("/"):
            img = urljoin(BASE_URL, img)

        if img.startswith(BASE_URL + "/upload/"):
            image = img
            break

    # -------------------------
    # БРЕНД
    # -------------------------

    brand = "Apple"

    # -------------------------
    # ОПИСАНИЕ
    # -------------------------

    description_parts = []

    if memory:
        description_parts.append(memory)

    if color:
        description_parts.append(f"цвет: {color}")

    description = ", ".join(description_parts)

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


print("================================")
print("🚀 D&V STORE — СИНХРОНИЗАЦИЯ")
print("================================")

try:

    print("\n🌐 Загружаем каталог Apple Avenue...")

    category_html = get_html(CATEGORY_URL)

    print("✅ Каталог загружен")
    print("Размер:", len(category_html), "символов")

    product_links = get_product_links(category_html)

    print("\n📦 Найдено товаров:", len(product_links))

    if not product_links:
        raise Exception("Товары не найдены")

    products = []

    for index, url in enumerate(product_links, start=1):

        print(
            f"\n[{index}/{len(product_links)}] "
            f"Загружаем товар..."
        )

        try:

            product = parse_product(url)

            products.append(product)

            print("✅", product["name"])
            print("💰", product["price"])
            print("📦", product["stock"])
            print("🖼", "Есть" if product["image"] else "Нет")

        except Exception as e:

            print("❌ Ошибка:", e)

        # Небольшая пауза между запросами
        time.sleep(1)

    # -------------------------
    # ЗАЩИТА ОТ ПУСТОГО КАТАЛОГА
    # -------------------------

    if not products:
        raise Exception(
            "Не удалось получить ни одного товара. "
            "products.json не изменён."
        )

    # -------------------------
    # СОХРАНЕНИЕ
    # -------------------------

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

    print("\n================================")
    print("🎉 СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА")
    print("================================")

    print("Товаров сохранено:", len(products))
    print("Файл: products.json")

except Exception as e:

    print("\n================================")
    print("❌ СИНХРОНИЗАЦИЯ ОСТАНОВЛЕНА")
    print("================================")

    print(e)

    raise
