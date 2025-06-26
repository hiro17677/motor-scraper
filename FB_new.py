#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

# =============================================================================
# Configuration
# =============================================================================
# 指定 FB Excel 檔案的輸出資料夾
FB_OUTPUT_DIR = r"C:\Users\hiro1\OneDrive\文件\二手車上架\motor-scraper\data\FB"

# 品牌列表 (與原腳本一致)
BRANDS_LIST = ['三陽', '光陽', '山葉', '台鈴', '宏佳騰', 'PGO', 'SUZUKI', 'YAMAHA', 'SYM', 'KYMCO', 'AEON', '偉士牌', '本田', '鈴木', 'YAMAHA', 'SYM', 'KYMCO', 'AEON', '川崎', 'GOGORO']

# =============================================================================
# Helper Functions
# =============================================================================
def create_directory(path):
    """如果路徑不存在，則建立資料夾"""
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            print(f"成功建立資料夾: {path}")
        except Exception as e:
            print(f"建立資料夾失敗: {path}, 錯誤: {e}")
            raise

# =============================================================================
# Core Scraping and Data Extraction (Adapted from original)
# =============================================================================

def extract_vehicle_condition_mileage_and_images(soup, location_unused):
    """
    從商品頁面的soup物件中提取車況、里程、圖片和保固資訊。
    location_unused 參數在此函數中未被使用，但保留以符合原始函數簽名。
    """
    condition = "檢查和更換耗材，確保車輛運作順暢" # 預設車況描述
    mileage = "未知"
    images = []
    warranty = False  # 預設無保固
    
    # 檢查標題是否包含「未整理保固」字樣
    title_element = soup.select_one('h1.product__title')
    if title_element and "未整理保固" in title_element.text:
        warranty = False
        # 若標題已註明未整理保固，則直接返回，不進一步解析描述
        return condition, mileage, images, warranty

    description_div = soup.select_one('div.product-description')
    if description_div:
        text = description_div.get_text(separator=" ", strip=True)
        
        # 定義有保固的正則表達式模式
        warranty_patterns = [
            r"保固項目[：:]\s*(?:引擎|消耗品)\s*\d+\s*個月",
            r"保固[：:]\s*(?:引擎|消耗品)\s*\d+\s*個月",
            r"(?:引擎|消耗品)(?:提供)?\s*\d+\s*個月保固",
            r"原廠保固中",
        ]
        
        # 定義無保固的正則表達式模式
        no_warranty_patterns = [
            r"不提供保固",
            r"恕不提供保固服務",
            r"現況[售販](?:售|出).*不提供保固",
            r"無(?:附)?保固",
            r"優惠價.*不提供保固",
            r"未整理保固", # 也檢查描述內文
        ]
        
        # 提取里程數
        mileage_match = re.search(r"里程(?:數)?\s*[:：]?\s*約?\s*([\d,xX]+)\s*(?:km|公里)", text)
        if mileage_match:
            mileage_val = mileage_match.group(1).strip().upper()
            # 處理 'XXXX' 或 'XXX' 這種里程表示方式
            if 'X' in mileage_val:
                mileage = mileage_val + " (請店洽)"
            else:
                mileage = mileage_val + " km"
        
        # 檢查是否有保固
        for pattern in warranty_patterns:
            if re.search(pattern, text):
                warranty = True
                break
                
        # 如果未找到有保固的模式，則檢查是否明確說明無保固
        if not warranty:
            for pattern in no_warranty_patterns:
                if re.search(pattern, text):
                    warranty = False
                    break
                    
    # 抓取圖片連結
    media_list = soup.select('.product__media-list img')
    for img in media_list:
        if 'src' in img.attrs:
            images.append(img['src'])
    
    return condition, mileage, images, warranty


def extract_vehicle_links(directory_url):
    """從目錄頁面提取所有車輛的獨立連結"""
    try:
        response = requests.get(directory_url, timeout=10)
        response.raise_for_status() # 檢查請求是否成功
    except requests.exceptions.RequestException as e:
        print(f"無法訪問目錄頁面：{directory_url}, 錯誤: {e}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.select('a.full-unstyled-link') # 根據觀察，這是車輛連結的選擇器
    vehicle_urls = []
    for link in links:
        href = link.get('href')
        if href and '/products/' in href: #確保是商品頁面
             vehicle_urls.append(requests.compat.urljoin(directory_url, href))
    return list(set(vehicle_urls)) #去除重複的連結

def extract_vehicle_data(url):
    """從單一車輛頁面提取詳細資料"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"無法訪問網頁：{url}, 錯誤: {e}")
        return None
        
    soup = BeautifulSoup(response.text, 'html.parser')
    try:
        product_title_element = soup.select_one('h1.product__title')
        if not product_title_element:
            print(f"未找到車輛名稱標題: {url}")
            return None
        product_title = product_title_element.text.strip()
        
        # 正則表達式模式列表 (與原腳本一致)
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
        
        print(f"正在處理標題: {product_title}")
        
        match = None
        for pattern_idx, pattern in enumerate(patterns):
            match = re.search(pattern, product_title)
            if match:
                print(f"成功匹配模式 (索引 {pattern_idx}): {pattern}")
                # print(f"匹配結果: {match.groups()}") # 可用於調試
                break
        
        if not match:
            print(f"標題解析失敗 (無匹配模式): {product_title} (URL: {url})")
            return None
            
        _groups = match.groups()
        location, year, initial_brand, initial_model, tag = "", "", "", "", ""

        # 根據原始腳本的邏輯處理不同數量的捕獲組
        if len(_groups) == 5:
            location, year, initial_brand, initial_model, tag = _groups
            if len(year) == 2: year = "20" + year
        elif len(_groups) == 4:
            # 原始腳本中此情況下： location, brand, model, tag = _groups
            # 這意味著第二個組被視為 brand (可能實際上是年份)，年份會從標題中重新提取
            location, initial_brand, initial_model, tag = _groups
            year_match_local = re.search(r"(\d{2,4})年?", product_title)
            year = year_match_local.group(1) if year_match_local else "0000"
            if len(year) == 2 and year != "00": year = "20" + year
        elif len(_groups) == 3:
            # 原始腳本中此情況下： location, brand_model_text, tag = _groups
            location, brand_model_text, tag = _groups
            _brand_candidate = None
            _model_candidate = brand_model_text
            for known_brand_in_split in BRANDS_LIST:
                if known_brand_in_split in brand_model_text:
                    _brand_candidate = known_brand_in_split
                    _model_candidate = brand_model_text.replace(known_brand_in_split, "").strip()
                    break
            if not _brand_candidate and brand_model_text:
                parts = brand_model_text.split(maxsplit=1)
                _brand_candidate = parts[0]
                _model_candidate = parts[1] if len(parts) > 1 else ""
            initial_brand = _brand_candidate if _brand_candidate else ""
            initial_model = _model_candidate
            year = "0000"
        else:
            print(f"標題解析後分組數量 ({len(_groups)}) 不符預期: {product_title} (URL: {url})")
            return None

        brand = initial_brand.strip()
        model = initial_model.strip()
        print(f"初步解析 -> 地點: {location}, 年份: {year}, 品牌: '{brand}', 型號: '{model}', Tag: {tag}")

        # 品牌名稱標準化與修正 (基於原始腳本的邏輯)
        if brand not in BRANDS_LIST:
            # print(f"品牌 '{brand}' (來自Regex) 不在已知列表。嘗試從型號 '{model}' 中修正。")
            found_brand_in_model = False
            for known_b in BRANDS_LIST:
                if known_b in model: # 檢查型號中是否包含已知品牌
                    brand = known_b
                    # print(f"品牌從型號修正為: '{brand}'")
                    # 注意：原腳本此處未明確從 model 字串中移除品牌，這可能在後續描述生成時處理
                    found_brand_in_model = True
                    break
            if not found_brand_in_model:
                # print(f"品牌 '{brand}' 未知，且在型號 '{model}' 中未找到已知品牌。")
                # 如果 'brand' 看起來像年份或其他非品牌字串，則設為未知
                if not brand or brand.isdigit() or len(brand) <=1 and brand not in ["PGO"]: # PGO是一個例外
                     brand = "未知"

        # 如果品牌仍然是 "未知"，再次嘗試從型號中提取 (更寬鬆的檢查)
        if brand == "未知" or brand not in BRANDS_LIST:
            for known_b in BRANDS_LIST:
                # 檢查型號是否以品牌開頭，或包含品牌 (作為獨立詞)
                if model.startswith(known_b) or re.search(r'\b' + re.escape(known_b) + r'\b', model, re.IGNORECASE):
                    brand = known_b
                    model = model.replace(known_b, "").strip() # 從型號中移除品牌
                    # print(f"品牌因 '未知' 或不在列表，從型號提取/修正為: '{brand}', 新型號: '{model}'")
                    break
        
        if brand not in BRANDS_LIST : brand = "未知" #最終確認


        # 清理型號中的特殊字元但保留連字符 (與原腳本一致)
        model = re.sub(r'(?<![\w-])[\W_]+(?![\w-])', ' ', model).strip()
        if not model and product_title: model = product_title # 如果型號為空，使用原始標題作為備用
        elif not model: model = "N/A"


        # 確保 tag 前面加上 "#" 符號，並處理空標籤 (與原腳本一致)
        tag = f"#{tag.lstrip('#')}" if tag and tag.strip() else ""
        
        # 提取車況、里程、圖片和保固 (與原腳本一致)
        condition, mileage, images, warranty = extract_vehicle_condition_mileage_and_images(soup, location)

        # 提取價格 (與原腳本一致)
        price_element = soup.select_one('span.price-item.price-item--regular .money')
        price = ""
        if price_element:
            price_data = price_element.get('data-ori-price')
            if price_data:
                 price = price_data.replace(',', '').split('.')[0]
            else: # 如果 data-ori-price 為空，嘗試直接取文字
                 price_text = price_element.text.strip().replace('NT$', '').replace('$', '').replace(',', '')
                 if price_text.isdigit():
                     price = price_text
                 else: # 如果還是無法解析，嘗試從頁面文本中尋找價格
                    price_text_match = re.search(r'[售價價]\s*[:：]?\s*\$?\s*([\d,]+)', soup.get_text())
                    if price_text_match:
                        price = price_text_match.group(1).replace(',', '')
                    else:
                        price = "店洽" # 最終備用價格
        else:
            price_text_match = re.search(r'[售價價]\s*[:：]?\s*\$?\s*([\d,]+)', soup.get_text())
            if price_text_match:
                price = price_text_match.group(1).replace(',', '')
            else:
                price = "店洽" # 最終備用價格
        
        print(f"最終提取 -> 品牌: '{brand}', 型號: '{model}', 價格: '{price}'")

        return {
            "location": location,
            "year": year,
            "brand": brand,
            "model": model,
            "tag": tag,
            "condition_text_from_extract": condition, # 內部使用的車況描述
            "mileage": mileage,
            "images": images, # 圖片URL列表
            "price": price,
            "warranty": warranty, # 布林值
            "original_title": product_title, # 用於調試或參考
            "url": url # 原始URL，用於參考
        }
    except Exception as e:
        print(f"解析車輛資料時發生嚴重錯誤：{url}, 錯誤：{e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================================================
# FB Excel Generation (Adapted from original)
# =============================================================================

def generate_fb_excel_new(data_list, output_dir_fb):
    """根據提取的車輛資料列表產生 FB Excel 檔案"""
    if not data_list:
        print("無資料可供產生 FB Excel。")
        return

    create_directory(output_dir_fb) # 確保輸出資料夾存在

    rows = []
    for item in data_list:
        # 從 item 中獲取已處理好的 brand 和 model
        display_brand = item.get('brand', '未知')
        display_model = item.get('model', '未知車型')

        # 如果品牌是 "未知"，但型號可能包含品牌資訊 (作為最後的補救措施)
        if display_brand == "未知" and display_model != '未知車型':
            for kb in BRANDS_LIST:
                if kb.lower() in display_model.lower(): # 不區分大小寫檢查
                    display_brand = kb
                    # 從型號中移除品牌 (不區分大小寫)
                    regex = re.compile(re.escape(kb), re.IGNORECASE)
                    display_model = regex.sub("", display_model).strip()
                    break
        
        # 如果型號為空，給一個預設值
        if not display_model: display_model = "詳細請參考標題"


        car_name_tag = f"{display_model.upper()} |{item.get('location','店洽')}| {item.get('tag','')}"
        computed_price = item.get("price", "店洽")
        year = item.get('year', '未知')
        mileage = item.get('mileage', '未知')

        # 根據保固狀態選擇描述文字 (與原腳本一致)
        if item.get('warranty', False):
            condition_text_fb = ("車輛已做機油、齒輪油、火星塞、煞車油更換，噴油嘴、節流閥清潔，"
                              "引擎、傳動、空濾已檢查完畢並更換磨耗之消耗品，車況良好、無待修、"
                              "引擎有提供3~12月保固，消耗品、電系1個月保固。")
        else:
            condition_text_fb = ("本車採現況販售，無附保固，但我們會針對部分消耗品進行基本檢查與更換，"
                              "讓車況更穩定")

        description_fb = ""
        location_desc = item.get('location', '')

        # 根據地點調整描述文字 (與原腳本一致)
        # 注意: display_model 應該是純型號，不含品牌
        if "桃園" in location_desc:
            description_fb = (
                "💰私訊預約賞車，可享專屬優惠\n\n"
                f"車輛名稱: {display_model}\n\n" 
                f"年份: {year}年\n"
                f"里程: {mileage}\n"
                "地點: 桃園中壢\n"
                f"{condition_text_fb}\n\n"
                "價格 & 付款方案\n\n"
                f"售價: {computed_price}\n"
                "可分期 / 可刷卡 / 零頭款輕鬆入手\n\n"
                "⚠️ 車輛流動快，下手要快\n\n"
                "📩請先私訊確認車輛是否還在\n\n"
                "聯絡方式\n"
                "• Line官方：https://lin.ee/aaZY1C7（截圖想看車輛）\n\n"
                "保障服務\n\n"
                "買賣履約保證，交易更安心\n"
                "保證無重大事故 & 無泡水（如有事故會事先說明）\n"
                "可無卡分期 & 全額貸款，輕鬆入手\n"
                "車換車補價差，提供線上估價\n"
                "可協助托運，全台配送"
            )
        else:
            description_fb = (
                f"車輛名稱: {display_model}\n\n"
                f"年份: {year}年\n"
                f"里程: {mileage}\n"
                f"地點: {location_desc if location_desc else '店洽'}\n"
                f"{condition_text_fb}\n\n"
                "價格 & 付款方案\n\n"
                f"售價: {computed_price}\n"
                "可分期 / 可刷卡 / 零頭款輕鬆入手\n\n"
                "⚠️ 車輛流動快，下手要快\n\n"
                "📩請先私訊確認車輛是否還在\n\n"
                "聯絡方式\n"
                "• Line官方：https://lin.ee/aaZY1C7（截圖想看車輛）\n\n"
                "保障服務\n\n"
                "買賣履約保證，交易更安心\n"
                "保證無重大事故 & 無泡水（如有事故會事先說明）\n"
                "可無卡分期 & 全額貸款，輕鬆入手\n"
                "車換車補價差，提供線上估價\n"
                "可協助托運，全台配送"
            )

        rows.append({
            "地點": item.get("location", "店洽"),
            "年分": year,
            "廠牌": display_brand, 
            "車名+標籤": car_name_tag,
            "里程": mileage,
            "價格": computed_price,
            "車況": description_fb # FB Excel 中的 "車況" 欄位是完整的描述文案
        })

    df = pd.DataFrame(rows)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 修改檔案名稱格式，更清晰標示其用途
    fb_excel_file_name = f"二手機車FB上架資料_{timestamp}.xlsx" 
    fb_excel_file_path = os.path.join(output_dir_fb, fb_excel_file_name)
    
    try:
        df.to_excel(fb_excel_file_path, index=False, engine="openpyxl")
        print(f"FB Excel 檔案已成功建立：{fb_excel_file_path}")
    except Exception as e:
        print(f"儲存FB Excel檔案失敗: {e}")

# =============================================================================
# Main Process
# =============================================================================
def process_single_directory_for_fb(directory_url, output_dir_for_fb_excel):
    """處理單一目錄URL，提取所有車輛資料"""
    print(f"\n處理目錄 (FB Excel): {directory_url}")
    vehicle_urls_list = extract_vehicle_links(directory_url)
    
    if not vehicle_urls_list:
        print(f"在目錄 {directory_url} 中未找到任何有效的車輛連結。")
        return []
        
    extracted_results = []
    total_links = len(vehicle_urls_list)
    print(f"找到 {total_links} 個車輛連結，開始處理...")

    for idx, vehicle_url_item in enumerate(vehicle_urls_list):
        print(f"處理車輛 ({idx + 1}/{total_links})：{vehicle_url_item}")
        vehicle_item_data = extract_vehicle_data(vehicle_url_item)
        if vehicle_item_data:
            extracted_results.append(vehicle_item_data)
        else:
            # extract_vehicle_data 內部已有錯誤打印
            print(f"未能成功解析車輛資料或已跳過：{vehicle_url_item}")
            
    return extracted_results

def main_fb_scraper():
    """主函數， orchestrates the scraping and Excel generation process."""
    # 你可以在這裡修改或增加需要爬取的目錄網址
    target_urls = [
        "https://shop.2motor.tw/collections/2motor888?limit=50&page=2&sort=position%2Bdesc"
        # "https://shop.2motor.tw/collections/another-collection", # 可以加入更多
    ]
    
    all_extracted_vehicle_data = []
    
    # 確保主輸出資料夾存在
    try:
        create_directory(FB_OUTPUT_DIR)
    except Exception:
        print(f"無法建立主輸出資料夾 {FB_OUTPUT_DIR}，程式終止。")
        return

    for url_to_crawl in target_urls:
        data_from_single_url = process_single_directory_for_fb(url_to_crawl, FB_OUTPUT_DIR)
        if data_from_single_url:
            all_extracted_vehicle_data.extend(data_from_single_url)
            print(f"從目錄 {url_to_crawl} 成功處理 {len(data_from_single_url)} 台車輛的資料。")
        else:
            print(f"目錄 {url_to_crawl} 未能提取到任何車輛資料。")

    if all_extracted_vehicle_data:
        print(f"\n總共提取到 {len(all_extracted_vehicle_data)} 台車輛的資料，開始產生 FB Excel 檔案...")
        generate_fb_excel_new(all_extracted_vehicle_data, FB_OUTPUT_DIR)
    else:
        print("\n未收集到任何有效的車輛資料，無法產生 FB Excel 檔案。")
        
    print("\nFB Excel 爬取與產生流程完成。")

# =============================================================================
# Script Execution
# =============================================================================
if __name__ == "__main__":
    try:
        main_fb_scraper()
    except Exception as e:
        print(f"主程式執行過程中發生未預期錯誤：{e}")
        import traceback
        traceback.print_exc()