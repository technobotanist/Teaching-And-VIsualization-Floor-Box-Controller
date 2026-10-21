from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


class DisplayIdentifierError(RuntimeError):
    pass


def show_display_identifier(
    label: str,
    monitor_index: int,
    monitor: dict[str, object],
    duration_seconds: int = 20,
) -> None:
    if sys.platform != "win32":
        raise DisplayIdentifierError("Display identification is available on Windows only")

    geometry = {
        "width": monitor.get("width"),
        "height": monitor.get("height"),
        "x": monitor.get("x"),
        "y": monitor.get("y"),
    }
    if not all(isinstance(value, int) for value in geometry.values()):
        raise DisplayIdentifierError("OBS did not report complete monitor geometry")

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    command = [
        str(executable),
        "-m",
        "tv_display_controller.display_identifier",
        "--label",
        label,
        "--monitor-index",
        str(monitor_index),
        "--monitor-name",
        str(monitor.get("name") or f"Display {monitor_index}"),
        "--width",
        str(geometry["width"]),
        "--height",
        str(geometry["height"]),
        "--x",
        str(geometry["x"]),
        "--y",
        str(geometry["y"]),
        "--duration",
        str(duration_seconds),
    ]
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess,
        "DETACHED_PROCESS",
        0,
    )
    try:
        subprocess.Popen(
            command,
            close_fds=True,
            creationflags=creation_flags,
        )
    except OSError as error:
        raise DisplayIdentifierError("Could not open the display identifier") from error


def _draw_card(
    label: str,
    monitor_index: int,
    monitor_name: str,
    width: int,
    height: int,
    x: int,
    y: int,
    duration_seconds: int,
) -> None:
    import ctypes
    import tkinter

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass

    root = tkinter.Tk()
    root.title(f"Display identifier {label}")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(background="#101214")
    root.geometry(f"{width}x{height}+0+0")
    root.update_idletasks()
    ctypes.windll.user32.SetWindowPos(
        root.winfo_id(),
        -1,
        x,
        y,
        width,
        height,
        0x0040,
    )

    canvas = tkinter.Canvas(root, background="#101214", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    def draw_pattern(event: tkinter.Event) -> None:
        canvas.delete("all")
        current_width = max(event.width, 1)
        current_height = max(event.height, 1)
        margin = max(24, min(current_width, current_height) // 24)
        for column in range(1, 12):
            position = current_width * column / 12
            canvas.create_line(position, 0, position, current_height, fill="#30363a")
        for row in range(1, 8):
            position = current_height * row / 8
            canvas.create_line(0, position, current_width, position, fill="#30363a")
        canvas.create_rectangle(
            margin,
            margin,
            current_width - margin,
            current_height - margin,
            outline="#cc0000",
            width=max(8, margin // 3),
        )
        canvas.create_text(
            current_width / 2,
            current_height * 0.42,
            text=label.upper(),
            fill="#ffffff",
            font=("Bahnschrift", max(96, current_height // 3), "bold"),
        )
        canvas.create_text(
            current_width / 2,
            current_height * 0.68,
            text=f"OBS MONITOR INDEX {monitor_index}",
            fill="#59d5e0",
            font=("Consolas", max(24, current_height // 28), "bold"),
        )
        canvas.create_text(
            current_width / 2,
            current_height * 0.77,
            text=monitor_name,
            fill="#c6cbce",
            font=("Bahnschrift", max(18, current_height // 38)),
        )
        canvas.create_text(
            current_width / 2,
            current_height - margin * 1.7,
            text="CLICK ANYWHERE OR PRESS ESC TO CLOSE",
            fill="#ffffff",
            font=("Consolas", max(14, current_height // 55), "bold"),
        )

    canvas.bind("<Configure>", draw_pattern)
    root.bind("<Escape>", lambda _event: root.destroy())
    root.bind("<Button-1>", lambda _event: root.destroy())
    root.after(duration_seconds * 1000, root.destroy)
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--monitor-index", required=True, type=int)
    parser.add_argument("--monitor-name", required=True)
    parser.add_argument("--width", required=True, type=int)
    parser.add_argument("--height", required=True, type=int)
    parser.add_argument("--x", required=True, type=int)
    parser.add_argument("--y", required=True, type=int)
    parser.add_argument("--duration", required=True, type=int)
    arguments = parser.parse_args()
    _draw_card(
        arguments.label,
        arguments.monitor_index,
        arguments.monitor_name,
        arguments.width,
        arguments.height,
        arguments.x,
        arguments.y,
        arguments.duration,
    )


if __name__ == "__main__":
    main()