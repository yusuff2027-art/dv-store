import re
import urllib.request

SOURCE_URL = "https://apple-avenue.ru/catalog/iphone_17_pro_max/"

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

    print("✅ Страница Apple Avenue получена")
    print("Размер страницы:", len(html))

    # Ищем цены
    prices = re.findall(r'[\d\s]+(?:₽|руб)', html)

    print("\n💰 Найденные цены:")
    for price in prices[:30]:
        print(price.strip())

    # Ищем названия iPhone
    products = re.findall(
        r'(iPhone\s+17\s+Pro\s+Max[^<"]*)',
        html,
        flags=re.IGNORECASE
    )

    print("\n📱 Найденные товары:")
    for product in products[:30]:
        print(product.strip())

    print("\n✅ Тест завершён")

except Exception as e:
    print("❌ Ошибка:", e)
