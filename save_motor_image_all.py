import os
import requests
import json

# 設置儲存資料夾的路徑
upload_folder = r"C:\\Users\\hiro1\\OneDrive\\文件\\二手車上架\\上傳區\\所有圖片"

# 檢查 JSON 檔案是否存在
def check_file_exists(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"檔案不存在: {file_path}")

# 讀取 JSON 檔案
def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

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

    # 確保上傳區資料夾存在
    os.makedirs(upload_folder, exist_ok=True)

    for car_data in car_data_list:
        # 下載所有圖片到同一資料夾
        for image_url in car_data['images']:
            image_name = image_url.split('/')[-1]  # 提取檔名
            save_path = os.path.join(upload_folder, image_name)

            # 如果圖片已存在，跳過下載
            if not os.path.exists(save_path):
                download_image(image_url, save_path)
            else:
                print(f"跳過已存在的圖片: {image_name}")

    print(f"所有圖片已下載到資料夾: {upload_folder}")

# 指定 JSON 檔案路徑
json_file_path = r"C:\\Users\\hiro1\\OneDrive\\文件\\二手車上架\\JSON檔案\\progress_20250113_191733.json"

if __name__ == "__main__":
    try:
        check_file_exists(json_file_path)
        main(json_file_path)
    except FileNotFoundError as e:
        print(f"錯誤: {e}")
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
