import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

MAX_DISCOUNT_RATE = 0.50

WATSONS_URL = "https://www.watsons.com.tw/全部商品/c/1"
WATSONS_BASE = "https://www.watsons.com.tw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
}


def clean_price(text):
    if not text:
        return None

    text = text.replace(",", "")
    match = re.search(r"\$?\s*(\d+)", text)

    if not match:
        return None

    return int(match.group(1))


def add_product(products, store, name, original, sale, url):

    if not name or not original or not sale:
        return

    if original <= 0 or sale <= 0:
        return

    if sale >= original:
        return

    rate = sale / original

    if rate > MAX_DISCOUNT_RATE:
        return

    # 排除條件式優惠
    bad_words = [
        "買2件",
        "買二件",
        "第二件",
        "第2件",
        "買一送一",
        "買1送1",
        "加價購",
        "任選",
        "任2",
        "任3",
        "任4",
        "組合價"
    ]

    for word in bad_words:
        if word in name:
            return

    products.append({
        "store": store,
        "name": name.strip(),
        "original": original,
        "sale": sale,
        "rate": round(rate, 4),
        "discount": round(rate * 10, 1),
        "save": original - sale,
        "url": url
    })


def scrape_watsons(products):

    print("")
    print("========================")
    print("開始掃描屈臣氏")
    print("========================")

    session = requests.Session()
    session.headers.update(HEADERS)

    page = 0
    max_pages = 1000

    while page < max_pages:

        url = f"{WATSONS_URL}?page={page}"

        print("")
        print("掃描第", page + 1, "頁")
        print(url)

        try:

            response = session.get(url, timeout=30)

            print("HTTP:", response.status_code)

            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.text, "html.parser")

            # 找商品連結
            product_links = []

            for a in soup.find_all("a", href=True):

                href = a.get("href", "")

                # Watsons 商品網址通常包含 /p/
                if "/p/" not in href:
                    continue

                full_url = urljoin(WATSONS_BASE, href)

                if full_url not in product_links:
                    product_links.append(full_url)

            print("找到商品連結：", len(product_links))

            # 沒商品代表翻到底
            if len(product_links) == 0:
                print("沒有更多商品，停止翻頁")
                break

            found_this_page = 0

            for product_url in product_links:

                # 找對應商品區塊
                product_link = soup.find(
                    "a",
                    href=lambda x:
                    x and product_url.split(WATSONS_BASE)[-1] in x
                )

                if not product_link:
                    continue

                # 往上找商品容器
                container = product_link

                for _ in range(8):

                    if not container:
                        break

                    text = container.get_text(
                        " ",
                        strip=True
                    )

                    # 找到至少兩個價格就停止往上
                    prices = re.findall(
                        r"\$\s*[\d,]+",
                        text
                    )

                    if len(prices) >= 2:
                        break

                    container = container.parent

                if not container:
                    continue

                text = container.get_text(
                    " ",
                    strip=True
                )

                # 排除買多件優惠
                blocked_words = [
                    "買2件",
                    "買二件",
                    "第二件",
                    "第2件",
                    "買一送一",
                    "買1送1",
                    "加價購"
                ]

                blocked = False

                for word in blocked_words:
                    if word in text:
                        blocked = True
                        break

                if blocked:
                    continue

                # 商品名稱
                name = product_link.get_text(
                    " ",
                    strip=True
                )

                if not name:
                    continue

                # 找價格
                price_texts = re.findall(
                    r"\$\s*([\d,]+)",
                    text
                )

                prices = []

                for p in price_texts:

                    value = clean_price(p)

                    if value and value not in prices:
                        prices.append(value)

                if len(prices) < 2:
                    continue

                # Watsons 商品卡通常：
                # 售價較低
                # 原價較高
                sale = min(prices)
                original = max(prices)

                before = len(products)

                add_product(
                    products,
                    "屈臣氏",
                    name,
                    original,
                    sale,
                    product_url
                )

                if len(products) > before:

                    found_this_page += 1

                    print(
                        "★",
                        name[:35],
                        original,
                        "→",
                        sale
                    )

            print(
                "本頁找到5折以下：",
                found_this_page
            )

            page += 1

            # 避免對網站造成太密集請求
            time.sleep(1)

        except Exception as e:

            print(
                "頁面讀取失敗：",
                e
            )

            break


def remove_duplicates(products):

    unique = {}

    for product in products:

        key = (
            product["store"],
            product["url"]
        )

        unique[key] = product

    return list(unique.values())


def main():

    products = []

    scrape_watsons(products)

    products = remove_duplicates(products)

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
    print("========================")
    print("完成")
    print(
        "5折以下商品：",
        len(products),
        "個"
    )
    print("========================")


if __name__ == "__main__":
    main()
