import os
import json
import zipfile
import requests
from pathlib import Path

# --- Cấu hình ---
BASE_URL = "https://f-droid.org/repo/"
INDEX_URL = BASE_URL + "index-v1.jar"
SAVE_DIR = Path.home() / "benign_from_droid"
MAX_FILES = 1000
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
TEMP_JAR = "index-v1.jar"
TEMP_JSON = "index-v1.json"

def setup():
    if not SAVE_DIR.exists():
        SAVE_DIR.mkdir(parents=True)
        print(f"[*] Đã tạo thư mục: {SAVE_DIR}")

def get_index():
    print("[*] Đang tải file chỉ mục (index-v1.jar)...")
    r = requests.get(INDEX_URL, stream=True)
    with open(TEMP_JAR, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print("[*] Đang giải nén JSON từ Jar...")
    with zipfile.ZipFile(TEMP_JAR, 'r') as zip_ref:
        zip_ref.extract(TEMP_JSON)

def crawl_apks():
    with open(TEMP_JSON, 'r') as f:
        data = json.load(f)

    # Lấy danh sách các package và phiên bản của chúng
    packages = data.get('packages', {})
    downloaded_count = 0

    print(f"[*] Bắt đầu quét và tải tối đa {MAX_FILES} file...")

    # Duyệt qua từng package (app)
    for pkg_name, versions in packages.items():
        if downloaded_count >= MAX_FILES:
            break

        for version in versions:
            apk_name = version.get('apkName')
            size = version.get('size') # lấy size

            # Kiểm tra điều kiện kích thước
            if size and size <= MAX_SIZE_BYTES:
                download_url = BASE_URL + apk_name
                save_path = SAVE_DIR / apk_name

                # Nếu file đã tồn tại thì bỏ qua
                if save_path.exists():
                    print(f"[-] Bỏ qua {apk_name} (Đã tồn tại)")
                    downloaded_count += 1
                    break

                try:
                    print(f"[+] ({downloaded_count+1}/{MAX_FILES}) Đang tải: {apk_name} ({round(size/1024/1024, 2)} MB)")
                    resp = requests.get(download_url, timeout=30)
                    if resp.status_code == 200:
                        with open(save_path, 'wb') as apk_file:
                            apk_file.write(resp.content)
                        downloaded_count += 1
                    else:
                        print(f"[!] Lỗi khi tải {apk_name}: HTTP {resp.status_code}")
                except Exception as e:
                    print(f"[!] Lỗi kết nối khi tải {apk_name}: {e}")
                
                # Thoát vòng lặp version sau khi tải được 1 bản của app này
                break 

    print(f"\n[OK] Hoàn tất! Đã tải {downloaded_count} file vào {SAVE_DIR}")

def cleanup():
    for f in [TEMP_JAR, TEMP_JSON]:
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    setup()
    try:
        get_index()
        crawl_apks()
    finally:
        cleanup()