import os
import subprocess
import shutil

class AndroidObfuscator:
    def __init__(self, apk_path, output_dir="obfuscation_working_dir"):
        self.apk_path = apk_path
        self.output_dir = output_dir
        self.smali_dir = os.path.join(self.output_dir, "smali")
        # Thông số keystore để ký APK
        self.keystore = "debug.keystore"
        self.ks_pass = "android"
        self.alias = "androiddebugkey"

    def decompile(self):
        print(f"[+] Đang dịch ngược {os.path.basename(self.apk_path)}...")
        # Thêm cờ --keep-broken-res để ép Apktool xử lý các tài nguyên bị malware làm hỏng
        subprocess.run(["apktool", "d", self.apk_path, "-o", self.output_dir, "-f", "--keep-broken-res"], check=True)

    def _ensure_keystore(self):
        """Tự động tạo keystore nếu chưa tồn tại"""
        if not os.path.exists(self.keystore):
            print("[+] Đang tạo keystore để ký APK...")
            cmd = [
                "keytool", "-genkey", "-v", "-keystore", self.keystore,
                "-storepass", self.ks_pass, "-alias", self.alias,
                "-keypass", self.ks_pass, "-keyalg", "RSA", "-keysize", "2048",
                "-validity", "10000", "-dname", "CN=Android Debug,O=Android,C=US"
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def build_and_sign(self, output_apk):
        intermediate_apk = output_apk + ".unaligned"
        
        print("[+] Đang đóng gói lại APK...")
        subprocess.run(["apktool", "b", self.output_dir, "-o", intermediate_apk], check=True)

        aligned_apk = output_apk + ".aligned"
        print("[+] Đang tối ưu hóa bằng zipalign...")
        subprocess.run(["zipalign", "-f", "-v", "4", intermediate_apk, aligned_apk], check=True, stdout=subprocess.DEVNULL)

        self._ensure_keystore()
        print(f"[+] Đang ký APK: {os.path.basename(output_apk)}")
        sign_cmd = [
            "apksigner", "sign", "--ks", self.keystore,
            "--ks-pass", f"pass:{self.ks_pass}",
            "--out", output_apk,
            aligned_apk
        ]
        subprocess.run(sign_cmd, check=True)

        for temp_file in [intermediate_apk, aligned_apk]:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def process_smali_files(self, plugin_function):
        """Quét và áp dụng plugin lên tất cả file .smali"""
        if not os.path.exists(self.output_dir):
            return

        for item in os.listdir(self.output_dir):
            current_path = os.path.join(self.output_dir, item)
            if os.path.isdir(current_path) and item.startswith("smali"):
                for root, _, files in os.walk(current_path):
                    for file in files:
                        if file.endswith(".smali"):
                            file_path = os.path.join(root, file)
                            plugin_function(file_path)

    def process_manifest(self, plugin_function):
        """Áp dụng plugin lên file AndroidManifest.xml"""
        manifest_path = os.path.join(self.output_dir, "AndroidManifest.xml")
        if os.path.exists(manifest_path):
            plugin_function(manifest_path)
        else:
            print(f"[-] Cảnh báo: Không tìm thấy AndroidManifest.xml tại {manifest_path}")

    def cleanup(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
            print(f"[+] Đã dọn dẹp thư mục tạm: {self.output_dir}")
