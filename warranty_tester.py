import requests
from bs4 import BeautifulSoup
import re
import time

def extract_vehicle_links(directory_url):
    """從目錄頁面提取所有車輛連結"""
    response = requests.get(directory_url)
    if response.status_code != 200:
        print(f"無法訪問目錄頁面：{directory_url}")
        return []
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.select('a.full-unstyled-link')
    vehicle_urls = [requests.compat.urljoin(directory_url, link['href']) for link in links]
    return vehicle_urls

def check_warranty(soup):
    """檢查車輛是否有保固"""
    # 檢查標題是否包含「未整理保固」
    title = soup.select_one('h1.product__title')
    if title and "未整理保固" in title.text:
        return False

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
        
        # 檢查是否符合有保固的模式
        for pattern in warranty_patterns:
            if re.search(pattern, text):
                return True
                
        # 檢查是否明確說明無保固
        for pattern in no_warranty_patterns:
            if re.search(pattern, text):
                return False

    return False

def test_single_page(url):
    """測試單一頁面的保固判斷"""
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"無法訪問網頁：{url}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.select_one('h1.product__title')
        description_div = soup.select_one('div.product-description')
        
        print("\n" + "="*80)
        print(f"測試URL: {url}")
        print(f"車輛標題: {title.text.strip() if title else '無標題'}")
        
        if description_div:
            text = description_div.get_text(separator=" ", strip=True)
            print("\n描述文字片段:")
            print(text[:200] + "..." if len(text) > 200 else text)
            
            warranty = check_warranty(soup)
            print("\n保固判斷結果:", "有保固" if warranty else "無保固")
            if title and "未整理保固" in title.text:
                print("注意: 標題中標記為「未整理保固」")
        print("="*80)
        return warranty
    except Exception as e:
        print(f"處理頁面時發生錯誤: {e}")
        return None

def main():
    """主要測試流程"""
    try:
        # 要測試的所有頁面
        test_urls = [
            "https://shop.2motor.tw/collections/2motor178",  # 桃園中壢店
            "https://shop.2motor.tw/collections/2motor123",  # 新北中和店
            "https://shop.2motor.tw/collections/2motor321"   # 新竹店
        ]
        
        # 總結果統計
        total_results = {
            "有保固": 0,
            "無保固": 0,
            "錯誤": 0,
            "總數": 0
        }
        
        # 依序測試每個頁面
        for test_url in test_urls:
            print(f"\n{'='*40}")
            print(f"開始測試頁面: {test_url}")
            print(f"{'='*40}\n")
            
            vehicle_urls = extract_vehicle_links(test_url)
            
            # 當前頁面的結果統計
            page_results = {
                "有保固": 0,
                "無保固": 0,
                "錯誤": 0,
                "總數": len(vehicle_urls)
            }
            
            for url in vehicle_urls:
                try:
                    warranty = test_single_page(url)
                    if warranty is not None:
                        if warranty:
                            page_results["有保固"] += 1
                        else:
                            page_results["無保固"] += 1
                    else:
                        page_results["錯誤"] += 1
                    time.sleep(1)  # 避免請求過快
                except Exception as e:
                    print(f"處理 {url} 時發生錯誤: {e}")
                    page_results["錯誤"] += 1
            
            # 顯示當前頁面的統計結果
            print(f"\n{'-'*20}")
            print(f"當前頁面測試結果:")
            print(f"總車輛數: {page_results['總數']}")
            print(f"有保固車輛數: {page_results['有保固']}")
            print(f"無保固車輛數: {page_results['無保固']}")
            print(f"處理失敗數: {page_results['錯誤']}")
            print(f"{'-'*20}")
            
            # 更新總結果
            total_results["有保固"] += page_results["有保固"]
            total_results["無保固"] += page_results["無保固"]
            total_results["錯誤"] += page_results["錯誤"]
            total_results["總數"] += page_results["總數"]
        
        # 顯示所有頁面的總結果
        print("\n最終測試結果統計:")
        print(f"總車輛數: {total_results['總數']}")
        print(f"有保固車輛數: {total_results['有保固']}")
        print(f"無保固車輛數: {total_results['無保固']}")
        print(f"處理失敗數: {total_results['錯誤']}")
        
    except Exception as e:
        print(f"執行測試時發生錯誤：{e}")

if __name__ == "__main__":
    main() 