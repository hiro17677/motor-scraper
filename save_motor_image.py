import os
import requests
import json

# 設置儲存資料夾的路徑
base_folder = r"C:\\Users\\hiro1\\OneDrive\\文件\\二手車上架\\車輛圖片區"

# 檢查 JSON 檔案是否存在
def check_file_exists(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"檔案不存在: {file_path}")

# 讀取 JSON 檔案
def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 建立資料夾名稱，過濾非法字元
def create_folder_name(car_data):
    folder_name = f"{car_data['location'].replace('店', '')}_{car_data['tag']}_{car_data['brand']}_{car_data['model']}_{car_data['mileage'].split(' ')[0]}_{car_data['price']}"
    # 過濾 Windows 不允許的字元
    return ''.join(c for c in folder_name if c not in r"<>:""/\\|?*")

# 下載圖片函數
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

# 主程式
def main(json_file):
    # 檢查檔案是否存在
    check_file_exists(json_file)

    # 載入 JSON 數據
    try:
        car_data_list = load_json(json_file)
    except json.JSONDecodeError as e:
        print(f"無法解析 JSON 檔案: {e}")
        return

    for car_data in car_data_list:
        # 建立資料夾
        folder_name = create_folder_name(car_data)
        folder_path = os.path.join(base_folder, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # 檢查是否已有圖片存在，避免重複下載
        existing_files = set(os.listdir(folder_path))

        # 下載圖片並儲存到資料夾
        for index, image_url in enumerate(car_data['images']):
            image_extension = image_url.split('.')[-1]
            image_name = f"image_{index + 1}.{image_extension}"
            save_path = os.path.join(folder_path, image_name)

            if image_name not in existing_files:
                download_image(image_url, save_path)
            else:
                print(f"跳過已存在的圖片: {image_name}")

        print(f"所有圖片已儲存至資料夾: {folder_path}")

# 指定 JSON 檔案路徑
json_file_path = r"C:\\Users\\hiro1\\OneDrive\\文件\\二手車上架\\JSON檔案\\progress_20250208_000504.json"

if __name__ == "__main__":
    try:
        check_file_exists(json_file_path)
        main(json_file_path)
    except FileNotFoundError as e:
        print(f"錯誤: {e}")
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
