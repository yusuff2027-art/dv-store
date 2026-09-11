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

# Ищем именно цену 110 950
for target in ["110 950", "110950", "110\u00a0950"]:

    pos = html.find(target)

    if pos != -1:

        print("================================")
        print("🎯 НАШЛИ ЦЕНУ:", target)
        print("================================")

        start = max(0, pos - 1500)
        end = min(len(html), pos + 1500)

        fragment = html[start:end]

        print(unescape(fragment))

        break

else:
    print("❌ Цена 110 950 не найдена в исходном HTML")
