import os
import json
from tqdm import tqdm
from datetime import datetime

def decode_fb_string(s: str) -> str:
    """
    將 Facebook 原始 JSON 裡被拆成 code point ≤0xFF 的字串
    先當 latin-1 回編位元組，再用 utf-8 解碼，還原正確中/英文字。
    """
    try:
        b = s.encode('latin-1', errors='ignore')
        return b.decode('utf-8', errors='ignore')
    except Exception:
        return s

def merge_fb_threads_to_json_and_txt(base_dir: str, out_json: str, out_txt: str):
    """
    1) 遍歷 base_dir 下每個子資料夾（每位對話）中的 message_*.json，
       將所有訊息合併為一個 list of dict。
    2) 輸出合併後的 JSON 檔（UTF-8, ensure_ascii=False, indent=2）。
    3) 輸出同樣內容的 TXT 檔，每行格式：
       datetime\tthread_title\tsender\tcontent
    """
    records = []

    for thread in tqdm(os.listdir(base_dir), desc="讀取對話資料夾"):
        thread_dir = os.path.join(base_dir, thread)
        if not os.path.isdir(thread_dir):
            continue

        for fn in os.listdir(thread_dir):
            if not fn.startswith("message") or not fn.endswith(".json"):
                continue

            path = os.path.join(thread_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"⚠️ 無法讀取 {path}：{e}")
                continue

            # 解碼對話標題
            raw_title = data.get("title", thread)
            title = decode_fb_string(raw_title)

            # 處理每條訊息
            for m in data.get("messages", []):
                raw_sender  = m.get("sender_name", "")
                raw_content = m.get("content", "")

                sender  = decode_fb_string(raw_sender)
                content = decode_fb_string(raw_content)

                ts = m.get("timestamp_ms")
                dt = None
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts / 1000).isoformat()

                records.append({
                    "thread_title": title,
                    "sender":       sender,
                    "datetime":     dt,
                    "content":      content
                })

    # 1) 輸出 JSON
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # 2) 輸出 TXT
    with open(out_txt, "w", encoding="utf-8") as f:
        for rec in records:
            line = f"{rec['datetime']}\t{rec['thread_title']}\t{rec['sender']}\t{rec['content']}\n"
            f.write(line)

    print(f"✅ 完成！\n- JSON：{out_json}\n- TXT：{out_txt}\n共 {len(records)} 筆訊息。")

if __name__ == "__main__":
    # ■■■ 請修改下面三個變數為你的路徑 ■■■
    BASE_DIR = r"C:\Users\hiro1\Downloads\facebook-hellohiryan-2025-5-19-sgm890D0\your_facebook_activity\messages\archived_threads"
    OUT_JSON = r"C:\Users\hiro1\Downloads\facebook_messages_combined.json"
    OUT_TXT  = r"C:\Users\hiro1\Downloads\facebook_messages_combined.txt"

    merge_fb_threads_to_json_and_txt(BASE_DIR, OUT_JSON, OUT_TXT)
