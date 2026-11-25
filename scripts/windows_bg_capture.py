"""
Windows Non-Intrusive Background Window Capture (vrc-character-forge)
---------------------------------------------------------------------
Inspired by ok-wuthering-waves / ok-script background capture principles.
Captures a background/occluded Windows application window by HWND using Win32
`PrintWindow(..., PW_RENDERFULLCONTENT)` without:
  - switching foreground focus (NEVER calls SetForegroundWindow / ShowWindow)
  - moving or touching the user's mouse cursor or keyboard
  - requiring any third-party Python packages (100% Python stdlib + ctypes)

Note:
  - Prefer Blender/Unity offscreen camera rendering whenever possible.
  - Use this script ONLY when inspecting an application UI window (e.g. VCC, ALCOM,
    VRCSDK panel, plugin UI) that has no offscreen render or MCP text API.
  - Minimized (Iconic) windows may stop DWM redrawing on Windows; keep target
    windows unminimized behind your active workspace instead of minimized.

Usage:
  # List candidate windows (read-only)
  python scripts/windows_bg_capture.py --list

  # Capture a background window matching title substring to PNG
  python scripts/windows_bg_capture.py --title "Unity" --out bg_unity.png

  # Capture by exact HWND (decimal or 0x hex)
  python scripts/windows_bg_capture.py --hwnd 0x001204A0 --out bg_window.png
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.platform != "win32":
    raise SystemExit("windows_bg_capture.py only runs on Windows.")

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Explicit 64-bit safe Win32 prototypes (prevents 32-bit handle truncation on x64 Windows)
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL
user32.IsWindow.argtypes = [wt.HWND]
user32.IsWindow.restype = wt.BOOL
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL
user32.IsIconic.argtypes = [wt.HWND]
user32.IsIconic.restype = wt.BOOL
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowRect.restype = wt.BOOL
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetWindowDC.argtypes = [wt.HWND]
user32.GetWindowDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
user32.PrintWindow.restype = wt.BOOL

gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteObject.restype = wt.BOOL
gdi32.DeleteDC.argtypes = [wt.HDC]
gdi32.DeleteDC.restype = wt.BOOL

# Enable Per-Monitor DPI awareness so captured dimensions match physical pixels
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

PW_RENDERFULLCONTENT = 0x00000002
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", wt.LONG),
        ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wt.DWORD * 3),
    ]


gdi32.GetDIBits.argtypes = [
    wt.HDC,
    wt.HBITMAP,
    wt.UINT,
    wt.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(BITMAPINFO),
    wt.UINT,
]
gdi32.GetDIBits.restype = ctypes.c_int


def list_windows(title_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        if title_filter and title_filter.lower() not in title.lower():
            return True

        rect = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return True

        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append(
            {
                "hwnd": hwnd,
                "hwnd_hex": hex(hwnd),
                "pid": pid.value,
                "title": title,
                "width": width,
                "height": height,
                "minimized": bool(user32.IsIconic(hwnd)),
            }
        )
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return results


def _write_png_rgb(path: Path, width: int, height: int, bgra_bytes: bytes) -> None:
    """Minimal dependency-free PNG writer converting top-down BGRA buffer to RGB PNG."""
    stride = width * 4
    raw_rows = bytearray()
    for y in range(height):
        raw_rows.append(0)  # PNG filter type 0 (None)
        row_start = y * stride
        row = bgra_bytes[row_start : row_start + stride]
        # Convert BGRA -> RGB slice-by-slice
        rgb_row = bytearray(width * 3)
        rgb_row[0::3] = row[2::4]  # R
        rgb_row[1::3] = row[1::4]  # G
        rgb_row[2::3] = row[0::4]  # B
        raw_rows.extend(rgb_row)

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw_rows), level=6)
    png_data = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", idat)
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_data)


def capture_hwnd_background(hwnd: int, out_path: str) -> Dict[str, Any]:
    """Capture a window by HWND without changing focus or touching user input."""
    if not user32.IsWindow(hwnd):
        return {"ok": False, "error": f"Invalid HWND: {hwnd}"}

    if user32.IsIconic(hwnd):
        return {
            "ok": False,
            "error": (
                "Target window is minimized (Iconic). Refusing to restore/activate it to avoid "
                "interrupting the user. Keep the window unminimized behind other windows for background capture."
            ),
            "hwnd": hwnd,
            "hwnd_hex": hex(hwnd),
        }

    rect = wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return {"ok": False, "error": "GetWindowRect failed."}

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return {"ok": False, "error": f"Invalid window dimensions: {width}x{height}"}

    hwnd_dc = user32.GetWindowDC(hwnd)
    if not hwnd_dc:
        return {"ok": False, "error": "GetWindowDC returned null."}

    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    old_obj = gdi32.SelectObject(mem_dc, bmp)

    try:
        ok_print = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
        if not ok_print:
            # Fallback to standard PrintWindow flags if PW_RENDERFULLCONTENT returns 0
            ok_print = user32.PrintWindow(hwnd, mem_dc, 0)
        if not ok_print:
            return {
                "ok": False,
                "error": (
                    "PrintWindow failed for this HWND (possibly protected/elevated window). "
                    "Do NOT steal focus; consider WGC or offscreen engine rendering instead."
                ),
                "hwnd": hwnd,
                "hwnd_hex": hex(hwnd),
            }

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # Negative height = top-down DIB
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buf = ctypes.create_string_buffer(width * height * 4)
        lines = gdi32.GetDIBits(mem_dc, bmp, 0, height, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
        if lines == 0:
            return {"ok": False, "error": "GetDIBits failed to read pixel buffer."}

        target = Path(out_path).resolve()
        _write_png_rgb(target, width, height, buf.raw)

        # Quick black-frame check (samples pixels to warn if DWM produced an empty frame)
        sample = buf.raw[:: max(4, (len(buf.raw) // 4000) * 4)]
        non_zero = any(b != 0 for b in sample)

        return {
            "ok": True,
            "method": "PrintWindow(PW_RENDERFULLCONTENT)",
            "focus_changed": False,
            "hwnd": hwnd,
            "hwnd_hex": hex(hwnd),
            "width": width,
            "height": height,
            "output_path": str(target),
            "warning": None if non_zero else "Captured frame appears completely black (window may be hardware-protected or suspended).",
        }
    finally:
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-intrusive Windows background window capture by HWND.")
    parser.add_argument("--list", action="store_true", help="List visible windows (read-only).")
    parser.add_argument("--title", type=str, default=None, help="Case-insensitive title substring filter.")
    parser.add_argument("--hwnd", type=str, default=None, help="Exact HWND (decimal or 0x hex).")
    parser.add_argument("--out", type=str, default=None, help="Output PNG path.")
    args = parser.parse_args()

    if args.list:
        wins = list_windows(args.title)
        print(json.dumps({"ok": True, "count": len(wins), "windows": wins}, ensure_ascii=False, indent=2))
        return 0

    if not args.out:
        parser.error("--out is required unless --list is used.")

    target_hwnd: Optional[int] = None
    if args.hwnd:
        target_hwnd = int(args.hwnd, 0)
    elif args.title:
        matches = [w for w in list_windows(args.title) if not w["minimized"]]
        if not matches:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"No unminimized window matching title '{args.title}'.",
                        "all_matches": list_windows(args.title),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        target_hwnd = matches[0]["hwnd"]
    else:
        parser.error("Provide --hwnd or --title.")

    res = capture_hwnd_background(target_hwnd, args.out)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
