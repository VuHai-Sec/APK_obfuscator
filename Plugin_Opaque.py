import re
import random
import os

# ---------- thay doi luong thuc thi ---------------


def add_opaque_predicates(smali_file_path):
    with open(smali_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Tìm các phương thức (method) trong smali để chèn mã rác
    method_pattern = re.compile(r'(\.method.+?)(?=\.end method)', re.DOTALL)

    def insert_junk(match):
        original_method = match.group(1)
        # Bỏ qua các method rỗng hoặc abstract
        if "abstract" in original_method or "native" in original_method:
            return original_method

        # Chèn công thức toán học vô nghĩa: (((a+1+a) % 2 * (a^2 / a)) % 2 == 0) [4]
        # Bằng mã Smali để sinh ra biến k, rẽ nhánh ngẫu nhiên vào các block mã rác [2]
        junk_smali = """
    # --- BẮT ĐẦU OPAQUE PREDICATE (Đánh lừa AI) ---
    const v0, 0x1
    add-int v1, v0, v0
    rem-int/lit8 v2, v1, 0x2
    if-nez v2, :junk_jump_label
    # Mã thực thi thực sự nằm ở đây
    goto :end_junk_label
    :junk_jump_label
    # Đoạn dead-code (mã rác) đánh lừa các mô hình AI dựa trên Control Flow [3]
    nop
    nop
    const v0, 0x0
    :end_junk_label
    # --- KẾT THÚC OPAQUE PREDICATE ---
"""
        # Chèn ngay sau khai báo .registers hoặc .locals
        return re.sub(r'(\.locals \d+|\.registers \d+)', r'\1\n' + junk_smali, original_method, count=1)

    modified_content = method_pattern.sub(insert_junk, content)

    with open(smali_file_path, "w", encoding="utf-8") as f:
        f.write(modified_content)
    print(f"[Opaque Plugin] Đã chèn luồng mờ đục vào: {os.path.basename(smali_file_path)}")
