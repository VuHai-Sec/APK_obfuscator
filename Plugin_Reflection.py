import os
import re

def add_inline_reflection(smali_file_path):
    # Lấy đường dẫn gốc của thư mục đang decompile (temp_xxx_apk)
    parts = smali_file_path.split(os.sep)
    try:
        smali_index = parts.index("smali")
        base_dir = os.sep.join(parts[:smali_index])
    except ValueError:
        return

    # Đường dẫn file Helper sẽ được tạo
    helper_dir = os.path.join(base_dir, "smali", "com", "obfuscator")
    helper_path = os.path.join(helper_dir, "ReflectionHelper.smali")

    # 1. Tạo class Helper 1 lần duy nhất cho toàn bộ APK
    if not os.path.exists(helper_path):
        os.makedirs(helper_dir, exist_ok=True)
        with open(helper_path, "w", encoding="utf-8") as f:
            f.write("""
.class public Lcom/obfuscator/ReflectionHelper;
.super Ljava/lang/Object;

.method public static getLength(Ljava/lang/String;)I
    .locals 4
    
    # Mã Reflection an toàn thực thi tại đây
    const-class v0, Ljava/lang/String;
    const-string v1, "length"
    const/4 v2, 0x0
    new-array v2, v2, [Ljava/lang/Class;
    invoke-virtual {v0, v1, v2}, Ljava/lang/Class;->getDeclaredMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;
    move-result-object v0
    
    const/4 v1, 0x0
    new-array v1, v1, [Ljava/lang/Object;
    invoke-virtual {v0, p0, v1}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v0
    
    check-cast v0, Ljava/lang/Integer;
    invoke-virtual {v0}, Ljava/lang/Integer;->intValue()I
    move-result v0
    
    return v0
.end method
""")

    # 2. Quét file smali hiện tại và đổi lời gọi hàm
    with open(smali_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Tìm lệnh: invoke-virtual {vX}, Ljava/lang/String;->length()I
    pattern = re.compile(r'invoke-virtual\s+\{([vp]\d+)\},\s+Ljava/lang/String;->length\(\)I')
    
    # Thay bằng: invoke-static {vX}, Lcom/obfuscator/ReflectionHelper;->getLength(Ljava/lang/String;)I
    new_content, count = pattern.subn(r'invoke-static {\1}, Lcom/obfuscator/ReflectionHelper;->getLength(Ljava/lang/String;)I', content)

    if count > 0:
        with open(smali_file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[Reflection Plugin] Đã chuyển đổi {count} lệnh sang Reflection an toàn tại: {os.path.basename(smali_file_path)}")
