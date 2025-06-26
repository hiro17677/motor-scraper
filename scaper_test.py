import os
import json
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

# 創建目錄
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# 初始化資料夾
BASE_DIR = "data"
RESULTS_DIR = os.path.join(BASE_DIR, "results")
PROCESSED_PAGES_FILE = os.path.join(BASE_DIR, "processed_pages.json")
create_directory(BASE_DIR)
create_directory(RESULTS_DIR)

# 初始化已處理頁面記錄
if not os.path.exists(PROCESSED_PAGES_FILE):
    with open(PROCESSED_PAGES_FILE, "w") as file:
        json.dump([], file)

# 加載已處理的頁面
def load_processed_pages():
    with open(PROCESSED_PAGES_FILE, "r") as file:
        return json.load(file)

# 保存已處理的頁面
def save_processed_page(url):
    processed_pages = load_processed_pages()
    processed_pages.append(url)
    with open(PROCESSED_PAGES_FILE, "w") as file:
        json.dump(processed_pages, file)

# 品牌與蝦皮代號對應表
BRAND_TO_SHOPEE_CODE = {
    "光陽": "1095314",
    "三陽": "1107843",
    "山葉": "1802940",
    "睿能": "1091869",
    "PGO": "1101057",
    "哈特佛": "1089745",
    "台鈴": "1147069",
    "本田": "1146583",
    "宏佳騰": "1082956",
}

# 品牌與露天商品編號對應表
BRAND_TO_RUTEN_CODE = {
    "光陽": "0019000200020001",
    "PGO": "0019000200020002",
    "台鈴": "0019000200020003",
    "三陽": "0019000200020004",
    "本田": "0019000200020008",
    "偉士牌": "0019000200020005",
    "山葉": "0019000200020006",
    "宏佳騰": "0019000200020009",
}

# 根據品牌名稱生成蝦皮代號
def get_shopee_code(brand):
    return BRAND_TO_SHOPEE_CODE.get(brand, "999999")

# 根據品牌名稱生成露天商品編號
def get_ruten_code(brand):
    return BRAND_TO_RUTEN_CODE.get(brand, "9999999999999999")

# 針對不同店別處理車況
def extract_vehicle_condition_mileage_and_images(soup, location):
    condition = "無詳細描述"
    mileage = "未知"
    images = []

    # 找到描述的 div
    description_div = soup.select_one('div.product-description')
    if description_div:
        text = description_div.get_text(separator="\n", strip=True)

        # 抓里程數
        mileage_match = re.search(r"[◎◉]\s*(?:行駛里程|里程數)\s*[:：]?\s*([\dXx,]+\s*(?:km|公里))",text)
        if mileage_match:
            mileage = mileage_match.group(1).strip()

        # 依據店別來處理車況
        if "中和" in location:
            # 中和店 - 固定文字
            condition = "交車前檢查燈系、輪胎、電池壽命。"
        elif "桃園" in location:
            # 桃園店 - 只抓「◎ 車輛狀況」那段 & 下方改裝資訊
            condition_parts = []
            all_p = description_div.select('p')
            start_collecting = False
            for p_tag in all_p:
                line = p_tag.get_text(strip=True)
                # 從出現「車輛狀況」這行開始收集
                if "車輛狀況" in line:
                    start_collecting = True
                if start_collecting:
                    condition_parts.append(line)
            if condition_parts:
                # 將收集到的內容串起來
                condition = " ".join(condition_parts)

    # 只抓「主圖」(不抓描述區圖片)
    media_list = soup.select('.product__media-list img')
    for img in media_list:
        if 'src' in img.attrs:
            images.append(img['src'])

    # 去重
    images = list(set(images))

    return condition, mileage, images

# 提取車輛詳細資料
def extract_vehicle_data(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"無法訪問網頁：{url}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    try:
        # 抓標題
        product_title_element = soup.select_one('h1.product__title')
        if not product_title_element:
            raise ValueError("未找到車輛名稱標題")

        product_title = product_title_element.text.strip()
        match = re.search(r"【(.+?)】(\d{4})(\s*[\w]+)?\s+([\w\s\-\.\+\(\)\|]+)\s+(#\d+)", product_title)
        if not match:
            with open("invalid_titles.txt", "a", encoding="utf-8") as f:
                f.write(f"URL: {url}, Title: {product_title}\n")
            raise ValueError(f"車輛名稱格式不符: {product_title}")

        location, year, brand, model, tag = match.groups()

        # 取得蝦皮代號 & 露天商品編號
        shopee_code = get_shopee_code(brand.strip())
        ruten_code = get_ruten_code(brand.strip())

        # 取得車況、里程和圖片
        condition, mileage, images = extract_vehicle_condition_mileage_and_images(soup, location)

        # 價格 - 保留完整金額(去掉非數字)
        price_text = soup.select_one('span.price-item.price-item--regular .money').text.strip()
        raw_price = re.sub(r"[^\d]", "", price_text)  # 去除非數字字符
        price = str(int(raw_price))  # 不做 // 100，直接保留

        return {
            "location": location,
            "year": year,
            "brand": brand.strip() if brand else "未知",
            "shopee_code": shopee_code,
            "ruten_code": ruten_code,
            "model": model.strip(),
            "tag": tag.strip(),
            "condition": condition,
            "mileage": mileage,
            "images": images,
            "price": price,
        }
    except Exception as e:
        print(f"解析失敗：{url}, 錯誤：{e}")
        return None

# 保存數據到 JSON
def save_to_json(data, file_path):
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)

# 保存數據到 Excel
def save_to_excel(data, file_path):
    rows = []

    for item in data:
        base_info = {
            "地點": item["location"],
            "年份": item["year"],
            "品牌": item["brand"],
            "蝦皮代號": item["shopee_code"],
            "露天商品編號": item["ruten_code"],
            "車型": item["model"],
            "標籤": item["tag"],
            "車況": item["condition"],
            "里程": item["mileage"],
            "價格": item["price"],
        }

        # 添加圖片連結
        for idx, img in enumerate(item.get("images", [])):
            base_info[f"圖片{idx + 1}"] = img

        rows.append(base_info)

    df = pd.DataFrame(rows)
    df.to_excel(file_path, index=False, engine="openpyxl")
    print(f"數據已保存到 Excel：{file_path}")

def main():
    """
    此版本示範「分別測試 2 個地區、各 5 台車」，共 10 個商品頁 URL。
    以下 URL 皆為範例，需自行替換為實際商品頁連結。
    """
    # 中和店 5 台 (示範)
    czh_urls = [
        "https://shop.2motor.tw/collections/2motor123/products/-%E6%96%B0%E5%8C%97%E4%B8%AD%E5%92%8C%E5%BA%97-2021-%E5%B1%B1%E8%91%89-drg-158-abs-3921",
        "https://shop.2motor.tw/collections/2motor123/products/-%E6%96%B0%E5%8C%97%E4%B8%AD%E5%92%8C%E5%BA%97-2019-%E5%B1%B1%E8%91%89-smax-155-abs-2818",
        "https://shop.2motor.tw/collections/2motor123/products/-%E6%96%B0%E5%8C%97%E4%B8%AD%E5%92%8C%E5%BA%97-2019-%E7%9D%BF%E8%83%BD-gogoro-2-rumbler-5596-1",
        "https://shop.2motor.tw/collections/2motor123/products/-%E6%96%B0%E5%8C%97%E4%B8%AD%E5%92%8C%E5%BA%97-2017-%E5%85%89%E9%99%BD-%E9%9B%B7%E9%9C%86s150-racings-150-8002",
        "https://shop.2motor.tw/collections/2motor123/products/-%E6%96%B0%E5%8C%97%E4%B8%AD%E5%92%8C%E5%BA%97-2021-%E5%B1%B1%E8%91%89-smax-155-abs-8737",
    ]
    # 桃園店 5 台 (示範)
    tyn_urls = [
        "https://shop.2motor.tw/collections/2motor178/products/-%E6%A1%83%E5%9C%92%E4%B8%AD%E5%A3%A2%E5%BA%97-2021-%E5%B1%B1%E8%91%89-force-155-3570",
        "https://shop.2motor.tw/collections/2motor178/products/-%E6%A1%83%E5%9C%92%E4%B8%AD%E5%A3%A2%E5%BA%97-2014-pgo-j-bubu-115-282",
        "https://shop.2motor.tw/collections/2motor178/products/-%E6%A1%83%E5%9C%92%E4%B8%AD%E5%A3%A2%E5%BA%97-2023-%E5%85%89%E9%99%BD-krv-moto-180-7019",
        "https://shop.2motor.tw/collections/2motor178/products/-%E6%A1%83%E5%9C%92%E4%B8%AD%E5%A3%A2%E5%BA%97-2024%E4%B8%89%E9%99%BD-mmbcu-158-7688",
        "https://shop.2motor.tw/collections/2motor178/products/-%E6%A1%83%E5%9C%92%E4%B8%AD%E5%A3%A2%E5%BA%97-2009-%E4%B8%89%E9%99%BD-gr125-659",
    ]

    test_urls = czh_urls + tyn_urls

    all_results = []
    processed_pages = load_processed_pages()

    for vehicle_url in test_urls:
        # 判斷是否已處理
        if vehicle_url not in processed_pages:
            print(f"處理測試車輛：{vehicle_url}")
            vehicle_data = extract_vehicle_data(vehicle_url)
            if vehicle_data:
                all_results.append(vehicle_data)
                save_processed_page(vehicle_url)
            else:
                print(f"解析失敗：{vehicle_url}")
        else:
            print(f"已跳過已處理的車輛：{vehicle_url}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = os.path.join(RESULTS_DIR, f"test_progress_{timestamp}.json")
    excel_file = os.path.join(RESULTS_DIR, f"test_progress_{timestamp}.xlsx")

    save_to_json(all_results, json_file)
    save_to_excel(all_results, excel_file)

    print(f"JSON 測試檔已保存：{json_file}")
    print(f"Excel 測試檔已保存：{excel_file}")

if __name__ == "__main__":
    main()

# ----------------------------
# [紀錄點] 測試版：
# 1) 僅保留主圖
# 2) 中和店 -> 固定車況
# 3) 桃園店 -> 抓「◎ 車輛狀況」段落
# 4) 測試 2 個地區 x 各 5 台車
# ----------------------------
