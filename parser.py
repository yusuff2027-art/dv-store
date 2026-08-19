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


def clean_price(text):
    """
    Ищем цену в формате:
    77 780 ₽
    77780 руб.
    """
    if not text:
        return None

    match = re.search(
        r"(\d[\d\s]{2,})\s*(?:₽|руб\.?|р\.)",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    number = re.sub(r"\D", "", match.group(1))

    if not number:
        return None

    return f"{int(number):,}".replace(",", " ") + " ₽"


def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


async def main():

    print("🚀 Запуск парсера Store77")
    print("🔎 Страница:", SEARCH_URL)

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

        await page.wait_for_timeout(7000)

        print("📦 Страница загружена")

        # Немного прокручиваем страницу,
        # чтобы динамический каталог успел загрузиться.
        for _ in range(5):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(1000)

        # Собираем ссылки на товары.
        links = await page.locator("a").evaluate_all(
            """
            elements => elements.map(a => ({
                href: a.href,
                text: a.innerText
            }))
            """
        )

        product_links = {}

        for item in links:

            href = item.get("href") or ""
            text = clean_text(item.get("text") or "")

            if not href:
                continue

            # Берём только ссылки Store77
            # и отбрасываем служебные страницы.
            if "store77.net" not in href:
                continue

            if "/search/" in href:
                continue

            if "/catalog/" in href:
                continue

            if "#" in href:
                continue

            # Нам нужны ссылки, в которых есть
            # признаки товара.
            if any(
                word in href.lower()
                for word in [
                    "/apple_",
                    "/iphone",
                    "/telefon_",
                    "/smartfon",
                    "/samsung_",
                    "/xiaomi_"
                ]
            ):
                product_links[href] = text

        print(
            f"🔗 Найдено потенциальных товаров: "
            f"{len(product_links)}"
        )

        products = []

        # Пока ограничиваемся 50 товарами,
        # чтобы первый тест не был слишком большим.
        for index, (url, link_text) in enumerate(
            list(product_links.items())[:50],
            start=1
        ):

            try:

                print(
                    f"📱 [{index}] Открываем: {url}"
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

                await product_page.wait_for_timeout(2000)

                body_text = await product_page.locator(
                    "body"
                ).inner_text()

                body_text = clean_text(body_text)

                title = ""

                # Пробуем получить нормальный title страницы.
                page_title = await product_page.title()

                if page_title:
                    title = clean_text(page_title)

                if not title:
                    title = link_text

                price = clean_price(body_text)

                # Если цена не нашлась — товар пока пропускаем.
                if not price:
                    print(
                        "⚠️ Цена не найдена — пропускаем"
                    )
                    await product_page.close()
                    continue

                # Пытаемся определить наличие.
                available = True

                lower_text = body_text.lower()

                unavailable_words = [
                    "нет в наличии",
                    "нет на складе",
                    "товар закончился",
                    "отсутствует"
                ]

                if any(
                    word in lower_text
                    for word in unavailable_words
                ):
                    available = False

                product = {
                    "name": title,
                    "price": price,
                    "brand": "Apple",
                    "memory": "",
                    "color": "",
                    "available": available,
                    "url": url
                }

                products.append(product)

                print(
                    f"✅ {title} — {price}"
                )

                await product_page.close()

            except Exception as error:

                print(
                    f"❌ Ошибка товара: {error}"
                )

        await browser.close()

    # Сохраняем каталог.
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
    print("=" * 50)
    print(
        f"🎉 Готово! Сохранено товаров: "
        f"{len(products)}"
    )
    print(
        f"📄 Файл: {OUTPUT_FILE}"
    )
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
