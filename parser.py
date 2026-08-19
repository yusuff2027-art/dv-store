import asyncio
import json
import re
from urllib.parse import quote, urljoin

from playwright.async_api import async_playwright


SEARCH_URL = (
    "https://store77.net/search/"
    "?cat_id=405&q=" + quote("Айфон 17") + "&ms=1"
)

OUTPUT_FILE = "products.json"


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_price(text):
    """
    Ищем цену товара.
    Сначала ищем крупные суммы от 5 000 ₽,
    чтобы не принять 690 ₽ за цену телефона.
    """

    if not text:
        return None

    patterns = [
        r"(\d[\d\s]{3,})\s*₽",
        r"(\d[\d\s]{3,})\s*руб\.?",
        r"(\d[\d\s]{3,})\s*р\."
    ]

    prices = []

    for pattern in patterns:
        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for match in matches:

            number = re.sub(r"\D", "", match)

            if not number:
                continue

            value = int(number)

            # Телефоны дешевле 5000 ₽ нам не нужны.
            if value < 5000:
                continue

            # Отбрасываем подозрительно большие значения.
            if value > 1000000:
                continue

            prices.append(value)

    if not prices:
        return None

    # Берём минимальную найденную цену.
    # Это защищает от старой/зачёркнутой цены.
    value = min(prices)

    return f"{value:,}".replace(",", " ") + " ₽"


def extract_memory(text):
    if not text:
        return ""

    match = re.search(
        r"\b(64|128|256|512|1024)\s*(?:GB|ГБ)\b",
        text,
        re.IGNORECASE
    )

    if not match:
        return ""

    return match.group(1) + " GB"


def extract_color(text):
    if not text:
        return ""

    colors = [
        "Black",
        "White",
        "Blue",
        "Green",
        "Purple",
        "Red",
        "Pink",
        "Yellow",
        "Silver",
        "Gold",
        "Gray",
        "Grey",
        "Natural",
        "Desert",
        "Lavender",
        "Midnight",
        "Starlight",
        "Черный",
        "Белый",
        "Синий",
        "Зеленый",
        "Фиолетовый",
        "Красный",
        "Розовый",
        "Желтый",
        "Серебристый",
        "Золотой"
    ]

    lower = text.lower()

    for color in colors:
        if color.lower() in lower:
            return color

    return ""


def is_product_url(url):
    """
    Отбрасываем поисковые, категории и служебные страницы.
    """

    if not url:
        return False

    url_lower = url.lower()

    if "store77.net" not in url_lower:
        return False

    blocked = [
        "/search/",
        "/catalog/",
        "/category/",
        "/compare/",
        "/favorite/",
        "/cart/",
        "/contacts/",
        "/about/"
    ]

    for item in blocked:
        if item in url_lower:
            return False

    # Берём только страницы, похожие на товары.
    keywords = [
        "telefon_",
        "iphone",
        "smartfon_",
        "apple_",
        "samsung_",
        "xiaomi_",
        "google_",
        "pixel_"
    ]

    return any(
        keyword in url_lower
        for keyword in keywords
    )


async def main():

    print("======================================")
    print("🚀 D&V STORE — Store77 parser")
    print("======================================")

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000
            },
            locale="ru-RU"
        )

        print("🌐 Открываем Store77...")

        await page.goto(
            SEARCH_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        await page.wait_for_timeout(6000)

        # Прокручиваем страницу.
        for _ in range(8):

            await page.mouse.wheel(
                0,
                1800
            )

            await page.wait_for_timeout(
                700
            )

        print("🔎 Ищем ссылки на товары...")

        links = await page.locator(
            "a[href]"
        ).evaluate_all(
            """
            elements => elements.map(a => ({
                href: a.href,
                text: a.innerText
            }))
            """
        )

        product_links = {}

        for item in links:

            href = item.get("href", "")
            text = clean_text(
                item.get("text", "")
            )

            if not is_product_url(href):
                continue

            product_links[href] = text

        print(
            f"🔗 Найдено ссылок: "
            f"{len(product_links)}"
        )

        products = []

        for index, (
            url,
            link_text
        ) in enumerate(
            product_links.items(),
            start=1
        ):

            if index > 100:
                break

            try:

                print()
                print(
                    f"📱 [{index}] {url}"
                )

                product_page = await browser.new_page(
                    viewport={
                        "width": 1440,
                        "height": 1000
                    },
                    locale="ru-RU"
                )

                await product_page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                await product_page.wait_for_timeout(
                    1500
                )

                # Получаем текст страницы.
                body_text = clean_text(
                    await product_page.locator(
                        "body"
                    ).inner_text()
                )

                # Заголовок.
                title = ""

                for selector in [
                    "h1",
                    ".product-title",
                    "[class*='product-title']"
                ]:

                    locator = product_page.locator(
                        selector
                    ).first

                    if await locator.count():

                        value = clean_text(
                            await locator.inner_text()
                        )

                        if value:
                            title = value
                            break

                if not title:
                    title = clean_text(
                        link_text
                    )

                # Не принимаем страницы категорий.
                if not title:
                    await product_page.close()
                    continue

                # Цена.
                price = None

                # Сначала пытаемся найти цену в элементах,
                # которые обычно используются для цены.
                price_selectors = [
                    ".price",
                    ".product-price",
                    "[class*='price']",
                    "[class*='Price']"
                ]

                for selector in price_selectors:

                    elements = product_page.locator(
                        selector
                    )

                    count = min(
                        await elements.count(),
                        20
                    )

                    for i in range(count):

                        try:

                            text = clean_text(
                                await elements.nth(
                                    i
                                ).inner_text()
                            )

                            candidate = extract_price(
                                text
                            )

                            if candidate:

                                price = candidate
                                break

                        except Exception:
                            pass

                    if price:
                        break

                # Если специальный блок не найден,
                # используем текст страницы.
                if not price:

                    price = extract_price(
                        body_text
                    )

                if not price:

                    print(
                        "⚠️ Цена не найдена"
                    )

                    await product_page.close()
                    continue

                memory = extract_memory(
                    body_text
                )

                color = extract_color(
                    body_text
                )

                lower_body = body_text.lower()

                unavailable = [
                    "нет в наличии",
                    "нет на складе",
                    "товар закончился",
                    "отсутствует"
                ]

                available = not any(
                    word in lower_body
                    for word in unavailable
                )

                product = {
                    "name": title,
                    "price": price,
                    "brand": "Apple",
                    "memory": memory,
                    "color": color,
                    "available": available,
                    "url": url
                }

                products.append(
                    product
                )

                print(
                    f"✅ {title}"
                )

                print(
                    f"💰 {price}"
                )

                print(
                    f"💾 {memory}"
                )

                print(
                    f"🎨 {color}"
                )

                await product_page.close()

            except Exception as error:

                print(
                    f"❌ Ошибка: {error}"
                )

        await browser.close()

    # Убираем дубли по URL.
    unique = {}

    for product in products:

        unique[
            product["url"]
        ] = product

    products = list(
        unique.values()
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            products,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("======================================")
    print(
        f"🎉 Товаров сохранено: "
        f"{len(products)}"
    )
    print("📄 products.json обновлён")
    print("======================================")


if __name__ == "__main__":
    asyncio.run(main())
