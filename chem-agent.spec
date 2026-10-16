# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run_server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('chem_agent/data/crc.db', 'chem_agent/data'),
        ('chem_agent/data/rules.yaml', 'chem_agent/data'),
        ('chem_agent/data/supplement.yaml', 'chem_agent/data'),
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
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
    [],
    exclude_binaries=True,
    name='chem-agent',
    debug=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='chem-agent',
)