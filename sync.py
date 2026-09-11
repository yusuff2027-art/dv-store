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

print("Размер страницы:", len(html))

# Название из title
title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)

if title:
    name = re.sub(r"\s+", " ", unescape(title.group(1))).strip()
    print("\n📱 TITLE:")
    print(name)

# Все цены на странице
prices = re.findall(
    r"\d[\d\s]*(?:₽|руб\.?)",
    html,
    re.I
)

print("\n💰 ЦЕНЫ:")

unique_prices = []

for price in prices:
    price = re.sub(r"\s+", " ", price).strip()

    if price not in unique_prices:
        unique_prices.append(price)

for price in unique_prices[:20]:
    print(price)

# Картинки
images = re.findall(
    r'(?:"|\')([^"\']+\.(?:jpg|jpeg|png|webp))(?:"|\')',
    html,
    re.I
)

print("\n🖼 КАРТИНКИ:")

unique_images = []

for image in images:
    if image not in unique_images:
        unique_images.append(image)

for image in unique_images[:20]:
    if image.startswith("/"):
        image = "https://apple-avenue.ru" + image

    print(image)

print("\n✅ Карточка проверена")
