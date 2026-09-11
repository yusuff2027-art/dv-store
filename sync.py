import re
import urllib.request

URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/"

req = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

with urllib.request.urlopen(req, timeout=30) as response:
    html = response.read().decode("utf-8", errors="ignore")

print("Размер страницы:", len(html))

patterns = [
    r'https?://[^"\']+\.(?:jpg|jpeg|png|webp)',
    r'(?:"|\')([^"\']+)\.(?:jpg|jpeg|png|webp)(?:"|\')',
    r'\d[\d\s]{2,}\s*₽',
    r'iPhone\s+17\s+Pro\s+Max[^<]{0,150}'
]

for pattern in patterns:
    print("\n" + "=" * 70)
    print("ШАБЛОН:", pattern)
    print("=" * 70)

    matches = re.findall(pattern, html, re.I)

    unique = []

    for item in matches:
        if isinstance(item, tuple):
            item = item[0]

        item = item.strip()

        if item and item not in unique:
            unique.append(item)

    for item in unique[:50]:
        print(item)

print("\n✅ Тест завершён")
