#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

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
PROCESSED_PAGES_FILE_2 = os.path.join(BASE_DIR, "processed_pages_product2.json")
create_directory(BASE_DIR)
create_directory(RESULTS_DIR)

# 初始化已處理頁面記錄檔
if not os.path.exists(PROCESSED_PAGES_FILE):
    with open(PROCESSED_PAGES_FILE, "w", encoding="utf-8") as file:
        json.dump([], file)
if not os.path.exists(PROCESSED_PAGES_FILE_2):
    with open(PROCESSED_PAGES_FILE_2, "w", encoding="utf-8") as file:
        json.dump([], file)

def load_processed_pages():
    with open(PROCESSED_PAGES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def load_processed_pages_2():
    with open(PROCESSED_PAGES_FILE_2, "r", encoding="utf-8") as file:
        return json.load(file)

def save_processed_page(url):
    processed_pages = load_processed_pages()
    processed_pages.append(url)
    with open(PROCESSED_PAGES_FILE, "w", encoding="utf-8") as file:
        json.dump(processed_pages, file)

def save_processed_page_2(url):
    processed_pages = load_processed_pages_2()
    processed_pages.append(url)
    with open(PROCESSED_PAGES_FILE_2, "w", encoding="utf-8") as file:
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
    condition = "檢查和更換耗材，確保車輛運作順暢"
    mileage = "未知"
    images = []
    warranty = False  # 預設無保固
    
    # 檢查標題是否包含「未整理保固」
    title = soup.select_one('h1.product__title')
    if title and "未整理保固" in title.text:
        warranty = False
        return condition, mileage, images, warranty

    description_div = soup.select_one('div.product-description')
    if description_div:
        text = description_div.get_text(separator=" ", strip=True)
        
        # 檢查是否有保固
        warranty_patterns = [
            r"保固項目[：:]\s*(?:引擎|消耗品)\s*\d+\s*個月",
            r"保固[：:]\s*(?:引擎|消耗品)\s*\d+\s*個月",
            r"(?:引擎|消耗品)(?:提供)?\s*\d+\s*個月保固",
            r"原廠保固中",
        ]
        
        no_warranty_patterns = [
            r"不提供保固",
            r"恕不提供保固服務",
            r"現況[售販](?:售|出).*不提供保固",
            r"無(?:附)?保固",
            r"優惠價.*不提供保固",
            r"未整理保固",
        ]
        
        # 檢查里程數
        mileage_match = re.search(r"里程(?:數)?\s*[:：]?\s*約?\s*([\d,xX]+)\s*(?:km|公里)", text)
        if mileage_match:
            mileage = mileage_match.group(1).strip() + " km"
        
        # 檢查是否符合有保固的模式
        for pattern in warranty_patterns:
            if re.search(pattern, text):
                warranty = True
                break
                
        # 如果沒找到有保固的模式，檢查是否明確說明無保固
        if not warranty:
            for pattern in no_warranty_patterns:
                if re.search(pattern, text):
                    warranty = False
                    break

    # 抓取圖片
    media_list = soup.select('.product__media-list img')
    for img in media_list:
        if 'src' in img.attrs:
            images.append(img['src'])
    
    return condition, mileage, images, warranty

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
        
        # 定義品牌列表
        brands = ['三陽', '光陽', '山葉', '台鈴', '宏佳騰', 'PGO', 'SUZUKI', 'YAMAHA', 'SYM', 'KYMCO', 'AEON', '偉士牌', '本田', '鈴木', 'YAMAHA', 'SYM', 'KYMCO', 'AEON', '川崎', 'GOGORO']
        
        # 更新的正則表達式模式，放寬品牌匹配條件
        patterns = [
            # 完整年份格式，使用更寬鬆的品牌匹配
            r"【(.+?)】\s*(\d{4})\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*(?:循環檔|國際檔|ABS|TCS)?\s*#(\d+)",
            # 簡短年份格式，使用更寬鬆的品牌匹配
            r"【(.+?)】\s*(\d{2})年\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*(?:循環檔|國際檔|ABS|TCS)?\s*#(\d+)",
            # 特殊格式，使用更寬鬆的品牌匹配
            r"【(.+?)】\s*\d{2,4}(?:年)?\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*#(\d+)",
            # 新增：直接年份格式（無【】括號）
            r"(\d{4})\s+([\w\u4e00-\u9fff\(\)]+)\s+([\w\u4e00-\u9fff\s\.\(\)\/\-\+]+?)\s*#(\d+)",
            # 新增：直接年份格式（無【】括號，簡短年份）
            r"(\d{2})年\s+([\w\u4e00-\u9fff\(\)]+)\s+([\w\u4e00-\u9fff\s\.\(\)\/\-\+]+?)\s*#(\d+)",
            # 新增：處理中文括號
            r"【(.+?)】\s*(\d{4})\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*（(.+?)）\s*#(\d+)",
            # 新增：處理特殊標記
            r"【(.+?)】\s*(\d{4})\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*([\w\u4e00-\u9fff]+)\s*#(\d+)",
            # 新增：處理無年份格式
            r"【(.+?)】\s*([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*#(\d+)"
        ]
        
        match = None
        for pattern in patterns:
            match = re.search(pattern, product_title)
            if match:
                break
                
        if not match:
            with open("invalid_titles.txt", "a", encoding="utf-8") as f:
                f.write(f"URL: {url}\nTitle: {product_title}\n\n")
            raise ValueError(f"車輛名稱格式不符: {product_title}")
            
        # 處理不同的匹配結果
        if len(match.groups()) == 5:  # 完整格式或簡短年份格式
            location, year, brand, model, tag = match.groups()
            # 處理簡短年份 (例如 "23" -> "2023")
            if len(year) == 2:
                year = "20" + year
        elif len(match.groups()) == 4:  # 特殊格式
            location, brand, model, tag = match.groups()
            # 從標題中提取年份
            year_match = re.search(r"(\d{2,4})年?", product_title)
            year = year_match.group(1) if year_match else "0000"
            if len(year) == 2:
                year = "20" + year
        elif len(match.groups()) == 3:  # 無年份格式
            location, brand_model, tag = match.groups()
            # 從品牌和型號中分離品牌
            brand = None
            for known_brand in brands:
                if known_brand in brand_model:
                    brand = known_brand
                    model = brand_model.replace(known_brand, "").strip()
                    break
            if not brand:
                brand = brand_model.split()[0]  # 取第一個詞作為品牌
                model = " ".join(brand_model.split()[1:])  # 其餘部分作為型號
            year = "0000"  # 無年份時設為0000

        # 品牌名稱標準化
        brand = brand.strip()
        
        # 檢查品牌是否在預定義列表中
        if brand not in brands:
            # 嘗試從型號中提取品牌
            for known_brand in brands:
                if known_brand in model:
                    brand = known_brand
                    break
            # 如果仍然找不到品牌，記錄到錯誤日誌
            if brand not in brands:
                with open("unknown_brands.txt", "a", encoding="utf-8") as f:
                    f.write(f"URL: {url}\nTitle: {product_title}\nBrand: {brand}\n\n")
        
        # 清理型號中的特殊字元但保留連字符
        model = re.sub(r'(?<![\w-])[\W_]+(?![\w-])', ' ', model).strip()
        
        # 確保 tag 前面加上 "#" 符號
        tag = f"#{tag}" if not tag.startswith("#") else tag
        
        shopee_code = get_shopee_code(brand)
        ruten_code = get_ruten_code(brand)

        condition, mileage, images, warranty = extract_vehicle_condition_mileage_and_images(soup, location)

        price_element = soup.select_one('span.price-item.price-item--regular .money')
        price = price_element.get('data-ori-price', '').replace(',', '').split('.')[0]

        return {
            "location": location,
            "year": year,
            "brand": brand,
            "shopee_code": shopee_code,
            "ruten_code": ruten_code,
            "model": model,
            "tag": tag,
            "condition": condition,
            "mileage": mileage,
            "images": images,
            "price": price,
            "warranty": warranty,
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

def process_directory(directory_url, load_func=load_processed_pages, save_func=save_processed_page):
    print(f"\n處理目錄: {directory_url}")
    vehicle_urls = extract_vehicle_links(directory_url)
    processed_pages = load_func()
    results = []
    for vehicle_url in vehicle_urls:
        if vehicle_url not in processed_pages:
            print(f"處理車輛：{vehicle_url}")
            vehicle_data = extract_vehicle_data(vehicle_url)
            if vehicle_data:
                results.append(vehicle_data)
                save_func(vehicle_url)
            else:
                print(f"解析失敗：{vehicle_url}")
        else:
            print(f"已跳過已處理的車輛：{vehicle_url}")
    return results

def crawl_main():
    # 可依實際需求調整分頁 URL
    directory_urls = [
        "https://shop.2motor.tw/collections/2motor321",
        "https://shop.2motor.tw/collections/2motor123",
        "https://shop.2motor.tw/collections/2motor178",
        "https://shop.2motor.tw/collections/2motor700",
        "https://shop.2motor.tw/collections/2motor988",
        "https://shop.2motor.tw/collections/2motor168",
        "https://shop.2motor.tw/collections/2motor111",
        "https://shop.2motor.tw/collections/2motor999",
        "https://shop.2motor.tw/collections/2motor888",
        "https://shop.2motor.tw/collections/2motor666",
        "https://shop.2motor.tw/collections/2motor888?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor666?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor123?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor700?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor988?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor178?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor321?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor168?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor999?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor168?limit=50&page=3&sort=position%2Bdesc"       
    ]
    
    all_results = []
    error_logs = []  # 用於記錄錯誤
    
    print("開始處理指定的分頁列表...")
    for url in directory_urls:
        try:
            results = process_directory(url)
            all_results.extend(results)
            print(f"從 {url} 成功處理 {len(results)} 台車輛")
        except Exception as e:
            error_msg = f"處理 {url} 時發生錯誤: {str(e)}"
            print(error_msg)
            error_logs.append(error_msg)
    
    if error_logs:
        print("\n發現以下錯誤:")
        for error in error_logs:
            print(f"- {error}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    error_file = os.path.join(RESULTS_DIR, f"errors_{timestamp}.txt")
    
    # 保存錯誤日誌
    if error_logs:
        with open(error_file, "w", encoding="utf-8") as f:
            f.write("\n".join(error_logs))
        print(f"錯誤日誌已保存：{error_file}")
    
    print(f"\n處理完成:")
    print(f"總車輛數: {len(all_results)}")

    return all_results, timestamp

def crawl_main_product2():
    # 另行設定的分頁 URL 列表，可依需求調整
    directory_urls = [
        "https://shop.2motor.tw/collections/2motor178",
    ]

    all_results = []
    error_logs = []

    print("開始處理 product2 分頁列表...")
    for url in directory_urls:
        try:
            results = process_directory(url, load_processed_pages_2, save_processed_page_2)
            all_results.extend(results)
            print(f"從 {url} 成功處理 {len(results)} 台車輛")
        except Exception as e:
            error_msg = f"處理 {url} 時發生錯誤: {str(e)}"
            print(error_msg)
            error_logs.append(error_msg)

    if error_logs:
        print("\n發現以下錯誤:")
        for error in error_logs:
            print(f"- {error}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    error_file = os.path.join(RESULTS_DIR, f"errors2_{timestamp}.txt")

    if error_logs:
        with open(error_file, "w", encoding="utf-8") as f:
            f.write("\n".join(error_logs))
        print(f"錯誤日誌已保存：{error_file}")

    print(f"\nproduct2 處理完成:")
    print(f"總車輛數: {len(all_results)}")

    return all_results, timestamp

# =============================================================================
# 2. JSON 轉換成商品列表格式 Excel（含車輛描述格式調整）
# =============================================================================

def create_product_listing(data):
    formatted_data = []
    for item in data:
        year = item['year']
        mileage = item['mileage']
        computed_price = item['price']  # 直接使用原始價格
        
        # 根據保固狀態選擇描述文字
        if item.get('warranty', False):
            condition_text = ("車輛交車前預計做保養及耗材更換，"
                            "引擎有提供3~12月保固，消耗品1個月保固。")
        else:
            condition_text = ("本車採現況販售，無附保固，但我們會針對部分消耗品進行基本檢查與更換，"
                            "讓車況更穩定")

        # 修改描述文字
        if "桃園" in item["location"]:
            description = (
                "💰私訊預約賞車，可享專屬優惠\n\n"
                "車輛狀況\n\n"
                f"年份: {year}年\n"
                f"里程: {mileage}\n"
                "地點: 桃園中壢\n"
                f"{condition_text}\n\n"
                f"售價: {computed_price}\n"
                "⚠️ 車輛流動快，下手要快\n\n"
                "📩請先蝦皮聊聊確認車輛是否還在\n\n"
                "保障服務\n\n"
                "買賣履約保證，交易更安心\n"
                "無重大事故 & 無泡水（重大事故會事先說明）\n"
                "車換車補價差，提供線上估價\n"
            )
        else:
            description = (
                "車輛狀況\n\n"
                f"年份: {year}年\n"
                f"里程: {mileage}\n"
                f"地點: {item['location']}\n"
                f"{condition_text}\n\n"
                f"售價: {computed_price}\n"
                "⚠️ 車輛流動快，下手要快\n\n"
                "📩請先蝦皮聊聊確認車輛是否還在\n\n"
                "保障服務\n\n"
                "買賣履約保證，交易更安心\n"
                "無重大事故 & 無泡水（重大事故會事先說明）\n"
                "車換車補價差，提供線上估價\n"
            )
        product_name = f"[{item['location']}]{year}年 {item['model']}{item['tag']}"
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

def convert_data_to_product_listing(data, timestamp, suffix="product"):
    if not data:
        print("無法讀取資料，轉換中止。")
        return
    formatted_data = create_product_listing(data)
    output_file = os.path.join(RESULTS_DIR, f"progress_{timestamp}_{suffix}.xlsx")
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
    # 組合完整資料夾名稱
    folder_name = f"{car_data['model']} |{car_data['location']}| {car_data['tag']}"
    # 過濾掉 Windows 不允許的字元
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

def download_images_from_data(car_data_list):
    
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

def generate_fb_excel_from_data(data, timestamp):
    if not data:
        print("無法讀取 JSON 資料，無法產生 FB Excel。")
        return

    rows = []
    brands = ['三陽', '光陽', '山葉', '台鈴', '宏佳騰', 'PGO', 'SUZUKI', 'YAMAHA', 'SYM', 'KYMCO', 'AEON', '偉士牌', '本田', '鈴木', 'YAMAHA', 'SYM', 'KYMCO', 'AEON', '川崎', 'GOGORO']
    for item in data:
        # 組合車名和標籤
        model_with_brand = item['model']
        extracted_brand = None
        extracted_model = model_with_brand

        for known_brand in brands:
            if known_brand.lower() in model_with_brand.lower():
                extracted_brand = known_brand
                extracted_model = model_with_brand.lower().replace(known_brand.lower(), "").strip()
                break
        if not extracted_brand:
            extracted_brand = "未知" # 或者根據你的需求設定

        car_name_tag = f"{extracted_model.upper()}  |{item['location']}|  {item['tag']}"
        # 直接使用原始價格
        computed_price = item["price"]
        year = item['year']
        mileage = item['mileage']

        # 根據保固狀態選擇描述文字
        if item.get('warranty', False):
            condition_text = ("車輛交車前預計做保養及耗材更換，"
                            "引擎有提供3~12月保固，消耗品1個月保固。")
        else:
            condition_text = ("本車採現況販售，無附保固，但我們會針對部分消耗品進行基本檢查與更換，"
                              "讓車況更穩定")

        # 修改描述文字
        if "桃園" in item["location"]:
            description = (
                "💰私訊預約賞車，可享專屬優惠\n\n"
                f"車輛名稱: {extracted_model}\n\n" # 使用處理後的車型
                f"年份: {year}年\n"
                f"里程: {mileage}\n"
                "地點: 桃園中壢\n"
                f"{condition_text}\n\n"
                "價格 & 付款方案\n\n"
                f"售價: {computed_price}\n"
                "可分期 / 可刷卡 / 零頭款輕鬆入手\n\n"
                "⚠️ 車輛流動快，下手要快\n\n"
                "📩請先私訊確認車輛是否還在\n\n"
                "聯絡方式\n"
                "• Line官方：https://lin.ee/aaZY1C7（截圖想看車輛）\n\n"
                "保障服務\n\n"
                "買賣履約保證，交易更安心\n"
                "無重大事故 & 無泡水（重大事故會事先說明）\n"
                "可無卡分期 & 全額貸款，輕鬆入手\n"
                "車換車補價差，提供線上估價\n"
                "可協助托運，全台配送"
            )
        else:
            description = (
                f"車輛名稱: {extracted_model}\n\n" # 使用處理後的車型
                f"年份: {year}年\n"
                f"里程: {mileage}\n"
                f"地點: {item['location']}\n"
                f"{condition_text}\n\n"
                "價格 & 付款方案\n\n"
                f"售價: {computed_price}\n"
                "可分期 / 可刷卡 / 零頭款輕鬆入手\n\n"
                "⚠️ 車輛流動快，下手要快\n\n"
                "📩請先私訊確認車輛是否還在\n\n"
                "聯絡方式\n"
                "• Line官方：https://lin.ee/aaZY1C7（截圖想看車輛）\n\n"
                "保障服務\n\n"
                "買賣履約保證，交易更安心\n"
                "無重大事故 & 無泡水（重大事故會事先說明）\n"
                "可無卡分期 & 全額貸款，輕鬆入手\n"
                "車換車補價差，提供線上估價\n"
                "可協助托運，全台配送"
            )

        rows.append({
            "地點": item["location"],
            "年分": item["year"],
            "廠牌": extracted_brand, # 使用分離出的品牌
            "車名+標籤": car_name_tag,
            "里程": item["mileage"],
            "價格": computed_price,
            "車況": description
        })

    df = pd.DataFrame(rows)
    fb_excel_file = os.path.join(RESULTS_DIR, f"progress_{timestamp}_FB.xlsx")
    df.to_excel(fb_excel_file, index=False)
    print(f"FB Excel 檔案已建立：{fb_excel_file}")

# =============================================================================
# 主流程：依序執行爬蟲、商品列表轉換、圖片下載、產生 FB Excel
# =============================================================================

def main():
    # 1. 執行爬蟲，取得資料列表與時間戳
    data, timestamp = crawl_main()

    # 2. 轉換成商品列表格式 Excel
    convert_data_to_product_listing(data, timestamp)

    # 3. 根據資料下載圖片到指定資料夾
    download_images_from_data(data)

    # 4. 產生 FB 格式的 Excel
    generate_fb_excel_from_data(data, timestamp)

    # 5. 執行第二組爬蟲並輸出 product2 Excel
    data2, timestamp2 = crawl_main_product2()
    convert_data_to_product_listing(data2, timestamp2, suffix="product2")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"發生錯誤：{e}")
