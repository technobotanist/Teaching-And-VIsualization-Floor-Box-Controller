from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def focus_obs_editor() -> bool:
    if sys.platform != "win32":
        return False

    user32 = ctypes.windll.user32
    matching_windows: list[int] = []
    enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit_window(window_handle: int, _: int) -> bool:
        if not user32.IsWindowVisible(window_handle):
            return True
        title_length = user32.GetWindowTextLengthW(window_handle)
        if title_length == 0:
            return True
        title = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(window_handle, title, title_length + 1)
        normalized_title = title.value.casefold()
        if "obs" in normalized_title and "projector" not in normalized_title:
            matching_windows.append(window_handle)
            return False
        return True

    user32.EnumWindows(enum_callback(visit_window), 0)
    if not matching_windows:
        return False

    window_handle = matching_windows[0]
    user32.ShowWindow(window_handle, 9)
    user32.SetForegroundWindow(window_handle)
    return True
