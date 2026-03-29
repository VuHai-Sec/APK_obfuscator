import os
import random
import xml.etree.ElementTree as Xml
from xml.etree.ElementTree import Element

# ---------- CÁC HÀM HỖ TRỢ XỬ LÝ XML ----------

def indent_xml(element: Element, level=0):
    """Căn lề lại file XML sau khi đã xáo trộn để tránh lỗi format."""
    indentation = "\n" + level * "    "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indentation + "    "
        if not element.tail or not element.tail.strip():
            element.tail = indentation
        for child in element:
            indent_xml(child, level + 1)
        if not element.tail or not element.tail.strip():
            element.tail = indentation
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = indentation

def xml_elements_equal(one: Element, other: Element) -> bool:
    """Kiểm tra xem hai node XML có nội dung và thuộc tính giống hệt nhau không."""
    if type(one) != type(other): return False
    if one.tag != other.tag: return False
    
    if one.text and other.text:
        if one.text.strip() != other.text.strip(): return False
    elif one.text != other.text: return False
    
    if one.tail and other.tail:
        if one.tail.strip() != other.tail.strip(): return False
    elif one.tail != other.tail: return False
    
    if one.attrib != other.attrib: return False
    if len(one) != len(other): return False
    
    return all(xml_elements_equal(e1, e2) for e1, e2 in zip(one, other))

def remove_xml_duplicates(root: Element):
    """Đệ quy tìm và xóa các node trùng lặp có cùng node cha."""
    for element in root:
        remove_xml_duplicates(element)
        
    non_duplicates = []
    elements_to_remove = []
    
    for element in root:
        if any(xml_elements_equal(element, nd) for nd in non_duplicates):
            elements_to_remove.append(element)
        else:
            non_duplicates.append(element)
            
    for element_to_remove in elements_to_remove:
        root.remove(element_to_remove)

def scramble_xml_element(element: Element):
    """Đệ quy xáo trộn thứ tự các node con bên trong một node cha."""
    children = list(element)
    
    # Gỡ bỏ các node con hiện tại
    for child in children:
        element.remove(child)
        
    # Trộn ngẫu nhiên và gắn lại
    random.shuffle(children)
    for child in children:
        element.append(child)
        scramble_xml_element(child)

# ---------- HÀM THỰC THI CHÍNH CỦA PLUGIN ----------

def randomize_manifest(manifest_path):
    """
    Hàm entry point để gọi từ main.py.
    Áp dụng logic xáo trộn cấu trúc XML lên file AndroidManifest.
    """
    if not os.path.exists(manifest_path):
        print(f"[Manifest Plugin] Cảnh báo: Không tìm thấy {manifest_path}.")
        return

    try:
        # Thay đổi namespace mặc định thành 'obfuscation' thay vì 'android'
        Xml.register_namespace("obfuscation", "http://schemas.android.com/apk/res/android")
        
        # Parse file Manifest hiện tại
        manifest_tree = Xml.parse(manifest_path)
        manifest_root = manifest_tree.getroot()
        
        # Thực hiện các bước làm rối
        remove_xml_duplicates(manifest_root)
        scramble_xml_element(manifest_root)
        indent_xml(manifest_root)
        
        # Ghi đè lại file
        manifest_tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
        print(f"[Manifest Plugin] Đã xáo trộn cấu trúc file: {os.path.basename(manifest_path)}")
        
    except Exception as e:
        print(f"[Manifest Plugin] Lỗi trong quá trình xử lý XML: {e}")
