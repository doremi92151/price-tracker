import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


MAX_DISCOUNT_RATE = 0.50

WATSONS_URL = "https://www.watsons.com.tw/全部商品/c/1"
WATSONS_BASE = "https://www.watsons.com.tw"

BLOCKED_WORDS = [
    "買2件",
    "買二件",
    "買 2 件",
    "第二件",
    "第2件",
    "買一送一",
    "買1送1",
    "加價購",
    "任選",
    "任2",
    "任3",
    "任4",
    "組合價",
]


def clean_price(text):
    if not text:
        return None

    text = text.replace(",", "")

    match = re.search(r"\$?\s*(\d+)", text)

    if not match:
        return None

    return int(match.group(1))


def blocked(text):
    text = text or ""

    for word in BLOCKED_WORDS:
        if word in text:
            return True

    return False


def add_product(products, name, original, sale, url):

    if not name:
        return False

    if not original or not sale:
        return False

    if original <= 0 or sale <= 0:
        return False

    if sale >= original:
        return False

    rate = sale / original

    if rate > MAX_DISCOUNT_RATE:
        return False

    if blocked(name):
        return False

    products.append({
        "store": "屈臣氏",
        "name": name.strip(),
        "original": original,
        "sale": sale,
        "rate": round(rate, 4),
        "discount": round(rate * 10, 1),
        "save": original - sale,
        "url": url
    })

    return True


def scrape_watsons(products):

    print("")
    print("==============================")
    print("開始掃描屈臣氏 Playwright")
    print("==============================")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = browser.new_context(
            locale="zh-TW",
            viewport={
                "width": 1440,
                "height": 1600
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()

        print("開啟：")
        print(WATSONS_URL)

        try:

            response = page.goto(
                WATSONS_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            if response:
                print("HTTP:", response.status)

            page.wait_for_timeout(8000)

            print("頁面標題：", page.title())
            print("目前網址：", page.url)

            # 往下捲動，觸發 lazy loading
            previous_height = 0

            for i in range(12):

                height = page.evaluate(
                    "document.body.scrollHeight"
                )

                print(
                    f"Scroll {i + 1}:",
                    height
                )

                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )

                page.wait_for_timeout(1500)

                if height == previous_height:
                    break

                previous_height = height

            html = page.content()

            print(
                "HTML 長度：",
                len(html)
            )

            body_text = page.locator(
                "body"
            ).inner_text()

            print(
                "頁面文字長度：",
                len(body_text)
            )

            print("")
            print("===== 頁面前 2000 字 =====")
            print(body_text[:2000])
            print("===== 結束 =====")
            print("")

            # 找出所有連結
            links = page.locator("a").all()

            print(
                "全部連結數：",
                len(links)
            )

            seen_urls = set()

            for link in links:

                try:

                    href = link.get_attribute(
                        "href"
                    )

                    if not href:
                        continue

                    full_url = urljoin(
                        WATSONS_BASE,
                        href
                    )

                    # 商品網址通常包含 product / p / sku 等資訊
                    href_lower = href.lower()

                    possible_product = (
                        "/p/" in href_lower
                        or "/product/" in href_lower
                        or "product" in href_lower
                    )

                    if not possible_product:
                        continue

                    if full_url in seen_urls:
                        continue

                    seen_urls.add(full_url)

                    # 往上找包含價格的商品卡
                    card = link

                    card_text = ""

                    for _ in range(10):

                        try:
                            card_text = card.inner_text(
                                timeout=1000
                            )
                        except:
                            card_text = ""

                        prices = re.findall(
                            r"\$\s*[\d,]+",
                            card_text
                        )

                        if len(prices) >= 2:
                            break

                        card = card.locator("..")

                    if not card_text:
                        continue

                    if blocked(card_text):
                        continue

                    price_matches = re.findall(
                        r"\$\s*([\d,]+)",
                        card_text
                    )

                    price_values = []

                    for price in price_matches:

                        value = clean_price(
                            price
                        )

                        if (
                            value
                            and value not in price_values
                        ):
                            price_values.append(
                                value
                            )

                    if len(price_values) < 2:
                        continue

                    sale = min(
                        price_values
                    )

                    original = max(
                        price_values
                    )

                    # 優先使用連結文字當商品名稱
                    name = ""

                    try:
                        name = link.inner_text(
                            timeout=1000
                        ).strip()
                    except:
                        pass

                    # 連結本身沒文字時，用商品卡文字第一行
                    if not name:

                        lines = [
                            x.strip()
                            for x in card_text.splitlines()
                            if x.strip()
                        ]

                        for line in lines:

                            if "$" in line:
                                continue

                            if len(line) < 3:
                                continue

                            name = line
                            break

                    if not name:
                        continue

                    if add_product(
                        products,
                        name,
                        original,
                        sale,
                        full_url
                    ):

                        print(
                            "★",
                            name[:50],
                            f"${original}",
                            "→",
                            f"${sale}"
                        )

                except Exception:
                    continue

            print("")
            print(
                "疑似商品網址：",
                len(seen_urls)
            )

            print(
                "符合5折以下：",
                len(products)
            )

        finally:

            browser.close()


def remove_duplicates(products):

    unique = {}

    for product in products:

        key = (
            product["store"],
            product["url"]
        )

        unique[key] = product

    return list(
        unique.values()
    )


def main():

    products = []

    scrape_watsons(
        products
    )

    products = remove_duplicates(
        products
    )

    products.sort(
        key=lambda x: x["rate"]
    )

    taiwan_timezone = timezone(
        timedelta(hours=8)
    )

    now = datetime.now(
        taiwan_timezone
    )

    output = {
        "updated": now.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "count": len(products),
        "products": products
    }

    with open(
        "products.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("")
    print("==============================")
    print("完成")
    print(
        "5折以下商品：",
        len(products),
        "個"
    )
    print("==============================")


if __name__ == "__main__":
    main()
