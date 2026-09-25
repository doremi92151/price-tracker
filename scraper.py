import json
from datetime import datetime, timezone, timedelta


# =========================================================
# 基本設定
# =========================================================

MAX_DISCOUNT_RATE = 0.50  # 只保留 5 折以下（含 5 折）


# =========================================================
# 商品整理
# =========================================================

def add_product(products, store, name, original, sale, url):
    """
    加入商品。
    只有「特價 <= 原價的 50%」才會被保留。
    """

    try:
        original = int(float(original))
        sale = int(float(sale))
    except (ValueError, TypeError):
        return

    # 排除錯誤價格
    if original <= 0 or sale <= 0:
        return

    if sale >= original:
        return

    rate = sale / original

    # 超過 5 折不要
    if rate > MAX_DISCOUNT_RATE:
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
# 寶雅
# =========================================================

def scrape_poya(products):
    """
    下一步加入寶雅實際抓取程式。
    """
    print("開始檢查寶雅...")


# =========================================================
# 屈臣氏
# =========================================================

def scrape_watsons(products):
    """
    下一步加入屈臣氏實際抓取程式。
    """
    print("開始檢查屈臣氏...")


# =========================================================
# 康是美
# =========================================================

def scrape_cosmed(products):
    """
    下一步加入康是美實際抓取程式。
    """
    print("開始檢查康是美...")


# =========================================================
# 主程式
# =========================================================

def main():

    products = []

    scrape_poya(products)
    scrape_watsons(products)
    scrape_cosmed(products)

    # 折扣越低排越前面
    products.sort(key=lambda x: x["rate"])

    # 台灣時間
    taiwan_timezone = timezone(timedelta(hours=8))
    now = datetime.now(taiwan_timezone)

    output = {
        "updated": now.strftime("%Y-%m-%d %H:%M"),
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

    print("-------------------------")
    print(f"完成，共找到 {len(products)} 個 5 折以下商品")
    print("-------------------------")


if __name__ == "__main__":
    main()
