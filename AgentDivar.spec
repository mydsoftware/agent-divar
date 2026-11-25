# -*- mode: python ; coding: utf-8 -*-
"""پیکربندی PyInstaller برای نسخه پوشه‌ای ویندوز."""
from PyInstaller.utils.hooks import collect_all

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all("playwright")
openpyxl_datas, openpyxl_binaries, openpyxl_hiddenimports = collect_all("openpyxl")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=playwright_binaries + openpyxl_binaries,
    datas=playwright_datas + openpyxl_datas,
    hiddenimports=playwright_hiddenimports + openpyxl_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AgentDivar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AgentDivar",
)
