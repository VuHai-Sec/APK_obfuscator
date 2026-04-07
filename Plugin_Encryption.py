import base64
import os
import re
from typing import List, Optional, Sequence, Tuple

from ObfuscationContext import ObfuscationContext
from SmaliUtils import (
    ensure_extra_locals,
    extract_class_descriptor,
    find_register_directive_index,
    find_safe_instruction_indices,
    get_line_ending,
    is_simple_transformable_method,
    iter_smali_methods,
    split_line_content,
)


EXTRA_LOCAL_COUNT = 3
UTF8_LITERAL = "UTF-8"

CONST_STRING_PATTERN = re.compile(
    r'^(?P<indent>\s*)'
    r'(?P<opcode>const-string(?:/jumbo)?)'
    r'\s+(?P<register>[vp]\d+)'
    r'\s*,\s*"(?P<literal>(?:\\.|[^"\\])*)"'
    r'(?P<suffix>\s*(?:#.*)?)$'
)
CLASS_DESCRIPTOR_PATTERN = re.compile(r"^\[*L[\w$/-]+;$")
PACKAGE_LIKE_PATTERN = re.compile(r"^[A-Za-z_][\w$]*(?:[./][A-Za-z_][\w$-]*)+$")


def encode_string(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def contains_surrogate_codepoint(value: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def smali_unescape_string(literal: str) -> str:
    # xử lý các ký tự escape trước khi mã hoá
    result: List[str] = []
    index = 0

    while index < len(literal):
        char = literal[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        if index + 1 >= len(literal):
            raise ValueError("Dangling escape in smali string literal")

        escape = literal[index + 1]
        if escape == "n":
            result.append("\n")
            index += 2
        elif escape == "r":
            result.append("\r")
            index += 2
        elif escape == "t":
            result.append("\t")
            index += 2
        elif escape == "b":
            result.append("\b")
            index += 2
        elif escape == "f":
            result.append("\f")
            index += 2
        elif escape in {'"', "'", "\\"}:
            result.append(escape)
            index += 2
        elif escape == "u":
            hex_value = literal[index + 2 : index + 6]
            if len(hex_value) != 4 or not re.fullmatch(r"[0-9a-fA-F]{4}", hex_value):
                raise ValueError("Invalid unicode escape in smali string literal")
            result.append(chr(int(hex_value, 16)))
            index += 6
        else:
            result.append(escape)
            index += 2

    return "".join(result)


def should_encrypt_string(value: str) -> bool:
    # kiểm duyệt, tránh mã hoá những chuỗi nguy hiểm
    if not value or value.isspace():
        return False
    if value == UTF8_LITERAL:
        return False
    if CLASS_DESCRIPTOR_PATTERN.match(value):
        return False
    if contains_surrogate_codepoint(value):
        return False
    if value.startswith(("Landroid/", "Ljava/", "Lkotlin/", "Ldalvik/")):
        return False
    if value.startswith(("android.", "androidx.", "java.", "javax.", "kotlin.", "dalvik.")):
        return False
    if value.startswith(("android.intent.", "intent.action.", "intent.category.", "intent.extra.")):
        return False
    if value.startswith(("@", "?attr/", "?android:", "res/")):
        return False
    if PACKAGE_LIKE_PATTERN.match(value) and ("/" in value or "." in value):
        return False
    return True


def replace_const_string_with_runtime_decode(
    # thêm runtime-decode
    line: str, temp_registers: Tuple[str, str, str]
) -> Optional[List[str]]:
    line_content, line_ending = split_line_content(line)
    match = CONST_STRING_PATTERN.match(line_content)
    if not match:
        return None

    try:
        original_value = smali_unescape_string(match.group("literal"))
    except ValueError:
        return None

    if not should_encrypt_string(original_value):
        return None

    try:
        encoded_value = encode_string(original_value)
    except UnicodeEncodeError:
        return None

    string_register, bytes_register, charset_register = temp_registers
    indent = match.group("indent")
    opcode = match.group("opcode")
    target_register = match.group("register")
    suffix = match.group("suffix")

    return [
        # chia 16 tránh lỗi thanh ghi
        f'{indent}{opcode} {string_register}, "{encoded_value}"{suffix}{line_ending}',
        f"{indent}const/16 {bytes_register}, 0x0{line_ending}",
        (
            f"{indent}invoke-static/range "
            f"{{{string_register} .. {bytes_register}}}, "
            f"Landroid/util/Base64;->decode(Ljava/lang/String;I)[B{line_ending}"
        ),
        f"{indent}move-result-object {bytes_register}{line_ending}",
        f"{indent}new-instance {string_register}, Ljava/lang/String;{line_ending}",
        f'{indent}const-string {charset_register}, "{UTF8_LITERAL}"{line_ending}',
        (
            f"{indent}invoke-direct/range "
            f"{{{string_register} .. {charset_register}}}, "
            f"Ljava/lang/String;-><init>([BLjava/lang/String;)V{line_ending}"
        ),
        f"{indent}move-object/16 {target_register}, {string_register}{line_ending}",
    ]


def transform_method(method_lines: Sequence[str]) -> Tuple[List[str], int]:
    # kiểm tra method có đủ an toàn để biến đổi khôgn?
    register_line_index = find_register_directive_index(method_lines)
    if register_line_index == -1 or not is_simple_transformable_method(method_lines):
        return list(method_lines), 0

    # Lấy các biến tạm mới
    prepared = ensure_extra_locals(method_lines, EXTRA_LOCAL_COUNT)
    if prepared is None:
        return list(method_lines), 0

    # lấy danh sách lệnh an toàn
    prepared_lines, temp_registers, register_line_index = prepared
    safe_instruction_indices = set(find_safe_instruction_indices(prepared_lines, register_line_index))
    if not safe_instruction_indices:
        return list(method_lines), 0

    transformed_lines: List[str] = prepared_lines[: register_line_index + 1]
    replacements = 0

    for line_index in range(register_line_index + 1, len(prepared_lines) - 1):
        line = prepared_lines[line_index]
        if line_index not in safe_instruction_indices:
            transformed_lines.append(line)
            continue

        try:
            replacement = replace_const_string_with_runtime_decode(
                line, (temp_registers[0], temp_registers[1], temp_registers[2])
            )
        except Exception:
            replacement = None

        if replacement is None:
            transformed_lines.append(line)
            continue

        transformed_lines.extend(replacement)
        replacements += 1

    transformed_lines.append(prepared_lines[-1])
    # thêm giải mã runtime vào code

    if replacements == 0:
        return list(method_lines), 0

    return transformed_lines, replacements


def encrypt_strings(smali_file_path: str, context: Optional[ObfuscationContext] = None) -> None:
    # kiểm tra xem đây có phải helper do công cụ khác sinh không?
    if context is not None and context.is_generated_helper(smali_file_path):
        return

    try:
        # đọc toàn bộ file
        with open(smali_file_path, "r", encoding="utf-8", newline="") as handle:
            lines = handle.readlines()
        method_identifiers = {}
        if context is not None:
            # lấy descriptor của class
            class_descriptor = extract_class_descriptor(lines)
            method_identifiers = {
                #duyệt từng method
                method.start_index: method.identifier 
                for method in iter_smali_methods(lines, class_descriptor)
            }
        else:
            class_descriptor = extract_class_descriptor(lines)

        output_lines: List[str] = []
        cursor = 0
        total_replacements = 0
        #duyệt từng method
        for method in iter_smali_methods(lines, class_descriptor):
            output_lines.extend(lines[cursor : method.start_index])
            method_identifier = method_identifiers.get(method.start_index)
            if context is not None and method_identifier is not None:
                context.track_method(method_identifier)

            # với mỗi method, gọi transform_method
            try:
                transformed_block, replacement_count = transform_method(method.lines)
            except Exception as exc:
                transformed_block = list(method.lines)
                replacement_count = 0
                print(
                    f"[Encrypt Plugin] Warning: skipped unsafe method in "
                    f"{os.path.basename(smali_file_path)}: {exc}"
                )

            output_lines.extend(transformed_block)
            total_replacements += replacement_count
            if context is not None and replacement_count and method_identifier is not None:
                context.mark_method_modified(method_identifier)
            cursor = method.end_index + 1

        output_lines.extend(lines[cursor:])

        if output_lines != lines:
            with open(smali_file_path, "w", encoding="utf-8", newline="") as handle:
                handle.writelines(output_lines)

        if total_replacements:
            print(
                f"[Encrypt Plugin] Runtime-encrypted {total_replacements} string(s) in: "
                f"{os.path.basename(smali_file_path)}"
            )
    except Exception as exc:
        print(
            f"[Encrypt Plugin] Warning: kept original file due to transform failure in "
            f"{os.path.basename(smali_file_path)}: {exc}"
        )
