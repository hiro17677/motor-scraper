import os

# 檢查目錄結構
def check_directory_structure(base_dir="data"):
    directories = ["results", "pages", "images"]
    processed_file = os.path.join(base_dir, "processed_pages.json")
    
    # 確認主目錄
    if not os.path.exists(base_dir):
        print(f"缺少主目錄：{base_dir}")
        return False
    
    # 確認子目錄
    for directory in directories:
        path = os.path.join(base_dir, directory)
        if not os.path.exists(path):
            print(f"缺少目錄：{path}")
            return False
    
    # 確認檔案
    if not os.path.exists(processed_file):
        print(f"缺少檔案：{processed_file}")
        return False
    
    print("目錄和檔案結構正確！")
    return True

check_directory_structure()
