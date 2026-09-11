import urllib.request
import re

URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/"

req = urllib.request.Request(
    URL,
    headers={"User-Agent": "Mozilla/5.0"}
)

with urllib.request.urlopen(req, timeout=30) as response:
    html = response.read().decode("utf-8", errors="ignore")

print("РАЗМЕР:", len(html))

# Показываем фрагменты вокруг iPhone 17 Pro Max
matches = list(re.finditer("iPhone 17 Pro Max", html, re.I))

print("НАЙДЕНО УПОМИНАНИЙ:", len(matches))

for i, match in enumerate(matches[:3]):
    start = max(0, match.start() - 1000)
    end = min(len(html), match.end() + 2000)

    print("\n" + "=" * 80)
    print("ТОВАР", i + 1)
    print("=" * 80)
    print(html[start:end])
