# -*- mode: python ; coding: utf-8 -*-
# Compilar con:  .venv\Scripts\python.exe -m PyInstaller main.spec
# Resultado: dist\PROVA.exe (un solo archivo, sin consola, con el logo como icono).
# Junto a PROVA.exe deben quedar menu_precios.xlsx y prova.png (el dueño los edita).


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # La pantalla de meseros y el icono de la ventana van dentro del ejecutable
    datas=[('templates', 'templates'), ('prova.ico', '.')],
    hiddenimports=['openpyxl', 'openpyxl.styles'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pandas', 'numpy', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PROVA',
    icon='prova.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
