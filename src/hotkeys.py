"""Cross-version global hotkey helper built on the Win32 API."""
from __future__ import annotations

import itertools
import sys
from typing import Callable, Dict, Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal, Qt
from PySide6.QtGui import QGuiApplication, QKeyCombination, QKeySequence

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    WM_HOTKEY = 0x0312
    _MOD_ALT = 0x0001
    _MOD_CONTROL = 0x0002
    _MOD_SHIFT = 0x0004
    _MOD_WIN = 0x0008

    _user32 = ctypes.windll.user32


class _WinHotkeyFilter(QAbstractNativeEventFilter):
    """Bridge native WM_HOTKEY events back into Qt signals."""

    def __init__(self) -> None:
        super().__init__()
        self._callbacks: Dict[int, Callable[[], None]] = {}

    # ------------------------------------------------------------------
    # Registration bookkeeping
    # ------------------------------------------------------------------
    def add(self, hotkey_id: int, callback: Callable[[], None]) -> None:
        self._callbacks[hotkey_id] = callback

    def remove(self, hotkey_id: int) -> None:
        self._callbacks.pop(hotkey_id, None)

    # ------------------------------------------------------------------
    # Qt hook
    # ------------------------------------------------------------------
    def nativeEventFilter(self, event_type: str, message: int) -> Tuple[bool, int]:
        if not _IS_WINDOWS or event_type != "windows_generic_MSG":
            return False, 0

        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            callback = self._callbacks.get(msg.wParam)
            if callback is not None:
                callback()
                return True, 0
        return False, 0


class GlobalHotkey(QObject):
    """Minimal global shortcut manager backed by RegisterHotKey on Windows."""

    activated = Signal()

    _id_counter = itertools.count(1)
    _filter: Optional[_WinHotkeyFilter] = None

    def __init__(self, sequence: QKeySequence, *, auto_register: bool = False, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        if sequence.count() == 0:
            raise ValueError("GlobalHotkey requires a non-empty key sequence")

        self._sequence = sequence
        self._id = next(self._id_counter)
        self._registered = False
        self._native: Optional[Tuple[int, int]] = self._sequence_to_native(sequence) if self.is_supported() else None

        if auto_register and not self.setRegistered(True):
            raise RuntimeError("Unable to register global hotkey")

    # ------------------------------------------------------------------
    # Capability helpers
    # ------------------------------------------------------------------
    @classmethod
    def is_supported(cls) -> bool:
        """Return True when the current platform can register native hotkeys."""

        return _IS_WINDOWS

    # ------------------------------------------------------------------
    # Qt compatibility helpers
    # ------------------------------------------------------------------
    def shortcut(self) -> QKeySequence:
        return self._sequence

    def isRegistered(self) -> bool:  # noqa: N802 - Qt compatibility
        return self._registered

    def setRegistered(self, enabled: bool) -> bool:  # noqa: N802 - Qt compatibility
        if not self.is_supported():
            self._registered = False
            return False

        if enabled and self._registered:
            return True
        if not enabled and not self._registered:
            return True

        if enabled:
            assert self._native is not None
            app = QGuiApplication.instance()
            if app is None:
                raise RuntimeError("GlobalHotkey requires a running QGuiApplication")

            filter_ = self._ensure_filter(app)
            modifiers, vk = self._native
            filter_.add(self._id, self._emit_activation)
            success = bool(_user32.RegisterHotKey(None, self._id, modifiers, vk))
            if not success:
                filter_.remove(self._id)
                return False
            self._registered = True
            return True

        # disabling
        _user32.UnregisterHotKey(None, self._id)
        filter_ = self._filter
        if filter_ is not None:
            filter_.remove(self._id)
        self._registered = False
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _emit_activation(self) -> None:
        self.activated.emit()

    @classmethod
    def _ensure_filter(cls, app: QGuiApplication) -> _WinHotkeyFilter:
        if cls._filter is None:
            cls._filter = _WinHotkeyFilter()
            app.installNativeEventFilter(cls._filter)
        return cls._filter

    @staticmethod
    def _sequence_to_native(sequence: QKeySequence) -> Tuple[int, int]:
        if not _IS_WINDOWS:
            raise RuntimeError("Native hotkeys are only implemented for Windows")

        combination = QKeyCombination(sequence[0])
        modifiers = combination.keyboardModifiers()
        key = combination.key()

        native_modifiers = 0
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            native_modifiers |= _MOD_CONTROL
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            native_modifiers |= _MOD_SHIFT
        if modifiers & Qt.KeyboardModifier.AltModifier:
            native_modifiers |= _MOD_ALT
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            native_modifiers |= _MOD_WIN

        native_key = int(key) & 0x01FFFFFF
        if native_key == 0:
            raise ValueError("Unsupported key for global hotkey registration")

        return native_modifiers, native_key

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            self.setRegistered(False)
        except Exception:
            pass
