import json
import re
from urllib.request import Request, urlopen

URL = "https://li-phone.ru/catalog/smartfony/honor-600-pro"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
}

request = Request(URL, headers=headers)

try:
    html = urlopen(request, timeout=20).read().decode("utf-8", errors="ignore")

    print("Страница получена")
    print("Размер:", len(html), "символов")

    # Ищем цену
    prices = re.findall(r'(\d[\d\s]{2,})\s*₽', html)

    print("Найденные цены:", prices[:10])

except Exception as e:
    print("Ошибка:", e)
