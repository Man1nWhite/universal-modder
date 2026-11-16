"""Exercise Windows restore handle policy without requiring a Windows runner."""
import ctypes
from ctypes import wintypes
from pathlib import Path

import pytest

from um import backup


class Call:
    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *args):
        return self.fn(*args)


def test_windows_directory_handles_block_delete_sharing_and_reparse_points(monkeypatch, tmp_path):
    opened, closed = [], []

    def open_handle(name, access, share, security, disposition, flags, template):
        opened.append((name, access, share, flags))
        return len(opened)

    def attributes(handle, kind, pointer, size):
        assert kind == 9
        # Mark the destination itself as a junction to ensure it is rejected.
        if opened[handle - 1][0] == str(tmp_path):
            ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))[0] = 0x400
        return 1

    class Kernel:
        CreateFileW = Call(open_handle)
        GetFileInformationByHandleEx = Call(attributes)
        CloseHandle = Call(lambda handle: closed.append(handle) or 1)

    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: Kernel(), raising=False)
    with pytest.raises(SystemExit):
        with backup._windows_parent(Path(tmp_path), "file", False):
            pytest.fail("a junction must not be used")
    assert opened
    assert all(share == 0x3 and flags & 0x00200000 for _, _, share, flags in opened)
    assert closed == list(range(len(opened), 0, -1))
