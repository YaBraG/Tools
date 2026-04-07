# -*- mode: python ; coding: utf-8 -*-

import json
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT_DIR = Path(SPECPATH).resolve().parents[1]
TOOLS_DIR = ROOT_DIR / "tools"
ASSETS_DIR = ROOT_DIR / "assets"
LICENSE_FILE = ROOT_DIR / "LICENSE"


def discover_tool_hidden_imports() -> list[str]:
    hidden_imports = set(collect_submodules("tools"))

    for manifest_path in sorted(TOOLS_DIR.glob("*/manifest.json")):
        with manifest_path.open("r", encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)

        entry_point = str(manifest.get("entry_point", ""))
        module_name = entry_point.partition(":")[0]
        if module_name:
            hidden_imports.add(module_name)

    return sorted(hidden_imports)


datas = [
    (
        str(manifest_path),
        str(Path("tools") / manifest_path.parent.name),
    )
    for manifest_path in sorted(TOOLS_DIR.glob("*/manifest.json"))
]

if ASSETS_DIR.exists():
    datas.append((str(ASSETS_DIR), "assets"))
else:
    raise FileNotFoundError(f"Assets directory was not found: {ASSETS_DIR}")

for required_ffmpeg_file in (
    ASSETS_DIR / "ffmpeg" / "bin" / "ffmpeg.exe",
    ASSETS_DIR / "ffmpeg" / "bin" / "ffprobe.exe",
    ASSETS_DIR / "ffmpeg" / "LICENSE",
    ASSETS_DIR / "ffmpeg" / "THIRD_PARTY_NOTICES.md",
):
    if not required_ffmpeg_file.exists():
        raise FileNotFoundError(
            f"Required bundled FFmpeg file was not found: {required_ffmpeg_file}"
        )

if LICENSE_FILE.exists():
    datas.append((str(LICENSE_FILE), "."))

icon_file = ASSETS_DIR / "app.ico"
version_file = ROOT_DIR / "build" / "version_info.txt"

a = Analysis(
    [str(ROOT_DIR / "app" / "main.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=discover_tool_hidden_imports(),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Tools",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon_file) if icon_file.exists() else None,
    version=str(version_file) if version_file.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Tools",
)
