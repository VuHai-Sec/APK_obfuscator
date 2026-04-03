import os
from typing import Optional, Set, Tuple

from ObfuscationContext import ObfuscationContext, WrapperSpec
from SmaliUtils import InvokeInstruction, build_invoke_register_operand, descriptor_parameter_types, descriptor_return_type


SUPPORTED_SIGNATURES: Set[Tuple[str, str, str, str]] = {
    ("invoke-virtual", "Ljava/lang/String;", "length", "()I"),
    ("invoke-virtual", "Ljava/lang/String;", "isEmpty", "()Z"),
    ("invoke-virtual", "Ljava/io/File;", "exists", "()Z"),
    ("invoke-virtual", "Ljava/io/File;", "isDirectory", "()Z"),
    ("invoke-virtual", "Ljava/lang/StringBuilder;", "toString", "()Ljava/lang/String;"),
}


class ReflectionRegistry:
    def __init__(self, context: ObfuscationContext):
        self.context = context

    def get_or_create_wrapper(self, invoke: InvokeInstruction) -> Optional[WrapperSpec]:
        if not self._is_supported(invoke):
            return None

        key = (invoke.base_opcode, invoke.owner, invoke.method_name, invoke.descriptor)
        cached = self.context.wrapper_signatures.get(key)
        if cached is not None:
            return cached

        wrapper_descriptor = self._build_wrapper_descriptor(invoke)
        if wrapper_descriptor is None:
            return None

        helper_class = self.context.next_wrapper_class()
        helper_path = self._descriptor_to_path(helper_class)
        wrapper = WrapperSpec(
            helper_class=helper_class,
            helper_path=helper_path,
            method_name="wrap",
            wrapper_descriptor=wrapper_descriptor,
            target_opcode=invoke.base_opcode,
            target_owner=invoke.owner,
            target_method=invoke.method_name,
            target_descriptor=invoke.descriptor,
        )

        try:
            os.makedirs(os.path.dirname(helper_path), exist_ok=True)
            with open(helper_path, "w", encoding="utf-8", newline="") as handle:
                handle.write(self._build_helper_class(wrapper))
        except OSError:
            return None

        self.context.wrapper_signatures[key] = wrapper
        self.context.register_helper_class(helper_class, helper_path)
        self.context.register_helper_method()
        return wrapper

    def _is_supported(self, invoke: InvokeInstruction) -> bool:
        if invoke.is_range:
            return False
        if invoke.owner.startswith(f"L{self.context.helper_package}/"):
            return False
        if invoke.method_name.startswith("<"):
            return False
        return (invoke.base_opcode, invoke.owner, invoke.method_name, invoke.descriptor) in SUPPORTED_SIGNATURES

    def _build_wrapper_descriptor(self, invoke: InvokeInstruction) -> Optional[str]:
        if invoke.base_opcode != "invoke-virtual":
            return None
        if descriptor_parameter_types(invoke.descriptor):
            return None
        return f"({invoke.owner}){descriptor_return_type(invoke.descriptor)}"

    def _build_helper_class(self, wrapper: WrapperSpec) -> str:
        wrapper_params = descriptor_parameter_types(wrapper.wrapper_descriptor)
        invoke_registers, use_range = build_invoke_register_operand(wrapper_params)
        invoke_opcode = f"{wrapper.target_opcode}/range" if use_range else wrapper.target_opcode
        return_type = descriptor_return_type(wrapper.wrapper_descriptor)

        body_lines = [
            f"    {invoke_opcode} {invoke_registers}, "
            f"{wrapper.target_owner}->{wrapper.target_method}{wrapper.target_descriptor}",
        ]

        locals_count = 0
        if return_type == "V":
            body_lines.append("    return-void")
        elif return_type in {"J", "D"}:
            locals_count = 2
            body_lines.extend(["    move-result-wide v0", "    return-wide v0"])
        elif return_type.startswith("L") or return_type.startswith("["):
            locals_count = 1
            body_lines.extend(["    move-result-object v0", "    return-object v0"])
        else:
            locals_count = 1
            body_lines.extend(["    move-result v0", "    return v0"])

        return "\n".join(
            [
                f".class public final {wrapper.helper_class}",
                ".super Ljava/lang/Object;",
                "",
                ".method private constructor <init>()V",
                "    .locals 0",
                "    invoke-direct {p0}, Ljava/lang/Object;-><init>()V",
                "    return-void",
                ".end method",
                "",
                f".method public static {wrapper.method_name}{wrapper.wrapper_descriptor}",
                f"    .locals {locals_count}",
                *body_lines,
                ".end method",
                "",
            ]
        ) + "\n"

    def _descriptor_to_path(self, class_descriptor: str) -> str:
        relative = class_descriptor[1:-1].replace("/", os.sep) + ".smali"
        return os.path.join(self.context.get_helper_output_root(), relative)
