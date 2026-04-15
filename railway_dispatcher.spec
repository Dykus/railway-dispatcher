# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# === Собираем все данные, бинарники и скрытые импорты ===
datas = []
binaries = []
hiddenimports = []

for package in [
    'flask',
    'werkzeug',
    'jinja2',
    'itsdangerous',
    'click',
    'pandas',
    'openpyxl',
    'pystray',
    'PIL',
    'sqlite3',
]:
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

hiddenimports += collect_submodules('app')

# === Ручное добавление папок с шаблонами и статикой ===
def collect_files_from_dir(src_dir, dest_dir):
    files = []
    if os.path.exists(src_dir):
        for root, _, filenames in os.walk(src_dir):
            for f in filenames:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, src_dir)
                dest_path = os.path.join(dest_dir, os.path.dirname(rel_path))
                files.append((full_path, dest_path))
    return files

datas += collect_files_from_dir(os.path.join('app', 'templates'), 'templates')
datas += collect_files_from_dir(os.path.join('app', 'static'), 'static')

if os.path.exists('CHANGELOG.txt'):
    datas.append(('CHANGELOG.txt', '.'))

# Иконка (если есть)
if os.path.exists('icon.ico'):
    datas.append(('icon.ico', '.'))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RailwayDispatcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # ← меняем на False (без консоли)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',            # ← указываем иконку
)