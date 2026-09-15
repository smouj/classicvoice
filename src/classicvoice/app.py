from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import PRESETS, VoicePreset, build_espeak_command, resolve_espeak

APP_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_DIR / "classicvoice.json"

# DPI awareness for consistent rendering on Windows
if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class ClassicVoiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ClassicVoice")
        self.geometry("620x520")
        self.minsize(560, 460)

        # Load saved config
        cfg = _load_config()
        saved_preset = cfg.get("preset", PRESETS[0].label)
        self.preset_label = tk.StringVar(value=saved_preset)
        self.speed = tk.IntVar(value=cfg.get("speed", PRESETS[0].speed))
        self.pitch = tk.IntVar(value=cfg.get("pitch", PRESETS[0].pitch))
        self.volume = tk.IntVar(value=cfg.get("volume", PRESETS[0].amplitude))
        self._last_dir = cfg.get("last_dir", str(APP_DIR / "output"))
        self.status = tk.StringVar(value="Listo")
        self.preview_file = Path(tempfile.gettempdir()) / "classicvoice_preview.wav"

        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 9))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=9)
        style.configure("Dim.TLabel", font=("Segoe UI", 8), foreground="#888888")

    def _build(self):
        root = ttk.Frame(self, padding=22)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="ClassicVoice", style="Title.TLabel").pack(anchor="w")
        ttk.Label(root, text="Síntesis de voz clásica, local y sin cuentas.", style="Sub.TLabel").pack(anchor="w", pady=(0, 14))

        self.text = tk.Text(root, height=8, wrap="word", font=("Segoe UI", 11), undo=True)
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", "Hola. Esto es una prueba de ClassicVoice.")

        controls = ttk.LabelFrame(root, text="Configuración", padding=8)
        controls.pack(fill="x", pady=(14, 0))

        row0 = ttk.Frame(controls)
        row0.pack(fill="x", pady=(0, 6))
        ttk.Label(row0, text="Preset").pack(side="left")
        combo = ttk.Combobox(row0, textvariable=self.preset_label, values=[p.label for p in PRESETS], state="readonly", width=22)
        combo.pack(side="left", padx=(8, 0))
        combo.bind("<<ComboboxSelected>>", self._apply_preset)

        self._slider(controls, "Velocidad", self.speed, 80, 300)
        self._slider(controls, "Tono", self.pitch, 0, 99)
        self._slider(controls, "Volumen", self.volume, 0, 200)

        # Output folder row
        folder_frame = ttk.Frame(controls)
        folder_frame.pack(fill="x", pady=(4, 0))
        ttk.Label(folder_frame, text="Carpeta").pack(side="left")
        self.dir_label = ttk.Label(folder_frame, text=self._short_dir(), style="Dim.TLabel", width=35, anchor="w")
        self.dir_label.pack(side="left", padx=(8, 4))
        ttk.Button(folder_frame, text="…", width=3, command=self._choose_dir).pack(side="left")

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(18, 7))
        ttk.Button(buttons, text="▶  Escuchar", style="Action.TButton", command=self._preview).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(buttons, text="Guardar WAV", style="Action.TButton", command=self._save).pack(side="left", expand=True, fill="x", padx=(6, 0))
        ttk.Label(root, textvariable=self.status).pack(anchor="center")

    def _short_dir(self) -> str:
        d = self._last_dir
        if len(d) > 38:
            return "…" + d[-35:]
        return d

    def _choose_dir(self):
        chosen = filedialog.askdirectory(
            title="Carpeta de guardado",
            initialdir=self._last_dir,
        )
        if chosen:
            self._last_dir = chosen
            self.dir_label.configure(text=self._short_dir())

    def _slider(self, parent, label, variable, low, high):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=8).pack(side="left")
        scale = tk.Scale(
            row,
            from_=low,
            to=high,
            variable=variable,
            orient="horizontal",
            showvalue=True,
            resolution=1,
            highlightthickness=0,
            bd=0,
            length=300,
        )
        scale.pack(side="left", fill="x", expand=True, padx=(4, 4))
        ttk.Label(row, textvariable=variable, width=4).pack(side="right")

    def _preset(self) -> VoicePreset:
        return next(p for p in PRESETS if p.label == self.preset_label.get())

    def _apply_preset(self, _event=None):
        preset = self._preset()
        self.speed.set(preset.speed)
        self.pitch.set(preset.pitch)
        self.volume.set(preset.amplitude)

    def _text_value(self) -> str:
        return self.text.get("1.0", "end").strip()

    def _generate(self, output: Path) -> bool:
        executable = resolve_espeak(APP_DIR)
        if not executable:
            messagebox.showerror("eSpeak NG no encontrado", "Instala eSpeak NG o copia espeak-ng.exe y sus archivos requeridos en bin/.")
            return False
        try:
            cmd = build_espeak_command(executable, self._text_value(), output, self._preset(), self.speed.get(), self.pitch.get(), self.volume.get())
        except ValueError as exc:
            messagebox.showinfo("ClassicVoice", str(exc))
            return False

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            result = subprocess.run(cmd, capture_output=True, creationflags=creationflags, timeout=45)
        except (OSError, subprocess.TimeoutExpired) as exc:
            messagebox.showerror("No se pudo sintetizar", str(exc))
            return False
        if result.returncode != 0 or not output.exists():
            error = result.stderr.decode(errors="replace").strip() or "eSpeak NG terminó con un error."
            messagebox.showerror("Síntesis fallida", error)
            return False
        return True

    def _preview(self):
        if not self._generate(self.preview_file):
            return
        self.status.set("Reproduciendo vista previa")
        try:
            if os.name == "nt":
                import winsound
                winsound.PlaySound(str(self.preview_file), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                self.status.set(f"Vista previa generada: {self.preview_file}")
        except Exception as exc:
            messagebox.showerror("No se pudo reproducir", str(exc))

    def _save(self):
        output_dir = Path(self._last_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        selected = filedialog.asksaveasfilename(
            title="Guardar diálogo",
            initialdir=str(output_dir),
            initialfile="dialogue.wav",
            defaultextension=".wav",
            filetypes=[("Audio WAV", "*.wav")],
        )
        if not selected:
            return
        # Remember the chosen directory
        self._last_dir = str(Path(selected).parent)
        self.dir_label.configure(text=self._short_dir())
        if self._generate(Path(selected)):
            self.status.set(f"Guardado: {Path(selected).name}")

    def _close(self):
        # Save config on exit
        cfg = {
            "preset": self.preset_label.get(),
            "speed": self.speed.get(),
            "pitch": self.pitch.get(),
            "volume": self.volume.get(),
            "last_dir": self._last_dir,
        }
        _save_config(cfg)
        self.destroy()


def main():
    ClassicVoiceApp().mainloop()


if __name__ == "__main__":
    main()