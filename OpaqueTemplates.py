from dataclasses import dataclass
from typing import Callable, List, Sequence


LabelFactory = Callable[[str], str]


@dataclass(frozen=True)
class OpaqueTemplate:
    name: str
    temp_register_count: int
    build: Callable[[str, Sequence[str], LabelFactory], List[str]]
    # indent: mức tụt đầu dòng
    # Sequece[str] : Các thanh ghi tạm
    # label_factory: Tạo label khác nhau


def _arithmetic_invariant(indent: str, temps: Sequence[str], label_factory: LabelFactory) -> List[str]:
    v0, v1, v2 = temps[:3]
    dead_label = label_factory("opq_dead")
    join_label = label_factory("opq_join")
    return [
        f"{indent}const/16 {v0}, 0x5",
        f"{indent}mul-int/lit8 {v1}, {v0}, 0x2",
        f"{indent}rem-int/lit8 {v2}, {v1}, 0x2",
        f"{indent}if-nez {v2}, {dead_label}",
        f"{indent}goto {join_label}",
        dead_label,
        f"{indent}const/16 {v0}, 0x0",
        f"{indent}nop",
        join_label,
        f"{indent}nop",
    ]


def _string_length_invariant(indent: str, temps: Sequence[str], label_factory: LabelFactory) -> List[str]:
    v0, v1, v2 = temps[:3]
    dead_label = label_factory("opq_dead")
    join_label = label_factory("opq_join")
    return [
        f'{indent}const-string {v0}, "obf"',
        f"{indent}invoke-virtual/range {{{v0} .. {v0}}}, Ljava/lang/String;->length()I",
        f"{indent}move-result {v1}",
        f"{indent}const/16 {v2}, 0x3",
        f"{indent}sub-int {v1}, {v1}, {v2}",
        f"{indent}if-nez {v1}, {dead_label}",
        f"{indent}goto {join_label}",
        dead_label,
        f"{indent}const/16 {v2}, 0x0",
        f"{indent}nop",
        join_label,
        f"{indent}nop",
    ]


def _class_equality_invariant(indent: str, temps: Sequence[str], label_factory: LabelFactory) -> List[str]:
    v0, v1, v2 = temps[:3]
    dead_label = label_factory("opq_dead")
    join_label = label_factory("opq_join")
    return [
        f"{indent}const-class {v0}, Ljava/lang/String;",
        f"{indent}const-class {v1}, Ljava/lang/String;",
        f"{indent}invoke-virtual/range {{{v0} .. {v1}}}, Ljava/lang/Object;->equals(Ljava/lang/Object;)Z",
        f"{indent}move-result {v2}",
        f"{indent}if-eqz {v2}, {dead_label}",
        f"{indent}goto {join_label}",
        dead_label,
        f"{indent}nop",
        f"{indent}goto {join_label}",
        join_label,
        f"{indent}nop",
    ]


def _array_length_invariant(indent: str, temps: Sequence[str], label_factory: LabelFactory) -> List[str]:
    v0, v1, v2 = temps[:3]
    dead_label = label_factory("opq_dead")
    join_label = label_factory("opq_join")
    return [
        f"{indent}const/16 {v0}, 0x1",
        f"{indent}const/16 {v1}, 0x2",
        f"{indent}filled-new-array/range {{{v0} .. {v1}}}, [I",
        f"{indent}move-result-object {v2}",
        f"{indent}invoke-static/range {{{v2} .. {v2}}}, Ljava/lang/reflect/Array;->getLength(Ljava/lang/Object;)I",
        f"{indent}move-result {v1}",
        f"{indent}const/16 {v0}, 0x2",
        f"{indent}sub-int {v1}, {v1}, {v0}",
        f"{indent}if-nez {v1}, {dead_label}",
        f"{indent}goto {join_label}",
        dead_label,
        f"{indent}const/16 {v2}, 0x0",
        f"{indent}nop",
        join_label,
        f"{indent}nop",
    ]


OPAQUE_TEMPLATES = [
    OpaqueTemplate("arithmetic_invariant", 3, _arithmetic_invariant),
    OpaqueTemplate("string_length_invariant", 3, _string_length_invariant),
    OpaqueTemplate("class_equality_invariant", 3, _class_equality_invariant),
    OpaqueTemplate("array_length_invariant", 3, _array_length_invariant),
]
