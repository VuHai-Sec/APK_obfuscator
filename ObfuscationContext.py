import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple


@dataclass
class ObfuscationStats:
    smali_files_scanned: int = 0
    methods_seen: int = 0
    methods_modified: int = 0
    opaque_blocks_inserted: int = 0
    api_calls_wrapped: int = 0
    helper_classes_created: int = 0
    helper_methods_created: int = 0


@dataclass
class WrapperSpec:
    helper_class: str
    helper_path: str
    method_name: str
    wrapper_descriptor: str
    target_opcode: str
    target_owner: str
    target_method: str
    target_descriptor: str


@dataclass
class ObfuscationContext: # đối tượng lưu các thông tin về file đang chạy
    #1. Thông tin cơ bản của lần xử lý này
    apk_name: str
    work_dir: str
    # 2. Thông tin quản lý phần CI (helper class)
    helper_package: str = "com/obf"  # package để sinh helper class
    helper_classes: Dict[str, str] = field(default_factory=dict)
    primary_smali_dir: Optional[str] = None # nơi đặt helper class
    wrapper_signatures: Dict[Tuple[str, str, str, str], WrapperSpec] = field(default_factory=dict)
    #3. Thống kê các thông tin làm rối
    stats: ObfuscationStats = field(default_factory=ObfuscationStats)
    # 4. tập chứa các công việc đã làm (VD: Các hàm đươc làm rối, ...)
    _scanned_smali_files: Set[str] = field(default_factory=set, repr=False)
    _seen_methods: Set[str] = field(default_factory=set, repr=False)
    _modified_methods: Set[str] = field(default_factory=set, repr=False)
    _generated_helper_paths: Set[str] = field(default_factory=set, repr=False)
    # 5. Bộ đếm phục vụ sinh tên mới (tên lable, helper class)
    _label_counter: int = field(default=0, repr=False)
    _helper_counter: int = field(default=0, repr=False)

    def register_smali_root(self, smali_root: str) -> None:
        normalized = os.path.normpath(smali_root)
        if self.primary_smali_dir is None or os.path.basename(normalized) == "smali":
            self.primary_smali_dir = normalized
    
    def track_smali_file(self, file_path: str) -> None:
        # ghi nhận 1 file smali đã được quét
        normalized = os.path.normpath(file_path)
        if normalized not in self._scanned_smali_files:
            self._scanned_smali_files.add(normalized)
            self.stats.smali_files_scanned += 1

    def track_method(self, method_identifier: str) -> None:
        # ghi nhận 1 method đã được tìm thấy
        if method_identifier not in self._seen_methods:
            self._seen_methods.add(method_identifier)
            self.stats.methods_seen += 1

    def mark_method_modified(self, method_identifier: str) -> None:
        # ghi nhận 1 method bị sửa đổi
        if method_identifier not in self._modified_methods:
            self._modified_methods.add(method_identifier)
            self.stats.methods_modified += 1

    # record: Thống kê số lần biến đổi
    def record_opaque_blocks(self, count: int = 1) -> None:
        self.stats.opaque_blocks_inserted += count

    def record_api_calls_wrapped(self, count: int = 1) -> None:
        self.stats.api_calls_wrapped += count
    

    # next: Sinh label mới
    def next_label(self, prefix: str = "obf") -> str:
        self._label_counter += 1
        return f":{prefix}_{self._label_counter:04x}"

    def next_wrapper_class(self) -> str:
        descriptor = f"L{self.helper_package}/W{self._helper_counter};"
        self._helper_counter += 1
        return descriptor

    def get_helper_output_root(self) -> str:
        # xác định nơi ghi helper class
        if self.primary_smali_dir:
            return self.primary_smali_dir
        return os.path.join(self.work_dir, "smali")

    def register_helper_class(self, class_descriptor: str, file_path: str) -> None:
        # đăng kí helper class mới
        if class_descriptor in self.helper_classes:
            return

        normalized = os.path.normpath(file_path)
        self.helper_classes[class_descriptor] = normalized
        self._generated_helper_paths.add(normalized)
        self.stats.helper_classes_created += 1

    def register_helper_method(self) -> None:
        # đếm số helper method
        self.stats.helper_methods_created += 1

    def is_generated_helper(self, file_path: str) -> bool:
        # kiểm tra xem có phải helper được tạo ra không?
        return os.path.normpath(file_path) in self._generated_helper_paths

    def format_summary(self) -> str:
        stats = self.stats
        lines = [
            f"[*] Obfuscation summary for {self.apk_name}:",
            f"    - smali_files_scanned: {stats.smali_files_scanned}",
            f"    - methods_seen: {stats.methods_seen}",
            f"    - methods_modified: {stats.methods_modified}",
            f"    - opaque_blocks_inserted: {stats.opaque_blocks_inserted}",
            f"    - api_calls_wrapped: {stats.api_calls_wrapped}",
            f"    - helper_classes_created: {stats.helper_classes_created}",
            f"    - helper_methods_created: {stats.helper_methods_created}",
        ]
        return "\n".join(lines)
