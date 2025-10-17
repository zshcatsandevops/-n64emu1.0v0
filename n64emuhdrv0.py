#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N64EMU 1.0X — Project64-style GUI Emulator
Standalone Edition
© 2025 N64EMU Team
"""

from __future__ import annotations
import argparse
import time
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path

# ============================================================
# Internal HDR Core (Fake CPU / Memory / PPU / Controller)
# ============================================================

class CPU:
    def __init__(self):
        self.pc = 0xA4000040
        self.cycles = 0

    def reset(self):
        self.pc = 0xA4000040
        self.cycles = 0
        print("[CPU] Reset complete")

    def step(self, mem, logger=None):
        self.cycles += 1
        self.pc += 4
        if logger:
            logger(f"[CPU] Step {self.cycles:06d} | PC=0x{self.pc:08X}")
        return self.pc


class Memory:
    def __init__(self):
        self.rom = b""
        self.info = {"name": "No ROM", "region": "NTSC", "version": "1.0", "crc1": "00000000", "crc2": "00000000", "cic": "6102"}

    def load_rom(self, data: bytes):
        self.rom = data
        self.info = {
            "name": "DemoROM",
            "region": "NTSC",
            "version": "1.0",
            "crc1": "DEADBEEF",
            "crc2": "CAFED00D",
            "cic": "6102"
        }
        print(f"[MEM] Loaded ROM ({len(data)} bytes)")
        return self.info


class PPU:
    def __init__(self):
        self.width, self.height = 320, 240
        self.buffer = [[0, 0, 0] for _ in range(self.width * self.height)]

    def reset(self):
        print("[PPU] Reset display buffer")

    def draw_random_square(self):
        x = random.randint(0, self.width - 20)
        y = random.randint(0, self.height - 20)
        size = random.randint(5, 30)
        color = "#%02x%02x%02x" % (
            random.randint(80, 255),
            random.randint(80, 255),
            random.randint(80, 255),
        )
        return (x, y, size, color)

    def blit_to_photoimage(self, photo: tk.PhotoImage):
        # Random demo pixel flicker
        for _ in range(120):
            x, y = random.randint(0, self.width - 1), random.randint(0, self.height - 1)
            c = "#%02x%02x%02x" % (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255),
            )
            photo.put(c, (x, y))


class Controller:
    def __init__(self):
        self.state = {}

    def set_from_keys(self, keys: set[str]):
        self.state = {
            "A": "space" in keys,
            "B": "Return" in keys,
            "UP": "Up" in keys,
            "DOWN": "Down" in keys,
            "LEFT": "Left" in keys,
            "RIGHT": "Right" in keys,
        }

# ============================================================
# GUI Application
# ============================================================

N64EMU_VERSION = "1.0X"
WINDOW_TITLE = "N64EMU 1.0X"
BUILD_STR = "Standalone Edition"
COPYRIGHT_STR = "© 2025 N64EMU Team"


class N64EmuApp:
    def __init__(self, root: tk.Tk, show_plugins: bool = True) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("800x600")

        # Core instances
        self.cpu = CPU()
        self.mem = Memory()
        self.ppu = PPU()
        self.controller = Controller()

        # State
        self.keys: set[str] = set()
        self.running = False
        self.fps = 0
        self.frame_count = 0
        self.last_fps_time = time.time()

        # Main frame
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Toolbar
        self._create_toolbar(main_frame)

        # Canvas for display
        self.photo = tk.PhotoImage(width=self.ppu.width, height=self.ppu.height)
        self.canvas = tk.Canvas(main_frame, width=self.ppu.width, height=self.ppu.height, bg="black", highlightthickness=0)
        self.canvas.pack(pady=5)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

        # ROM Info Panel (like GoodN64 info)
        self._create_rom_info_panel(main_frame)

        # Status and Log
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(bottom_frame)
        left.pack(side=tk.LEFT, fill=tk.Y)
        right = ttk.Frame(bottom_frame)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fps_label = ttk.Label(left, text="FPS: 0", font=("Courier", 10))
        self.fps_label.pack(anchor="w", padx=6, pady=4)
        self.status = ttk.Label(left, text="Ready.", anchor=tk.W)
        self.status.pack(anchor="w", padx=6)

        self.log = scrolledtext.ScrolledText(right, height=8, wrap=tk.WORD, state="disabled")
        self.log.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self._make_menu(show_plugins)

        root.bind("<KeyPress>", self._key_down)
        root.bind("<KeyRelease>", self._key_up)

        self._tick_job = None

    def _create_toolbar(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        buttons = [
            ("ROM Browser", self._rom_browser),  # Placeholder
            ("Play", self.start),
            ("Pause", self.pause),  # Add pause method
            ("Stop", self.stop),
            ("Frame Advance", self.frame_advance),  # Placeholder
            ("Fullscreen", self.fullscreen),  # Placeholder
        ]

        for text, cmd in buttons:
            btn = ttk.Button(toolbar, text=text, command=cmd)
            btn.pack(side=tk.LEFT, padx=2)

    def _create_rom_info_panel(self, parent):
        info_frame = ttk.LabelFrame(parent, text="ROM Information", padding=5)
        info_frame.pack(fill=tk.X, pady=(0, 5))

        self.info_labels = {}
        fields = ["Name", "Country", "Version", "CRC1", "CRC2", "CIC"]
        for field in fields:
            label = ttk.Label(info_frame, text=f"{field}: ", anchor=tk.W)
            label.grid(row=fields.index(field), column=0, sticky=tk.W, padx=5, pady=1)
            value_label = ttk.Label(info_frame, text="N/A", anchor=tk.W)
            value_label.grid(row=fields.index(field), column=1, sticky=tk.W, padx=5, pady=1)
            self.info_labels[field.lower()] = value_label

        self._update_rom_info()

    def _update_rom_info(self):
        info = self.mem.info
        for key, label in self.info_labels.items():
            if key in info:
                label.config(text=info[key])
            else:
                label.config(text="N/A")

    # --------------- Menu ----------------
    def _make_menu(self, show_plugins: bool):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open ROM...", command=self._open_rom)
        file_menu.add_command(label="Close ROM", command=self._close_rom)  # Placeholder
        file_menu.add_separator()
        file_menu.add_command(label="ROM Browser...", command=self._rom_browser)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Options Menu
        options_menu = tk.Menu(menubar, tearoff=0)
        options_menu.add_checkbutton(label="Always On Top", command=self._toggle_always_on_top)
        options_menu.add_checkbutton(label="Auto Fullscreen", command=self._toggle_auto_fullscreen)
        menubar.add_cascade(label="Options", menu=options_menu)

        # Config Menu
        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="Configure Graphics...", command=lambda: self._plugin_cfg("Graphics"))
        config_menu.add_command(label="Configure Audio...", command=lambda: self._plugin_cfg("Audio"))
        config_menu.add_command(label="Configure Input...", command=lambda: self._plugin_cfg("Input"))
        config_menu.add_command(label="Configure RSP...", command=lambda: self._plugin_cfg("RSP"))
        menubar.add_cascade(label="Config", menu=config_menu)

        if show_plugins:
            # Plugins Menu
            plugin_menu = tk.Menu(menubar, tearoff=0)
            plugin_menu.add_command(label="Current Plugin Settings...", command=self._current_plugin_settings)
            menubar.add_cascade(label="Plugins", menu=plugin_menu)

        # Tools Menu (placeholder)
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Cheats...", command=self._cheats)
        tools_menu.add_command(label="Debugger...", command=self._debugger)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About N64EMU 1.0X", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)

    # --------------- Input ----------------
    def _key_down(self, e):
        self.keys.add(e.keysym)
        self.controller.set_from_keys(self.keys)

    def _key_up(self, e):
        self.keys.discard(e.keysym)
        self.controller.set_from_keys(self.keys)

    # --------------- ROM ----------------
    def _open_rom(self):
        path = filedialog.askopenfilename(
            title="Select ROM",
            filetypes=[("N64 ROM", "*.z64 *.n64 *.v64"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            data = Path(path).read_bytes()
            info = self.mem.load_rom(data)
            self._set_status(f"Loaded {Path(path).name}")
            self._update_rom_info()
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))

    def _close_rom(self):
        self.mem.rom = b""
        self.mem.info = {"name": "No ROM", "region": "NTSC", "version": "1.0", "crc1": "00000000", "crc2": "00000000", "cic": "6102"}
        self._update_rom_info()
        self._set_status("No ROM loaded")

    def _rom_browser(self):
        messagebox.showinfo("ROM Browser", "ROM Browser feature coming soon!")

    # --------------- Start / Stop / Pause ----------------
    def start(self):
        if self.running:
            return
        self.cpu.reset()
        self.ppu.reset()
        self.running = True
        self.paused = False
        self._set_status("Running…")
        self._schedule_tick()

    def pause(self):
        if not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self._set_status("Paused")
        else:
            self._set_status("Running…")

    def stop(self):
        self.running = False
        self.paused = False
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        self._set_status("Stopped")

    def frame_advance(self):
        if not self.running or self.paused:
            return
        # Single frame advance logic (placeholder)
        self._tick_once()

    def fullscreen(self):
        # Placeholder for fullscreen
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))

    # --------------- Main Loop ----------------
    def _schedule_tick(self):
        self._tick_job = self.root.after(16, self._tick)

    def _tick(self):
        if not self.running or self.paused:
            if self.paused:
                self._schedule_tick()
            return

        for _ in range(200):
            self.cpu.step(self.mem, logger=self._append_log)
        self.ppu.blit_to_photoimage(self.photo)
        self._update_fps()
        self._tick_job = self.root.after(16, self._tick)

    def _tick_once(self):
        for _ in range(200):
            self.cpu.step(self.mem, logger=self._append_log)
        self.ppu.blit_to_photoimage(self.photo)
        self._update_fps()

    # --------------- Placeholder Methods ----------------
    def _toggle_always_on_top(self):
        self.root.attributes("-topmost", not self.root.attributes("-topmost"))

    def _toggle_auto_fullscreen(self):
        messagebox.showinfo("Auto Fullscreen", "Feature coming soon!")

    def _current_plugin_settings(self):
        messagebox.showinfo("Plugin Settings", "Current Plugin Settings (placeholder)")

    def _cheats(self):
        messagebox.showinfo("Cheats", "Cheats manager coming soon!")

    def _debugger(self):
        messagebox.showinfo("Debugger", "Debugger feature coming soon!")

    # --------------- UI helpers ----------------
    def _plugin_cfg(self, name: str):
        win = tk.Toplevel(self.root)
        win.title(f"Configure {name}")
        win.geometry("300x150")
        tk.Label(win, text=f"{name} Configuration", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(win, text="Basic config window (placeholder)").pack(pady=10)
        tk.Button(win, text="OK", command=win.destroy).pack(pady=10)

    def _about(self):
        messagebox.showinfo(
            "About N64EMU 1.0X",
            f"{WINDOW_TITLE}\n{BUILD_STR}\n{COPYRIGHT_STR}\n\n"
            "N64 Emulator with Project64-style interface.\n"
            "Playable demo with fake GPU/CPU loop.\n"
            "Arrows = DPAD, Space = A, Enter = B.\n"
            "Core: internal EMU64 stub."
        )

    def _set_status(self, msg: str):
        self.status.config(text=msg)

    def _append_log(self, line: str):
        self.log.configure(state="normal")
        self.log.insert(tk.END, line + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def _update_fps(self):
        self.frame_count += 1
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = now
            self.fps_label.config(text=f"FPS: {self.fps}")

# ============================================================
# Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="N64EMU 1.0X — Project64-style N64 Emulator")
    parser.add_argument("--rom", type=str, default=None, help="Path to ROM")
    parser.add_argument("--headless", action="store_true", help="Run without GUI (CPU log only)")
    parser.add_argument("--plugins", choices=["on", "off"], default="on", help="Plugins menu toggle")
    args = parser.parse_args()

    if args.headless:
        mem, cpu = Memory(), CPU()
        if args.rom:
            blob = Path(args.rom).read_bytes()
            mem.load_rom(blob)
        cpu.reset()
        for _ in range(50):
            cpu.step(mem, logger=print)
        return

    root = tk.Tk()
    app = N64EmuApp(root, show_plugins=(args.plugins != "off"))

    if args.rom:
        try:
            blob = Path(args.rom).read_bytes()
            info = app.mem.load_rom(blob)
            app._set_status(f"Loaded {Path(args.rom).name}")
            app._update_rom_info()
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))

    root.mainloop()

if __name__ == "__main__":
    main()
