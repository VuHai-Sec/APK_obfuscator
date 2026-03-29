import argparse
import os
import sys

# Đảm bảo Python ưu tiên tìm module ở thư mục chứa file script này
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

# Import các module chuẩn xác theo tên file bạn đã cung cấp
from CoreManager import AndroidObfuscator
from Plugin_RandomManifest import randomize_manifest
from Plugin_Encryption import encrypt_strings
from Plugin_Opaque import add_opaque_predicates
from Plugin_Reflection import add_inline_reflection

def run_obfuscation(input_dir, output_dir, algorithms):
    input_path = os.path.abspath(input_dir)
    output_path = os.path.abspath(output_dir)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Ánh xạ các tham số viết tắt với (Tên hiển thị, Hàm thực thi, Mục tiêu)
    algo_map = {
	    "OP": ("Opaque Predicates", add_opaque_predicates, "smali"),
	    "RF": ("Inline Reflection", add_inline_reflection, "smali"),
        "RM": ("Random Manifest", randomize_manifest, "manifest"),
        "SE": ("String Encryption", encrypt_strings, "smali")        
    }

    # Lọc và xác nhận các thuật toán hợp lệ được yêu cầu
    selected_algos = []
    for alg in algorithms:
        alg_upper = alg.upper()
        if alg_upper in algo_map:
            selected_algos.append(algo_map[alg_upper])
        else:
            print(f"[-] Bỏ qua thuật toán không hợp lệ: {alg}")

    if not selected_algos:
        print("[-] Không có thuật toán hợp lệ nào được chọn. Dừng chương trình.")
        return

    print(f"[*] Các thuật toán sẽ áp dụng: {', '.join([name for name, _, _ in selected_algos])}")

    # Duyệt qua từng file apk trong thư mục
    for file_name in os.listdir(input_path):
        if file_name.endswith(".apk"):
            apk_full_path = os.path.join(input_path, file_name)
            output_apk_name = os.path.join(output_path, f"obfuscated_{file_name}")
            
            print(f"\n[*] Bắt đầu xử lý: {file_name}")
            # Dùng tên file làm folder tạm để tránh xung đột khi chạy liên tục
            work_dir = os.path.join(base_dir, f"temp_{file_name.replace('.', '_')}")
            
            obf = AndroidObfuscator(apk_full_path, output_dir=work_dir)
            try:
                obf.decompile()
                
                # Chạy lần lượt các thuật toán đã chọn
                for name, func, target_type in selected_algos:
                    if target_type == "manifest":
                        obf.process_manifest(func)
                    elif target_type == "smali":
                        obf.process_smali_files(func)
                
                obf.build_and_sign(output_apk_name)
                print(f"[ thành công ] File lưu tại: {output_apk_name}")
            except Exception as e:
                print(f"[ lỗi ] Quá trình xử lý thất bại cho {file_name}: {e}")
            finally:
                obf.cleanup()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tool tự động làm rối hàng loạt APK")
    
    # Cấu hình tham số dòng lệnh
    parser.add_argument("-i", "--input", required=True, 
                        help="Đường dẫn thư mục chứa các file APK đầu vào")
    parser.add_argument("-o", "--output", default="./obfuscated_malwares", 
                        help="Đường dẫn thư mục lưu APK đầu ra (mặc định: ./obfuscated_malwares)")
    parser.add_argument("-a", "--algorithms", nargs='+', required=True, 
                        help="Danh sách thuật toán phân cách bằng khoảng trắng (RM, SE, OP, RF). VD: -a RM SE OP")
    
    args = parser.parse_args()
    
    run_obfuscation(args.input, args.output, args.algorithms)
