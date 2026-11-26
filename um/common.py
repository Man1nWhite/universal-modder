"""Small helpers shared by the subcommands: platform checks, WSL path mapping, subprocess, output."""
from __future__ import annotations

import json
import locale
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def is_windows() -> bool:
    return os.name == "nt"


def is_mac() -> bool:
    return sys.platform == "darwin"


def is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    return "microsoft" in platform.release().lower() or os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop")


def ps_exe() -> str:
    """Windows PowerShell. Falls back to its full path: an agent's PATH often lacks System32\\WindowsPowerShell\\v1.0."""
    name = "powershell.exe" if is_wsl() else "powershell"
    found = shutil.which(name)
    if found:
        return found
    if is_wsl():
        full = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    else:
        full = os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return full if os.path.exists(full) else name


def to_win(path: str | Path) -> str:
    """/mnt/c/Games/x -> C:\\Games\\x (WSL); paths that are already Windows paths pass through."""
    p = str(path).strip()
    if len(p) > 1 and p[1] == ":":
        # Already a drive path: normalise the drive letter and the separators and change nothing
        # else. `C:Games` is drive-relative on Windows, so it keeps its missing separator: adding
        # one would silently move the target to the drive root. (The old one-line conditional
        # nested three cases and ended in a branch that could never run.)
        return p[0].upper() + ":" + p[2:].replace("/", "\\")
    if p.startswith("/mnt/") and len(p) > 6 and p[6] in "/" and p[5].isalpha():
        return p[5].upper() + ":\\" + p[7:].replace("/", "\\")
    if p.startswith("/mnt/") and len(p) == 6 and p[5].isalpha():
        return p[5].upper() + ":\\"
    if is_wsl() and shutil.which("wslpath"):
        try:
            out = subprocess.run(["wslpath", "-w", p], capture_output=True, **text_utf8(), timeout=5).stdout.strip()
            return out or p
        except (OSError, subprocess.SubprocessError):
            return p
    return p


def to_posix(path: str | Path) -> str:
    """C:\\Games\\x -> /mnt/c/Games/x under WSL; unchanged elsewhere."""
    p = str(path).strip()
    if is_wsl() and len(p) > 1 and p[1] == ":":
        # Handle both C:\ and C:/ forms, and normalize drive letter
        drive = p[0].lower()
        rest = p[2:].lstrip("\\/").replace("\\", "/")
        return f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}"
    return p


def data_dir() -> Path:
    """Per-user state: backups, downloaded tools. Override with UM_HOME."""
    d = Path(os.environ.get("UM_HOME", Path.home() / ".universal-modder"))
    try:
        d.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            try:
                os.chmod(d, 0o700)
            except OSError:
                pass
    except OSError as e:
        die(f"cannot create data directory {d}: {e}")
    return d


def text_utf8(**kw) -> dict:
    """The kwargs for a command whose text output we parse.

    ffmpeg (for a path), git and gh (for a note title) print UTF-8 on Windows, and so does PowerShell
    once a script starts with PS_UTF8, while a bare `text=True` decodes with
    `locale.getpreferredencoding()`: cp936 on a Chinese Windows, cp1252 on a Western one. One CJK window
    title, save folder or game path is then enough to raise `UnicodeDecodeError` in subprocess's reader
    thread and take the command down (`um win ps`, `um video` on a 中文 path). `errors="replace"` keeps a
    wrong guess to one mojibake line instead of a traceback.
    """
    return dict(text=True, encoding="utf-8", errors="replace", **kw)


def text_console(**kw) -> dict:
    """The kwargs for Windows' own console tools (taskkill, reg), which print in the console's code page.

    That's the OEM code page unless `chcp` changed it. On CJK Windows it equals the locale codec (936, 932,
    949, 950), so these keep decoding with the locale, as before; `errors="replace"` turns a mismatch (a
    Western OEM code page, or WSL's UTF-8 locale) into replacement characters instead of a traceback.
    """
    return dict(text=True, encoding=locale.getpreferredencoding(False), errors="replace", **kw)


# Windows PowerShell 5.1 encodes what it prints to a pipe with [Console]::OutputEncoding, the console's code
# page (OEM, so 936 on a Chinese Windows). Start every -Command script with this so its output is UTF-8 and
# matches text_utf8(). Best-effort: with no console attached the setter throws, and the script still runs.
PS_UTF8 = "try{[Console]::OutputEncoding=[Text.Encoding]::UTF8}catch{};"


def run(cmd: list[str], check: bool = True, capture: bool = True, timeout: float | None = None, **kw) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=check, capture_output=capture, **text_utf8(), timeout=timeout, **kw)
    except FileNotFoundError:
        die(f"not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        die(f"{' '.join(map(str, cmd[:3]))}... timed out after {timeout}s")
    except subprocess.CalledProcessError as e:
        die(f"{' '.join(map(str, cmd[:3]))}... failed ({e.returncode}):\n{(e.stderr or e.stdout or '').strip()[-2000:]}")


def die(msg: str, code: int = 1):
    print(f"um: {msg}", file=sys.stderr)
    sys.exit(code)


def emit(obj, as_json: bool = False):
    if as_json or not isinstance(obj, str):
        print(json.dumps(obj, indent=2, default=str))
    else:
        print(obj)


MAX_DIMENSION = 16384


def parse_size(s: str) -> tuple[int, int]:
    """'64x26' -> (64, 26); '128' -> (128, 128). Validates positive, bounded dimensions."""
    if not isinstance(s, str) or not s.strip():
        die(f"invalid size {s!r}: expected 'N' or 'WxH' with positive integers")
    raw = s.strip().lower()
    try:
        if "x" in raw:
            a, b = raw.split("x", 1)
            w, h = int(a.strip()), int(b.strip())
        else:
            w = h = int(raw)
    except ValueError:
        die(f"invalid size {s!r}: expected 'N' or 'WxH' with positive integers")
    for dim, name in ((w, "width"), (h, "height")):
        if dim <= 0:
            die(f"invalid size {s!r}: {name} must be > 0, got {dim}")
        if dim > MAX_DIMENSION:
            die(f"invalid size {s!r}: {name} {dim} exceeds maximum {MAX_DIMENSION}")
    return w, h


def need(module: str, pip_name: str | None = None):
    try:
        return __import__(module)
    except ImportError:
        die(f"this command needs {pip_name or module}: `pip install {pip_name or module}` (or run through bin/um, which uses uv)")
