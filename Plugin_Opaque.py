import os
from typing import Optional

from ObfuscationContext import ObfuscationContext
from OpaqueTemplates import OPAQUE_TEMPLATES
from SmaliUtils import (
    ensure_extra_locals,
    extract_class_descriptor,
    find_indent_after_registers,
    find_safe_entry_insertion_index,
    get_line_ending,
    is_simple_transformable_method,
    iter_smali_methods,
    method_hash_seed,
    next_local_label,
)


def _build_fallback_context(smali_file_path: str) -> ObfuscationContext:
    smali_root = os.path.dirname(smali_file_path)
    while smali_root and not os.path.basename(smali_root).startswith("smali"):
        parent = os.path.dirname(smali_root)
        if parent == smali_root:
            break
        smali_root = parent

    work_dir = (
        os.path.dirname(smali_root)
        if os.path.basename(smali_root).startswith("smali")
        else os.path.dirname(smali_file_path)
    )
    context = ObfuscationContext(apk_name=os.path.basename(work_dir), work_dir=work_dir)
    if os.path.basename(smali_root).startswith("smali"):
        context.register_smali_root(smali_root)
    return context


def _build_label_factory(context: Optional[ObfuscationContext]):
    if context is None:
        return next_local_label
    return context.next_label


def _transform_method(method, context: ObfuscationContext):
    context.track_method(method.identifier)
    if not method.has_code or not is_simple_transformable_method(method.lines):
        return list(method.lines), 0

    seed = method_hash_seed(method.identifier)
    template = OPAQUE_TEMPLATES[seed % len(OPAQUE_TEMPLATES)]
    prepared = ensure_extra_locals(method.lines, template.temp_register_count)
    if prepared is None:
        return list(method.lines), 0

    updated_lines, temp_registers, register_line_index = prepared
    entry_index = find_safe_entry_insertion_index(updated_lines, register_line_index)
    if entry_index == -1:
        return list(method.lines), 0

    indent = find_indent_after_registers(updated_lines, register_line_index)
    line_ending = get_line_ending(updated_lines[register_line_index])
    label_factory = _build_label_factory(context)
    block_lines = template.build(indent, temp_registers[: template.temp_register_count], label_factory)
    if not block_lines:
        return list(method.lines), 0

    updated_lines[entry_index:entry_index] = [f"{line}{line_ending}" for line in block_lines]
    context.mark_method_modified(method.identifier)
    return updated_lines, 1


def add_opaque_predicates(smali_file_path: str, context: Optional[ObfuscationContext] = None) -> None:
    active_context = context or _build_fallback_context(smali_file_path)
    if active_context.is_generated_helper(smali_file_path):
        return

    try:
        with open(smali_file_path, "r", encoding="utf-8", newline="") as handle:
            lines = handle.readlines()

        class_descriptor = extract_class_descriptor(lines)
        output_lines = []
        cursor = 0
        total_blocks = 0

        for method in iter_smali_methods(lines, class_descriptor):
            output_lines.extend(lines[cursor : method.start_index])
            try:
                transformed_lines, inserted_blocks = _transform_method(method, active_context)
            except Exception as exc:
                transformed_lines = list(method.lines)
                inserted_blocks = 0
                print(
                    f"[Opaque Plugin] Warning: skipped unsafe method in "
                    f"{os.path.basename(smali_file_path)}: {exc}"
                )
            output_lines.extend(transformed_lines)
            total_blocks += inserted_blocks
            cursor = method.end_index + 1

        output_lines.extend(lines[cursor:])

        if output_lines != lines:
            with open(smali_file_path, "w", encoding="utf-8", newline="") as handle:
                handle.writelines(output_lines)

        if total_blocks:
            active_context.record_opaque_blocks(total_blocks)
            print(
                f"[Opaque Plugin] Inserted {total_blocks} opaque block(s) in: "
                f"{os.path.basename(smali_file_path)}"
            )
    except Exception as exc:
        print(
            f"[Opaque Plugin] Warning: kept original file due to transform failure in "
            f"{os.path.basename(smali_file_path)}: {exc}"
        )
