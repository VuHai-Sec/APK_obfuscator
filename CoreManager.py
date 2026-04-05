import os
import shutil
import subprocess

from ObfuscationContext import ObfuscationContext


class AndroidObfuscator:
    def __init__(self, apk_path, output_dir="obfuscation_working_dir"):
        self.apk_path = apk_path
        self.output_dir = output_dir
        self.smali_dir = os.path.join(self.output_dir, "smali")
        self.keystore = "debug.keystore"
        self.ks_pass = "android"
        self.alias = "androiddebugkey"

    def create_context(self):
        return ObfuscationContext(
            apk_name=os.path.basename(self.apk_path),
            work_dir=self.output_dir,
        )

    def decompile(self):
        print(f"[+] Dang dich nguoc {os.path.basename(self.apk_path)}...")
        subprocess.run(
            ["apktool", "d", self.apk_path, "-o", self.output_dir, "-f", "--keep-broken-res"],
            check=True,
        )

    def _ensure_keystore(self):
        if not os.path.exists(self.keystore):
            print("[+] Dang tao keystore de ky APK...")
            cmd = [
                "keytool",
                "-genkey",
                "-v",
                "-keystore",
                self.keystore,
                "-storepass",
                self.ks_pass,
                "-alias",
                self.alias,
                "-keypass",
                self.ks_pass,
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "10000",
                "-dname",
                "CN=Android Debug,O=Android,C=US",
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def build_and_sign(self, output_apk):
        intermediate_apk = output_apk + ".unaligned"

        print("[+] Dang dong goi lai APK...")
        subprocess.run(["apktool", "b", self.output_dir, "-o", intermediate_apk], check=True)

        aligned_apk = output_apk + ".aligned"
        print("[+] Dang toi uu hoa bang zipalign...")
        subprocess.run(
            ["zipalign", "-f", "-v", "4", intermediate_apk, aligned_apk],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        self._ensure_keystore()
        print(f"[+] Dang ky APK: {os.path.basename(output_apk)}")
        sign_cmd = [
            "apksigner",
            "sign",
            "--ks",
            self.keystore,
            "--ks-pass",
            f"pass:{self.ks_pass}",
            "--out",
            output_apk,
            aligned_apk,
        ]
        subprocess.run(sign_cmd, check=True)

        for temp_file in [intermediate_apk, aligned_apk]:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def process_smali_files(self, plugin_function, context=None):
        if not os.path.exists(self.output_dir):
            return

        for item in os.listdir(self.output_dir):
            current_path = os.path.join(self.output_dir, item)
            if os.path.isdir(current_path) and item.startswith("smali"):
                if context is not None:
                    context.register_smali_root(current_path)
                for root, _, files in os.walk(current_path):
                    for file in files:
                        if file.endswith(".smali"):
                            file_path = os.path.join(root, file)
                            if context is not None:
                                context.track_smali_file(file_path)
                            try:
                                plugin_function(file_path, context)
                            except Exception as exc:
                                print(
                                    f"[CoreManager] Warning: plugin {plugin_function.__name__} "
                                    f"skipped {os.path.basename(file_path)} due to: {exc}"
                                )

    def cleanup(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
            print(f"[+] Da don dep thu muc tam: {self.output_dir}")
