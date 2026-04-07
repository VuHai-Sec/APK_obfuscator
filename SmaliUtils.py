import re
from dataclasses import dataclass
from itertools import count
from typing import Iterator, List, Optional, Sequence, Tuple


LOCALS_PATTERN = re.compile(r"^(?P<indent>\s*)\.locals\s+(?P<count>\d+)(?P<suffix>\s*(?:#.*)?)$")
REGISTERS_PATTERN = re.compile(r"^(?P<indent>\s*)\.registers\s+(?P<count>\d+)(?P<suffix>\s*(?:#.*)?)$")
CLASS_PATTERN = re.compile(r"^\s*\.class\b.*?\s(?P<descriptor>L[^;]+;)\s*$")
METHOD_DECL_PATTERN = re.compile(r"^\s*\.method\b.*\s(?P<name>[^\s(]+)(?P<descriptor>\([^\)]*\)\S+)")
METHOD_SIGNATURE_PATTERN = re.compile(r"\((?P<params>[^)]*)\)")
INVOKE_PATTERN = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<opcode>invoke-(?:virtual|static|direct)(?:/range)?)"
    r"\s+\{(?P<registers>[^}]*)\}"
    r"\s*,\s*(?P<owner>L[^;]+;)->(?P<method>[^\s(]+)(?P<descriptor>\([^\)]*\)\S+)"
    r"(?P<suffix>\s*(?:#.*)?)$"
)

DEBUG_DIRECTIVE_PREFIXES = (
    ".line",
    ".local",
    ".end local",
    ".restart local",
    ".prologue",
    ".epilogue",
    ".param",
    ".end param",
)
ANNOTATION_DIRECTIVE_PREFIXES = (
    ".annotation",
    ".end annotation",
    ".subannotation",
    ".end subannotation",
)
PAYLOAD_DIRECTIVE_PREFIXES = (
    ".packed-switch",
    ".end packed-switch",
    ".sparse-switch",
    ".end sparse-switch",
    ".array-data",
    ".end array-data",
)
PAYLOAD_INSTRUCTION_PREFIXES = (
    "packed-switch",
    "sparse-switch",
    "fill-array-data",
)

_LOCAL_LABEL_COUNTER = count(1)


@dataclass
class SmaliMethod:
    class_descriptor: str
    start_index: int
    end_index: int
    lines: List[str]
    register_line_index: int

    @property
    def header(self) -> str:
        return self.lines[0]

    @property
    def is_abstract(self) -> bool:
        header = f" {self.header.strip()} "
        return " abstract " in header

    @property
    def is_native(self) -> bool:
        header = f" {self.header.strip()} "
        return " native " in header

    @property
    def has_code(self) -> bool:
        return self.register_line_index != -1 and not self.is_abstract and not self.is_native

    @property
    def identifier(self) -> str:
        content, _ = split_line_content(self.header)
        match = METHOD_DECL_PATTERN.match(content)
        if match:
            return f"{self.class_descriptor}->{match.group('name')}{match.group('descriptor')}"
        return f"{self.class_descriptor}->{self.header.strip()}"


@dataclass
class InvokeInstruction:
    indent: str
    opcode: str
    registers_raw: str
    owner: str
    method_name: str
    descriptor: str
    suffix: str

    @property
    def is_range(self) -> bool:
        return self.opcode.endswith("/range")

    @property
    def base_opcode(self) -> str:
        return self.opcode.replace("/range", "")

    def build_line(
        self,
        new_opcode: Optional[str] = None,
        new_owner: Optional[str] = None,
        new_method_name: Optional[str] = None,
        new_descriptor: Optional[str] = None,
    ) -> str:
        opcode = new_opcode or self.opcode
        owner = new_owner or self.owner
        method_name = new_method_name or self.method_name
        descriptor = new_descriptor or self.descriptor
        return (
            f"{self.indent}{opcode} {{{self.registers_raw}}}, "
            f"{owner}->{method_name}{descriptor}{self.suffix}"
        )


def get_line_ending(line: str) -> str:
    # lấy kiểu kí tự xuống dòng mà code đang dùng
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    if line.endswith("\r"):
        return "\r"
    return "\n"


def split_line_content(line: str) -> Tuple[str, str]:
    line_ending = get_line_ending(line)
    if line.endswith(("\r\n", "\n", "\r")):
        return line[: -len(line_ending)], line_ending
    return line, line_ending


def classify_method_line(line: str) -> str:
    # phân loại method
    content, _ = split_line_content(line)
    stripped = content.strip()

    if not stripped:
        return "empty"
    if stripped.startswith("#"):
        return "comment"
    if LOCALS_PATTERN.match(content) or REGISTERS_PATTERN.match(content):
        return "register"
    if stripped.startswith(ANNOTATION_DIRECTIVE_PREFIXES):
        return "annotation"
    if stripped.startswith(DEBUG_DIRECTIVE_PREFIXES):
        return "debug"
    if stripped.startswith((".catch", ".catchall")):
        return "catch"
    if stripped.startswith(PAYLOAD_DIRECTIVE_PREFIXES):
        return "payload"
    if stripped.startswith(":"):
        return "label"
    if stripped.startswith("."):
        return "directive"
    return "instruction"


def extract_class_descriptor(lines: Sequence[str]) -> str:
    for line in lines:
        content, _ = split_line_content(line)
        match = CLASS_PATTERN.match(content)
        if match:
            return match.group("descriptor")
    return "Lunknown/Unknown;"


def find_register_directive_index(method_lines: Sequence[str]) -> int:
    # tìm dòng ".registers" hoặc ".locals"
    for index in range(1, len(method_lines) - 1):
        category = classify_method_line(method_lines[index])
        if category == "register":
            return index
    return -1


def iter_smali_methods(lines: Sequence[str], class_descriptor: str) -> Iterator[SmaliMethod]:
    # liệt kê các method 
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith(".method "):
            index += 1
            continue

        method_end = index + 1
        while method_end < len(lines) and not lines[method_end].lstrip().startswith(".end method"):
            method_end += 1

        if method_end >= len(lines):
            break

        method_lines = list(lines[index : method_end + 1])
        yield SmaliMethod(
            class_descriptor=class_descriptor,
            start_index=index,
            end_index=method_end,
            lines=method_lines,
            register_line_index=find_register_directive_index(method_lines),
        )
        index = method_end + 1


def descriptor_parameter_types(descriptor: str) -> List[str]:
    if not descriptor.startswith("("):
        return []

    params_end = descriptor.find(")")
    if params_end == -1:
        return []

    params = descriptor[1:params_end]
    types: List[str] = []
    index = 0

    while index < len(params):
        start = index
        while index < len(params) and params[index] == "[":
            index += 1

        if index >= len(params):
            break

        current = params[index]
        if current == "L":
            semicolon = params.find(";", index)
            if semicolon == -1:
                break
            index = semicolon + 1
        else:
            index += 1

        types.append(params[start:index])

    return types


def descriptor_return_type(descriptor: str) -> str:
    if ")" not in descriptor:
        return "V"
    return descriptor.split(")", 1)[1]


def register_width(smali_type: str) -> int:
    return 2 if smali_type in {"J", "D"} else 1


def count_parameter_registers(method_header: str) -> int:
    signature_match = METHOD_SIGNATURE_PATTERN.search(method_header)
    if not signature_match:
        return 0

    params = signature_match.group("params")
    is_static = " static " in f" {method_header.strip()} "
    register_count = 0 if is_static else 1

    index = 0
    while index < len(params):
        current = params[index]

        if current == "[":
            while index < len(params) and params[index] == "[":
                index += 1
            if index >= len(params):
                break
            if params[index] == "L":
                semicolon = params.find(";", index)
                if semicolon == -1:
                    break
                index = semicolon + 1
            else:
                index += 1
            register_count += 1
            continue

        if current == "L":
            semicolon = params.find(";", index)
            if semicolon == -1:
                break
            index = semicolon + 1
            register_count += 1
            continue

        register_count += register_width(current)
        index += 1

    return register_count


def replace_param_v_registers_with_p_aliases(
    line: str, first_param_register: int, parameter_register_count: int
) -> str:
    if parameter_register_count <= 0:
        return line

    result: List[str] = []
    index = 0
    in_string = False

    while index < len(line):
        char = line[index]

        if in_string:
            result.append(char)
            if char == "\\" and index + 1 < len(line):
                result.append(line[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "v":
            prev_char = line[index - 1] if index > 0 else ""
            digit_index = index + 1
            while digit_index < len(line) and line[digit_index].isdigit():
                digit_index += 1

            if digit_index > index + 1:
                next_char = line[digit_index] if digit_index < len(line) else ""
                if not (prev_char.isalnum() or prev_char in {"_", "$"}) and not (
                    next_char.isalnum() or next_char in {"_", "$"}
                ):
                    register_number = int(line[index + 1 : digit_index])
                    if first_param_register <= register_number < first_param_register + parameter_register_count:
                        result.append(f"p{register_number - first_param_register}")
                        index = digit_index
                        continue

        result.append(char)
        index += 1

    return "".join(result)


def is_simple_transformable_method(method_lines: Sequence[str]) -> bool:
    # điều kiện: Có dòng thanh ghi
    # Không phải abstract, native
    # không chứa các phép phức tạp như annotation, try-catch, payload đặc biệt
    register_line_index = find_register_directive_index(method_lines)
    if register_line_index == -1:
        return False

    header = f" {method_lines[0].strip()} "
    if " abstract " in header or " native " in header:
        return False

    for index in range(register_line_index + 1, len(method_lines) - 1):
        line = method_lines[index]
        category = classify_method_line(line)
        content, _ = split_line_content(line)
        stripped = content.strip()

        if category in {"annotation", "debug", "catch", "payload", "directive"}:
            return False
        if category == "instruction" and stripped.startswith(PAYLOAD_INSTRUCTION_PREFIXES):
            return False

    return True


def find_safe_instruction_indices(method_lines: Sequence[str], register_line_index: int) -> List[int]:
    # tìm mọi lệnh có vẻ an toàn
    # đảm bảo simple
    # có register_line_index hợp lệ
    if register_line_index == -1 or not is_simple_transformable_method(method_lines):
        return []

    indices: List[int] = []
    for index in range(register_line_index + 1, len(method_lines) - 1):
        if classify_method_line(method_lines[index]) == "instruction":
            indices.append(index)
    return indices


def find_safe_entry_insertion_index(method_lines: Sequence[str], register_line_index: int) -> int:
    # lấy 1 lệnh an toàn đầu tiên
    safe_indices = find_safe_instruction_indices(method_lines, register_line_index)
    if not safe_indices:
        return -1
    return safe_indices[0]


def ensure_extra_locals(
    method_lines: Sequence[str], extra_needed: int
) -> Optional[Tuple[List[str], List[str], int]]:
    # Kiểm tra xem có thể thêm extra_needed biến cục bộ không
    register_line_index = find_register_directive_index(method_lines)
    if register_line_index == -1 or extra_needed <= 0:
        # thấy dòng .registers hoặc .locals
        return None
    if not is_simple_transformable_method(method_lines):
        # hàm abstract / native
        return None
    #chuẩn bị dữ liệu để làm rối
    updated_lines = list(method_lines)
    directive_content, directive_ending = split_line_content(updated_lines[register_line_index])
    parameter_register_count = count_parameter_registers(updated_lines[0])

    locals_match = LOCALS_PATTERN.match(directive_content)
    if locals_match:
        # nếu file dùng .local:
        # kiểm tra số biến mới < 255
        # không cho số thanh ghi > 15
        original_locals = int(locals_match.group("count"))
        new_locals = original_locals + extra_needed
        if new_locals - 1 > 255:
            return None
        if parameter_register_count > 0 and new_locals + parameter_register_count - 1 > 15:
            return None

        first_param_register = original_locals
        for line_index in range(register_line_index + 1, len(updated_lines) - 1):
            updated_lines[line_index] = replace_param_v_registers_with_p_aliases(
                updated_lines[line_index], first_param_register, parameter_register_count
            )

        updated_lines[register_line_index] = (
            f'{locals_match.group("indent")}.locals {new_locals}'
            f'{locals_match.group("suffix")}{directive_ending}'
        )
        #duyệt code, thay v... thành p0, p1, p2
        # cập nhật .locals
        temp_registers = [f"v{original_locals + offset}" for offset in range(extra_needed)]
        return updated_lines, temp_registers, register_line_index

    # trường hợp .registers
    registers_match = REGISTERS_PATTERN.match(directive_content)
    if not registers_match:
        return None
    # Tìm số registers
    original_registers = int(registers_match.group("count"))
    original_locals = original_registers - parameter_register_count
    if original_locals < 0:
        # số register còn lại < 0 -> Bỏ
        return None

    # tương tự .locals
    new_locals = original_locals + extra_needed
    if new_locals - 1 > 255:
        return None
    if parameter_register_count > 0 and new_locals + parameter_register_count - 1 > 15:
        return None

    for line_index in range(register_line_index + 1, len(updated_lines) - 1):
        updated_lines[line_index] = replace_param_v_registers_with_p_aliases(
            updated_lines[line_index], original_locals, parameter_register_count
        )

    updated_lines[register_line_index] = (
        f'{registers_match.group("indent")}.locals {new_locals}'
        f'{registers_match.group("suffix")}{directive_ending}'
    )
    temp_registers = [f"v{original_locals + offset}" for offset in range(extra_needed)]
    # return: Code đã sửa, biến cục bộ tạm, vị trí.
    return updated_lines, temp_registers, register_line_index


def parse_invoke_instruction(line: str) -> Optional[InvokeInstruction]:
    # kiểm tra xem có phải dòng chứa invoke không
    match = INVOKE_PATTERN.match(line)
    if not match:
        return None
    # tách các thành phần trong opcode đó
    return InvokeInstruction(
        indent=match.group("indent"),
        opcode=match.group("opcode"),
        registers_raw=match.group("registers").strip(),
        owner=match.group("owner"),
        method_name=match.group("method"),
        descriptor=match.group("descriptor"),
        suffix=match.group("suffix"),
    )


def split_register_tokens(registers_raw: str) -> List[str]:
    if not registers_raw.strip():
        return []
    return [token.strip() for token in registers_raw.split(",") if token.strip()]


def is_safe_non_range_register_token(register_token: str) -> bool:
    if register_token.startswith("v") and register_token[1:].isdigit():
        return int(register_token[1:]) <= 15
    return False


def find_first_invoke_index(method_lines: Sequence[str], register_line_index: int) -> int:
    for index in find_safe_instruction_indices(method_lines, register_line_index):
        content, _ = split_line_content(method_lines[index])
        if parse_invoke_instruction(content):
            return index
    return -1


def find_last_exit_index(method_lines: Sequence[str], register_line_index: int) -> int:
    for index in reversed(find_safe_instruction_indices(method_lines, register_line_index)):
        content, _ = split_line_content(method_lines[index])
        stripped = content.strip()
        if stripped.startswith("return") or stripped.startswith("throw "):
            return index
    return -1


def find_indent_after_registers(method_lines: Sequence[str], register_line_index: int) -> str:
    #tính độ thụt đầu dòng
    safe_entry_index = find_safe_entry_insertion_index(method_lines, register_line_index)
    if safe_entry_index == -1:
        return "    "

    content, _ = split_line_content(method_lines[safe_entry_index])
    return content[: len(content) - len(content.lstrip())]


def next_local_label(prefix: str) -> str:
    return f":{prefix}_{next(_LOCAL_LABEL_COUNTER):04x}"


def method_hash_seed(value: str) -> int:
    # tạo seed
    return sum(ord(char) for char in value)


def parameter_register_tokens(parameter_types: Sequence[str]) -> Tuple[List[str], int]:
    tokens: List[str] = []
    next_register = 0

    for smali_type in parameter_types:
        tokens.append(f"p{next_register}")
        next_register += register_width(smali_type)

    return tokens, next_register


def build_invoke_register_operand(parameter_types: Sequence[str]) -> Tuple[str, bool]:
    tokens, total_words = parameter_register_tokens(parameter_types)
    if not tokens:
        return "{}", False

    if total_words > 5:
        return f"{{p0 .. p{total_words - 1}}}", True

    return "{%s}" % ", ".join(tokens), False
