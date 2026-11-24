"""Build dist/copybook-gui.exe (or the platform equivalent) with PyInstaller.

  uv sync
  uv run python tools/build_exe.py

Unlike zhbook-gui, the exe carries the whole copybook package and its
dependencies (pypdf, segno), so it runs without Python or this repository.
It still needs XeLaTeX and the KaiTi font (or another --font), plus a working
folder for data/ and output/: the folder containing the exe or one above it
that has data/makemeahanzi/, otherwise it asks once. "Download data" in the
app fetches Make Me a Hanzi into that folder.

Builds run as "copybook-gui.exe --run-cli <copybook arguments>", so a build
is a separate process (it can be stopped) and matches the command line.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "copybook-gui",
        "--paths", str(ROOT / "src"),
        "--collect-submodules", "copybook",
        "--collect-data", "copybook",  # aruco_4x4_1000.txt
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build" / "pyinstaller"),
        str(ROOT / "tools" / "gui_launcher.py"),
    ]
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
