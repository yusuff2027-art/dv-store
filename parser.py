import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


BASE_URL = "https://store77.net"
OUTPUT_FILE = "products.json"

# Стартовые страницы каталога Store77
CATALOG_URLS = [
    "https://store77.net/telefony_apple/",
    "https://store77.net/telefony_samsung/",
    "https://store77.net/telefony_xiaomi/",
    "https://store77.net/telefony_poco/",
    "https://store77.net/telefony_huawei/",
    "https://store77.net/telefony_pixel/",
    "https://store77.net/telefony_oneplus_1/",
    "https://store77.net/telefony_honor/",
    "https://store77.net/telefony_nothing/",
    "https://store77.net/planshety/",
    "https://store77.net/kompyuternaya_tekhnika/",
    "https://store77.net/umnye_chasy_i_braslety/",
    "https://store77.net/audio/",
    "https://store77.net/igrovye_pristavki/",
    "https://store77.net/foto/",
    "https://store77.net/dlya_doma/",
    "https://store77.net/aksessuary/",
]


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_price(text):
    if not text:
        return ""

    # Ищем цены вида:
    # 77 780 ₽
    # 77780 ₽
    # 77 780 руб.
    patterns = [
        r"\d[\d\s\u00A0]*[₽р]\.?",
        r"\d[\d\s\u00A0]*руб\.?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_text(match.group(0))

    return ""


def is_product_url(url):
    if not url:
        return False

    if not url.startswith(BASE_URL):
        return False

    bad_parts = [
        "/search/",
        "/personal/",
        "/favorites",
        "/catalog/",
        "/telefony_",
        "/planshety_",
        "/kompyuternaya_",
        "/audio/",
        "/foto/",
        "/dlya_",
        "/aksessuary/",
        "/umnye_",
        "/igrovye_",
        "/naushniki/",
        "/pylesosy/",
        "/steylery/",
    ]

    # Категорийные страницы нам не нужны.
    for part in bad_parts:
        if part in url:
            return False

    return url.rstrip("/") != BASE_URL


def get_product_links(page, catalog_url):
    print(f"Каталог: {catalog_url}")

    try:
        page.goto(
            catalog_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(2500)

        links = page.locator("a").evaluate_all(
            """
            elements => elements.map(a => ({
                href: a.href,
                text: a.innerText || a.textContent || ""
            }))
            """
        )

        result = {}

        for item in links:
            href = item.get("href", "")
            text = clean_text(item.get("text", ""))

            if is_product_url(href) and text:
                result[href] = text

        print(f"Найдено ссылок: {len(result)}")

        return result

    except Exception as e:
        print(f"Ошибка каталога: {e}")
        return {}


def parse_product(page, url, fallback_name=""):
    print(f"Товар: {url}")

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(1800)

        # Получаем весь видимый текст страницы
        body_text = page.locator("body").inner_text()

        body_text = clean_text(body_text)

        # Заголовок
        title = ""

        selectors = [
            "h1",
            ".product-item-detail-name",
            ".catalog-detail__title",
            "[itemprop='name']",
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector).first

                if locator.count() > 0:
                    value = clean_text(locator.inner_text())

                    if value:
                        title = value
                        break
            except Exception:
                pass

        if not title:
            title = fallback_name

        # Цена
        price = ""

        selectors = [
            "[itemprop='price']",
            ".price",
            ".product-item-detail-price-current",
            ".catalog-detail__price",
            ".price_value",
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector).first

                if locator.count() > 0:
                    value = clean_text(locator.inner_text())

                    found = extract_price(value)

                    if found:
                        price = found
                        break
            except Exception:
                pass

        # Если отдельный селектор не нашёл цену,
        # ищем цену по всему тексту страницы.
        if not price:
            price = extract_price(body_text)

        # Наличие
        available = True

        unavailable_words = [
            "нет в наличии",
            "нет в продаже",
            "под заказ",
            "товар закончился",
        ]

        lower_text = body_text.lower()

        if any(word in lower_text for word in unavailable_words):
            available = False

        # Память
        memory = ""

        memory_patterns = [
            r"\b\d+\s?(?:GB|TB)\b",
            r"\b\d+\s?ГБ\b",
            r"\b\d+\s?ТБ\b",
        ]

        for pattern in memory_patterns:
            match = re.search(pattern, body_text, re.IGNORECASE)

            if match:
                memory = clean_text(match.group(0))
                break

        # Цвет
        color = ""

        color_patterns = [
            r"Цвет[:\s]+([A-Za-zА-Яа-яЁё0-9\- ]{2,30})",
        ]

        for pattern in color_patterns:
            match = re.search(
                pattern,
                body_text,
                re.IGNORECASE,
            )

            if match:
                color = clean_text(match.group(1))
                break

        # Изображение
        image = ""

        image_selectors = [
            "meta[property='og:image']",
            "img[itemprop='image']",
            ".product-detail-image img",
            ".catalog-detail img",
        ]

        for selector in image_selectors:
            try:
                locator = page.locator(selector).first

                if locator.count() > 0:
                    if selector.startswith("meta"):
                        image = locator.get_attribute("content") or ""
                    else:
                        image = locator.get_attribute("src") or ""

                    if image:
                        image = urljoin(BASE_URL, image)
                        break
            except Exception:
                pass

        product = {
            "name": title,
            "price": price,
            "brand": "",
            "memory": memory,
            "color": color,
            "available": available,
            "url": url,
            "image": image,
        }

        print(
            f"  → {title} | "
            f"{price or 'цена не найдена'} | "
            f"{'в наличии' if available else 'нет'}"
        )

        return product

    except Exception as e:
        print(f"Ошибка товара {url}: {e}")
        return None


def main():
    all_links = {}

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 900,
            },
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
        )

        # ---------------------------------
        # 1. Собираем ссылки товаров
        # ---------------------------------

        for catalog_url in CATALOG_URLS:
            links = get_product_links(
                page,
                catalog_url,
            )

            all_links.update(links)

        print()
        print(
            f"ВСЕГО УНИКАЛЬНЫХ ССЫЛОК: "
            f"{len(all_links)}"
        )

        # ---------------------------------
        # 2. Сохраняем диагностику
        # ---------------------------------

        Path("store77_links.json").write_text(
            json.dumps(
                [
                    {
                        "href": url,
                        "text": name,
                    }
                    for url, name in all_links.items()
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # ---------------------------------
        # 3. Парсим товары
        # ---------------------------------

        products = []

        # Пока ограничим количество для теста.
        # После успешного теста уберём ограничение.
        test_links = list(all_links.items())[:30]

        for url, name in test_links:

            product = parse_product(
                page,
                url,
                name,
            )

            if product:
                products.append(product)

            time.sleep(0.5)

        browser.close()

    # ---------------------------------
    # 4. Сохраняем каталог
    # ---------------------------------

    Path(OUTPUT_FILE).write_text(
        json.dumps(
            products,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("==============================")
    print(f"ГОТОВО: {len(products)} товаров")
    print("==============================")


if __name__ == "__main__":
    main()
