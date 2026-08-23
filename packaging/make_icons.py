#!/usr/bin/env python3
"""Render ytgrab's icon to PNG files for the desktop.

The app draws its window icon in code; this renders the same artwork at the
sizes a Linux icon theme expects, so the menu entry doesn't fall back to a
generic placeholder.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QGuiApplication, QPixmap, QPainter, QColor, QPolygonF

SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)


def render(size):
    """Draw at the target size rather than upscaling, so edges stay crisp."""
    s = size / 64.0
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)

    p.setBrush(QColor("#ff4b4b"))
    p.drawRoundedRect(QRectF(4 * s, 12 * s, 56 * s, 40 * s), 10 * s, 10 * s)

    p.setBrush(QColor("#ffffff"))
    p.drawPolygon(QPolygonF([
        QPointF(26 * s, 20 * s),
        QPointF(26 * s, 44 * s),
        QPointF(44 * s, 32 * s),
    ]))
    p.end()
    return pix


def main():
    out_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/icons")
    QGuiApplication(["-platform", "offscreen"])

    written = []
    for size in SIZES:
        out_dir = out_root / f"{size}x{size}" / "apps"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "ytgrab.png"
        if not render(size).save(str(target)):
            raise SystemExit(f"failed to write {target}")
        written.append(target)

    for path in written:
        print(f"  {path}  ({path.stat().st_size} B)")


if __name__ == "__main__":
    main()
