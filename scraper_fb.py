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
        
        # 定義品牌列表 - 擴充更多可能的品牌名稱
        brands = [
            '三陽', '光陽', '山葉', '台鈴', '宏佳騰', 'PGO', 'SUZUKI', 'YAMAHA', 'SYM', 'KYMCO', 'AEON',
            '哈特佛', '本田', '偉士牌', '睿能', 'GOGORO', 'GGR', 'Kymco', 'Sym', 'Yamaha', 'Suzuki',
            'Honda', 'Vespa', 'Hartford', 'Aeon', 'PGO', '台鈴', '台鈴機車'
        ]
        
        # 更新的正則表達式模式，放寬品牌匹配條件
        patterns = [
            # 完整年份格式，使用更寬鬆的品牌匹配
            r"【(.+?)】\s*(\d{4})\s+([\w\u4e00-\u9fff]+(?:\s*[\w\u4e00-\u9fff\.]+)*)\s*(?:循環檔|國際檔|ABS|TCS)?\s*#(\d+)",
            # 簡短年份格式，使用更寬鬆的品牌匹配
            r"【(.+?)】\s*(\d{2})年\s+([\w\u4e00-\u9fff]+(?:\s*[\w\u4e00-\u9fff\.]+)*)\s*(?:循環檔|國際檔|ABS|TCS)?\s*#(\d+)",
            # 特殊格式，使用更寬鬆的品牌匹配
            r"【(.+?)】\s*\d{2,4}(?:年)?\s+([\w\u4e00-\u9fff]+(?:\s*[\w\u4e00-\u9fff\.]+)*)\s*#(\d+)",
            # 新增：直接年份格式（無【】括號）
            r"(\d{4})\s+([\w\u4e00-\u9fff]+)\s+([\w\u4e00-\u9fff\s\.]+?)\s*#(\d+)",
            # 新增：直接年份格式（無【】括號，簡短年份）
            r"(\d{2})年\s+([\w\u4e00-\u9fff]+)\s+([\w\u4e00-\u9fff\s\.]+?)\s*#(\d+)"
        ]
        
        # 添加調試輸出
        print(f"正在處理標題: {product_title}")
        
        match = None
        for pattern in patterns:
            match = re.search(pattern, product_title)
            if match:
                print(f"成功匹配模式: {pattern}")
                print(f"匹配結果: {match.groups()}")
                break
                
        if not match:
            print(f"標題解析失敗: {product_title}")
            with open("invalid_titles.txt", "a", encoding="utf-8") as f:
                f.write(f"URL: {url}\nTitle: {product_title}\n\n")
            return None
            
        # 處理不同的匹配結果
        if len(match.groups()) == 4:  # 完整格式或簡短年份格式
            location, year, model, tag = match.groups()
            # 處理簡短年份 (例如 "23" -> "2023")
            if len(year) == 2:
                year = "20" + year
        else:  # 特殊格式
            location, model, tag = match.groups()
            # 從標題中提取年份
            year_match = re.search(r"(\d{2,4})年?", product_title)
            year = year_match.group(1) if year_match else "0000"
            if len(year) == 2:
                year = "20" + year

        # 品牌名稱標準化
        brand = None
        print(f"提取到的車型: {model}")
        
        # 檢查品牌是否在預定義列表中
        for known_brand in brands:
            if known_brand in model:
                brand = known_brand
                print(f"從車型中找到品牌: {brand}")
                break
        
        # 如果仍然找不到品牌，記錄到錯誤日誌
        if not brand:
            print(f"無法識別品牌: {model}")
            brand = "未知"
            with open("unknown_brands.txt", "a", encoding="utf-8") as f:
                f.write(f"URL: {url}\nTitle: {product_title}\nModel: {model}\n\n")
        
        # 清理型號中的特殊字元但保留連字符和小數點
        model = re.sub(r'(?<![\w\-\.])[\W_]+(?![\w\-\.])', ' ', model).strip()
        
        # 確保 tag 前面加上 "#" 符號
        tag = f"#{tag}" if not tag.startswith("#") else tag

        condition, mileage, images, warranty = extract_vehicle_condition_mileage_and_images(soup, location)

        price_element = soup.select_one('span.price-item.price-item--regular .money')
        price = price_element.get('data-ori-price', '').replace(',', '').split('.')[0]

        return {
            "location": location,
            "year": year,
            "brand": brand,
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

def process_directory(directory_url):
    print(f"\n處理目錄: {directory_url}")
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
        "https://shop.2motor.tw/collections/2motor321?limit=50&page=2&sort=position%2Bdesc"
    ]
    
    all_results = []
    error_logs = []  # 用於記錄錯誤
    
    print("開始處理指定的分頁列表...")
    for url in directory_urls:
        try:
            vehicle_urls = extract_vehicle_links(url)
            for vehicle_url in vehicle_urls:
                vehicle_data = extract_vehicle_data(vehicle_url)
                if vehicle_data:
                    all_results.append(vehicle_data)
            print(f"從 {url} 成功處理 {len(vehicle_urls)} 台車輛")
        except Exception as e:
            error_msg = f"處理 {url} 時發生錯誤: {str(e)}"
            print(error_msg)
            error_logs.append(error_msg)
    
    if error_logs:
        print("\n發現以下錯誤:")
        for error in error_logs:
            print(f"- {error}")
    
    # 儲存 JSON 檔案
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = os.path.join("data/results", f"progress_{timestamp}.json")
    os.makedirs(os.path.dirname(json_file), exist_ok=True)
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)
    
    print(f"\n處理完成:")
    print(f"總車輛數: {len(all_results)}")
    print(f"JSON 檔案已保存：{json_file}")
    
    return json_file

# =============================================================================
# 2. 產生 FB 格式的 Excel
# =============================================================================

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

def generate_fb_excel(json_file):
    data = read_json_file(json_file)
    if not data:
        print("無法讀取 JSON 資料，無法產生 FB Excel。")
        return
        
    rows = []
    for item in data:
        # 組合車名和標籤
        car_name_tag = f"{item['model'].upper()}  |{item['location']}|  {item['tag']}"
        # 直接使用原始價格
        computed_price = item["price"]
        year = item['year']
        mileage = item['mileage']
        
        # 根據保固狀態選擇描述文字
        if item.get('warranty', False):
            condition_text = ("車輛已做機油、齒輪油、火星塞、煞車油更換，噴油嘴、節流閥清潔，"
                            "引擎、傳動、空濾已檢查完畢並更換磨耗之消耗品，車況良好、無待修、"
                            "引擎有提供3~12月保固，消耗品、電系1個月保固。")
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
                "價格 & 付款方案\n\n"
                f"售價: {computed_price}\n"
                "可分期 / 可刷卡 / 零頭款輕鬆入手\n\n"
                "⚠️ 車輛流動快，下手要快\n\n"
                "📩請先私訊確認車輛是否還在\n\n"
                "聯絡方式\n"
                "• Line官方：@748luazt（截圖想看車輛）\n\n"
                "保障服務\n\n"
                "買賣履約保證，交易更安心\n"
                "保證無重大事故 & 無泡水（如有事故會事先說明）\n"
                "可無卡分期 & 全額貸款，輕鬆入手\n"
                "車換車補價差，提供線上估價\n"
                "可協助托運，全台配送"
            )
        else:
            description = (
                "車輛狀況\n\n"
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
                "• Line官方：@748luazt（截圖想看車輛）\n\n"
                "保障服務\n\n"
                "買賣履約保證，交易更安心\n"
                "保證無重大事故 & 無泡水（如有事故會事先說明）\n"
                "可無卡分期 & 全額貸款，輕鬆入手\n"
                "車換車補價差，提供線上估價\n"
                "可協助托運，全台配送"
            )
        
        rows.append({
            "地點": item["location"],
            "年分": item["year"],
            "廠牌": item["brand"],
            "車名+標籤": car_name_tag,
            "里程": item["mileage"],
            "價格": computed_price,
            "車況": description
        })
    
    df = pd.DataFrame(rows)
    fb_excel_file = json_file.replace('.json', '_FB.xlsx')
    df.to_excel(fb_excel_file, index=False)
    print(f"FB Excel 檔案已建立：{fb_excel_file}")

# =============================================================================
# 主流程：只執行爬蟲和產生 FB Excel
# =============================================================================

def main():
    # 1. 執行爬蟲，取得 JSON 檔案路徑
    json_file = crawl_main()
    
    # 2. 產生 FB 格式的 Excel
    generate_fb_excel(json_file)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"發生錯誤：{e}")
