"""Optional 2x page upscaling with waifu2x-ncnn-vulkan (runs on any Vulkan GPU, e.g. AMD).

Enabled by setting WAIFU2X_EXE to the executable's path; otherwise pages are used as-is.
Results are cached next to the original page as `up_<name>.png`.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def waifu2x_exe() -> Path | None:
    exe = os.environ.get("WAIFU2X_EXE")
    return Path(exe) if exe and Path(exe).is_file() else None


def upscaled_path(page_path: Path) -> Path:
    return page_path.with_name(f"up_{page_path.stem}.png")


def ensure_upscaled(page_path: Path) -> Path | None:
    """Return the upscaled image path (creating it if needed), or None if disabled/failed."""
    exe = waifu2x_exe()
    if exe is None:
        return None
    dst = upscaled_path(page_path)
    if dst.is_file():
        return dst
    tmp = dst.with_suffix(".tmp.png")
    cmd = [str(exe), "-i", str(page_path), "-o", str(tmp), "-n", "1", "-s", "2", "-m", str(exe.parent / "models-cunet")]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except (subprocess.SubprocessError, OSError):
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(dst)
    return dst
