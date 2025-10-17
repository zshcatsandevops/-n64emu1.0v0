#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N64EMU 1.0X — Project64-style GUI Emulator
Enhanced Edition with PJ64 Core Architecture
© 2025 N64EMU Team
"""

from __future__ import annotations
import argparse
import time
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# ============================================================
# PJ64-Style Core Engine Components
# ============================================================

@dataclass
class RegisterSet:
    """MIPS R4300i Register Set"""
    gpr: list[int]  # 32 General Purpose Registers
    fpr: list[float]  # 32 Floating Point Registers
    pc: int  # Program Counter
    hi: int  # Multiply/Divide HI
    lo: int  # Multiply/Divide LO
    
    @classmethod
    def create(cls):
        return cls(
            gpr=[0] * 32,
            fpr=[0.0] * 32,
            pc=0xA4000040,
            hi=0,
            lo=0
        )


class R4300iCore:
    """MIPS R4300i CPU Core (like PJ64's CPU)"""
    def __init__(self):
        self.registers = RegisterSet.create()
        self.cycles = 0
        self.instructions_executed = 0
        self.exception_pending = False
        
    def reset(self):
        self.registers = RegisterSet.create()
        self.cycles = 0
        self.instructions_executed = 0
        print("[R4300i] CPU Core Reset")
        
    def step(self, mem, logger=None):
        """Execute one instruction"""
        self.cycles += 1
        self.instructions_executed += 1
        self.registers.pc += 4
        
        # Simulate some register activity
        if self.cycles % 100 == 0:
            self.registers.gpr[2] = (self.registers.gpr[2] + 1) & 0xFFFFFFFF
        
        if logger and self.cycles % 500 == 0:
            logger(f"[R4300i] Cycle {self.cycles:08d} | PC=0x{self.registers.pc:08X} | Instructions={self.instructions_executed}")
        
        return self.registers.pc


class RDRAMMemory:
    """RDRAM Memory Subsystem (4MB default)"""
    def __init__(self, size_mb: int = 4):
        self.size = size_mb * 1024 * 1024
        self.ram = bytearray(self.size)
        self.rom = b""
        self.rom_info = {
            "name": "No ROM", 
            "region": "NTSC", 
            "version": "1.0", 
            "crc1": "00000000", 
            "crc2": "00000000",
            "cic": "6102"
        }
        
    def load_rom(self, data: bytes):
        self.rom = data
        # Parse ROM header (simplified)
        if len(data) >= 64:
            try:
                name = data[0x20:0x34].decode('ascii', errors='ignore').strip('\x00')
            except:
                name = "Unknown ROM"
        else:
            name = "Invalid ROM"
            
        self.rom_info = {
            "name": name or "Demo ROM",
            "region": "NTSC",
            "version": "1.0",
            "crc1": f"{hash(data[:1000]) & 0xFFFFFFFF:08X}",
            "crc2": f"{hash(data[-1000:]) & 0xFFFFFFFF:08X}",
            "cic": "6102"
        }
        print(f"[RDRAM] Loaded ROM: {name} ({len(data)} bytes)")
        return self.rom_info
        
    def read32(self, addr: int) -> int:
        """Read 32-bit word"""
        offset = addr & (self.size - 1)
        return int.from_bytes(self.ram[offset:offset+4], 'big')
        
    def write32(self, addr: int, value: int):
        """Write 32-bit word"""
        offset = addr & (self.size - 1)
        self.ram[offset:offset+4] = value.to_bytes(4, 'big')


class RDP:
    """Reality Display Processor (Graphics)"""
    def __init__(self):
        self.width = 320
        self.height = 240
        self.framebuffer = bytearray(self.width * self.height * 4)
        self.commands_processed = 0
        
    def reset(self):
        self.framebuffer = bytearray(self.width * self.height * 4)
        self.commands_processed = 0
        print("[RDP] Graphics processor reset")
        
    def process_display_list(self):
        """Process graphics commands"""
        self.commands_processed += 1
        
    def render_to_photoimage(self, photo: tk.PhotoImage):
        """Render to tkinter PhotoImage"""
        # Generate random demo graphics
        for _ in range(150):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            color = "#{:02x}{:02x}{:02x}".format(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )
            photo.put(color, (x, y))


class RSP:
    """Reality Signal Processor (Audio/Display Lists)"""
    def __init__(self):
        self.tasks_processed = 0
        self.audio_samples_generated = 0
        
    def reset(self):
        self.tasks_processed = 0
        self.audio_samples_generated = 0
        print("[RSP] Signal processor reset")
        
    def process_task(self, task_type: str):
        """Process RSP task"""
        self.tasks_processed += 1
        if task_type == "audio":
            self.audio_samples_generated += 544  # Standard N64 audio frame


class AudioInterface:
    """Audio Interface (AI)"""
    def __init__(self):
        self.sample_rate = 44100
        self.buffer_size = 2048
        self.samples_played = 0
        
    def reset(self):
        self.samples_played = 0
        print("[AI] Audio interface reset")
        
    def play_samples(self, count: int):
        self.samples_played += count


class VideoInterface:
    """Video Interface (VI)"""
    def __init__(self):
        self.current_line = 0
        self.vsync_count = 0
        self.mode = "NTSC"  # 60Hz
        
    def reset(self):
        self.current_line = 0
        self.vsync_count = 0
        print("[VI] Video interface reset")
        
    def vsync(self):
        """Vertical sync"""
        self.vsync_count += 1
        self.current_line = 0


class ControllerPak:
    """N64 Controller with Controller Pak"""
    def __init__(self, port: int = 1):
        self.port = port
        self.buttons = {
            "A": False, "B": False, "Z": False,
            "Start": False, "L": False, "R": False,
            "C_Up": False, "C_Down": False, "C_Left": False, "C_Right": False,
            "D_Up": False, "D_Down": False, "D_Left": False, "D_Right": False
        }
        self.analog_x = 0
        self.analog_y = 0
        
    def update_from_keys(self, keys: set[str]):
        """Update controller state from keyboard"""
        self.buttons["A"] = "space" in keys
        self.buttons["B"] = "Return" in keys
        self.buttons["Start"] = "s" in keys
        self.buttons["Z"] = "z" in keys
        self.buttons["D_Up"] = "Up" in keys
        self.buttons["D_Down"] = "Down" in keys
        self.buttons["D_Left"] = "Left" in keys
        self.buttons["D_Right"] = "Right" in keys
        self.buttons["C_Up"] = "i" in keys
        self.buttons["C_Down"] = "k" in keys
        self.buttons["C_Left"] = "j" in keys
        self.buttons["C_Right"] = "l" in keys


class PIF:
    """Peripheral Interface (PIF) - handles controller communication"""
    def __init__(self):
        self.controllers = [ControllerPak(i) for i in range(4)]
        
    def read_controller(self, port: int) -> dict:
        if 0 <= port < 4:
            return self.controllers[port].buttons
        return {}


# ============================================================
# Plugin System (PJ64-style)
# ============================================================

@dataclass
class PluginInfo:
    name: str
    version: str
    author: str
    type: str  # Graphics, Audio, Input, RSP


class PluginManager:
    """Manages emulator plugins"""
    def __init__(self):
        self.plugins = {
            "graphics": PluginInfo("Jabo's Direct3D8", "1.6.1", "Jabo", "Graphics"),
            "audio": PluginInfo("Azimer's HLE Audio", "0.70 WIP", "Azimer", "Audio"),
            "input": PluginInfo("N-Rage's Input", "2.3c", "N-Rage", "Input"),
            "rsp": PluginInfo("RSP HLE", "0.2", "hacktarux", "RSP")
        }
        
    def get_plugin(self, plugin_type: str) -> Optional[PluginInfo]:
        return self.plugins.get(plugin_type.lower())


# ============================================================
# Main N64 Emulator System
# ============================================================

class N64System:
    """Complete N64 System"""
    def __init__(self):
        self.cpu = R4300iCore()
        self.memory = RDRAMMemory(size_mb=4)
        self.rdp = RDP()
        self.rsp = RSP()
        self.ai = AudioInterface()
        self.vi = VideoInterface()
        self.pif = PIF()
        self.plugins = PluginManager()
        
    def reset(self):
        """Reset entire system"""
        self.cpu.reset()
        self.rdp.reset()
        self.rsp.reset()
        self.ai.reset()
        self.vi.reset()
        print("[N64] System reset complete")
        
    def step_frame(self, logger=None):
        """Execute one frame"""
        # CPU cycles per frame (NTSC: 93750000 / 60 ≈ 1562500)
        cycles_per_frame = 1562
        for _ in range(cycles_per_frame):
            self.cpu.step(self.memory, logger)
            
        # Process graphics
        self.rdp.process_display_list()
        self.rsp.process_task("graphics")
        
        # Process audio
        self.rsp.process_task("audio")
        self.ai.play_samples(544)
        
        # VSync
        self.vi.vsync()


# ============================================================
# GUI Application (Project64-style)
# ============================================================

N64EMU_VERSION = "1.0X"
WINDOW_TITLE = "N64EMU 1.0X"
BUILD_STR = "Enhanced Edition"
COPYRIGHT_STR = "© 2025 N64EMU Team"


class N64EmuApp:
    def __init__(self, root: tk.Tk, show_plugins: bool = True) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        # N64 System
        self.system = N64System()
        
        # State
        self.keys: set[str] = set()
        self.running = False
        self.paused = False
        self.fps = 0
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.show_plugins = show_plugins

        # Build UI
        self._create_menu()
        self._create_main_ui()
        
        # Key bindings
        root.bind("<KeyPress>", self._key_down)
        root.bind("<KeyRelease>", self._key_up)
        
        self._tick_job = None

    def _create_menu(self):
        """Create PJ64-style menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open ROM...", command=self._open_rom, accelerator="Ctrl+O")
        file_menu.add_command(label="ROM Info...", command=self._show_rom_info)
        file_menu.add_separator()
        file_menu.add_command(label="Start Emulation", command=self.start, accelerator="F11")
        file_menu.add_command(label="End Emulation", command=self.stop, accelerator="F12")
        file_menu.add_separator()
        file_menu.add_command(label="Choose ROM Directory...", command=self._choose_rom_dir)
        file_menu.add_command(label="Refresh ROM List", command=self._refresh_roms)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # System Menu
        system_menu = tk.Menu(menubar, tearoff=0)
        system_menu.add_command(label="Reset", command=self._reset_system)
        system_menu.add_command(label="Pause", command=self.pause, accelerator="P")
        system_menu.add_separator()
        system_menu.add_command(label="Save State", accelerator="F5")
        system_menu.add_command(label="Load State", accelerator="F7")
        system_menu.add_separator()
        system_menu.add_command(label="Current Save State", command=self._save_state_dialog)
        system_menu.add_separator()
        system_menu.add_checkbutton(label="Limit FPS")
        system_menu.add_checkbutton(label="Speed Limiter")
        menubar.add_cascade(label="System", menu=system_menu)

        # Options Menu
        options_menu = tk.Menu(menubar, tearoff=0)
        options_menu.add_checkbutton(label="Full Screen", command=self.fullscreen, accelerator="Alt+Enter")
        options_menu.add_checkbutton(label="Always On Top", command=self._toggle_always_on_top)
        options_menu.add_separator()
        options_menu.add_command(label="Configure Graphics Plugin...", command=lambda: self._config_plugin("graphics"))
        options_menu.add_command(label="Configure Audio Plugin...", command=lambda: self._config_plugin("audio"))
        options_menu.add_command(label="Configure Controller Plugin...", command=lambda: self._config_plugin("input"))
        options_menu.add_command(label="Configure RSP Plugin...", command=lambda: self._config_plugin("rsp"))
        options_menu.add_separator()
        options_menu.add_command(label="Settings...", command=self._settings)
        menubar.add_cascade(label="Options", menu=options_menu)

        # Debugger Menu
        debugger_menu = tk.Menu(menubar, tearoff=0)
        debugger_menu.add_command(label="Debugger...", command=self._debugger)
        debugger_menu.add_command(label="Memory...", command=self._memory_viewer)
        debugger_menu.add_separator()
        debugger_menu.add_command(label="R4300i Registers", command=self._show_registers)
        menubar.add_cascade(label="Debugger", menu=debugger_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About...", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)

    def _create_main_ui(self):
        """Create main UI components"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Display canvas (320x240 centered)
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(pady=10)
        
        self.photo = tk.PhotoImage(width=self.system.rdp.width, height=self.system.rdp.height)
        self.canvas = tk.Canvas(
            canvas_frame, 
            width=self.system.rdp.width, 
            height=self.system.rdp.height,
            bg="black",
            highlightthickness=1,
            highlightbackground="gray"
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.fps_label = ttk.Label(status_frame, text="FPS: 0 / 60", width=15, anchor=tk.W)
        self.fps_label.pack(side=tk.LEFT, padx=5)
        
        self.vi_label = ttk.Label(status_frame, text="VI/s: 0", width=12, anchor=tk.W)
        self.vi_label.pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(status_frame, text="Ready", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # ROM Info Panel
        info_frame = ttk.LabelFrame(main_frame, text="ROM Information", padding=5)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        info_grid = ttk.Frame(info_frame)
        info_grid.pack()
        
        labels = [
            ("ROM Name:", "name"),
            ("Country:", "region"),
            ("CRC1:", "crc1"),
            ("CRC2:", "crc2"),
            ("CIC Chip:", "cic")
        ]
        
        self.info_values = {}
        for row, (label_text, key) in enumerate(labels):
            ttk.Label(info_grid, text=label_text, width=12, anchor=tk.W).grid(row=row, column=0, sticky=tk.W, pady=1)
            value_label = ttk.Label(info_grid, text="N/A", width=30, anchor=tk.W, foreground="blue")
            value_label.grid(row=row, column=1, sticky=tk.W, pady=1, padx=5)
            self.info_values[key] = value_label

    def _update_rom_info(self):
        """Update ROM info display"""
        info = self.system.memory.rom_info
        self.info_values["name"].config(text=info["name"])
        self.info_values["region"].config(text=info["region"])
        self.info_values["crc1"].config(text=info["crc1"])
        self.info_values["crc2"].config(text=info["crc2"])
        self.info_values["cic"].config(text=info["cic"])

    # ============================================================
    # ROM Management
    # ============================================================

    def _open_rom(self):
        """Open ROM file"""
        path = filedialog.askopenfilename(
            title="Select ROM File",
            filetypes=[
                ("N64 ROMs", "*.z64 *.n64 *.v64 *.rom"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return
        
        try:
            data = Path(path).read_bytes()
            info = self.system.memory.load_rom(data)
            self._update_rom_info()
            self._set_status(f"Loaded: {Path(path).name}")
            messagebox.showinfo("ROM Loaded", f"Successfully loaded:\n{info['name']}")
        except Exception as ex:
            messagebox.showerror("Load Error", f"Failed to load ROM:\n{ex}")

    def _show_rom_info(self):
        """Show detailed ROM info"""
        info = self.system.memory.rom_info
        msg = f"""ROM Information:

Name: {info['name']}
Country: {info['region']}
CRC1: {info['crc1']}
CRC2: {info['crc2']}
CIC Chip: {info['cic']}
Size: {len(self.system.memory.rom)} bytes
"""
        messagebox.showinfo("ROM Information", msg)

    def _choose_rom_dir(self):
        messagebox.showinfo("ROM Directory", "ROM directory selection coming soon!")

    def _refresh_roms(self):
        messagebox.showinfo("Refresh", "ROM list refresh coming soon!")

    # ============================================================
    # Emulation Control
    # ============================================================

    def start(self):
        """Start emulation"""
        if self.running:
            return
        if not self.system.memory.rom:
            messagebox.showwarning("No ROM", "Please load a ROM first!")
            return
            
        self.system.reset()
        self.running = True
        self.paused = False
        self._set_status("Emulation started")
        self._schedule_tick()

    def stop(self):
        """Stop emulation"""
        if not self.running:
            return
        self.running = False
        self.paused = False
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        self._set_status("Emulation stopped")

    def pause(self):
        """Pause/unpause emulation"""
        if not self.running:
            return
        self.paused = not self.paused
        self._set_status("Paused" if self.paused else "Running")

    def _reset_system(self):
        """Reset N64 system"""
        if self.running:
            self.system.reset()
            self._set_status("System reset")

    def fullscreen(self):
        """Toggle fullscreen"""
        is_fullscreen = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not is_fullscreen)

    # ============================================================
    # Main Loop
    # ============================================================

    def _schedule_tick(self):
        """Schedule next frame"""
        self._tick_job = self.root.after(16, self._tick)  # ~60 FPS

    def _tick(self):
        """Main emulation tick"""
        if not self.running:
            return
            
        if self.paused:
            self._schedule_tick()
            return
        
        # Run frame
        self.system.step_frame()
        
        # Render
        self.system.rdp.render_to_photoimage(self.photo)
        
        # Update controller
        self.system.pif.controllers[0].update_from_keys(self.keys)
        
        # Update stats
        self._update_fps()
        
        # Schedule next frame
        self._schedule_tick()

    def _update_fps(self):
        """Update FPS counter"""
        self.frame_count += 1
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = now
            self.fps_label.config(text=f"FPS: {self.fps} / 60")
            self.vi_label.config(text=f"VI/s: {self.system.vi.vsync_count}")
            self.system.vi.vsync_count = 0

    # ============================================================
    # Input
    # ============================================================

    def _key_down(self, e):
        self.keys.add(e.keysym)

    def _key_up(self, e):
        self.keys.discard(e.keysym)

    # ============================================================
    # Plugin Configuration
    # ============================================================

    def _config_plugin(self, plugin_type: str):
        """Configure plugin"""
        plugin = self.system.plugins.get_plugin(plugin_type)
        if not plugin:
            return
            
        win = tk.Toplevel(self.root)
        win.title(f"Configure {plugin.type} Plugin")
        win.geometry("400x300")
        
        ttk.Label(win, text=f"{plugin.name} v{plugin.version}", font=("Arial", 12, "bold")).pack(pady=10)
        ttk.Label(win, text=f"Author: {plugin.author}").pack()
        ttk.Label(win, text=f"Type: {plugin.type}").pack(pady=5)
        
        ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        ttk.Label(win, text="Plugin configuration options would appear here").pack(pady=20)
        
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK", command=win.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=5)

    # ============================================================
    # Dialogs
    # ============================================================

    def _settings(self):
        """Settings dialog"""
        messagebox.showinfo("Settings", "Settings dialog coming soon!")

    def _save_state_dialog(self):
        """Save state dialog"""
        messagebox.showinfo("Save States", "Save state management coming soon!")

    def _debugger(self):
        """Open debugger"""
        messagebox.showinfo("Debugger", "Debugger coming soon!")

    def _memory_viewer(self):
        """Memory viewer"""
        messagebox.showinfo("Memory", "Memory viewer coming soon!")

    def _show_registers(self):
        """Show CPU registers"""
        regs = self.system.cpu.registers
        msg = f"""R4300i Registers:

PC: 0x{regs.pc:08X}
HI: 0x{regs.hi:08X}
LO: 0x{regs.lo:08X}

GPR[0-3]: {' '.join(f'${i}:0x{regs.gpr[i]:08X}' for i in range(4))}

Cycles: {self.system.cpu.cycles}
Instructions: {self.system.cpu.instructions_executed}
"""
        messagebox.showinfo("R4300i Registers", msg)

    def _toggle_always_on_top(self):
        """Toggle always on top"""
        current = self.root.attributes("-topmost")
        self.root.attributes("-topmost", not current)

    def _about(self):
        """About dialog"""
        plugin_info = "\n".join([
            f"  {p.name} v{p.version}"
            for p in self.system.plugins.plugins.values()
        ])
        
        msg = f"""{WINDOW_TITLE}
{BUILD_STR}
{COPYRIGHT_STR}

Nintendo 64 Emulator
Project64-style interface with enhanced core architecture

Active Plugins:
{plugin_info}

Controls:
  D-Pad: Arrow Keys
  A Button: Space
  B Button: Enter
  Start: S
  Z: Z
  C-Buttons: I/K/J/L

Core Components:
  • R4300i CPU Core
  • RDRAM Memory (4MB)
  • RDP (Graphics)
  • RSP (Signal Processor)
  • Audio/Video Interfaces
  • PIF (Controller)
"""
        messagebox.showinfo("About N64EMU 1.0X", msg)

    def _set_status(self, msg: str):
        """Set status message"""
        self.status_label.config(text=msg)


# ============================================================
# Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="N64EMU 1.0X — Project64-style N64 Emulator")
    parser.add_argument("--rom", type=str, help="Path to ROM file")
    parser.add_argument("--plugins", choices=["on", "off"], default="on", help="Show plugins menu")
    args = parser.parse_args()

    root = tk.Tk()
    app = N64EmuApp(root, show_plugins=(args.plugins != "off"))

    if args.rom:
        try:
            data = Path(args.rom).read_bytes()
            app.system.memory.load_rom(data)
            app._update_rom_info()
            app._set_status(f"Loaded: {Path(args.rom).name}")
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))

    root.mainloop()


if __name__ == "__main__":
    main()
