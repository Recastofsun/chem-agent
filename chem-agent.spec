# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# Собираем все внутренности pywebview и pythonnet
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')
pythonnet_datas, pythonnet_binaries, pythonnet_hiddenimports = collect_all('pythonnet')

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=webview_binaries + pythonnet_binaries,
    datas=[
        ('chem_agent/data/crc.db', 'chem_agent/data'),
        ('chem_agent/data/rules.yaml', 'chem_agent/data'),
        ('chem_agent/data/supplement.yaml', 'chem_agent/data'),
        ('static', 'static'),
        ('data', 'data'),
    ] + webview_datas + pythonnet_datas,
    hiddenimports=[
        'clr',
        'clr_loader',
        'pythonnet',
        'webview',
        'webview.platforms.edgechromium',
    ] + webview_hiddenimports + pythonnet_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'fastapi', 'uvicorn', 'pydantic', 'starlette', 'anyio',
        'tkinter', 'matplotlib',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'IPython', 'pytest', 'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Chem-Agent',
    debug=False,
    icon='C:\\work\\chem-agent\\chem-agent.ico',
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)