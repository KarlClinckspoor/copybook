"""Regenerate src/copybook/aruco_4x4_1000.txt from OpenCV.

One line per marker ID (0-999): the 16 inner data bits, row by row from the
top-left, 1 = white module. The black one-module border is implicit.
Run with: uv run python tools/make_aruco_table.py
"""

from pathlib import Path

import cv2

OUT = Path(__file__).resolve().parents[1] / "src" / "copybook" / "aruco_4x4_1000.txt"


def main() -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000)
    lines = []
    for marker_id in range(1000):
        image = dictionary.generateImageMarker(marker_id, 6)  # one pixel per module
        inner = image[1:5, 1:5]
        lines.append("".join("1" if v > 127 else "0" for v in inner.flatten()))
    OUT.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
