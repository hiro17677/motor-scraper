import pandas as pd
import json
import os

def create_product_listing(data):
    """將JSON資料轉換為商品列表格式"""
    formatted_data = []

    for item in data:
        # 格式化商品描述
        description = f"""年分:{item['year']}年\n里程:{item['mileage']} 公里\n看車地點:{item['location']}\n車輛狀況:{item['condition']}\n\n\u25CF 提供 6 至 36 期的分期選擇\n\u25CF 可到店免費試乘體驗\n\u25CF 車輛狀況需確認，請勿直接下單"""

        # 商品名稱格式
        product_name = f"[{item['location']}]{item['year']}年 {item['brand']} {item['model']}{item['tag']}"

        # 價格處理
        price = int(item['price']) // 100

        # 處理物品所在地
        location_city = item['location'][:2] + "市"

        # 創建一行資料
        row = {
            "類別(必填)": item['ruten_code'],  # 僅使用 ruten_code
            "物品名稱(必填)": product_name,
            "商品價格(必填)": price,
            "數量(必填)": 1,
            "自訂賣場分類": "",  # 空白
            "物品說明": description,
            "物品新舊": "二手",
        }

        # 添加圖片欄位，僅保留檔名
        for i in range(3):
            image_key = f"圖片{i + 1}"
            if i < len(item['images']):
                row[image_key] = os.path.basename(item['images'][i])
            else:
                row[image_key] = ""

        # 添加物品所在地到圖片欄位之後
        row["物品所在地"] = location_city

        # 填充其餘欄位為空
        additional_columns = [
            "可開收據", "附保證書", "附鑑定書", "有多種尺寸", "有多種顏色", "海外運送", "賣家自用料號",
            "備貨狀態", "預計出貨年月(若備貨狀態為2，則必填)", "較長備商品出貨天數(若備貨狀態為6，則必填)"
        ]
        for col in additional_columns:
            row[col] = None

        formatted_data.append(row)

    return formatted_data

def save_to_excel(data, output_file):
    """將資料儲存為Excel檔案"""
    df = pd.DataFrame(data)
    df.to_excel(output_file, index=False)
    print(f"Excel檔案已建立: {output_file}")

def read_json_file(file_path):
    """從檔案讀取JSON資料"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"讀取檔案時發生錯誤: {str(e)}")
        return None

def main():
    input_file = 'progress_20250113_191733.json'
    output_file = 'formatted_output.xlsx'

    if not os.path.exists(input_file):
        print(f"錯誤：找不到檔案 {input_file}")
        return

    data = read_json_file(input_file)

    if data:
        formatted_data = create_product_listing(data)
        save_to_excel(formatted_data, output_file)

if __name__ == "__main__":
    main()
