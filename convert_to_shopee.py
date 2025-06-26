import pandas as pd
import json
import os

def create_product_listing(data):
    """將JSON資料轉換為商品列表格式"""
    # 創建一個列表來存儲格式化後的資料
    formatted_data = []
    
    for item in data:
        # 格式化商品描述
        description = f"""年分:{item['year']}年
里程:{item['mileage']}
看車地點:{item['location']}
車輛狀況:{item['condition']}
🟢 提供 6 至 36 期的分期選擇
🏍️ 可到店免費試乘體驗
❗ 車輛狀況需確認，請勿直接下單"""

        # 創建商品名稱
        product_name = f"[{item['location']}]{item['year']}年 {item['brand']} {item['model']}{item['tag']}"

        # 處理價格 - 去掉最後兩位數
        price = str(int(item['price']) // 100)

        # 創建一行資料
        row = {
            "分類": "100755",  # 根據範例設定的固定分類
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
            "價格": price, # 使用處理過的價格
            "庫存": "1",
            "商品選項貨號": "",
            "新版尺寸表": "",
            "圖片尺寸表": "",
            "GTIN": "",
            "主商品圖片": item['images'][0],
        }

        # 添加商品圖片
        for i in range(8):
            image_key = f"商品圖片 {i+1}"
            row[image_key] = item['images'][i] if i < len(item['images']) else ""

        # 添加配送方式設定
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

def save_to_excel(data, output_file):
    """將資料儲存為Excel檔案"""
    # 將格式化後的資料轉換為DataFrame
    df = pd.DataFrame(data)
    
    # 儲存為Excel
    df.to_excel(output_file, index=False)
    print(f"Excel檔案已建立: {output_file}")

def read_json_file(file_path):
    """從檔案讀取JSON資料"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"找不到檔案: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"JSON檔案格式錯誤: {file_path}")
        return None
    except Exception as e:
        print(f"讀取檔案時發生錯誤: {str(e)}")
        return None

def main():
    # 指定JSON檔案名稱
    input_file = 'progress_20250208_000504.json'
    
    # 建立對應的Excel檔案名稱
    output_file = input_file.replace('.json', '.xlsx')
    
    print(f"正在處理檔案: {input_file}")
    
    # 檢查檔案是否存在
    if not os.path.exists(input_file):
        print(f"錯誤：找不到檔案 {input_file}")
        input("按Enter鍵結束...")
        return
    
    # 讀取JSON檔案
    data = read_json_file(input_file)
    
    if data:
        try:
            # 處理資料
            formatted_data = create_product_listing(data)
            # 儲存為Excel
            save_to_excel(formatted_data, output_file)
            print("\n轉換完成！")
        except Exception as e:
            print(f"\n處理資料時發生錯誤: {str(e)}")
    
    input("\n按Enter鍵結束...")

if __name__ == "__main__":
    main()