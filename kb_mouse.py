import ctypes
import threading
import time
from ctypes import wintypes

import keyboard
import tkinter as tk

# Windows constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
VK_NUMLOCK = 0x90
ULONG_PTR = wintypes.WPARAM
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
LWA_COLORKEY = 0x00000001
SCREEN_WIDTH = ctypes.windll.user32.GetSystemMetrics(0)
SCREEN_HEIGHT = ctypes.windll.user32.GetSystemMetrics(1)

SHOW_CUSTOM_CURSOR = False

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUTUNION),
    ]


def send_mouse(flags, dx=0, dy=0, data=0):
    ensure_cursor_visible()
    event = INPUT(
        type=INPUT_MOUSE,
        union=INPUTUNION(
            mi=MOUSEINPUT(
                dx=dx,
                dy=dy,
                mouseData=data,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )
    sent = ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def numlock_on():
    return bool(ctypes.windll.user32.GetKeyState(VK_NUMLOCK) & 1)


def ensure_cursor_visible():
    user32 = ctypes.windll.user32
    while user32.ShowCursor(True) < 0:
        pass


MOVE_KEYS = {
    "w": (0, -1),
    "s": (0, 1),
    "a": (-1, 0),
    "d": (1, 0),
    "q": (-1, -1),
    "e": (1, -1),
    "z": (-1, 1),
    "c": (1, 1),
}

SPEED = 18
FAST_MULTIPLIER = 2
PRINT_SCREEN_KEYS = {"print screen", "prtsc", "snapshot"}


def get_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def get_screen_size():
    return (
        ctypes.windll.user32.GetSystemMetrics(0),
        ctypes.windll.user32.GetSystemMetrics(1),
    )


def run_crosshair_overlay():
    screen_width, screen_height = get_screen_size()
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.geometry(f"{screen_width}x{screen_height}+0+0")
    root.configure(bg="black")
    root.wm_attributes("-transparentcolor", "black")

    hwnd = root.winfo_id()
    exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    exstyle |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)
    ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 0, LWA_COLORKEY)

    canvas = tk.Canvas(
        root,
        width=screen_width,
        height=screen_height,
        bg="black",
        highlightthickness=0,
    )
    canvas.pack(fill="both", expand=True)

    def tick():
        canvas.delete("crosshair")
        x, y = get_cursor_pos()
        size = 10
        gap = 2
        color = "#ff3b30"
        width = 2
        canvas.create_line(x - size, y, x - gap, y, fill=color, width=width, tags="crosshair")
        canvas.create_line(x + gap, y, x + size, y, fill=color, width=width, tags="crosshair")
        canvas.create_line(x, y - size, x, y - gap, fill=color, width=width, tags="crosshair")
        canvas.create_line(x, y + gap, x, y + size, fill=color, width=width, tags="crosshair")
        root.after(16, tick)

    tick()
    root.mainloop()


def run_overlay_supervisor():
    while True:
        try:
            run_crosshair_overlay()
        except Exception as e:
            print(f"Overlay crashed, restarting: {e}")
            time.sleep(1)
            continue

        print("Overlay exited unexpectedly, restarting.")
        time.sleep(1)


def handle_key(event):
    if event.event_type != "down":
        return True

    key = event.name

    if key == "esc":
        print("Exiting.")
        keyboard.unhook_all()
        raise SystemExit

    if not numlock_on():
        return True

    # Windows can route PrtSc through special handlers; explicitly swallow it in mouse mode.
    if key in PRINT_SCREEN_KEYS:
        return False

    # While mouse mode is active, block typed input from reaching applications.
    suppress = key != "num lock"

    fast = keyboard.is_pressed("shift")
    step = SPEED * (FAST_MULTIPLIER if fast else 1)

    if key in MOVE_KEYS:
        dx, dy = MOVE_KEYS[key]
        send_mouse(MOUSEEVENTF_MOVE, dx * step, dy * step)
    elif key == "1":
        send_mouse(MOUSEEVENTF_LEFTDOWN)
        send_mouse(MOUSEEVENTF_LEFTUP)
    elif key == "2":
        send_mouse(MOUSEEVENTF_RIGHTDOWN)
        send_mouse(MOUSEEVENTF_RIGHTUP)
    elif key == "8":
        send_mouse(MOUSEEVENTF_WHEEL, data=120)
    elif key == "3":
        send_mouse(MOUSEEVENTF_WHEEL, data=-120)

    return not suppress


def main():
    ensure_cursor_visible()
    if SHOW_CUSTOM_CURSOR:
        overlay_thread = threading.Thread(target=run_overlay_supervisor, daemon=True)
        overlay_thread.start()
    print("Keyboard mouse helper started.")
    print("Custom crosshair overlay: ON")
    print("NumLock ON enables controls; NumLock OFF passes keys normally.")
    print("Move: W A S D + diagonals Q E Z C")
    print("Left click: 1 | Right click: 2 | Wheel: 8 (up), 3 (down)")
    print("Hold Shift for faster movement. Press Esc to quit.")

    keyboard.hook(handle_key, suppress=True)
    while True:
        time.sleep(0.1)


if __name__ == "__main__":
    main()
