#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime
import glob

# =============================================================================
# 1. 爬蟲相關：抓取二手機車資料、儲存 JSON 與原始格式 Excel
# =============================================================================

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# 資料夾設定
BASE_DIR = "data"
RESULTS_DIR = os.path.join(BASE_DIR, "results")
PROCESSED_PAGES_FILE = os.path.join(BASE_DIR, "processed_pages.json")
create_directory(BASE_DIR)
create_directory(RESULTS_DIR)

# 初始化已處理頁面記錄檔
if not os.path.exists(PROCESSED_PAGES_FILE):
    with open(PROCESSED_PAGES_FILE, "w", encoding="utf-8") as file:
        json.dump([], file)

def load_processed_pages():
    with open(PROCESSED_PAGES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_processed_page(url):
    processed_pages = load_processed_pages()
    processed_pages.append(url)
    with open(PROCESSED_PAGES_FILE, "w", encoding="utf-8") as file:
        json.dump(processed_pages, file)

# 品牌與代號對應設定
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

def get_shopee_code(brand):
    return BRAND_TO_SHOPEE_CODE.get(brand, "999999")

def get_ruten_code(brand):
    return BRAND_TO_RUTEN_CODE.get(brand, "9999999999999999")

# 修改後的抓取里程與車況的函式（所有店家統一）
def extract_vehicle_condition_mileage_and_images(soup, location):
    # 固定回傳的車輛狀況描述（供後續描述中使用，實際描述內容由轉換時組合）
    condition = "檢查和更換耗材，確保車輛運作順暢"
    mileage = "未知"
    images = []

    # 取得描述區塊 (以 class "product-description" 為依據)
    description_div = soup.select_one('div.product-description')
    if description_div:
        text = description_div.get_text(separator=" ", strip=True)
        # 正則：匹配「里程」或「里程數」，可有冒號及「約」字，再抓取數字、逗號與 x/X
        mileage_match = re.search(r"里程(?:數)?\s*[:：]?\s*約?\s*([\d,xX]+)\s*(?:km|公里)", text)
        if mileage_match:
            mileage = mileage_match.group(1).strip() + " km"

    # 只抓取主圖（非描述區的圖片）
    media_list = soup.select('.product__media-list img')
    for img in media_list:
        if 'src' in img.attrs:
            images.append(img['src'])
    
    return condition, mileage, images

def extract_vehicle_links(directory_url):
    response = requests.get(directory_url)
    if response.status_code != 200:
        print(f"無法訪問目錄頁面：{directory_url}")
        return []
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.select('a.full-unstyled-link')
    vehicle_urls = [requests.compat.urljoin(directory_url, link['href']) for link in links]
    return vehicle_urls

def extract_vehicle_data(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"無法訪問網頁：{url}")
        return None
    soup = BeautifulSoup(response.text, 'html.parser')
    try:
        product_title_element = soup.select_one('h1.product__title')
        if not product_title_element:
            raise ValueError("未找到車輛名稱標題")
        product_title = product_title_element.text.strip()
        # 假設標題格式為 【地點】年份 品牌 車型 標籤，請依實際狀況調整正則表達式
        match = re.search(r"【(.+?)】(\d{4})(\s*[\w]+)?\s+([\w\s\-\.\+\(\)\|]+)\s+(#\d+)", product_title)
        if not match:
            with open("invalid_titles.txt", "a", encoding="utf-8") as f:
                f.write(f"URL: {url}, Title: {product_title}\n")
            raise ValueError(f"車輛名稱格式不符: {product_title}")
        location, year, brand, model, tag = match.groups()

        shopee_code = get_shopee_code(brand.strip())
        ruten_code = get_ruten_code(brand.strip())

        condition, mileage, images = extract_vehicle_condition_mileage_and_images(soup, location)

        price_text = soup.select_one('span.price-item.price-item--regular .money').text.strip()
        raw_price = re.sub(r"[^\d]", "", price_text)
        price = str(int(raw_price))

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

def save_to_json(data, file_path):
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)

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
        for idx, img in enumerate(item.get("images", [])):
            base_info[f"圖片{idx + 1}"] = img
        rows.append(base_info)
    df = pd.DataFrame(rows)
    df.to_excel(file_path, index=False, engine="openpyxl")
    print(f"爬蟲資料已保存至 Excel：{file_path}")

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

def crawl_main():
    # 可依實際需求調整分頁 URL
    directory_urls = [
        "https://shop.2motor.tw/collections/2motor321",
        "https://shop.2motor.tw/collections/2motor321?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor123",
        "https://shop.2motor.tw/collections/2motor123?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor123?limit=50&page=3&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor178",
        "https://shop.2motor.tw/collections/2motor178?limit=50&page=2&sort=position%2Bdesc"
    ]
    
    all_results = []
    print("開始處理指定的分頁列表...")
    for url in directory_urls:
        results = process_directory(url)
        all_results.extend(results)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = os.path.join(RESULTS_DIR, f"progress_{timestamp}.json")
    excel_file = os.path.join(RESULTS_DIR, f"progress_{timestamp}.xlsx")
    
    save_to_json(all_results, json_file)
    save_to_excel(all_results, excel_file)
    
    print(f"JSON 檔案已保存：{json_file}")
    print(f"原始格式 Excel 檔案已保存：{excel_file}")
    
    return json_file

# =============================================================================
# 2. JSON 轉換成商品列表格式 Excel（含車輛描述格式調整）
# =============================================================================

def create_product_listing(data):
    formatted_data = []
    for item in data:
        year = item['year']
        mileage = item['mileage']
        computed_price = int(item['price']) // 100
        formatted_price = f"${computed_price:,} 元"
        # 若位置中含有「桃園」，則採用桃園客製化格式，否則使用一般格式
        if "桃園" in item["location"]:
            description = (
                "💰私訊預約賞車，可享專屬優惠\n\n" +
                "車輛狀況\n\n" +
                f"年份: {year}年\n" +
                f"里程: {mileage}\n" +
                "地點: 桃園中壢\n" +
                "剛換全新機油，動力更順、更穩\n\n" +
                "價格 & 付款方案\n\n" +
                f"售價: {computed_price}\n" +
                "可分期 / 可刷卡 / 零頭款輕鬆入手\n\n" +
                "⚠️ 車輛流動快，下手要快\n\n" +
                "📩請先私訊確認車輛是否還在，再安排看車\n\n" +
                "📩私訊或 @748luazt（截圖想看車輛）\n\n" +
                "保障服務\n\n" +
                "買賣履約保證，交易更安心\n" +
                "保證無重大事故 & 無泡水（如有事故會事先說明）\n" +
                "可無卡分期 & 全額貸款，輕鬆入手\n" +
                "車換車補價差，提供線上估價\n" +
                "可協助托運，全台配送"
            )
        else:
            description = (
                "車輛狀況\n\n" +
                f"年份: {year}年\n" +
                f"里程: {mileage}\n" +
                f"地點: {item['location']}\n" +
                "剛換全新機油，動力更順、更穩\n\n" +
                "價格 & 付款方案\n\n" +
                f"售價: {computed_price}\n" +
                "可分期 / 可刷卡 / 零頭款輕鬆入手\n\n" +
                "⚠️ 車輛流動快，下手要快\n\n" +
                "📩請先私訊確認車輛是否還在，再安排看車\n\n" +
                "📩私訊或 @748luazt（截圖想看車輛）\n\n" +
                "保障服務\n\n" +
                "買賣履約保證，交易更安心\n" +
                "保證無重大事故 & 無泡水（如有事故會事先說明）\n" +
                "可無卡分期 & 全額貸款，輕鬆入手\n" +
                "車換車補價差，提供線上估價\n" +
                "可協助托運，全台配送"
            )
        product_name = f"[{item['location']}]{year}年 {item['brand']} {item['model']}{item['tag']}"
        row = {
            "分類": "100755",
            "商品名稱": product_name,
            "商品描述": description,
            "最低購買數量": "1",
            "主商品貨號": "",
            "商品規格識別碼": "",
            "規格名稱 1": "",
            "規格選項 1": "",
            "規格圖片": "",
            "規格名稱 2": "",
            "規格選項 2": "",
            "價格": computed_price,
            "庫存": "1",
            "商品選項貨號": "",
            "新版尺寸表": "",
            "圖片尺寸表": "",
            "GTIN": "",
            "主商品圖片": item['images'][0] if item.get("images") else "",
        }
        for i in range(8):
            image_key = f"商品圖片 {i+1}"
            row[image_key] = item['images'][i] if i < len(item.get("images", [])) else ""
        
        row.update({
            "7-ELEVEN": "",
            "全家": "",
            "萊爾富": "",
            "嘉里快遞": "",
            "較長備貨天數": "",
            "重量": "",
            "長度": "",
            "寬度": "",
            "高度": ""
        })
        formatted_data.append(row)
    return formatted_data

def save_product_listing_excel(data, output_file):
    df = pd.DataFrame(data)
    df.to_excel(output_file, index=False)
    print(f"商品列表 Excel 檔案已建立：{output_file}")

def read_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"找不到檔案: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"JSON 格式錯誤: {file_path}")
        return None
    except Exception as e:
        print(f"讀取檔案時發生錯誤: {str(e)}")
        return None

def convert_json_to_product_listing(json_file):
    print(f"開始轉換 JSON 檔案：{json_file}")
    data = read_json_file(json_file)
    if not data:
        print("無法讀取資料，轉換中止。")
        return
    formatted_data = create_product_listing(data)
    output_file = json_file.replace('.json', '_product.xlsx')
    save_product_listing_excel(formatted_data, output_file)
    print("商品列表轉換完成！")

# =============================================================================
# 3. 圖片下載：將 JSON 中的圖片下載到指定資料夾
# =============================================================================

# 設定圖片儲存根資料夾（依需求調整路徑）
BASE_IMAGE_FOLDER = r"C:\Users\hiro1\OneDrive\文件\二手車上架\車輛圖片區"

def check_file_exists(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"檔案不存在: {file_path}")

def load_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_folder_name(car_data):
    # 依據各欄位組合資料夾名稱，並過濾掉 Windows 不允許的字元
    folder_name = f"{car_data['location'].replace('店', '')}_{car_data['tag']}_{car_data['brand']}_{car_data['model']}_{car_data['mileage'].split(' ')[0]}_{car_data['price']}"
    return ''.join(c for c in folder_name if c not in r"<>:""/\\|?*")

def download_image(url, save_path):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        print(f"成功下載: {url}")
    except Exception as e:
        print(f"下載失敗: {url}, 錯誤: {e}")

def download_images_from_json(json_file):
    check_file_exists(json_file)
    try:
        car_data_list = load_json_file(json_file)
    except json.JSONDecodeError as e:
        print(f"無法解析 JSON 檔案: {e}")
        return
    
    for car_data in car_data_list:
        folder_name = create_folder_name(car_data)
        folder_path = os.path.join(BASE_IMAGE_FOLDER, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        existing_files = set(os.listdir(folder_path))
        for index, image_url in enumerate(car_data.get('images', [])):
            image_extension = image_url.split('.')[-1]
            image_name = f"image_{index + 1}.{image_extension}"
            save_path = os.path.join(folder_path, image_name)
            if image_name not in existing_files:
                download_image(image_url, save_path)
            else:
                print(f"跳過已存在的圖片: {image_name}")
        print(f"所有圖片已儲存至資料夾: {folder_path}")

# =============================================================================
# 4. 產生摘要 Excel：根據 JSON 資料建立額外 Excel 檔案
# =============================================================================

def generate_summary_excel(json_file):
    data = read_json_file(json_file)
    if not data:
        print("無法讀取 JSON 資料，無法產生摘要 Excel。")
        return
    rows = []
    for item in data:
        # 車名+編號： tag 與 model 以空格連接
        car_name_number = f"{item['tag']} {item['model']}"
        # 價格除以 100（整數除法）
        price = int(item["price"]) // 100
        location = item["location"]
        rows.append({
            "車名+編號": car_name_number,
            "價格": price,
            "位置": location
        })
    df = pd.DataFrame(rows)
    summary_excel_file = json_file.replace('.json', '_summary.xlsx')
    df.to_excel(summary_excel_file, index=False)
    print(f"摘要 Excel 檔案已建立：{summary_excel_file}")

# =============================================================================
# 主流程：依序執行爬蟲、商品列表轉換、圖片下載、產生摘要 Excel
# =============================================================================

def main():
    # 1. 執行爬蟲，取得 JSON 檔案路徑
    json_file = crawl_main()
    
    # 2. 將爬蟲產生的 JSON 資料轉換成商品列表格式 Excel
    convert_json_to_product_listing(json_file)
    
    # 3. 根據 JSON 資料下載圖片到指定資料夾
    download_images_from_json(json_file)
    
    # 4. 產生摘要 Excel，內容包含 "車名+編號"、"價格" 與 "位置"
    generate_summary_excel(json_file)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"發生錯誤：{e}")
