import re
import urllib.request
from html import unescape

URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/apple_iphone_17_pro_max_256gb_cosmic_orange_esim/"

req = urllib.request.Request(
    URL,
    headers={"User-Agent": "Mozilla/5.0"}
)

with urllib.request.urlopen(req, timeout=30) as response:
    html = response.read().decode("utf-8", errors="ignore")

text = unescape(re.sub(r"<[^>]+>", " ", html))
text = re.sub(r"\s+", " ", text)

print("================================")
print("📱 НАЗВАНИЕ")
print("================================")

title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)

if title:
    name = re.sub(r"\s+", " ", unescape(title.group(1))).strip()
    name = re.sub(r"\s+купить.*$", "", name, flags=re.I)
    print(name)

print("\n================================")
print("💰 ЦЕНЫ")
print("================================")

prices = re.findall(
    r"\b\d{1,3}(?:[\s\u00a0]\d{3})+\s*(?:руб\.?|₽)",
    text,
    re.I
)

for price in dict.fromkeys(prices):
    print(price)

print("\n================================")
print("📦 ХАРАКТЕРИСТИКИ")
print("================================")

patterns = [
    ("Наличие", r"(В наличии|Нет в наличии|Под заказ)"),
    ("Память", r"Встроенная память\s*:?\s*([^<]{1,50}?)(?=\s*(?:Цвет|Тип|SIM|$))"),
    ("Цвет", r"Цвет\s*:?\s*([^<]{1,50}?)(?=\s*(?:Встроенная|Тип|SIM|$))"),
    ("Код товара", r"Код товара\s*:?\s*([A-Za-z0-9_-]+)"),
]

for label, pattern in patterns:
    match = re.search(pattern, text, re.I)

    if match:
        value = re.sub(r"\s+", " ", match.group(1)).strip()
        print(f"{label}: {value}")
    else:
        print(f"{label}: не найдено")

print("\n================================")
print("🖼 ГЛАВНАЯ КАРТИНКА")
print("================================")

images = re.findall(
    r'(?:src|data-src)=["\']([^"\']+)["\']',
    html,
    re.I
)

unique_images = []

for image in images:
    if image.startswith("/"):
        image = "https://apple-avenue.ru" + image

    if image.startswith("https://apple-avenue.ru/upload/"):
        if image not in unique_images:
            unique_images.append(image)

if unique_images:
    print(unique_images[0])
else:
    print("Картинка не найдена")

print("\n================================")
print("✅ ТЕСТ ЗАКОНЧЕН")
print("================================")
