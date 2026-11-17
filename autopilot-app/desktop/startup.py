"""'Start with Windows' via the per-user Run registry key (no admin rights needed)."""
import platform
import sys

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "Autopilot"


def _cmd():
    return f'"{sys.executable}" --minimized'


def is_enabled() -> bool:
    if platform.system() != "Windows":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            winreg.QueryValueEx(k, NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> bool:
    if platform.system() != "Windows" or not getattr(sys, "frozen", False):
        return False
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, _cmd())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except OSError:
                pass
    return True
