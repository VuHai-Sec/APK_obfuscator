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
class ObfuscationContext:
    apk_name: str
    work_dir: str
    helper_package: str = "com/obf"
    helper_classes: Dict[str, str] = field(default_factory=dict)
    wrapper_signatures: Dict[Tuple[str, str, str, str], WrapperSpec] = field(default_factory=dict)
    stats: ObfuscationStats = field(default_factory=ObfuscationStats)
    primary_smali_dir: Optional[str] = None
    _scanned_smali_files: Set[str] = field(default_factory=set, repr=False)
    _seen_methods: Set[str] = field(default_factory=set, repr=False)
    _modified_methods: Set[str] = field(default_factory=set, repr=False)
    _generated_helper_paths: Set[str] = field(default_factory=set, repr=False)
    _label_counter: int = field(default=0, repr=False)
    _helper_counter: int = field(default=0, repr=False)

    def register_smali_root(self, smali_root: str) -> None:
        normalized = os.path.normpath(smali_root)
        if self.primary_smali_dir is None or os.path.basename(normalized) == "smali":
            self.primary_smali_dir = normalized

    def track_smali_file(self, file_path: str) -> None:
        normalized = os.path.normpath(file_path)
        if normalized not in self._scanned_smali_files:
            self._scanned_smali_files.add(normalized)
            self.stats.smali_files_scanned += 1

    def track_method(self, method_identifier: str) -> None:
        if method_identifier not in self._seen_methods:
            self._seen_methods.add(method_identifier)
            self.stats.methods_seen += 1

    def mark_method_modified(self, method_identifier: str) -> None:
        if method_identifier not in self._modified_methods:
            self._modified_methods.add(method_identifier)
            self.stats.methods_modified += 1

    def record_opaque_blocks(self, count: int = 1) -> None:
        self.stats.opaque_blocks_inserted += count

    def record_api_calls_wrapped(self, count: int = 1) -> None:
        self.stats.api_calls_wrapped += count

    def next_label(self, prefix: str = "obf") -> str:
        self._label_counter += 1
        return f":{prefix}_{self._label_counter:04x}"

    def next_wrapper_class(self) -> str:
        descriptor = f"L{self.helper_package}/W{self._helper_counter};"
        self._helper_counter += 1
        return descriptor

    def get_helper_output_root(self) -> str:
        if self.primary_smali_dir:
            return self.primary_smali_dir
        return os.path.join(self.work_dir, "smali")

    def register_helper_class(self, class_descriptor: str, file_path: str) -> None:
        if class_descriptor in self.helper_classes:
            return

        normalized = os.path.normpath(file_path)
        self.helper_classes[class_descriptor] = normalized
        self._generated_helper_paths.add(normalized)
        self.stats.helper_classes_created += 1

    def register_helper_method(self) -> None:
        self.stats.helper_methods_created += 1

    def is_generated_helper(self, file_path: str) -> bool:
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
