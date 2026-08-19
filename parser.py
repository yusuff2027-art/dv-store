import asyncio
import json
import re
from urllib.parse import quote

from playwright.async_api import async_playwright


SEARCH_URL = (
    "https://store77.net/search/"
    "?cat_id=405&q=" + quote("Айфон 17") + "&ms=1"
)

OUTPUT_FILE = "products.json"
DEBUG_FILE = "store77_debug.html"


def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def extract_price(text):
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

            number = re.sub(
                r"\D",
                "",
                match
            )

            if not number:
                continue

            value = int(number)

            if value < 5000:
                continue

            if value > 1000000:
                continue

            prices.append(value)

    if not prices:
        return None

    value = min(prices)

    return (
        f"{value:,}"
        .replace(",", " ")
        + " ₽"
    )


async def main():

    print("================================")
    print("🚀 D&V STORE DEBUG PARSER")
    print("================================")

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

        await page.wait_for_timeout(
            8000
        )

        print("📜 Прокручиваем страницу...")

        for _ in range(10):

            await page.mouse.wheel(
                0,
                1800
            )

            await page.wait_for_timeout(
                1000
            )

        print("🧪 Сохраняем HTML...")

        html = await page.content()

        with open(
            DEBUG_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(html)

        print(
            f"✅ Сохранён {DEBUG_FILE}"
        )

        print("🔎 Получаем все ссылки...")

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

        print(
            f"🔗 Всего ссылок: {len(links)}"
        )

        # Сохраняем ссылки для диагностики.
        with open(
            "store77_links.json",
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                links,
                file,
                ensure_ascii=False,
                indent=2
            )

        candidates = []

        for item in links:

            href = item.get(
                "href",
                ""
            )

            text = clean_text(
                item.get(
                    "text",
                    ""
                )
            )

            if (
                "store77.net" in href
                and href.startswith("http")
                and "/search/" not in href
            ):

                candidates.append({
                    "href": href,
                    "text": text
                })

        print(
            f"🔎 Кандидатов: "
            f"{len(candidates)}"
        )

        products = []

        # Проверяем первые 30 ссылок.
        for index, item in enumerate(
            candidates[:30],
            start=1
        ):

            url = item["href"]

            try:

                print()
                print(
                    f"📱 [{index}]"
                )

                print(url)

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

                body = clean_text(
                    await product_page.locator(
                        "body"
                    ).inner_text()
                )

                title = clean_text(
                    await product_page.title()
                )

                price = extract_price(
                    body
                )

                if price:

                    product = {
                        "name": title,
                        "price": price,
                        "brand": "Apple",
                        "memory": "",
                        "color": "",
                        "available": True,
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

                else:

                    print(
                        "⚠️ Цена не найдена"
                    )

                await product_page.close()

            except Exception as error:

                print(
                    f"❌ Ошибка: {error}"
                )

        await browser.close()

    print()
    print("================================")
    print(
        f"📦 Найдено товаров: "
        f"{len(products)}"
    )
    print("================================")

    # ВАЖНО:
    # если ничего не нашли,
    # НЕ затираем старый products.json.
    if products:

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

        print(
            "✅ products.json обновлён"
        )

    else:

        print(
            "⚠️ Товары не найдены."
        )

        print(
            "⚠️ Старый products.json НЕ изменён."
        )


if __name__ == "__main__":
    asyncio.run(main())
