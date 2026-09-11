import json
import re
import urllib.request
from html import unescape

SOURCE_URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/"
OUTPUT_FILE = "products.json"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
    )
}

request = urllib.request.Request(
    SOURCE_URL,
    headers=headers
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="ignore")

    print("✅ Apple Avenue получен")
    print("Размер:", len(html))

    # Убираем лишний HTML
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)

    text = unescape(text)
    text = re.sub(r"\s+", " ", text)

    # Ищем цены
    prices = re.findall(
        r"\d[\d\s]*(?:₽|руб\.?)",
        text,
        flags=re.I
    )

    # Ищем модели
    names = re.findall(
        r"iPhone\s+17\s+Pro\s+Max[^|]{0,100}",
        text,
        flags=re.I
    )

    products = []

    used = set()

    for name in names:
        name = re.sub(r"\s+", " ", name).strip()

        if len(name) < 10:
            continue

        if name in used:
            continue

        used.add(name)

        products.append({
            "name": name,
            "brand": "Apple",
            "description": "iPhone 17 Pro Max",
            "price": "Цена уточняется",
            "stock": "Уточняйте наличие",
            "image": ""
        })

    # Если названия не нашли — не затираем существующий каталог
    if not products:
        print("⚠️ Товары не найдены.")
        print("❌ products.json НЕ изменён.")
        raise SystemExit(0)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"✅ Загружено товаров: {len(products)}")
    print("✅ products.json обновлён")

except Exception as e:
    print("❌ Ошибка:", e)
    raise
