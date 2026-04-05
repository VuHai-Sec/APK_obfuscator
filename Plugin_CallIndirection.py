import os
from typing import Optional

from ObfuscationContext import ObfuscationContext
from CallIndirectionRegistry import CallIndirectionRegistry
from SmaliUtils import (
    extract_class_descriptor,
    find_safe_instruction_indices,
    is_simple_transformable_method,
    iter_smali_methods,
    parse_invoke_instruction,
    split_register_tokens,
    is_safe_non_range_register_token,
    split_line_content,
)


MAX_WRAPS_PER_METHOD = 1
SKIPPED_CLASS_PREFIXES = (
    "Landroidx/",
    "Landroid/support/",
    "Lcom/google/",
    "Lkotlin/",
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


def _transform_method(
    method, registry: CallIndirectionRegistry, context: ObfuscationContext
):
    context.track_method(method.identifier)
    if not method.has_code or not is_simple_transformable_method(method.lines):
        return list(method.lines), 0

    updated_lines = list(method.lines)
    wrapped_calls = 0
    safe_indices = find_safe_instruction_indices(updated_lines, method.register_line_index)

    for line_index in safe_indices:
        if wrapped_calls >= MAX_WRAPS_PER_METHOD:
            break

        line_content, line_ending = split_line_content(updated_lines[line_index])
        invoke = parse_invoke_instruction(line_content)
        if invoke is None:
            continue
        register_tokens = split_register_tokens(invoke.registers_raw)
        if len(register_tokens) != 1:
            continue
        if not all(is_safe_non_range_register_token(token) for token in register_tokens):
            continue

        wrapper = registry.get_or_create_wrapper(invoke)
        if wrapper is None:
            continue

        updated_lines[line_index] = (
            invoke.build_line(
                new_opcode="invoke-static",
                new_owner=wrapper.helper_class,
                new_method_name=wrapper.method_name,
                new_descriptor=wrapper.wrapper_descriptor,
            )
            + line_ending
        )
        wrapped_calls += 1

    if wrapped_calls:
        context.mark_method_modified(method.identifier)

    return updated_lines, wrapped_calls


def add_call_indirection(
    smali_file_path: str, context: Optional[ObfuscationContext] = None
) -> None:
    active_context = context or _build_fallback_context(smali_file_path)
    if active_context.is_generated_helper(smali_file_path):
        return

    try:
        with open(smali_file_path, "r", encoding="utf-8", newline="") as handle:
            lines = handle.readlines()

        class_descriptor = extract_class_descriptor(lines)
        if class_descriptor.startswith(SKIPPED_CLASS_PREFIXES):
            return
        registry = CallIndirectionRegistry(active_context)
        output_lines = []
        cursor = 0
        total_wrapped_calls = 0

        for method in iter_smali_methods(lines, class_descriptor):
            output_lines.extend(lines[cursor : method.start_index])
            try:
                transformed_lines, wrapped_calls = _transform_method(method, registry, active_context)
            except Exception as exc:
                transformed_lines = list(method.lines)
                wrapped_calls = 0
                print(
                    f"[Call Indirection Plugin] Warning: skipped unsafe method in "
                    f"{os.path.basename(smali_file_path)}: {exc}"
                )
            output_lines.extend(transformed_lines)
            total_wrapped_calls += wrapped_calls
            cursor = method.end_index + 1

        output_lines.extend(lines[cursor:])

        if output_lines != lines:
            with open(smali_file_path, "w", encoding="utf-8", newline="") as handle:
                handle.writelines(output_lines)

        if total_wrapped_calls:
            active_context.record_api_calls_wrapped(total_wrapped_calls)
            print(
                f"[Call Indirection Plugin] Wrapped {total_wrapped_calls} API call(s) in: "
                f"{os.path.basename(smali_file_path)}"
            )
    except Exception as exc:
        print(
            f"[Call Indirection Plugin] Warning: kept original file due to transform failure in "
            f"{os.path.basename(smali_file_path)}: {exc}"
        )
