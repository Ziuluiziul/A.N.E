"""Shims so vault I/O works on Windows (fcntl.flock, POSIX open flags)."""

from __future__ import annotations

import os
import sys
import types


def apply() -> None:
    if os.name != "nt":
        return
    if not hasattr(os, "O_CLOEXEC"):
        os.O_CLOEXEC = getattr(os, "O_NOINHERIT", 0)
    if not hasattr(os, "O_NOFOLLOW"):
        os.O_NOFOLLOW = 0
    if not hasattr(os, "O_DIRECTORY"):
        os.O_DIRECTORY = 0
    if "fcntl" not in sys.modules:
        sys.modules["fcntl"] = _build_fcntl()


def _build_fcntl() -> types.ModuleType:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    lockfile_fail_immediately = 0x00000001
    lockfile_exclusive_lock = 0x00000002
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ulong_ptr = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32

    class Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", ulong_ptr),
            ("InternalHigh", ulong_ptr),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    lock_file_ex = kernel32.LockFileEx
    lock_file_ex.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(Overlapped),
    ]
    lock_file_ex.restype = wintypes.BOOL
    unlock_file_ex = kernel32.UnlockFileEx
    unlock_file_ex.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(Overlapped),
    ]
    unlock_file_ex.restype = wintypes.BOOL

    mod = types.ModuleType("fcntl")
    mod.LOCK_SH = 1
    mod.LOCK_EX = 2
    mod.LOCK_NB = 4
    mod.LOCK_UN = 8

    def flock(fd: int, operation: int) -> None:
        handle = msvcrt.get_osfhandle(fd)
        overlapped = Overlapped()
        if operation & mod.LOCK_UN:
            ok = unlock_file_ex(handle, 0, 0xFFFFFFFF, 0xFFFFFFFF, ctypes.byref(overlapped))
            if not ok:
                raise OSError(ctypes.get_last_error(), "UnlockFileEx failed")
            return
        flags = 0
        if operation & mod.LOCK_EX:
            flags |= lockfile_exclusive_lock
        if operation & mod.LOCK_NB:
            flags |= lockfile_fail_immediately
        ok = lock_file_ex(handle, flags, 0, 0xFFFFFFFF, 0xFFFFFFFF, ctypes.byref(overlapped))
        if not ok:
            raise OSError(ctypes.get_last_error(), "LockFileEx failed")

    mod.flock = flock
    return mod


apply()
