import json
import urllib.request

SOURCE_URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/"

req = urllib.request.Request(
    SOURCE_URL,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

try:
    with urllib.request.urlopen(req, timeout=30) as response:
        html = response.read().decode("utf-8", errors="ignore")

    print("✅ Apple Avenue доступен")
    print("Размер страницы:", len(html), "символов")

    # Пока только сохраняем полученную страницу для анализа
    with open("apple_test.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("✅ Страница сохранена в apple_test.html")

except Exception as e:
    print("❌ Ошибка:", e)
