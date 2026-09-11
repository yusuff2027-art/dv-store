import re
import urllib.request

URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/"

req = urllib.request.Request(
    URL,
    headers={"User-Agent": "Mozilla/5.0"}
)

with urllib.request.urlopen(req, timeout=30) as response:
    html = response.read().decode("utf-8", errors="ignore")

print("Размер:", len(html))

# Ищем ссылки на товары
links = re.findall(
    r'href=["\']([^"\']*iphone[^"\']*)["\']',
    html,
    re.I
)

print("\n🔗 ССЫЛКИ НА ТОВАРЫ:")

unique_links = []

for link in links:
    if link not in unique_links:
        unique_links.append(link)

for link in unique_links[:50]:
    print(link)

# Ищем цены
prices = re.findall(
    r'\d[\d\s]{2,}\s*₽',
    html
)

print("\n💰 ЦЕНЫ:")

unique_prices = []

for price in prices:
    price = price.strip()

    if price not in unique_prices:
        unique_prices.append(price)

for price in unique_prices[:50]:
    print(price)

print("\n✅ Тест завершён")
