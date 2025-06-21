# QView.spec
# -*- mode: python ; coding: utf-8 -*-
import os

# Define THIS_FOLDER right after imports
THIS_FOLDER = os.getcwd()

# Then define your my_data_files list (or directly use in Analysis)
my_data_files = [
    (os.path.join(THIS_FOLDER, 'data', 'qview_posts_data.json'), 'data'),
    (os.path.join(THIS_FOLDER, 'q_icon.ico'), '.'),
    (os.path.join(THIS_FOLDER, 'q_icon.png'), '.'), # Make sure this PNG name is exact
    (os.path.join(THIS_FOLDER, 'rwb_logo.png'), '.')
],

# --- Sanity Check Print (this will print when PyInstaller runs the spec file) ---
print("--- QView.spec: Processing Data Files ---")
for src, dest in my_data_files:
    print(f"Source: {src}, Exists: {os.path.exists(src)}, Destination: {dest}")
print("-----------------------------------------")
# --- End Sanity Check Print ---

a = Analysis(
    ['main.py'],
    pathex=[THIS_FOLDER], # You can use THIS_FOLDER here too, or keep your absolute path
    # pathex=['C:\\Users\\William\\QView'], # Your existing pathex
    binaries=[],
    datas=my_data_files, # Use the list defined above
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    # cipher=block_cipher,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='QView',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(THIS_FOLDER, 'q_icon.ico') # Use os.path.join for icon too
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas, # This should pick up my_data_files via the Analysis object
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QView',
)