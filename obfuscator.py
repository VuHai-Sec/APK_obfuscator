import argparse
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from CoreManager import AndroidObfuscator
from Plugin_Encryption import encrypt_strings
from Plugin_Opaque import add_opaque_predicates
from Plugin_RandomManifest import randomize_manifest
from Plugin_Reflection import add_inline_reflection


def run_obfuscation(input_dir, output_dir, algorithms):
    input_path = os.path.abspath(input_dir)
    output_path = os.path.abspath(output_dir)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    algo_map = {
        "RM": ("Random Manifest", randomize_manifest, "manifest"),
        "SE": ("String Encryption", encrypt_strings, "smali"),
        "OP": ("Opaque Predicates", add_opaque_predicates, "smali"),
        "RF": ("Reflection Wrappers", add_inline_reflection, "smali"),
    }

    selected_algos = []
    for alg in algorithms:
        alg_upper = alg.upper()
        if alg_upper in algo_map:
            selected_algos.append(algo_map[alg_upper])
        else:
            print(f"[-] Bo qua thuat toan khong hop le: {alg}")

    if not selected_algos:
        print("[-] Khong co thuat toan hop le nao duoc chon. Dung chuong trinh.")
        return

    print(f"[*] Cac thuat toan se ap dung: {', '.join([name for name, _, _ in selected_algos])}")

    for file_name in os.listdir(input_path):
        if not file_name.endswith(".apk"):
            continue

        apk_full_path = os.path.join(input_path, file_name)
        output_apk_name = os.path.join(output_path, f"obfuscated_{file_name}")

        print(f"\n[*] Bat dau xu ly: {file_name}")
        work_dir = os.path.join(base_dir, f"temp_{file_name.replace('.', '_')}")

        obf = AndroidObfuscator(apk_full_path, output_dir=work_dir)
        context = obf.create_context()

        try:
            obf.decompile()

            for _, func, target_type in selected_algos:
                if target_type == "manifest":
                    obf.process_manifest(func, context)
                elif target_type == "smali":
                    obf.process_smali_files(func, context)

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
        help="Danh sach thuat toan, cach nhau bang khoang trang (RM, SE, OP, RF)",
    )

    args = parser.parse_args()
    run_obfuscation(args.input, args.output, args.algorithms)
