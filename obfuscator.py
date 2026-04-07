import argparse
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from CoreManager import AndroidObfuscator
from Plugin_Encryption import encrypt_strings
from Plugin_Opaque import add_opaque_predicates
from Plugin_CallIndirection import add_call_indirection


def run_obfuscation(input_dir, output_dir, algorithms):
    input_path = os.path.abspath(input_dir)
    output_path = os.path.abspath(output_dir)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    algo_map = {
        "SE": ("String Encryption", encrypt_strings),
        "OP": ("Opaque Predicates", add_opaque_predicates),
        "CI": ("Call Indirection", add_call_indirection),
    }

    # kiểm tra xem có những thuật toán nào
    selected_algos = []
    for alg in algorithms:
        alg_upper = alg.upper()
        if alg_upper == "RF":
            print("[!] RF da duoc doi ten thanh CI. Tu dong su dung Call Indirection.")
            alg_upper = "CI"
        if alg_upper in algo_map:
            selected_algos.append(algo_map[alg_upper])
        else:
            print(f"[-] Bo qua thuat toan khong hop le: {alg}")

    if not selected_algos:
        print("[-] Khong co thuat toan hop le nao duoc chon. Dung chuong trinh.")
        return

    print(f"[*] Cac thuat toan se ap dung: {', '.join([name for name, _ in selected_algos])}")


    for file_name in os.listdir(input_path):
        # có phải apk không?
        if not file_name.endswith(".apk"):
            continue

        apk_full_path = os.path.join(input_path, file_name)
        output_apk_name = os.path.join(output_path, f"obfuscated_{file_name}")

        print(f"\n[*] Bat dau xu ly: {file_name}")
        work_dir = os.path.join(base_dir, f"temp_{file_name.replace('.', '_')}")

        obf = AndroidObfuscator(apk_full_path, output_dir=work_dir)
        # lấy context
        context = obf.create_context()

        try:
            # decompile (ngược với biên dịch)
            obf.decompile()
            # thực thi từng plugin
            for _, func in selected_algos:
                obf.process_smali_files(func, context)
            # build lại và ký
            obf.build_and_sign(output_apk_name)
            print(f"[ thanh cong ] File luu tai: {output_apk_name}")
        except Exception as e:
            print(f"[ loi ] Qua trinh xu ly that bai cho {file_name}: {e}")
        finally:
            print(context.format_summary())
            obf.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tool tu dong lam roi hang loat APK")
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Duong dan thu muc chua cac file APK dau vao",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="./obfuscated_malwares",
        help="Duong dan thu muc luu APK dau ra (mac dinh: ./obfuscated_malwares)",
    )
    parser.add_argument(
        "-a",
        "--algorithms",
        nargs="+",
        required=True,
        help="Danh sach thuat toan, cach nhau bang khoang trang (SE, OP, CI)",
    )

    args = parser.parse_args()
    run_obfuscation(args.input, args.output, args.algorithms)
 