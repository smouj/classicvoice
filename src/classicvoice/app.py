from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import PRESETS, VoicePreset, build_espeak_command, resolve_espeak

APP_DIR = Path(__file__).resolve().parents[2]


class ClassicVoiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ClassicVoice")
        self.geometry("620x500")
        self.minsize(560, 450)

        self.preset_label = tk.StringVar(value=PRESETS[0].label)
        self.speed = tk.IntVar(value=PRESETS[0].speed)
        self.pitch = tk.IntVar(value=PRESETS[0].pitch)
        self.volume = tk.IntVar(value=PRESETS[0].amplitude)
        self.status = tk.StringVar(value="Listo")
        self.preview_file = Path(tempfile.gettempdir()) / "classicvoice_preview.wav"

        self._style()
        self._build()

    def _style(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=9)

    def _build(self):
        root = ttk.Frame(self, padding=22)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="ClassicVoice", style="Title.TLabel").pack(anchor="w")
        ttk.Label(root, text="Síntesis de voz clásica, local y sin cuentas.").pack(anchor="w", pady=(0, 14))

        self.text = tk.Text(root, height=10, wrap="word", font=("Segoe UI", 11), undo=True)
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", "Hola. Esto es una prueba de ClassicVoice.")

        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(14, 0))
        ttk.Label(controls, text="Preset").grid(row=0, column=0, sticky="w")
        combo = ttk.Combobox(controls, textvariable=self.preset_label, values=[p.label for p in PRESETS], state="readonly", width=22)
        combo.grid(row=0, column=1, sticky="w", padx=(10, 24))
        combo.bind("<<ComboboxSelected>>", self._apply_preset)

        self._slider(controls, "Velocidad", self.speed, 80, 300, 1)
        self._slider(controls, "Tono", self.pitch, 0, 99, 2)
        self._slider(controls, "Volumen", self.volume, 0, 200, 3)

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(18, 7))
        ttk.Button(buttons, text="▶  Escuchar", style="Action.TButton", command=self._preview).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(buttons, text="Guardar WAV", style="Action.TButton", command=self._save).pack(side="left", expand=True, fill="x", padx=(6, 0))
        ttk.Label(root, textvariable=self.status).pack(anchor="center")

    def _slider(self, parent, label, variable, low, high, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        scale = tk.Scale(
            parent,
            from_=low,
            to=high,
            variable=variable,
            orient="horizontal",
            showvalue=False,
            resolution=1,
            highlightthickness=0,
            bd=0,
        )
        scale.grid(row=row, column=1, sticky="ew", padx=(10, 10))
        value = ttk.Label(parent, textvariable=variable, width=4)
        value.grid(row=row, column=2, sticky="e")
        parent.columnconfigure(1, weight=1)

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
        output_dir = APP_DIR / "output"
        output_dir.mkdir(exist_ok=True)
        selected = filedialog.asksaveasfilename(
            title="Guardar diálogo",
            initialdir=output_dir,
            initialfile="dialogue.wav",
            defaultextension=".wav",
            filetypes=[("Audio WAV", "*.wav")],
        )
        if not selected:
            return
        if self._generate(Path(selected)):
            self.status.set(f"Guardado: {Path(selected).name}")


def main():
    ClassicVoiceApp().mainloop()


if __name__ == "__main__":
    main()
