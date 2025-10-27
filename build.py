"""Helper script for producing a compact Windows executable with PyInstaller."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


EXCLUDED_MODULES = (
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtPrintSupport",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtXml",
    "PySide6.QtXmlPatterns",
)


def _build_arguments(args: argparse.Namespace) -> list[str]:
    project_root = Path(__file__).resolve().parent
    main_script = project_root / "src" / "main.py"

    if not main_script.exists():
        raise SystemExit(f"Cannot find entry point at {main_script}")

    options: list[str] = [
        "--noconfirm",
        "--windowed",
        "--onefile",
        "--clean",
        "--optimize",
        "2",
        "--name",
        args.name,
        f"--distpath={args.dist_dir}",
        f"--workpath={args.build_dir}",
        "--hidden-import=pytesseract.pytesseract",
    ]

    if args.strip:
        options.append("--strip")

    for module in EXCLUDED_MODULES:
        options.append(f"--exclude-module={module}")

    if not args.no_upx:
        upx_dir = args.upx_dir
        if upx_dir:
            options.append(f"--upx-dir={upx_dir}")
        else:
            detected_upx = shutil.which("upx")
            if detected_upx:
                options.append(f"--upx-dir={Path(detected_upx).parent}")

    if args.icon:
        icon_path = Path(args.icon)
        if not icon_path.exists():
            raise SystemExit(f"Icon not found: {icon_path}")
        options.append(f"--icon={icon_path}")

    if args.runtime_tmpdir:
        options.append(f"--runtime-tmpdir={args.runtime_tmpdir}")

    options.append(str(main_script))
    return options


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="ORC-WIN", help="Nama executable yang dihasilkan")
    parser.add_argument("--dist-dir", default="dist", help="Folder output PyInstaller")
    parser.add_argument("--build-dir", default="build", help="Folder kerja PyInstaller")
    parser.add_argument(
        "--strip",
        action="store_true",
        help="Hilangkan simbol debug untuk memperkecil ukuran (opsional, hanya di Windows terbaru)",
    )
    parser.add_argument(
        "--no-upx",
        action="store_true",
        help="Jangan gunakan kompresi UPX meski tersedia",
    )
    parser.add_argument(
        "--upx-dir",
        help="Lokasi folder UPX bila tidak ada di PATH",
    )
    parser.add_argument(
        "--icon",
        help="File icon .ico opsional untuk disematkan ke executable",
    )
    parser.add_argument(
        "--runtime-tmpdir",
        help="Override lokasi ekstraksi runtime PyInstaller untuk keamanan tambahan",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        from PyInstaller.__main__ import run as pyinstaller_run
    except ImportError as exc:  # pragma: no cover - depends on developer setup
        raise SystemExit(
            "PyInstaller belum terpasang. Jalankan 'pip install pyinstaller' di environment aktif."
        ) from exc

    arguments = _build_arguments(args)
    pyinstaller_run(arguments)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

