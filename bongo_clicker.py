# -*- coding: utf-8 -*-
"""
BongoCatClicker - autoclicker for the Steam game Bongo Cat.
Python standard library only (tkinter + ctypes). Windows 10/11.
"""

import ctypes
import json
import os
import random
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import ttk, messagebox

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "settings.json")
ICON_ICO = os.path.join(APP_DIR, "assets", "cat_icon.ico")
GOAL = 1_000_000

# ---------------------------------------------------------------- WinAPI

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def _enable_dpi_awareness():
    """Per-Monitor v2 -> v1 -> system-aware -> nothing. Keeps click-area
    coordinates accurate across monitors with different scaling."""
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


_enable_dpi_awareness()

try:
    # Gives the window its own taskbar identity instead of a shared,
    # possibly mis-cached pythonw.exe icon.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BongoCatClicker.App")
except Exception:
    pass

# Single-instance guard: a second launch focuses the existing window instead
# of opening a confusing duplicate (two clickers fighting over one hotkey).
ERROR_ALREADY_EXISTS = 183
kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE
user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
user32.FindWindowW.restype = wintypes.HWND
_mutex = kernel32.CreateMutexW(None, False, "BongoCatClicker_SingleInstance")
ALREADY_RUNNING = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF = {
    "left":   (0x0002, 0x0004),
    "right":  (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}

KEYEVENTF_KEYUP = 0x0002
MAPVK_VK_TO_VSC = 0

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
VK_F6, VK_F7, VK_ESCAPE = 0x75, 0x76, 0x1B

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.WindowFromPoint.argtypes = (wintypes.POINT,)
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND
GA_ROOT = 2


def point_is_over_window(x, y, target_hwnd):
    """True if (x, y) is over target_hwnd or one of its child widgets - used
    to stop clicks from ever landing on the clicker's own window. Both sides
    are normalized through GetAncestor(GA_ROOT) because tkinter's
    winfo_id() returns a child widget's HWND, not the real framed window."""
    if not target_hwnd:
        return False
    hwnd = user32.WindowFromPoint(wintypes.POINT(x, y))
    if not hwnd:
        return False
    target_root = user32.GetAncestor(target_hwnd, GA_ROOT) or target_hwnd
    return hwnd == target_root or user32.GetAncestor(hwnd, GA_ROOT) == target_root


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.LONG)
user32.SetWindowLongW.restype = wintypes.LONG


def real_top_level_hwnd(tk_widget):
    """See point_is_over_window - normalizes winfo_id() to the real window."""
    raw = tk_widget.winfo_id()
    return user32.GetAncestor(raw, GA_ROOT) or raw


def make_click_through(hwnd):
    """Window stays visible, but clicks pass straight through it."""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)


def send_inputs(items):
    n = len(items)
    if n == 0:
        return 0
    arr = (INPUT * n)(*items)
    return user32.SendInput(n, arr, ctypes.sizeof(INPUT))


def mouse_event_input(flag):
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi = MOUSEINPUT(0, 0, 0, flag, 0, 0)
    return inp


def key_input(vk, up=False):
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_KEYUP if up else 0
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return inp


def cursor_pos():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor_pos(x, y):
    user32.SetCursorPos(int(x), int(y))


def geometry_string(w, h, x, y):
    """Tk "WxH+X+Y" geometry - plain %d breaks on negative X/Y."""
    sx = "+%d" % x if x >= 0 else "-%d" % (-x)
    sy = "+%d" % y if y >= 0 else "-%d" % (-y)
    return "%dx%d%s%s" % (w, h, sx, sy)


def virtual_screen():
    return (user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ---------------------------------------------------------------- keys

NUMPAD_VK = {str(i): 0x60 + i for i in range(10)}
PHANTOM_VK = {"F%d" % n: 0x7C + (n - 13) for n in range(13, 25)}   # F13..F24

# Normal typing keys, for the typing auto-pause. The clicker itself only
# ever sends Numpad/F13-F24, so these reflect only the user's real presses.
TYPING_VKS = tuple(
    list(range(0x41, 0x5B)) + list(range(0x30, 0x3A)) +
    [0x20, 0x0D, 0x08, 0x09, 0x1B] + list(range(0x25, 0x29)) + list(range(0xBA, 0xE0))
)


def is_typing():
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in TYPING_VKS)


# ---------------------------------------------------------------- engine

class ClickerEngine:
    """Runs on its own thread; talks to the GUI only through plain,
    lock-protected attributes - it never touches tkinter directly, since Tk
    is not thread-safe."""

    def __init__(self):
        self.cfg = {}
        self.running = threading.Event()
        self.thread = None
        # A monotonic counter instead of a shared stop flag: a thread only
        # keeps running while its own generation is still current. This is
        # what makes stop()+start() race-proof - a stale thread that hasn't
        # noticed it should exit yet can never be "un-stopped" by a
        # following start() the way a shared Event could be (that used to
        # let an old thread with old settings, e.g. mouse mode, keep running
        # alongside a new one, doubling up on clicks/keys and confusing the
        # Start/Stop buttons until the app was restarted).
        self.generation = 0
        self.lock = threading.Lock()
        self.clicks = 0
        self.keys = 0
        self.started_at = None
        self.paused_by_user = False

    def start(self, cfg):
        if self.running.is_set():
            return
        if self.thread and self.thread.is_alive():
            self.thread.join()   # no timeout - never let two generations overlap
        self.generation += 1
        my_gen = self.generation
        self.cfg = cfg
        self.running.set()
        self.started_at = time.time()
        self.thread = threading.Thread(target=self._loop, args=(my_gen,), daemon=True)
        self.thread.start()

    def stop(self):
        self.generation += 1
        self.running.clear()
        self.paused_by_user = False

    def reset(self):
        with self.lock:
            self.clicks = 0
            self.keys = 0
            self.started_at = time.time()

    def stats(self):
        with self.lock:
            elapsed = (time.time() - self.started_at) if self.started_at else 0
            return self.clicks, self.keys, elapsed, self.paused_by_user

    def _loop(self, my_gen):
        kernel32.timeBeginPeriod(1)
        try:
            self._run(my_gen)
        finally:
            kernel32.timeEndPeriod(1)
            if self.generation == my_gen:
                self.running.clear()

    def _run(self, my_gen):
        c = self.cfg
        hold = max(c["hold_ms"], 1) / 1000.0
        pause = max(c["pause_ms"], 0) / 1000.0
        mode = c["mode"]
        down_flag, up_flag = MOUSEEVENTF[c["button"]]
        vks = list(c["vks"])
        area = c["area"]
        self_hwnd = c.get("self_hwnd")
        return_cursor = c["return_cursor"]
        autopause_mouse = c["autopause"]
        autopause_typing = c["autopause_typing"]

        last_known_pos = cursor_pos()
        mouse_pause_until = 0.0
        keys_pause_until = 0.0

        while self.generation == my_gen:
            try:
                now = time.time()

                # Mouse-move pause and typing pause are independent of each
                # other and of the mode: one only ever throttles clicks, the
                # other only ever throttles keys. last_known_pos updates
                # right after the comparison (not after SendInput/sleep) so
                # a fast move that fits inside one cycle can't slip by
                # unnoticed.
                cur_pos = cursor_pos()
                mouse_paused = False
                if autopause_mouse:
                    if cur_pos != last_known_pos:
                        mouse_pause_until = max(mouse_pause_until, now + 2.0)
                    mouse_paused = now < mouse_pause_until
                last_known_pos = cur_pos

                keys_paused = False
                if autopause_typing:
                    if is_typing():
                        keys_pause_until = max(keys_pause_until, now + 2.0)
                    keys_paused = now < keys_pause_until

                # Hybrid fires mouse+keys in one down->hold->up cycle (not
                # sequentially); still a bit slower than keys-only overall
                # due to the mouse-only work below. Clicking requires an area
                # (see App.start() for the warning shown before that).
                do_mouse = mode in ("mouse", "hybrid") and area is not None and not mouse_paused
                do_keys = mode in ("keys", "hybrid") and bool(vks) and not keys_paused

                self.paused_by_user = (mode in ("mouse", "hybrid") and mouse_paused) or \
                                       (mode in ("keys", "hybrid") and keys_paused)
                self.paused_by_user = self.paused_by_user and not (do_mouse or do_keys)

                if not do_mouse and not do_keys:
                    time.sleep(0.05)
                    continue

                origin = None
                down_items, up_items = [], []

                if do_mouse:
                    origin = cursor_pos() if return_cursor else None
                    # Never click our own window - try a few random points
                    # in the area and skip the click if all of them land on it.
                    x = y = None
                    for _ in range(20):
                        cx = random.randint(area[0], area[2])
                        cy = random.randint(area[1], area[3])
                        if not point_is_over_window(cx, cy, self_hwnd):
                            x, y = cx, cy
                            break
                    if x is None:
                        do_mouse = False
                    else:
                        set_cursor_pos(x, y)
                        last_known_pos = (x, y)
                        time.sleep(0.001)
                    if do_mouse:
                        down_items.append(mouse_event_input(down_flag))
                        up_items.append(mouse_event_input(up_flag))

                if do_keys:
                    down_items.extend(key_input(vk) for vk in vks)
                    up_items.extend(key_input(vk, up=True) for vk in vks)

                if down_items:
                    # Press then release as two separate SendInput calls -
                    # an instant click only counts once in Bongo Cat.
                    send_inputs(down_items)
                    time.sleep(hold)
                    send_inputs(up_items)

                if do_mouse:
                    with self.lock:
                        self.clicks += 1
                    if origin:
                        set_cursor_pos(*origin)
                        last_known_pos = origin

                if do_keys:
                    with self.lock:
                        self.keys += len(vks)

                if pause:
                    time.sleep(pause)
            except Exception:
                # A transient WinAPI hiccup (locked session, RDP disconnect,
                # etc.) shouldn't kill the whole run - skip this cycle.
                time.sleep(0.1)


# ---------------------------------------------------------------- hotkeys

class HotkeyListener(threading.Thread):
    """F6 = start, F7 or Esc = stop, global. RegisterHotKey only notifies us -
    it doesn't consume the key, so Esc still works normally everywhere else.
    Callbacks hop back to the GUI thread via root.after() - this thread
    never touches tkinter."""

    def __init__(self, on_start, on_stop, on_status):
        super().__init__(daemon=True)
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_status = on_status      # "ok" | "fallback"
        self.thread_id = None
        self._stop_polling = threading.Event()

    def run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        ok6 = user32.RegisterHotKey(None, 1, MOD_NOREPEAT, VK_F6)
        ok7 = user32.RegisterHotKey(None, 2, MOD_NOREPEAT, VK_F7)
        if not (ok6 and ok7):
            self.on_status("fallback")
            self._polling_fallback()
            return
        ok_esc = user32.RegisterHotKey(None, 3, MOD_NOREPEAT, VK_ESCAPE)
        self.on_status("ok")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                (self.on_start if msg.wParam == 1 else self.on_stop)()
        user32.UnregisterHotKey(None, 1)
        user32.UnregisterHotKey(None, 2)
        if ok_esc:
            user32.UnregisterHotKey(None, 3)

    def _polling_fallback(self):
        prev6 = prev7 = prev_esc = False
        while not self._stop_polling.is_set():
            d6 = bool(user32.GetAsyncKeyState(VK_F6) & 0x8000)
            d7 = bool(user32.GetAsyncKeyState(VK_F7) & 0x8000)
            d_esc = bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
            if d6 and not prev6:
                self.on_start()
            if (d7 and not prev7) or (d_esc and not prev_esc):
                self.on_stop()
            prev6, prev7, prev_esc = d6, d7, d_esc
            time.sleep(0.03)

    def quit(self):
        self._stop_polling.set()
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)   # WM_QUIT


# ---------------------------------------------------------------- localization

STRINGS = {
    "ru": {
        "admin_yes": "Кликер запущен ОТ АДМИНИСТРАТОРА - Bongo Cat тоже обязан быть от админа!",
        "admin_no": "Кликер запущен без прав администратора (это нормально)",
        "box_mode": "Что нажимать",
        "mode_mouse": "Только мышь",
        "mode_keys": "Только клавиши (быстрее всего)",
        "mode_hybrid": "Мышь + клавиши",
        "mouse_button": "Кнопка мыши:",
        "box_area": "Область кликов",
        "pick_area": "Выбрать область мышью",
        "clear_area": "Сбросить",
        "area_none": "Область не задана - чтобы кликать мышью, сначала выберите область",
        "area_set": "Область: {x1}, {y1} -> {x2}, {y2}   ({w}x{h} px)",
        "return_cursor": "Возвращать курсор на место после каждого клика",
        "autopause_mouse": "Пауза, когда я сам двигаю мышь (действует только на клики мышью)",
        "autopause_typing": "Пауза, когда я печатаю (буквы, Enter, стрелки и т.п.) - защита от засорения терминала",
        "box_keys": "Клавиши",
        "numpad_label": "Цифры Numpad (нужен включённый NumLock):",
        "phantom_chk": "Клавиши F13-F24 (таких клавиш нет физически, они не мешают работе - рекомендуется)",
        "box_speed": "Скорость",
        "hold_label": "Удержание, мс:",
        "pause_label": "Пауза между циклами, мс:",
        "speed_hint": "Если Bongo Cat считает не все нажатия - увеличь оба значения (например 30 и 30).",
        "box_stat": "Счётчик",
        "stat_fmt": "Отправлено: {total}   (кликов {clicks}, клавиш {keys})",
        "rate_fmt": "Скорость: {rate} в секунду   |   до 1 000 000: ~{eta} мин",
        "reset_btn": "Обнулить",
        "start_btn": "СТАРТ  (F6)",
        "stop_btn": "СТОП  (F7 / Esc)",
        "diagnose_btn": "Диагностика",
        "state_stopped": "Остановлено",
        "state_running": "РАБОТАЕТ - остановить: F7 или Esc",
        "state_paused": "ПАУЗА - обнаружена твоя активность",
        "hotkey_ok": "Горячие клавиши F6 (старт) / F7 или Esc (стоп) активны",
        "hotkey_fallback": "F6/F7 заняты другой программой - включён запасной режим опроса",
        "warn_title": "Не выбраны клавиши",
        "warn_msg": "Отметь хотя бы одну цифру Numpad или включи F13-F24.",
        "warn_area_title": "Область не выбрана",
        "warn_area_msg": "Сначала выбери область для кликов мышью - кнопка «Выбрать область мышью».",
        "info_keys_only_title": "Будут работать только клавиши",
        "info_keys_only_msg": "Область для мыши не выбрана - в этот раз сработают только клавиши.",
        "diagnose_title": "Диагностика",
        "diagnose_admin_line": "Права администратора у кликера: {status}",
        "diagnose_admin_yes": "ДА",
        "diagnose_admin_no": "нет",
        "diagnose_lines": [
            "Если Bongo Cat не считает нажатия - проверь по порядку:",
            "",
            "1. Bongo Cat запущен ОТ ИМЕНИ АДМИНИСТРАТОРА.",
            "   Причина номер один. Пока Bongo Cat без прав админа, он не видит ввод,",
            "   когда активно окно программы, запущенной от админа (терминал и т.п.).",
            "2. В меню Bongo Cat снят флажок 'Ignore clicks'.",
            "3. Выключен игровой режим: нажми F4, когда окно Bongo Cat активно.",
            "4. Счётчик виден: F2 переключает его отображение.",
            "5. В Steam: правый клик по Bongo Cat -> Свойства -> Контроллер ->",
            "   отключить Steam Input.",
            "6. Если игра идёт в полноэкранном режиме - переключи её в оконный без рамки.",
            "",
            "Проверка: нажми СТАРТ и смотри счётчик в Bongo Cat.",
            "Если счётчик здесь растёт, а в Bongo Cat нет - дело в пунктах 1-6.",
        ],
        "area_prompt": "Зажми левую кнопку мыши и выдели область для кликов.   Esc - отмена.",
        "area_overlap_title": "Область перекрывает окно кликера",
        "area_overlap_msg": "Выбранная область частично или полностью перекрывает окно самой "
                             "программы. Клики будут попадать по её же кнопкам и чекбоксам, "
                             "программа во время работы уже пропускает такие клики автоматически, "
                             "но выбирать область над своим окном всё равно не рекомендуется.\n\n"
                             "Использовать эту область всё равно?",
        "lang_switch_to": "EN",
    },
    "en": {
        "admin_yes": "Clicker is running AS ADMINISTRATOR - Bongo Cat must run as admin too!",
        "admin_no": "Clicker is running without administrator rights (this is normal)",
        "box_mode": "What to press",
        "mode_mouse": "Mouse only",
        "mode_keys": "Keys only (fastest)",
        "mode_hybrid": "Mouse + keys",
        "mouse_button": "Mouse button:",
        "box_area": "Click area",
        "pick_area": "Pick area with mouse",
        "clear_area": "Clear",
        "area_none": "No area set - pick one first to enable mouse clicks",
        "area_set": "Area: {x1}, {y1} -> {x2}, {y2}   ({w}x{h} px)",
        "return_cursor": "Return the cursor after every click",
        "autopause_mouse": "Pause when I move the mouse myself (mouse clicks only)",
        "autopause_typing": "Pause when I'm typing (letters, Enter, arrows, etc.) - protects your terminal input",
        "box_keys": "Keys",
        "numpad_label": "Numpad digits (NumLock must be on):",
        "phantom_chk": "F13-F24 keys (don't exist on real keyboards, won't interfere with anything - recommended)",
        "box_speed": "Speed",
        "hold_label": "Hold, ms:",
        "pause_label": "Pause between cycles, ms:",
        "speed_hint": "If Bongo Cat doesn't count every press, increase both values (e.g. 30 and 30).",
        "box_stat": "Counter",
        "stat_fmt": "Sent: {total}   (clicks {clicks}, keys {keys})",
        "rate_fmt": "Speed: {rate}/sec   |   to 1,000,000: ~{eta} min",
        "reset_btn": "Reset",
        "start_btn": "START  (F6)",
        "stop_btn": "STOP  (F7 / Esc)",
        "diagnose_btn": "Diagnostics",
        "state_stopped": "Stopped",
        "state_running": "RUNNING - stop with F7 or Esc",
        "state_paused": "PAUSED - your activity detected",
        "hotkey_ok": "Hotkeys F6 (start) / F7 or Esc (stop) are active",
        "hotkey_fallback": "F6/F7 are taken by another app - fallback polling mode enabled",
        "warn_title": "No keys selected",
        "warn_msg": "Check at least one Numpad digit or enable F13-F24.",
        "warn_area_title": "No area selected",
        "warn_area_msg": "Pick a click area first - use the \"Pick area with mouse\" button.",
        "info_keys_only_title": "Keys only this time",
        "info_keys_only_msg": "No click area is set - only keys will run this time.",
        "diagnose_title": "Diagnostics",
        "diagnose_admin_line": "Clicker has administrator rights: {status}",
        "diagnose_admin_yes": "YES",
        "diagnose_admin_no": "no",
        "diagnose_lines": [
            "If Bongo Cat isn't counting your presses, check in this order:",
            "",
            "1. Bongo Cat is running AS ADMINISTRATOR.",
            "   Reason #1. While Bongo Cat has no admin rights, it can't see input",
            "   while an elevated app's window is active (a terminal, etc.).",
            "2. 'Ignore clicks' is unchecked in the Bongo Cat menu.",
            "3. Game mode is off: press F4 while the Bongo Cat window is active.",
            "4. The counter is visible: F2 toggles it.",
            "5. In Steam: right-click Bongo Cat -> Properties -> Controller ->",
            "   disable Steam Input.",
            "6. If the game runs fullscreen - switch it to borderless windowed.",
            "",
            "Test: press START and watch the counter in Bongo Cat.",
            "If the counter here grows but Bongo Cat's doesn't - see points 1-6.",
        ],
        "area_prompt": "Hold the left mouse button and drag out the click area.   Esc - cancel.",
        "area_overlap_title": "Area overlaps the clicker's own window",
        "area_overlap_msg": "The area you picked partially or fully overlaps the program's own "
                             "window. Clicks would land on its own buttons and checkboxes - the "
                             "program already skips such clicks automatically while running, but "
                             "picking an area over its own window still isn't recommended.\n\n"
                             "Use this area anyway?",
        "lang_switch_to": "RU",
    },
}

DEFAULT_LANG = "en"


def peek_saved_lang():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f).get("lang", DEFAULT_LANG)
    except (OSError, ValueError):
        return DEFAULT_LANG


# ---------------------------------------------------------------- area picking

MIN_AREA_PX = 10   # a plain click with no drag still yields at least this size


class AreaSelector:
    """Translucent full-screen window: drag out a rectangle with the mouse."""

    def __init__(self, root, callback, prompt_text):
        self.callback = callback
        vx, vy, vw, vh = virtual_screen()
        self.bounds = (vx, vy, vx + vw, vy + vh)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(geometry_string(vw, vh, vx, vy))
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.30)
        self.win.configure(bg="black")
        self.offset = (vx, vy)

        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(vw // 2, 40, fill="white", font=("Segoe UI", 16), text=prompt_text)
        self.rect = None
        self.start = None
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda e: self._cancel())
        self.win.focus_force()
        self.win.grab_set()

    def _press(self, e):
        self.start = (e.x, e.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="#39d353", width=2)

    def _drag(self, e):
        if self.rect:
            self.canvas.coords(self.rect, self.start[0], self.start[1], e.x, e.y)

    def _release(self, e):
        if not self.start:
            return
        ox, oy = self.offset
        x1, y1 = self.start[0] + ox, self.start[1] + oy
        x2, y2 = e.x + ox, e.y + oy
        self.win.destroy()

        left, right = min(x1, x2), max(x1, x2)
        top, bottom = min(y1, y2), max(y1, y2)
        # A click with little or no drag still needs a usable area - pad it
        # to a minimum size, centered on the clicked point.
        if right - left < MIN_AREA_PX:
            cx = (left + right) // 2
            left, right = cx - MIN_AREA_PX // 2, cx + MIN_AREA_PX // 2
        if bottom - top < MIN_AREA_PX:
            cy = (top + bottom) // 2
            top, bottom = cy - MIN_AREA_PX // 2, cy + MIN_AREA_PX // 2
        bx1, by1, bx2, by2 = self.bounds
        left, right = max(left, bx1), min(right, bx2)
        top, bottom = max(top, by1), min(bottom, by2)
        self.callback((left, top, right, bottom))

    def _cancel(self):
        self.win.destroy()
        self.callback(None)


class AreaOverlay:
    """Thin red, click-through border shown around the active click area."""

    COLOR = "#e11d2a"

    def __init__(self, root):
        self.root = root
        self.win = None
        self.canvas = None

    def show(self, area):
        x1, y1, x2, y2 = area
        w, h = max(x2 - x1, 1), max(y2 - y1, 1)
        if self.win is None:
            self.win = tk.Toplevel(self.root)
            self.win.overrideredirect(True)
            self.win.attributes("-topmost", True)
            self.win.configure(bg="black")
            self.win.attributes("-transparentcolor", "black")
            self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)
            self.win.update_idletasks()
            make_click_through(real_top_level_hwnd(self.win))
        self.win.geometry(geometry_string(w, h, x1, y1))
        self.canvas.config(width=w, height=h)
        self.canvas.delete("all")
        self.canvas.create_rectangle(1, 1, w - 2, h - 2, outline=self.COLOR, width=2)

    def hide(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None
            self.canvas = None


def _safe_int(var, default):
    """A Spinbox lets the user type garbage into it - fall back quietly."""
    try:
        return int(var.get())
    except (tk.TclError, ValueError):
        return default


# ---------------------------------------------------------------- GUI

class App:
    def __init__(self, root):
        self.root = root
        self.engine = ClickerEngine()
        # The click area is never persisted across restarts, on purpose: an
        # old area from a previous session (different resolution, different
        # window layout) should never silently start clicking again.
        self.area = None
        self.area_overlay = AreaOverlay(root)
        self.lang = peek_saved_lang()
        if self.lang not in STRINGS:
            self.lang = DEFAULT_LANG
        self.hotkey_state = None
        self._was_running = False

        root.title("BongoCatClicker")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        if os.path.exists(ICON_ICO):
            try:
                root.iconbitmap(ICON_ICO)   # also becomes the taskbar/thumbnail icon
            except tk.TclError:
                pass

        pad = dict(padx=8, pady=4)
        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)
        self.main = main

        top_bar = ttk.Frame(main)
        top_bar.grid(row=0, column=0, columnspan=4, sticky="ew", **pad)
        self.is_admin_now = is_admin()
        self.lbl_admin = ttk.Label(top_bar)
        self.lbl_admin.pack(side="left")
        self.btn_lang = ttk.Button(top_bar, width=4, command=self.toggle_language)
        self.btn_lang.pack(side="right")

        self.box_mode = ttk.LabelFrame(main, padding=8)
        self.box_mode.grid(row=1, column=0, columnspan=4, sticky="ew", **pad)
        self.mode = tk.StringVar(value="keys")
        self.mode_keys_order = ["mouse", "keys", "hybrid"]
        self.rb_mode = {}
        for i, val in enumerate(self.mode_keys_order):
            rb = ttk.Radiobutton(self.box_mode, value=val, variable=self.mode)
            rb.grid(row=0, column=i, sticky="w", padx=6)
            self.rb_mode[val] = rb
        self.button = tk.StringVar(value="left")
        self.lbl_mouse_button = ttk.Label(self.box_mode)
        self.lbl_mouse_button.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(self.box_mode, textvariable=self.button, width=10, state="readonly",
                     values=["left", "right", "middle"]).grid(row=1, column=1, sticky="w", pady=(6, 0))

        self.box_area = ttk.LabelFrame(main, padding=8)
        self.box_area.grid(row=2, column=0, columnspan=4, sticky="ew", **pad)
        self.btn_pick_area = ttk.Button(self.box_area, command=self.pick_area)
        self.btn_pick_area.grid(row=0, column=0, sticky="w")
        self.btn_clear_area = ttk.Button(self.box_area, command=self.clear_area)
        self.btn_clear_area.grid(row=0, column=1, padx=6)
        self.lbl_area = ttk.Label(self.box_area)
        self.lbl_area.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.return_cursor = tk.BooleanVar(value=True)
        self.chk_return_cursor = ttk.Checkbutton(self.box_area, variable=self.return_cursor)
        self.chk_return_cursor.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.autopause = tk.BooleanVar(value=True)
        self.chk_autopause_mouse = ttk.Checkbutton(self.box_area, variable=self.autopause)
        self.chk_autopause_mouse.grid(row=3, column=0, columnspan=3, sticky="w")
        self.autopause_typing = tk.BooleanVar(value=True)
        self.chk_autopause_typing = ttk.Checkbutton(self.box_area, variable=self.autopause_typing)
        self.chk_autopause_typing.grid(row=4, column=0, columnspan=3, sticky="w")

        self.box_keys = ttk.LabelFrame(main, padding=8)
        self.box_keys.grid(row=3, column=0, columnspan=4, sticky="ew", **pad)
        self.lbl_numpad = ttk.Label(self.box_keys)
        self.lbl_numpad.grid(row=0, column=0, columnspan=10, sticky="w")
        self.num_vars = {}
        for i in range(10):
            v = tk.BooleanVar(value=False)
            self.num_vars[str(i)] = v
            ttk.Checkbutton(self.box_keys, text=str(i), variable=v).grid(row=1, column=i, padx=2)
        self.use_phantom = tk.BooleanVar(value=True)
        self.chk_phantom = ttk.Checkbutton(self.box_keys, variable=self.use_phantom)
        self.chk_phantom.grid(row=2, column=0, columnspan=10, sticky="w", pady=(6, 0))

        self.box_speed = ttk.LabelFrame(main, padding=8)
        self.box_speed.grid(row=4, column=0, columnspan=4, sticky="ew", **pad)
        self.lbl_hold = ttk.Label(self.box_speed)
        self.lbl_hold.grid(row=0, column=0, sticky="w")
        self.hold_ms = tk.IntVar(value=20)
        ttk.Spinbox(self.box_speed, from_=1, to=200, width=6,
                    textvariable=self.hold_ms).grid(row=0, column=1, padx=(4, 16))
        self.lbl_pause = ttk.Label(self.box_speed)
        self.lbl_pause.grid(row=0, column=2, sticky="w")
        self.pause_ms = tk.IntVar(value=20)
        ttk.Spinbox(self.box_speed, from_=0, to=1000, width=6,
                    textvariable=self.pause_ms).grid(row=0, column=3, padx=4)
        self.lbl_speed_hint = ttk.Label(self.box_speed, foreground="#555")
        self.lbl_speed_hint.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        self.box_stat = ttk.LabelFrame(main, padding=8)
        self.box_stat.grid(row=5, column=0, columnspan=4, sticky="ew", **pad)
        self.lbl_stat = ttk.Label(self.box_stat, font=("Segoe UI", 10, "bold"))
        self.lbl_stat.grid(row=0, column=0, sticky="w")
        self.lbl_rate = ttk.Label(self.box_stat, text="")
        self.lbl_rate.grid(row=1, column=0, sticky="w")
        self.btn_reset = ttk.Button(self.box_stat, command=self.engine.reset)
        self.btn_reset.grid(row=0, column=1, rowspan=2, padx=8)

        bar = ttk.Frame(main)
        bar.grid(row=6, column=0, columnspan=4, sticky="ew", **pad)
        self.btn_start = ttk.Button(bar, command=self.start)
        self.btn_start.grid(row=0, column=0, ipadx=20, ipady=4)
        self.btn_stop = ttk.Button(bar, command=self.stop, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=8, ipadx=20, ipady=4)
        self.btn_diagnose = ttk.Button(bar, command=self.diagnose)
        self.btn_diagnose.grid(row=0, column=2, padx=8, ipady=4)

        self.lbl_state = ttk.Label(main, font=("Segoe UI", 11, "bold"), foreground="#b91c1c")
        self.lbl_state.grid(row=7, column=0, columnspan=4, sticky="w", **pad)
        self.lbl_hint = ttk.Label(main, text="", foreground="#555")
        self.lbl_hint.grid(row=8, column=0, columnspan=4, sticky="w", padx=8)

        self.retranslate()
        self.load_config()
        self.hotkeys = HotkeyListener(
            on_start=lambda: self.root.after(0, self.start),
            on_stop=lambda: self.root.after(0, self.stop),
            on_status=lambda s: self.root.after(0, lambda: self._set_hotkey_state(s)),
        )
        # Start the hotkey thread only after mainloop begins - on Python
        # 3.13+, root.after() from another thread raises before that.
        self.root.after(100, self.hotkeys.start)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.tick()

    # -------- localization
    def t(self, key):
        return STRINGS[self.lang][key]

    def toggle_language(self):
        self.lang = "en" if self.lang == "ru" else "ru"
        self.retranslate()
        self.save_config()

    def _set_hotkey_state(self, state):
        self.hotkey_state = state
        self.lbl_hint.config(text=self.t("hotkey_ok" if state == "ok" else "hotkey_fallback"))

    def retranslate(self):
        T = self.t
        self.lbl_admin.config(text=T("admin_yes" if self.is_admin_now else "admin_no"),
                              foreground=("#b45309" if self.is_admin_now else "#166534"))
        self.btn_lang.config(text=T("lang_switch_to"))

        self.box_mode.config(text=T("box_mode"))
        for val, rb in self.rb_mode.items():
            rb.config(text=T("mode_" + val))
        self.lbl_mouse_button.config(text=T("mouse_button"))

        self.box_area.config(text=T("box_area"))
        self.btn_pick_area.config(text=T("pick_area"))
        self.btn_clear_area.config(text=T("clear_area"))
        self._render_area_label()
        self.chk_return_cursor.config(text=T("return_cursor"))
        self.chk_autopause_mouse.config(text=T("autopause_mouse"))
        self.chk_autopause_typing.config(text=T("autopause_typing"))

        self.box_keys.config(text=T("box_keys"))
        self.lbl_numpad.config(text=T("numpad_label"))
        self.chk_phantom.config(text=T("phantom_chk"))

        self.box_speed.config(text=T("box_speed"))
        self.lbl_hold.config(text=T("hold_label"))
        self.lbl_pause.config(text=T("pause_label"))
        self.lbl_speed_hint.config(text=T("speed_hint"))

        self.box_stat.config(text=T("box_stat"))
        self.btn_reset.config(text=T("reset_btn"))

        self.btn_start.config(text=T("start_btn"))
        self.btn_stop.config(text=T("stop_btn"))
        self.btn_diagnose.config(text=T("diagnose_btn"))

        if self.hotkey_state:
            self.lbl_hint.config(text=T("hotkey_ok" if self.hotkey_state == "ok" else "hotkey_fallback"))

        self._render_state_label()

    def _render_state_label(self):
        """Also called from tick()/start()/stop(); recomputes the label for
        the current language and running/paused state."""
        if self.engine.running.is_set():
            key = "state_paused" if self.engine.paused_by_user else "state_running"
            color = "#b45309" if self.engine.paused_by_user else "#166534"
        else:
            key = "state_stopped"
            color = "#b91c1c"
        self.lbl_state.config(text=self.t(key), foreground=color)

    def _render_area_label(self):
        if self.area:
            x1, y1, x2, y2 = self.area
            self.lbl_area.config(text=self.t("area_set").format(
                x1=x1, y1=y1, x2=x2, y2=y2, w=x2 - x1, h=y2 - y1))
            self.area_overlay.show(self.area)
        else:
            self.lbl_area.config(text=self.t("area_none"))
            self.area_overlay.hide()

    # -------- area
    def pick_area(self):
        self.area_overlay.hide()
        self.root.withdraw()
        self.root.after(200, lambda: AreaSelector(self.root, self._area_done, self.t("area_prompt")))

    def _area_done(self, area):
        self.root.deiconify()
        self.root.update_idletasks()
        if area and self._area_overlaps_self(area):
            if not messagebox.askyesno(self.t("area_overlap_title"), self.t("area_overlap_msg")):
                self._render_area_label()
                return
        if area:
            self.area = area
        self._render_area_label()

    def own_top_level_hwnd(self):
        return real_top_level_hwnd(self.root)

    def _area_overlaps_self(self, area):
        """Warns before saving an area that overlaps the clicker's own
        window (the engine also guards against this at runtime)."""
        x0 = self.root.winfo_rootx()
        y0 = self.root.winfo_rooty()
        x1 = x0 + self.root.winfo_width()
        y1 = y0 + self.root.winfo_height()
        ax1, ay1, ax2, ay2 = area
        return ax1 < x1 and ax2 > x0 and ay1 < y1 and ay2 > y0

    def clear_area(self):
        self.area = None
        self._render_area_label()

    # -------- settings
    def collect_vks(self):
        vks = [NUMPAD_VK[d] for d, v in self.num_vars.items() if v.get()]
        if self.use_phantom.get():
            vks += list(PHANTOM_VK.values())
        return vks

    def build_cfg(self):
        return {
            "mode": self.mode.get(),
            "button": self.button.get(),
            "vks": self.collect_vks(),
            "area": self.area,
            "self_hwnd": self.own_top_level_hwnd(),
            "hold_ms": _safe_int(self.hold_ms, 20),
            "pause_ms": _safe_int(self.pause_ms, 20),
            "return_cursor": bool(self.return_cursor.get()),
            "autopause": bool(self.autopause.get()),
            "autopause_typing": bool(self.autopause_typing.get()),
        }

    # -------- start/stop
    def start(self):
        if self.engine.running.is_set():
            return
        cfg = self.build_cfg()
        if cfg["mode"] in ("keys", "hybrid") and not cfg["vks"]:
            messagebox.showwarning(self.t("warn_title"), self.t("warn_msg"))
            return
        if cfg["mode"] == "mouse" and not cfg["area"]:
            messagebox.showwarning(self.t("warn_area_title"), self.t("warn_area_msg"))
            return
        if cfg["mode"] == "hybrid" and not cfg["area"]:
            messagebox.showinfo(self.t("info_keys_only_title"), self.t("info_keys_only_msg"))
        self.engine.start(cfg)
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._render_state_label()
        self.save_config()

    def stop(self):
        self.engine.stop()
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._render_state_label()

    # -------- stats
    def tick(self):
        clicks, keys, elapsed, paused = self.engine.stats()
        total = clicks + keys
        self.lbl_stat.config(text=self.t("stat_fmt").format(
            total=fmt(total), clicks=fmt(clicks), keys=fmt(keys)))
        if elapsed > 1 and total > 0:
            rate = total / elapsed
            eta = (max(GOAL - total, 0) / rate / 60) if rate else 0
            self.lbl_rate.config(text=self.t("rate_fmt").format(rate=fmt(int(rate)), eta=fmt(int(eta))))

        running = self.engine.running.is_set()
        if running:
            self._render_state_label()
        elif self._was_running:
            # Engine thread stopped on its own (e.g. an unexpected error) -
            # don't leave the buttons stuck in the "running" state.
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
            self._render_state_label()
        self._was_running = running

        self.root.after(300, self.tick)

    # -------- diagnostics
    def diagnose(self):
        status = self.t("diagnose_admin_yes" if is_admin() else "diagnose_admin_no")
        lines = [self.t("diagnose_admin_line").format(status=status), ""] + self.t("diagnose_lines")
        messagebox.showinfo(self.t("diagnose_title"), "\n".join(lines))

    # -------- config (the click area is intentionally excluded - see __init__)
    def save_config(self):
        data = {
            "lang": self.lang,
            "mode": self.mode.get(),
            "button": self.button.get(),
            "hold_ms": _safe_int(self.hold_ms, 20),
            "pause_ms": _safe_int(self.pause_ms, 20),
            "return_cursor": bool(self.return_cursor.get()),
            "autopause": bool(self.autopause.get()),
            "autopause_typing": bool(self.autopause_typing.get()),
            "phantom": bool(self.use_phantom.get()),
            "nums": [d for d, v in self.num_vars.items() if v.get()],
        }
        try:
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, CONFIG_PATH)   # atomic - a crash mid-write can't corrupt the real file
        except OSError:
            pass

    def load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return
        try:
            self.mode.set(d.get("mode", "keys"))
            self.button.set(d.get("button", "left"))
            self.hold_ms.set(d.get("hold_ms", 20))
            self.pause_ms.set(d.get("pause_ms", 20))
            self.return_cursor.set(d.get("return_cursor", True))
            self.autopause.set(d.get("autopause", True))
            self.autopause_typing.set(d.get("autopause_typing", True))
            self.use_phantom.set(d.get("phantom", True))
            for n in d.get("nums", []):
                if n in self.num_vars:
                    self.num_vars[n].set(True)
        except (tk.TclError, TypeError, ValueError):
            pass   # a hand-edited or half-written settings.json shouldn't block startup

    def on_close(self):
        self.engine.stop()
        self.hotkeys.quit()
        self.area_overlay.hide()
        self.save_config()
        self.root.destroy()


def fmt(n):
    return "{:,}".format(int(n)).replace(",", " ")


def main():
    if sys.platform != "win32":
        print("This program only runs on Windows.")
        return
    if ALREADY_RUNNING:
        try:
            hwnd = user32.FindWindowW(None, "BongoCatClicker")
            if hwnd:
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
