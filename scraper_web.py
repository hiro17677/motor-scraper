#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# =============================================================================
# 1. 爬蟲相關：抓取二手機車資料、儲存 JSON
# =============================================================================

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# 資料夾設定
BASE_DIR = "data"
WEB_RESULTS_DIR = os.path.join(BASE_DIR, "web_results")
create_directory(BASE_DIR)
create_directory(WEB_RESULTS_DIR)

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
        brands = ['三陽', '光陽', '山葉', '台鈴', '宏佳騰', 'PGO', 'SUZUKI', 'YAMAHA', 'SYM', 'KYMCO', 'AEON', '睿能']
        
        # 更新的正則表達式模式，放寬品牌匹配條件
        patterns = [
            # 完整年份格式，使用更寬鬆的品牌匹配
            r"(?:【(.+?)】)?\s*(\d{4})\s+([\w\u4e00-\u9fff\(\)]+)\s+([\w\s\-\.\+\(\)\|]+?)\s*(?:循環檔|國際檔|ABS|TCS)*\s*#(\d+)",
            # 簡短年份格式，使用更寬鬆的品牌匹配
            r"(?:【(.+?)】)?\s*(\d{2})年\s+([\w\u4e00-\u9fff\(\)]+)\s+([\w\s\-\.\+\(\)\|]+?)\s*(?:循環檔|國際檔|ABS|TCS)*\s*#(\d+)",
            # 特殊格式，使用更寬鬆的品牌匹配
            r"(?:【(.+?)】)?\s*\d{2,4}(?:年)?\s+([\w\u4e00-\u9fff\(\)]+)\s+([\w\s\-\.\+\(\)\|]+?)\s*#(\d+)"
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
            raise ValueError(f"車輛名稱格式不符: {product_title}")
            
        # 處理不同的匹配結果
        if len(match.groups()) == 5:  # 完整格式或簡短年份格式
            location, year, brand, model, tag = match.groups()
            # 處理簡短年份 (例如 "23" -> "2023")
            if len(year) == 2:
                year = "20" + year
        else:  # 特殊格式
            location, brand, model, tag = match.groups()
            # 從標題中提取年份
            year_match = re.search(r"(\d{2,4})年?", product_title)
            year = year_match.group(1) if year_match else "0000"
            if len(year) == 2:
                year = "20" + year

        # 品牌名稱標準化
        brand = brand.strip()
        print(f"提取到的品牌: {brand}")
        
        # 檢查品牌是否在預定義列表中
        if brand not in brands:
            # 嘗試從型號中提取品牌
            for known_brand in brands:
                if known_brand in model:
                    brand = known_brand
                    print(f"從型號中找到品牌: {brand}")
                    break
            # 如果仍然找不到品牌，記錄到錯誤日誌
            if brand not in brands:
                print(f"未知品牌: {brand} (標題: {product_title})")
                with open("unknown_brands.txt", "a", encoding="utf-8") as f:
                    f.write(f"URL: {url}\nTitle: {product_title}\nBrand: {brand}\n\n")
        
        # 清理型號中的特殊字元但保留連字符
        model = re.sub(r'(?<![\w-])[\W_]+(?![\w-])', ' ', model).strip()
        
        # 確保 tag 前面加上 "#" 符號
        tag = f"#{tag}" if not tag.startswith("#") else tag

        condition, mileage, images, warranty = extract_vehicle_condition_mileage_and_images(soup, location)

        price_element = soup.select_one('span.price-item.price-item--regular .money')
        price = price_element.get('data-ori-price', '').replace(',', '').split('.')[0]

        # 精簡輸出格式
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
            "warranty": warranty
        }
    except Exception as e:
        print(f"解析失敗：{url}, 錯誤：{e}")
        return None

def save_to_json(data, file_path):
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)

def process_directory(directory_url, processed_urls):
    print(f"\n處理目錄: {directory_url}")
    vehicle_urls = extract_vehicle_links(directory_url)
    results = []
    for vehicle_url in vehicle_urls:
        if vehicle_url not in processed_urls:
            print(f"處理車輛：{vehicle_url}")
            vehicle_data = extract_vehicle_data(vehicle_url)
            if vehicle_data:
                results.append(vehicle_data)
                processed_urls.append(vehicle_url)
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
        "https://shop.2motor.tw/collections/2motor888"    
    ]
    
    all_results = []
    error_logs = []  # 用於記錄錯誤
    processed_urls = []  # 本次執行已處理的 URL
    
    print("開始處理指定的分頁列表...")
    for url in directory_urls:
        try:
            results = process_directory(url, processed_urls)
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
    json_file = os.path.join(WEB_RESULTS_DIR, f"motorcycles_{timestamp}.json")
    processed_file = os.path.join(WEB_RESULTS_DIR, f"processed_urls_{timestamp}.json")
    
    # 保存本次已處理的 URL
    save_to_json(processed_urls, processed_file)
    print(f"已處理的 URL 已保存至：{processed_file}")
    
    # 保存錯誤日誌
    if error_logs:
        error_file = os.path.join(WEB_RESULTS_DIR, f"errors_{timestamp}.txt")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write("\n".join(error_logs))
        print(f"錯誤日誌已保存：{error_file}")
    
    save_to_json(all_results, json_file)
    
    print(f"\n處理完成:")
    print(f"總車輛數: {len(all_results)}")
    print(f"JSON 檔案已保存：{json_file}")
    
    return json_file

# =============================================================================
# 主流程：執行爬蟲，取得 JSON 檔案
# =============================================================================

def main():
    # 執行爬蟲，取得 JSON 檔案路徑
    json_file = crawl_main()
    print(f"爬蟲完成，結果已保存至：{json_file}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"發生錯誤：{e}")
