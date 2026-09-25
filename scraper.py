import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin


# =========================================================
# 設定
# =========================================================

MAX_DISCOUNT_RATE = 0.50

BASE_URL = "https://www.poyabuy.com.tw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
}


# 寶雅主要分類
POYA_CATEGORIES = [
    "https://www.poyabuy.com.tw/v2/official/SalePageCategory/373989",  # 臉部保養
    "https://www.poyabuy.com.tw/v2/official/SalePageCategory/373990",  # 身體保養
    "https://www.poyabuy.com.tw/v2/official/SalePageCategory/374010",  # 個人清潔
    "https://www.poyabuy.com.tw/v2/official/SalePageCategory/569599",  # 清潔美容
    "https://www.poyabuy.com.tw/v2/official/SalePageCategory/566579",  # 臉部清潔卸妝
    "https://www.poyabuy.com.tw/v2/official/SalePageCategory/374096",  # 身體清潔
]


# =========================================================
# 工具
# =========================================================

def clean_price(text):
    if not text:
        return None

    text = text.replace(",", "")

    numbers = re.findall(r"\d+", text)

    if not numbers:
        return None

    try:
        return int(numbers[0])
    except:
        return None


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

    # 排除特殊促銷字樣
    bad_words = [
        "買一送一",
        "第二件",
        "第2件",
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


# =========================================================
# 從分類頁找商品網址
# =========================================================

def get_product_urls():

    session = requests.Session()
    session.headers.update(HEADERS)

    product_urls = set()

    for category_url in POYA_CATEGORIES:

        print("")
        print("掃描分類：")
        print(category_url)

        try:

            response = session.get(
                category_url,
                timeout=30
            )

            print("HTTP:", response.status_code)

            if response.status_code != 200:
                continue

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            # 找所有商品頁連結
            for a in soup.find_all("a", href=True):

                href = a.get("href", "")

                if "/SalePage/Index/" not in href:
                    continue

                full_url = urljoin(
                    BASE_URL,
                    href
                )

                # 清掉 query string
                full_url = full_url.split("?")[0]

                product_urls.add(full_url)

            print(
                "目前累計商品網址：",
                len(product_urls)
            )

        except Exception as e:

            print(
                "分類讀取失敗：",
                e
            )

        time.sleep(1)

    return list(product_urls)


# =========================================================
# 解析商品頁
# =========================================================

def parse_product_page(session, url):

    try:

        response = session.get(
            url,
            timeout=30
        )

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # -----------------------------
        # 商品名稱
        # -----------------------------

        name = None

        og_title = soup.find(
            "meta",
            property="og:title"
        )

        if og_title:
            name = og_title.get("content")

        if not name and soup.title:
            name = soup.title.get_text(
                strip=True
            )

        if not name:
            return None

        # -----------------------------
        # 取得頁面文字
        # -----------------------------

        page_text = soup.get_text(
            " ",
            strip=True
        )

        # 排除特殊促銷
        blocked_words = [
            "加價購商品",
            "下單請選購兩件"
        ]

        for word in blocked_words:
            if word in page_text:
                return None

        # -----------------------------
        # 找 NT$ 價格
        # -----------------------------

        price_matches = re.findall(
            r"NT\$\s*([\d,]+)",
            page_text
        )

        prices = []

        for price in price_matches:

            p = clean_price(price)

            if p and p not in prices:
                prices.append(p)

        if len(prices) < 2:
            return None

        # 寶雅頁面可能出現多個價格
        # 先取合理的最高價當原價
        # 最低價當目前售價

        original = max(prices)
        sale = min(prices)

        if original == sale:
            return None

        return {
            "name": name,
            "original": original,
            "sale": sale,
            "url": url
        }

    except Exception as e:

        print(
            "商品解析失敗：",
            url,
            e
        )

        return None


# =========================================================
# 寶雅
# =========================================================

def scrape_poya(products):

    print("")
    print("========================")
    print("開始掃描寶雅")
    print("========================")

    urls = get_product_urls()

    print("")
    print(
        "共找到",
        len(urls),
        "個商品網址"
    )

    session = requests.Session()
    session.headers.update(HEADERS)

    for index, url in enumerate(urls, 1):

        print(
            f"[{index}/{len(urls)}]",
            url
        )

        item = parse_product_page(
            session,
            url
        )

        if not item:
            continue

        add_product(
            products,
            "寶雅",
            item["name"],
            item["original"],
            item["sale"],
            item["url"]
        )

        time.sleep(0.3)


# =========================================================
# 去除重複
# =========================================================

def remove_duplicates(products):

    unique = {}

    for product in products:

        key = (
            product["store"],
            product["url"]
        )

        unique[key] = product

    return list(unique.values())


# =========================================================
# 主程式
# =========================================================

def main():

    products = []

    scrape_poya(products)

    products = remove_duplicates(
        products
    )

    # 折扣最低排最前面
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
