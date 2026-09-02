# PyInstaller spec for the SR Generator desktop build.
#
#   pip install -e ".[cloud,desktop]"
#   cd apps/web && STATIC_EXPORT=1 NEXT_PUBLIC_API_BASE=/api npm run build && cd ../..
#   pyinstaller sr_generator.spec --noconfirm
#
# Output: dist/SR Generator/SR Generator.exe  (a folder build - faster start and
# smaller than one-file, ship the whole folder / wrap it in an installer).

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

datas = [
    ("alembic", "alembic"),
    ("alembic.ini", "."),
    ("apps/web/out", "web"),
]
binaries = []
hiddenimports = [
    "sr.desktop",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
]

for pkg in ("alembic", "sr", "imageio_ffmpeg"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

datas += collect_data_files("soundfile")
binaries += collect_dynamic_libs("soundfile")


a = Analysis(
    ["sr/desktop.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "moto", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SR Generator",
    console=True,
    disable_windowed_traceback=False,
    icon="assets/icon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SR Generator",
)
