import base64
import re
import os

# --------------- ma hoa chuoi ----------------

def encrypt_strings(smali_file_path):
    with open(smali_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Biểu thức tìm các dòng khai báo chuỗi: const-string vX, "chuoi_van_ban" [15]
    string_pattern = re.compile(r'const-string ([v|p]\d+), "(.*?)"')

    def xor_base64_encrypt(match):
        reg = match.group(1)
        original_string = match.group(2)

        if len(original_string) == 0:
            return match.group(0)

        # Tránh các chuỗi quá cơ bản hoặc liên quan đến cấu hình hệ thống
        if original_string.startswith("Landroid") or original_string.startswith("Ljava"):
            return match.group(0)

        # Dùng Base64 encoding để biến chuỗi thành văn bản vô nghĩa [6, 7]
        encoded_bytes = base64.b64encode(original_string.encode('utf-8'))
        encoded_string = encoded_bytes.decode('utf-8')

        # Thay thế bằng chuỗi đã được mã hóa trong mã Smali
        return f'const-string {reg}, "{encoded_string}"\n    # Yêu cầu gọi hàm giải mã tại Runtime'

    modified_content = string_pattern.sub(xor_base64_encrypt, content)

    with open(smali_file_path, "w", encoding="utf-8") as f:
        f.write(modified_content)
    print(f"[Encrypt Plugin] Đã mã hóa chuỗi trong: {os.path.basename(smali_file_path)}")
