"""
sync_contracts.py — Schema-First 契约同步工具
═══════════════════════════════════════════════
从 protocol/src/schemas/*.schema.json 生成双端代码：
  - TypeScript 接口     → protocol/src/generated/  (json-schema-to-typescript)
    - Python Pydantic 模型 → ai-core/src/selrena/ipc_server/contracts/generated/  (datamodel-codegen)

用法：
  python scripts/sync_contracts.py            # 同步所有 schema
  python scripts/sync_contracts.py --check    # 仅校验是否需要同步（CI 可用）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

# ── 路径常量 ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "protocol" / "src" / "schemas"
TS_OUT_DIR = ROOT / "protocol" / "src" / "generated"
PY_OUT_DIR = ROOT / "core" / "ai-core" / "src" / "selrena" / "ipc_server" / "contracts" / "generated"
CHECKSUM_FILE = ROOT / "protocol" / "src" / "schemas" / ".checksum"


def compute_checksum(schema_dir: Path) -> str:
    """对所有 schema 文件内容做稳定哈希。"""
    h = hashlib.sha256()
    for path in sorted(schema_dir.glob("*.schema.json")):
        h.update(path.read_bytes())
    return h.hexdigest()


def needs_sync(schema_dir: Path) -> bool:
    """判断 schema 是否有变更。"""
    current = compute_checksum(schema_dir)
    if CHECKSUM_FILE.exists() and CHECKSUM_FILE.read_text().strip() == current:
        return False
    return True


def save_checksum(schema_dir: Path) -> None:
    CHECKSUM_FILE.write_text(compute_checksum(schema_dir))


def generate_typescript(schema_dir: Path, out_dir: Path) -> None:
    """调用 json-schema-to-typescript 生成 TS 接口。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    for schema_file in sorted(schema_dir.glob("*.schema.json")):
        stem = schema_file.stem.replace(".schema", "")
        out_file = out_dir / f"{stem}.ts"
        cmd = [
            "npx", "json-schema-to-typescript",
            str(schema_file),
            "-o", str(out_file),
            "--bannerComment", f"/* 自动生成 — 从 {schema_file.name} 生成，勿手动修改 */",
            "--style.singleQuote",
        ]
        print(f"  [TS] {schema_file.name} → {out_file.name}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        if result.returncode != 0:
            print(f"  ⚠ TS 生成失败: {result.stderr.strip()}", file=sys.stderr)
            # 退化方案：直接写入 type-only 文件
            _write_ts_fallback(schema_file, out_file)


def _write_ts_fallback(schema_file: Path, out_file: Path) -> None:
    """当 json-schema-to-typescript 不可用时，从 schema 手工提取简易类型。"""
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    title = schema.get("title", schema_file.stem)
    lines = [
        f"/* 自动生成 — 从 {schema_file.name} 退化生成，勿手动修改 */",
        f"// Schema: {schema.get('$id', '')}",
        f"// Description: {schema.get('description', '')}",
        "",
        f"/** {schema.get('description', title)} */",
        f"export interface {title} {{",
        f"  [key: string]: unknown;",
        "}",
        "",
    ]
    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [TS-fallback] {out_file.name}")


def generate_python(schema_dir: Path, out_dir: Path) -> None:
    """调用 datamodel-codegen 生成 Pydantic 模型。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    # 生成 __init__.py
    init_file = out_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# auto-generated contracts\n", encoding="utf-8")

    for schema_file in sorted(schema_dir.glob("*.schema.json")):
        stem = schema_file.stem.replace(".schema", "")
        module_name = _to_snake_case(stem)
        out_file = out_dir / f"{module_name}.py"
        cmd = [
            sys.executable, "-m", "datamodel_code_generator",
            "--input", str(schema_file),
            "--output", str(out_file),
            "--input-file-type", "jsonschema",
            "--output-model-type", "pydantic_v2.BaseModel",
            "--target-python-version", "3.12",
            "--use-standard-collections",
            "--use-union-operator",
            "--field-constraints",
        ]
        print(f"  [PY] {schema_file.name} → {module_name}.py")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        if result.returncode != 0:
            print(f"  ⚠ Python 生成失败: {result.stderr.strip()}", file=sys.stderr)
            _write_py_fallback(schema_file, out_file)


def _write_py_fallback(schema_file: Path, out_file: Path) -> None:
    """当 datamodel-codegen 不可用时，写入占位模型。"""
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    title = schema.get("title", "Model")
    lines = [
        f'"""自动生成 — 从 {schema_file.name} 退化生成，勿手动修改"""',
        "from __future__ import annotations",
        "from typing import Any",
        "from pydantic import BaseModel",
        "",
        "",
        f"class {title}(BaseModel):",
        f'    """Schema: {schema.get("$id", "")}"""',
        "",
    ]
    # 从 properties 提取字段
    for prop_name, prop_def in schema.get("properties", {}).items():
        py_type = _json_type_to_python(prop_def)
        required = prop_name in schema.get("required", [])
        default = "" if required else " = None"
        lines.append(f"    {prop_name}: {py_type}{default}")

    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  [PY-fallback] {out_file.name}")


def _json_type_to_python(prop: dict) -> str:
    """简易 JSON Schema type → Python type 映射。"""
    t = prop.get("type", "any")
    if isinstance(t, list):
        # ["string", "null"] → str | None
        non_null = [x for x in t if x != "null"]
        has_null = "null" in t
        base = _simple_type(non_null[0]) if non_null else "Any"
        return f"{base} | None" if has_null else base
    if t == "object":
        return "dict[str, Any]"
    if t == "array":
        return "list[Any]"
    return _simple_type(t)


def _simple_type(t: str) -> str:
    return {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}.get(t, "Any")


def _to_snake_case(name: str) -> str:
    import re
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Schema-First 契约同步")
    parser.add_argument("--check", action="store_true", help="仅校验是否需要同步")
    args = parser.parse_args()

    if not SCHEMA_DIR.exists() or not list(SCHEMA_DIR.glob("*.schema.json")):
        print("❌ 未找到 schema 文件", file=sys.stderr)
        sys.exit(1)

    if args.check:
        if needs_sync(SCHEMA_DIR):
            print("⚠ Schema 已变更，需要执行 sync_contracts.py")
            sys.exit(1)
        print("✅ 契约同步状态正常")
        return

    print(f"📜 扫描 Schema: {SCHEMA_DIR}")
    print()

    print("── 生成 TypeScript 接口 ──")
    generate_typescript(SCHEMA_DIR, TS_OUT_DIR)
    print()

    print("── 生成 Python Pydantic 模型 ──")
    generate_python(SCHEMA_DIR, PY_OUT_DIR)
    print()

    save_checksum(SCHEMA_DIR)
    print("✅ 契约同步完成")


if __name__ == "__main__":
    main()
