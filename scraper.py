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
        mileage_match = re.search(r"[◎◉]\s*(?:行駛里程|里程數)\s*[:：]?\s*([\dXx,]+\s*(?:km|公里))", text)
        if mileage_match:
            mileage = mileage_match.group(1).strip()

        # 依據店別來處理車況
        if "中和" in location:
            # 中和店 - 固定文字
            condition = "交車前檢查燈系、輪胎、電池壽命。"
        elif "桃園" in location or "新竹" in location:
            # 桃園店 & 新竹店 - 只抓「◎ 車輛狀況」那段 & 下方改裝資訊
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

    return condition, mileage, images



    # 只抓「主圖」(不抓描述區圖片)
    media_list = soup.select('.product__media-list img')
    for img in media_list:
        if 'src' in img.attrs:
            images.append(img['src'])

    return condition, mileage, images

# 提取車輛連結
def extract_vehicle_links(directory_url):
    response = requests.get(directory_url)
    if response.status_code != 200:
        print(f"無法訪問目錄頁面：{directory_url}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.select('a.full-unstyled-link')
    vehicle_urls = [requests.compat.urljoin(directory_url, link['href']) for link in links]
    return vehicle_urls

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
            # 記錄錯誤，並返回 None
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

# 處理車輛目錄
def process_directory(directory_url):
    vehicle_urls = extract_vehicle_links(directory_url)
    processed_pages = load_processed_pages()
    results = []

    for vehicle_url in vehicle_urls:
        if vehicle_url not in processed_pages:
            print(f"處理車輛：{vehicle_url}")
            vehicle_data = extract_vehicle_data(vehicle_url)
            if vehicle_data:
                results.append(vehicle_data)
                save_processed_page(vehicle_url)
            else:
                print(f"解析失敗：{vehicle_url}")
        else:
            print(f"已跳過已處理的車輛：{vehicle_url}")
    return results

def main():
    """
    此版本改為只抓取以下 5 個分頁：
    1) https://shop.2motor.tw/collections/2motor123
    2) https://shop.2motor.tw/collections/2motor123?limit=50&page=2&sort=position%2Bdesc
    3) https://shop.2motor.tw/collections/2motor123?limit=50&page=3&sort=position%2Bdesc
    4) https://shop.2motor.tw/collections/2motor178
    5) https://shop.2motor.tw/collections/2motor178?limit=50&page=2&sort=position%2Bdesc
    """
    directory_urls = [
        "https://shop.2motor.tw/collections/2motor321"
    ]

    all_results = []

    print("開始處理指定的分頁列表")
    for directory_url in directory_urls:
        results = process_directory(directory_url)
        all_results.extend(results)

    # 生成檔名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = os.path.join(RESULTS_DIR, f"progress_{timestamp}.json")
    excel_file = os.path.join(RESULTS_DIR, f"progress_{timestamp}.xlsx")

    # 存檔
    save_to_json(all_results, json_file)
    save_to_excel(all_results, excel_file)

    print(f"JSON 檔案已保存：{json_file}")
    print(f"Excel 檔案已保存：{excel_file}")

if __name__ == "__main__":
    main()

# --------------------------------------------------
# [紀錄點]：
# 1) 已移除「各店別各五台商品」的測試
# 2) 恢復為 5 個分頁 (3 個中和 + 2 個桃園)
# 3) 僅保留主圖, 中和店固定車況, 桃園店擷取「車輛狀況」下文, 價格保留完整
# --------------------------------------------------
