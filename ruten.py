#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime
import glob
import zipfile
from PIL import Image # For image processing
import shutil # For cleaning up temp folders
import csv

# =============================================================================
# 0. Configuration & Setup
# =============================================================================
BASE_DIR = "data" # Base directory for general data from scraper
RESULTS_DIR = os.path.join(BASE_DIR, "results") # For original scraper outputs
PROCESSED_PAGES_FILE = os.path.join(BASE_DIR, "processed_pages.json")
RUTEN_PROCESSED_PAGES_FILE = os.path.join(BASE_DIR, "ruten_processed_pages.json") # 新增露天專用記錄檔

RUTEN_OUTPUT_BASE_DIR = r"C:\Users\hiro1\OneDrive\文件\二手車上架\motor-scraper\data\ruten"
RUTEN_IMAGES_TEMP_DIR = os.path.join(RUTEN_OUTPUT_BASE_DIR, "temp_images_for_zip") # Temp folder for current batch images
RUTEN_EXCEL_TEMP_DIR = os.path.join(RUTEN_OUTPUT_BASE_DIR, "temp_excel_for_zip") # Temp folder for current batch excel

MAX_IMAGES_PER_VEHICLE = 3
VEHICLES_PER_BATCH = 5  # 修改為一次處理5台車
TARGET_IMAGE_MAX_DIMENSION = 1200 # px, for resizing
TARGET_IMAGE_QUALITY = 85 # For JPEG

# Ruten Specific Default Values
DEFAULT_RUTEN_LOCATION_CODE = "0" # Assuming 0 is a general code for Taiwan
DEFAULT_RUTEN_PAYMENT_METHODS = "1,2,3,4,5,9" # Example: PChomePay Cash, PChomePay Account, PChomePay CC, Bank Transfer, Postal Deposit, Face-to-Face
DEFAULT_RUTEN_SHIPPING_METHODS = "1,5" # Example: Face-to-Face, Freight/Cargo
DEFAULT_RUTEN_ITEM_CONDITION = "2" # 2 for Used/Second-hand

# 露天拍賣地區代碼對應表
RUTEN_LOCATION_CODES = {
    "台北市": "1",
    "新北市": "2",
    "桃園市": "3",
    "台中市": "4",
    "台南市": "5",
    "高雄市": "6",
    "基隆市": "7",
    "新竹市": "8",
    "嘉義市": "9",
    "新竹縣": "10",
    "苗栗縣": "11",
    "彰化縣": "12",
    "南投縣": "13",
    "雲林縣": "14",
    "嘉義縣": "15",
    "屏東縣": "16",
    "宜蘭縣": "17",
    "花蓮縣": "18",
    "台東縣": "19",
    "澎湖縣": "20",
    "金門縣": "21",
    "連江縣": "22"
}

def get_ruten_location_code(location):
    """從地點字串中提取縣市並轉換為露天拍賣地區代碼"""
    if not location:
        return DEFAULT_RUTEN_LOCATION_CODE
        
    # 移除可能的行政區名稱
    location = location.replace("區", "").replace("市", "").replace("縣", "")
    
    # 檢查是否包含任何縣市名稱
    for city, code in RUTEN_LOCATION_CODES.items():
        if city.replace("市", "").replace("縣", "") in location:
            return code
            
    return DEFAULT_RUTEN_LOCATION_CODE

# Columns for the Ruten Excel file (根據圖片調整，只到物品所在地)
RUTEN_EXCEL_COLUMNS = [
    "類別(必填)",
    "物品名稱(必填)",
    "商品價格(必填)",
    "數量(必填)",
    "自訂賣場分類",
    "物品說明",
    "物品新舊",
    "圖片1",
    "圖片2",
    "圖片3",
    "圖片4",
    "圖片5",
    "物品所在地"
]


def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

create_directory(BASE_DIR)
create_directory(RESULTS_DIR)
create_directory(RUTEN_OUTPUT_BASE_DIR)
create_directory(RUTEN_IMAGES_TEMP_DIR)
create_directory(RUTEN_EXCEL_TEMP_DIR)

# Initialize已處理頁面記錄檔 (from original script)
if not os.path.exists(PROCESSED_PAGES_FILE):
    with open(PROCESSED_PAGES_FILE, "w", encoding="utf-8") as file:
        json.dump([], file)

def load_processed_pages():
    """載入已處理頁面記錄"""
    try:
        with open(RUTEN_PROCESSED_PAGES_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        # 如果檔案不存在，創建一個新的空列表
        with open(RUTEN_PROCESSED_PAGES_FILE, "w", encoding="utf-8") as file:
            json.dump([], file)
        return []

def save_processed_page(url):
    """儲存已處理頁面記錄"""
    processed_pages = load_processed_pages()
    if url not in processed_pages:  # 避免重複記錄
        processed_pages.append(url)
        with open(RUTEN_PROCESSED_PAGES_FILE, "w", encoding="utf-8") as file:
            json.dump(processed_pages, file)

# =============================================================================
# 1. 爬蟲相關 (largely from original script, with minor adaptations if needed)
# =============================================================================
BRAND_TO_SHOPEE_CODE = {
    "光陽": "1095314", "三陽": "1107843", "山葉": "1802940", "睿能": "1091869",
    "PGO": "1101057", "哈特佛": "1089745", "台鈴": "1147069", "本田": "1146583",
    "宏佳騰": "1082956",
}

BRAND_TO_RUTEN_CODE = { # This will be crucial
    "光陽": "0019000200020001", "PGO": "0019000200020002", "台鈴": "0019000200020003",
    "三陽": "0019000200020004", "本田": "0019000200020008", "偉士牌": "0019000200020005",
    "山葉": "0019000200020006", "宏佳騰": "0019000200020009",
    # Add more as needed, or use a default if brand not found
}

def get_shopee_code(brand): # Retained for completeness if original functions call it
    return BRAND_TO_SHOPEE_CODE.get(brand, "999999")

def get_ruten_code(brand):
    # Normalize brand names for lookup if necessary
    brand_normalized = brand.upper()
    if "KYMCO" in brand_normalized or "光陽" in brand: return BRAND_TO_RUTEN_CODE.get("光陽", "001900020002") # Default motorcycle category if specific brand missing
    if "SYM" in brand_normalized or "三陽" in brand: return BRAND_TO_RUTEN_CODE.get("三陽", "001900020002")
    if "YAMAHA" in brand_normalized or "山葉" in brand: return BRAND_TO_RUTEN_CODE.get("山葉", "001900020002")
    if "PGO" in brand_normalized or "摩特動力" in brand: return BRAND_TO_RUTEN_CODE.get("PGO", "001900020002")
    if "SUZUKI" in brand_normalized or "台鈴" in brand: return BRAND_TO_RUTEN_CODE.get("台鈴", "001900020002")
    if "HONDA" in brand_normalized or "本田" in brand: return BRAND_TO_RUTEN_CODE.get("本田", "001900020002")
    if "AEON" in brand_normalized or "宏佳騰" in brand: return BRAND_TO_RUTEN_CODE.get("宏佳騰", "001900020002")
    if "VESPA" in brand_normalized or "偉士牌" in brand: return BRAND_TO_RUTEN_CODE.get("偉士牌", "001900020002")
    if "GOGORO" in brand_normalized or "睿能" in brand: return "001900020002" # Gogoro might not have a specific Ruten code, use general
    return BRAND_TO_RUTEN_CODE.get(brand, "001900020002") # Default to a general motorcycle category code

def extract_vehicle_condition_mileage_and_images(soup, location):
    condition = "檢查和更換耗材，確保車輛運作順暢"
    mileage = "未知"
    images = []
    warranty = False

    title_element = soup.select_one('h1.product__title')
    if title_element and "未整理保固" in title_element.text:
        warranty = False
        # Even if "未整理保固", still try to get mileage and images
    
    description_div = soup.select_one('div.product-description')
    description_text = ""
    if description_div:
        description_text = description_div.get_text(separator=" ", strip=True)
        
        # 更新里程數抓取邏輯
        mileage_match = re.search(r"里程(?:數)?\s*[:：]?\s*約?\s*([\d,xX]+)\s*(?:km|公里)", description_text, re.IGNORECASE)
        if mileage_match:
            mileage = mileage_match.group(1).strip() + " km"
        else:
            mileage = "0 km" # Default if not found

        # Warranty check (simplified from original for Ruten context if not primary focus)
        warranty_patterns = [r"保固項目[：:]", r"保固[：:]", r"個月保固", r"原廠保固中"]
        no_warranty_patterns = [r"不提供保固", r"恕不提供保固服務", r"現況[售販]", r"無(?:附)?保固", r"未整理保固"]

        for pattern in warranty_patterns:
            if re.search(pattern, description_text):
                warranty = True
                break
        if not warranty:
            for pattern in no_warranty_patterns:
                if re.search(pattern, description_text):
                    warranty = False
                    break
    
    # Extract all images, filtering will happen later
    media_list = soup.select('.product__media-list img')
    for img in media_list:
        if 'src' in img.attrs:
            img_src = img['src']
            # Shopify often has URLs like //cdn.shopify.com/... ensure protocol
            if img_src.startswith("//"):
                img_src = "https:" + img_src
            images.append(img_src)
            
    return condition, mileage, images, warranty, description_text # also return full desc text

def extract_vehicle_links(directory_url): # From original
    response = requests.get(directory_url)
    if response.status_code != 200:
        print(f"無法訪問目錄頁面：{directory_url}")
        return []
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.select('a.full-unstyled-link')
    vehicle_urls = [requests.compat.urljoin(directory_url, link['href']) for link in links]
    return list(set(vehicle_urls)) # Ensure unique URLs

def extract_vehicle_data(url): # Adapted from original
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
        
        brands = ['三陽', '光陽', '山葉', '台鈴', '宏佳騰', 'PGO', 'SUZUKI', 'YAMAHA', 'SYM', 'KYMCO', 'AEON', '偉士牌', '本田', '鈴木', 'KAWASAKI', '川崎', 'GOGORO', '睿能']
        
        patterns = [
            r"【(.+?)】\s*(\d{4})\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*(?:循環檔|國際檔|ABS|TCS)?\s*#(\d+)",
            r"【(.+?)】\s*(\d{2})年\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*(?:循環檔|國際檔|ABS|TCS)?\s*#(\d+)",
            r"【(.+?)】\s*\d{2,4}(?:年)?\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*#(\d+)",
            r"(\d{4})\s+([\w\u4e00-\u9fff\(\)]+)\s+([\w\u4e00-\u9fff\s\.\(\)\/\-\+]+?)\s*#(\d+)",
            r"(\d{2})年\s+([\w\u4e00-\u9fff\(\)]+)\s+([\w\u4e00-\u9fff\s\.\(\)\/\-\+]+?)\s*#(\d+)",
            r"【(.+?)】\s*(\d{4})\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*（(.+?)）\s*#(\d+)",
            r"【(.+?)】\s*(\d{4})\s+([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*([\w\u4e00-\u9fff]+)\s*#(\d+)",
            r"【(.+?)】\s*([\w\u4e00-\u9fff\(\)]+(?:\s*[\w\u4e00-\u9fff\.\(\)\/\-\+]+)*)\s*#(\d+)"
        ]
        
        match = None
        for pattern in patterns:
            match = re.search(pattern, product_title)
            if match:
                break
                
        if not match:
            print(f"標題解析失敗 (Ruten script): {product_title} URL: {url}")
            # Try a very basic extraction if complex patterns fail
            location = "未知地點"
            year = datetime.now().year # default to current year
            brand_model_part = product_title
            tag_match = re.search(r'#(\d+)', product_title)
            tag = tag_match.group(1) if tag_match else "000"

            # Attempt to get location from title if 【】 exists
            loc_match = re.search(r"【(.+?)】", product_title)
            if loc_match:
                location = loc_match.group(1).strip()
                brand_model_part = product_title.replace(loc_match.group(0), "").strip()
            
            # Attempt to get year
            year_m = re.search(r'(\d{4})年?', brand_model_part)
            if year_m:
                year = year_m.group(1)
                brand_model_part = brand_model_part.replace(year_m.group(0), "").strip()
            else:
                year_m_short = re.search(r'(\d{2})年', brand_model_part)
                if year_m_short:
                    year = "20" + year_m_short.group(1)
                    brand_model_part = brand_model_part.replace(year_m_short.group(0), "").strip()
            
            # Attempt to get brand and model
            extracted_brand = "未知品牌"
            model = brand_model_part.replace(f"#{tag}", "").strip() if tag != "000" else brand_model_part.strip()
            for b_name in brands:
                if b_name.lower() in model.lower():
                    extracted_brand = b_name
                    # Remove brand from model string (case-insensitive)
                    model = re.sub(re.escape(b_name), '', model, flags=re.IGNORECASE).strip()
                    break
            if extracted_brand == "未知品牌" and model.split():
                extracted_brand = model.split()[0] # Fallback to first word if no known brand found
                model = " ".join(model.split()[1:]) if len(model.split()) > 1 else ""


        else: # Original pattern matching logic
            groups = match.groups()
            if len(groups) == 5 and patterns[patterns.index(match.re.pattern)] in [patterns[5], patterns[6]]: # Chinese parenthesis or special marker
                 location, year, brand_candidate, model_details, tag = groups
                 model = f"{brand_candidate} {model_details}".strip() # Combine parts for model
            elif len(groups) == 4 and patterns[patterns.index(match.re.pattern)] in [patterns[0], patterns[1]]:
                location, year, model, tag = groups
            elif len(groups) == 4 and patterns[patterns.index(match.re.pattern)] in [patterns[3], patterns[4]]: # Direct year format
                year, location, model, tag = groups # Order is different for these patterns
            elif len(groups) == 3 and patterns[patterns.index(match.re.pattern)] == patterns[2]: # Special format with year in title but not first group
                location, model, tag = groups
                year_match_inner = re.search(r"(\d{2,4})年?", product_title)
                year = year_match_inner.group(1) if year_match_inner else "0000"
            elif len(groups) == 3 and patterns[patterns.index(match.re.pattern)] == patterns[7]: # No year format
                location, model, tag = groups
                year = "0000" # Placeholder
            else: # Fallback or unexpected match length
                print(f"標題解析群組不符預期: {product_title}, Groups: {groups}")
                return None # Skip this item


            if len(year) == 2:
                year = "20" + year
            
            extracted_brand = "未知品牌"
            # Try to extract brand from model string
            temp_model = model # use a temp variable for brand extraction
            for b_name in brands:
                if b_name.lower() in temp_model.lower():
                    extracted_brand = b_name
                    # Remove brand from model string (case-insensitive)
                    model = re.sub(re.escape(b_name), '', temp_model, flags=re.IGNORECASE).strip()
                    break
            if extracted_brand == "未知品牌" and temp_model.split(): # If brand not found in known list
                 # Check if the first part of temp_model is a brand
                first_word = temp_model.split()[0]
                if first_word in brands: # direct match for brands like PGO, SYM
                    extracted_brand = first_word
                    model = " ".join(temp_model.split()[1:]).strip()
                # else, brand remains "未知品牌", model is the rest

        model = re.sub(r'(?<![\w-])[\W_]+(?![\w-])', ' ', model).strip() # Clean model name
        tag = f"#{tag}" if not tag.startswith("#") else tag
        
        # Use the extracted_brand from parsing logic
        ruten_cat_code = get_ruten_code(extracted_brand)

        # Get mileage, images etc. using the existing function
        # The `location` from title parsing takes precedence if available
        parsed_location = location
        _condition_desc, mileage, images, warranty, full_description_text = extract_vehicle_condition_mileage_and_images(soup, parsed_location)

        price_element = soup.select_one('span.price-item.price-item--regular .money')
        price = "0" # Default price
        if price_element:
            price_text = price_element.get('data-ori-price', price_element.text)
            price = price_text.replace('$', '').replace(',', '').split('.')[0].strip()
            if not price.isdigit(): price = "0"
        else: # Try another common price selector pattern
            price_element_alt = soup.select_one('.price__regular .price-item') # Common on Shopify
            if price_element_alt:
                price_text = price_element_alt.text
                price = price_text.replace('$', '').replace(',', '').split('.')[0].strip()
                if not price.isdigit(): price = "0"


        return {
            "url": url, # Store original URL
            "title_full": product_title, # Store original title
            "location": parsed_location,
            "year": year,
            "brand": extracted_brand,
            "ruten_code": ruten_cat_code, # Ruten category code
            "model": model,
            "tag": tag,
            "condition_text": _condition_desc, # Original general condition text
            "raw_description": full_description_text, # Full raw description from site
            "mileage": mileage, # Expects "XXXX km" or "0 km" or "不明 (...)"
            "images_original_urls": images, # List of original image URLs
            "price": price,
            "warranty": warranty,
        }
    except Exception as e:
        print(f"解析失敗 (Ruten script)：{url}, 錯誤：{e}")
        # Log to a file for review
        with open(os.path.join(RESULTS_DIR, "ruten_parsing_errors.txt"), "a", encoding="utf-8") as f_err:
            f_err.write(f"URL: {url}\nTitle: {product_title if 'product_title' in locals() else 'N/A'}\nError: {e}\n\n")
        return None

def process_directory_page(directory_url): # Renamed from process_directory
    print(f"\n處理目錄 (Ruten script): {directory_url}")
    vehicle_urls = extract_vehicle_links(directory_url)
    processed_pages_log = load_processed_pages() # Use 'log' to avoid conflict
    results = []
    for vehicle_url in vehicle_urls:
        if vehicle_url not in processed_pages_log:
            print(f"處理車輛 (Ruten script)：{vehicle_url}")
            vehicle_data = extract_vehicle_data(vehicle_url)
            if vehicle_data:
                results.append(vehicle_data)
                save_processed_page(vehicle_url) # Mark as processed
            else:
                print(f"解析失敗，跳過 (Ruten script)：{vehicle_url}")
        else:
            print(f"已跳過已處理的車輛 (Ruten script)：{vehicle_url}")
    return results

def crawl_main_data(): # Renamed from crawl_main
    directory_urls = [ # Same URLs as original script
        "https://shop.2motor.tw/collections/2motor321",
        "https://shop.2motor.tw/collections/2motor178",
        "https://shop.2motor.tw/collections/2motor178?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor888",
        "https://shop.2motor.tw/collections/2motor888?limit=50&page=2&sort=position%2Bdesc",
        "https://shop.2motor.tw/collections/2motor111"
    ]
    
    all_results = []
    print("開始處理指定的分頁列表 (Ruten script)...")
    for url in directory_urls:
        try:
            results = process_directory_page(url)
            all_results.extend(results)
            print(f"從 {url} 成功處理 {len(results)} 台車輛 (Ruten script)")
        except Exception as e:
            print(f"處理 {url} 時發生錯誤 (Ruten script): {str(e)}")
            
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save a raw JSON dump of all scraped data for this run (optional, for debugging)
    raw_json_dump_file = os.path.join(RESULTS_DIR, f"ruten_scraped_raw_{timestamp}.json")
    with open(raw_json_dump_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)
    print(f"所有抓取資料已存檔於: {raw_json_dump_file}")
    
    return all_results

# =============================================================================
# 2. Ruten Specific Processing: Image Handling, Excel, Zipping
# =============================================================================

def generate_ruten_image_filename(vehicle_id_part, index, original_url):
    """Generates a Ruten-compatible image filename."""
    # Clean vehicle_id_part (e.g., from tag or model)
    # Remove '#' from tag, keep only alphanumeric
    name_part = re.sub(r'[^a-zA-Z0-9]', '', vehicle_id_part).lower()
    if not name_part: name_part = "image" # fallback

    # Get extension, default to .jpg
    original_ext = os.path.splitext(original_url.split('?')[0])[-1].lower()
    if original_ext not in ['.jpg', '.jpeg', '.png']:
        target_ext = '.jpg' # Default to JPG if unknown or unsupported
    elif original_ext == '.jpeg':
        target_ext = '.jpg'
    else:
        target_ext = original_ext
    
    return f"{name_part}_{index+1}{target_ext}"

def download_and_optimize_image(image_url, temp_batch_image_folder, target_image_filename):
    """Downloads an image, optimizes it, and saves to a specific path and filename."""
    full_save_path = os.path.join(temp_batch_image_folder, target_image_filename)
    try:
        response = requests.get(image_url, stream=True, timeout=20)
        response.raise_for_status() # Check for HTTP errors
        
        img = Image.open(response.raw)
        
        # Convert to RGB if it's RGBA (e.g. PNG with transparency) to avoid issues with JPG
        if img.mode == 'RGBA' or img.mode == 'P': # P is paletted
            img = img.convert('RGB')
            
        # Resize while maintaining aspect ratio
        img.thumbnail((TARGET_IMAGE_MAX_DIMENSION, TARGET_IMAGE_MAX_DIMENSION), Image.Resampling.LANCZOS)
        
        # Save based on target_image_filename extension
        if target_image_filename.lower().endswith('.png'):
            img.save(full_save_path, optimize=True)
        else: # Default to JPEG
            img.save(full_save_path, 'JPEG', quality=TARGET_IMAGE_QUALITY, optimize=True, progressive=True)
            
        print(f"成功下載並處理圖片: {image_url} -> {target_image_filename}")
        return full_save_path
    except requests.exceptions.RequestException as e:
        print(f"圖片下載失敗: {image_url}, 錯誤: {e}")
    except IOError as e: # PIL error
        print(f"圖片處理失敗: {image_url}, 錯誤: {e}")
    except Exception as e:
        print(f"下載/處理圖片時發生未知錯誤: {image_url}, 錯誤: {e}")
    return None

def create_ruten_description(item_data):
    """Creates a product description string for Ruten."""
    # 保留原始里程格式
    mileage_display = item_data.get('mileage', "0 km")
    if "km" in mileage_display:
        mileage_display = mileage_display.replace(" km", "").strip()
    if not mileage_display or mileage_display == "0":
        mileage_display = "0"

    desc_parts = [
        f"【車輛名稱】{item_data.get('brand', '')} {item_data.get('model', '')}<br>",
        f"【出廠年份】{item_data.get('year', '未知')} 年<br>",
        f"【目前里程】{mileage_display} 公里 <br>",
        f"【看車地點】{item_data.get('location', '台灣')}<br>",
        f"【車輛售價】{item_data.get('price', '0')} 元<br>",
        "<br>---- 車輛特色 ----<br>",
        f"{item_data.get('condition_text', '車況良好，歡迎現場看車。')}<br>",
        "<br>---- 聯絡方式 ----<br>",
        "• 官方帳號：@748luazt（截圖想看車輛）<br>",
        "<br>---- 注意事項 ----<br>",
        "1. 車輛流動快，請先私訊確認車輛是否還在。<br>",
        "2. 過戶相關費用另計。<br>",
        "3. 提供估價、車換車服務。<br>",
        "4. 請先詢問是否可看車，再行預約。<br>",
        "5. 可分期 / 可刷卡 / 零頭款輕鬆入手。"
    ]
    if item_data.get('warranty', False):
        desc_parts.insert(6, "本店提供基本保固，詳情請洽。<br>")

    return "".join(desc_parts)

def create_ruten_excel_for_batch(batch_vehicle_data, excel_filepath, image_filenames_for_excel_batch):
    """Creates and saves an Excel file for a batch of vehicles for Ruten."""
    excel_data_rows = []
    for i, item in enumerate(batch_vehicle_data):
        item_image_filenames = image_filenames_for_excel_batch[i] # list of filenames for this item
        
        # 保留原始里程格式
        mileage_display = item.get('mileage', "0 km")
        if "km" in mileage_display:
            mileage_display = mileage_display.replace(" km", "").strip()
        if not mileage_display or mileage_display == "0":
            mileage_display = "0"

        # 獲取商品所在地代碼
        location_code = get_ruten_location_code(item.get('location', ''))
        
        # 將代碼轉換為實際城市名稱
        location_name = ""  # 預設值
        for city, code in RUTEN_LOCATION_CODES.items():
            if code == location_code:
                location_name = city
                break

        row = {
            "類別(必填)": item.get('ruten_code', DEFAULT_RUTEN_ITEM_CONDITION),
            "物品名稱(必填)": f"{item.get('year','年份')}年 {item.get('brand','廠牌')} {item.get('model','型號')} |{item.get('location','中古')}| {item.get('tag','')} 二手機車 中古機車",
            "商品價格(必填)": item.get('price', "0"),
            "數量(必填)": "1",
            "自訂賣場分類": "",
            "物品說明": create_ruten_description(item),
            "物品新舊": "二手",
            "圖片1": item_image_filenames[0] if len(item_image_filenames) > 0 else "",
            "圖片2": item_image_filenames[1] if len(item_image_filenames) > 1 else "",
            "圖片3": item_image_filenames[2] if len(item_image_filenames) > 2 else "",
            "圖片4": item_image_filenames[3] if len(item_image_filenames) > 3 else "",
            "圖片5": item_image_filenames[4] if len(item_image_filenames) > 4 else "",
            "物品所在地": location_name
        }
        excel_data_rows.append(row)

    try:
        # 直接使用 CSV 寫入，確保特殊字符和換行符正確處理
        with open(excel_filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=RUTEN_EXCEL_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in excel_data_rows:
                writer.writerow(row)
            
        print(f"Ruten CSV 批次檔案已建立: {excel_filepath}")
        return excel_filepath
    except Exception as e:
        print(f"建立 Ruten CSV 檔案失敗: {excel_filepath}, 錯誤: {e}")
        return None

def create_batch_zip(zip_filename_fullpath, excel_filepath_to_add, image_filepaths_to_add):
    """Creates a ZIP file containing the Excel and image files for a batch."""
    try:
        with zipfile.ZipFile(zip_filename_fullpath, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add Excel file
            if os.path.exists(excel_filepath_to_add):
                zf.write(excel_filepath_to_add, arcname=os.path.basename(excel_filepath_to_add))
                print(f"已將 Excel 新增至 ZIP: {os.path.basename(excel_filepath_to_add)}")
            else:
                print(f"警告: Excel 檔案不存在，無法加入 ZIP: {excel_filepath_to_add}")

            # Add Image files
            for img_path in image_filepaths_to_add:
                if os.path.exists(img_path):
                    zf.write(img_path, arcname=os.path.basename(img_path)) # Store with simple name in ZIP
                    print(f"已將圖片新增至 ZIP: {os.path.basename(img_path)}")
                else:
                    print(f"警告: 圖片檔案不存在，無法加入 ZIP: {img_path}")
        
        zip_size_mb = os.path.getsize(zip_filename_fullpath) / (1024 * 1024)
        print(f"成功建立 ZIP 檔案: {zip_filename_fullpath} (大小: {zip_size_mb:.2f} MB)")
        if zip_size_mb > 8:
            print(f"警告: ZIP 檔案 {zip_filename_fullpath} 大小 ({zip_size_mb:.2f} MB) 超過 8MB 限制!")
        return zip_filename_fullpath
    except Exception as e:
        print(f"建立 ZIP 檔案失敗: {zip_filename_fullpath}, 錯誤: {e}")
        return None

# =============================================================================
# 3. Main Orchestration for Ruten Processing
# =============================================================================
def main_ruten_processing():
    all_vehicle_data = crawl_main_data()

    if not all_vehicle_data:
        print("未抓取到任何車輛資料，處理中止。")
        return

    print(f"\n總共抓取到 {len(all_vehicle_data)} 台車輛資料，開始批次處理...")

    batch_num = 0
    for i in range(0, len(all_vehicle_data), VEHICLES_PER_BATCH):
        current_batch_data = all_vehicle_data[i : i + VEHICLES_PER_BATCH]
        batch_num += 1
        print(f"\n--- 處理批次 {batch_num} (車輛 {i+1} 到 {i+len(current_batch_data)}) ---")

        # Create a unique temporary folder for this batch's images
        current_batch_image_folder = os.path.join(RUTEN_IMAGES_TEMP_DIR, f"batch_{batch_num}_images")
        create_directory(current_batch_image_folder)

        all_downloaded_image_paths_for_zip = [] # Full paths to actual image files for zipping
        image_filenames_for_excel_batch = [] # Just basenames for Excel

        for vehicle_item in current_batch_data:
            vehicle_tag_part = vehicle_item.get('tag', 'item').replace('#','')
            item_images_original_urls = vehicle_item.get('images_original_urls', [])
            
            downloaded_item_image_paths = [] # full paths for this one item
            excel_item_image_filenames = [] # basenames for this one item

            print(f"處理車輛: {vehicle_item.get('brand')} {vehicle_item.get('model')} ({vehicle_tag_part})")
            for img_idx, img_url in enumerate(item_images_original_urls):
                if img_idx >= MAX_IMAGES_PER_VEHICLE:
                    break # Max 3 images
                
                # Generate a Ruten-compatible, unique filename for the image
                safe_model_name = re.sub(r'\W+', '', vehicle_item.get('model', 'model')).lower()[:10]
                unique_id_part = f"{safe_model_name}_{vehicle_tag_part}"

                target_img_filename = generate_ruten_image_filename(unique_id_part, img_idx, img_url)
                
                saved_image_full_path = download_and_optimize_image(img_url, current_batch_image_folder, target_img_filename)
                
                if saved_image_full_path:
                    downloaded_item_image_paths.append(saved_image_full_path)
                    excel_item_image_filenames.append(target_img_filename) # Just the name for Excel

            all_downloaded_image_paths_for_zip.extend(downloaded_item_image_paths)
            image_filenames_for_excel_batch.append(excel_item_image_filenames) # list of lists for excel function

        # Create Excel for this batch
        temp_excel_filename = "ruten_auction_new.csv"  # 確保使用 .csv 副檔名
        temp_excel_filepath = os.path.join(RUTEN_EXCEL_TEMP_DIR, temp_excel_filename)
        
        created_excel_path = create_ruten_excel_for_batch(current_batch_data, temp_excel_filepath, image_filenames_for_excel_batch)

        if not created_excel_path:
            print(f"批次 {batch_num} 的 Excel/CSV 未能建立，跳過此批次 ZIP 產生。")
            # Clean up images for this failed batch
            if os.path.exists(current_batch_image_folder):
                 try: shutil.rmtree(current_batch_image_folder)
                 except Exception as e_clean: print(f"清理圖片資料夾 {current_batch_image_folder} 失敗: {e_clean}")
            continue # Move to next batch

        # Create ZIP for this batch
        zip_filename = f"Ruten_Batch_{batch_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_filepath_final = os.path.join(RUTEN_OUTPUT_BASE_DIR, zip_filename)
        
        zip_success_path = create_batch_zip(zip_filepath_final, created_excel_path, all_downloaded_image_paths_for_zip)

        # Cleanup: Remove the temporary image folder for this batch and the temp excel
        if os.path.exists(current_batch_image_folder):
            try:
                shutil.rmtree(current_batch_image_folder)
                print(f"已清理暫存圖片資料夾: {current_batch_image_folder}")
            except Exception as e:
                print(f"清理暫存圖片資料夾失敗 {current_batch_image_folder}: {e}")
        
        if os.path.exists(created_excel_path): # Temp excel path
             try:
                os.remove(created_excel_path)
                print(f"已清理暫存 Excel/CSV 檔案: {created_excel_path}")
             except Exception as e:
                print(f"清理暫存 Excel/CSV 檔案失敗 {created_excel_path}: {e}")


    print("\n--- 所有 Ruten 批次處理完成 ---")
    # Final cleanup of parent temp folders if they are empty
    if os.path.exists(RUTEN_IMAGES_TEMP_DIR) and not os.listdir(RUTEN_IMAGES_TEMP_DIR):
        try: os.rmdir(RUTEN_IMAGES_TEMP_DIR); print("已清理主暫存圖片資料夾。")
        except: pass # Ignore if not empty due to error in sub-folder cleanup
    if os.path.exists(RUTEN_EXCEL_TEMP_DIR) and not os.listdir(RUTEN_EXCEL_TEMP_DIR):
        try: os.rmdir(RUTEN_EXCEL_TEMP_DIR); print("已清理主暫存Excel資料夾。")
        except: pass


if __name__ == "__main__":
    try:
        main_ruten_processing()
    except Exception as e:
        print(f"主程式執行時發生嚴重錯誤: {e}")
        import traceback
        traceback.print_exc()