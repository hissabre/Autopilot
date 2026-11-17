# PyInstaller spec — builds a self-contained Autopilot folder (Python included).
# Run from the project root:  pyinstaller build/autopilot.spec --noconfirm
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821  (SPECPATH is injected by PyInstaller)

a = Analysis(
    [os.path.join(ROOT, "desktop", "main.py")],
    pathex=[ROOT],
    datas=[
        (os.path.join(ROOT, "templates"), "templates"),
        (os.path.join(ROOT, "fixtures"), "fixtures"),
        (os.path.join(ROOT, "desktop", "ui"), os.path.join("desktop", "ui")),
        (os.path.join(ROOT, "config.example.yaml"), "."),
    ],
    hiddenimports=collect_submodules("engine") + collect_submodules("desktop")
    + collect_submodules("webview") + ["pystray._win32"],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Autopilot",
    console=False,                       # no black terminal window
    icon=os.path.join(ROOT, "build", "icon.ico"),
    version=os.path.join(ROOT, "build", "version.txt"),
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Autopilot", upx=False)
