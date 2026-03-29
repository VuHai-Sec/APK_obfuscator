import os
import sys

# Đảm bảo Python ưu tiên tìm module ở thư mục chứa file main.py này
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from CoreManager import AndroidObfuscator
from Plugin_Opaque import add_opaque_predicates
from Plugin_Encryption import encrypt_strings
from Plugin_RandomManifest import randomize_manifest
from Plugin_Reflection import add_inline_reflection

def run_obfuscation(input_dir, output_dir, modes):
    # Chuẩn hóa đường dẫn tuyệt đối
    input_path = os.path.abspath(input_dir)
    output_path = os.path.abspath(output_dir)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    for file_name in os.listdir(input_path):
        if file_name.endswith(".apk"):
            apk_full_path = os.path.join(input_path, file_name)
            output_apk_name = os.path.join(output_path, f"obfuscated_{file_name}")
            
            print(f"\n[*] Bắt đầu xử lý: {file_name}")
            # Dùng tên file làm folder tạm để tránh xung đột
            work_dir = os.path.join(base_dir, f"temp_{file_name.replace('.', '_')}")
            
            obf = AndroidObfuscator(apk_full_path, output_dir=work_dir)
            try:
                obf.decompile()
                
                # Áp dụng các plugin dựa trên danh sách chế độ được chọn
                if "RM" in modes:
                    obf.process_manifest(randomize_manifest)
                if "OP" in modes:
                    obf.process_smali_files(add_opaque_predicates)
                if "SE" in modes:
                    obf.process_smali_files(encrypt_strings)
                if "RF" in modes:
                    obf.process_smali_files(add_inline_reflection)
                    
                obf.build_and_sign(output_apk_name)
                print(f"[ thành công ] File lưu tại: {output_apk_name}")
            except Exception as e:
                print(f"[-] Đã xảy ra lỗi khi xử lý {file_name}: {e}")
            finally:
                obf.cleanup()

def parse_arguments():
    """Hàm phân tích tham số dòng lệnh theo cú pháp yêu cầu."""
    args = {
        "mode": [],
        "i": None,
        "o": "./obfuscated_malwares"  # Giá trị mặc định
    }
    
    for arg in sys.argv[1:]:
        if arg.startswith("-mode="):
            # Cho phép truyền nhiều chế độ cách nhau bằng dấu phẩy
            modes_str = arg.split("=", 1)[1]
            args["mode"] = [m.strip().upper() for m in modes_str.split(",")]
        elif arg.startswith("-i="):
            args["i"] = arg.split("=", 1)[1]
        elif arg.startswith("-o="):
            args["o"] = arg.split("=", 1)[1]
            
    return args

if __name__ == "__main__":
    args = parse_arguments()
    
    # Kiểm tra tham số đầu vào bắt buộc
    if not args["i"]:
        print("Cách sử dụng: python main.py -i=<thư_mục_chứa_apk> [-o=<thư_mục_đầu_ra>] [-mode=RM,SE,RF,OP]")
        print("Trong đó:")
        print("  -i=   : (Bắt buộc) Đường dẫn đến thư mục chứa các file APK gốc.")
        print("  -o=   : (Tùy chọn) Đường dẫn lưu APK đầu ra. Mặc định: ./obfuscated_malwares")
        print("  -mode=: (Tùy chọn) Chọn các chế độ làm rối, có thể kết hợp bằng dấu phẩy.")
        print("          RM = Random Manifest")
        print("          SE = String Encryption")
        print("          RF = Reflection")
        print("          OP = Opaque Predicates")
        sys.exit(1)
        
    if not args["mode"]:
        print("[!] Cảnh báo: Không có chế độ (-mode=) nào được chọn. Công cụ sẽ chỉ decompile và đóng gói lại APK mà không làm rối.")
        
    print(f"[*] Thư mục đầu vào: {args['i']}")
    print(f"[*] Thư mục đầu ra : {args['o']}")
    print(f"[*] Chế độ làm rối : {', '.join(args['mode']) if args['mode'] else 'Không có'}")
    
    run_obfuscation(args["i"], args["o"], args["mode"])
