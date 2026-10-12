from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid
import wave

from . import __version__
from .core import (
    LEGACY_PRESET_LABELS,
    MAX_TEXT_CHARS,
    PRESETS,
    VoicePreset,
    app_data_dir,
    app_resource_dir,
    apply_pronunciation_rules,
    build_espeak_file_command,
    espeak_environment,
    normalize_wav,
    resolve_espeak,
    validate_wav,
)


if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


APP_DIR = app_resource_dir()
DATA_DIR = app_data_dir()
CONFIG_PATH = DATA_DIR / "settings.json"
DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "ClassicVoice"
PLACEHOLDER = "Escribe o pega aquí el texto que quieres convertir en voz…"
COLORS = {
    "canvas": "#f3f5fa",
    "card": "#ffffff",
    "text": "#172033",
    "muted": "#68758b",
    "border": "#e2e7f0",
    "accent": "#5148e5",
    "accent_hover": "#4338ca",
    "green": "#12764a",
    "green_soft": "#e8f6ee",
    "amber": "#81520a",
    "amber_soft": "#fff5df",
    "red": "#a23b43",
}


def _bounded_int(value: object, fallback: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _load_config() -> dict:
    candidates = [CONFIG_PATH]
    legacy_path = APP_DIR / "classicvoice.json"
    if legacy_path != CONFIG_PATH:
        candidates.append(legacy_path)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if isinstance(data, dict):
            rules = data.get("pronunciation_rules", {})
            if not isinstance(rules, dict):
                rules = {}
            data["pronunciation_rules"] = {
                str(key).strip()[:80]: str(value).strip()[:120]
                for key, value in rules.items()
                if str(key).strip() and str(value).strip()
            }
            return data
    return {}


def _save_config(config: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_PATH.with_name(f"settings.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, CONFIG_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_filename(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "voz")
    base = re.sub(r"[^\w -]", "", first_line, flags=re.UNICODE).strip(" .-")
    return (base[:48].strip() or "voz") + ".wav"


class ClassicVoiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ClassicVoice")
        self.geometry("900x820")
        self.minsize(780, 650)
        self.configure(bg=COLORS["canvas"])
        icon_path = APP_DIR / "assets" / "classicvoice.ico"
        if icon_path.is_file():
            try:
                self.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass

        cfg = _load_config()
        saved_key = str(cfg.get("preset_key", ""))
        if not saved_key:
            saved_value = str(cfg.get("preset", PRESETS[0].label))
            saved_key = LEGACY_PRESET_LABELS.get(saved_value, saved_value)
            if saved_key not in {preset.key for preset in PRESETS}:
                saved_key = next((p.key for p in PRESETS if p.label == saved_value), PRESETS[0].key)
        selected = next((p for p in PRESETS if p.key == saved_key), PRESETS[0])

        self.preset_label = tk.StringVar(value=selected.label)
        self.speed = tk.IntVar(value=_bounded_int(cfg.get("speed"), selected.speed, 80, 300))
        self.pitch = tk.IntVar(value=_bounded_int(cfg.get("pitch"), selected.pitch, 0, 99))
        self.volume = tk.IntVar(value=_bounded_int(cfg.get("volume"), selected.amplitude, 0, 200))
        normalize_value = cfg.get("normalize", True)
        self.normalize_audio = tk.BooleanVar(value=normalize_value if isinstance(normalize_value, bool) else True)
        output_dir = cfg.get("last_dir", str(DEFAULT_OUTPUT_DIR))
        self._last_dir = str(output_dir) if isinstance(output_dir, str) and output_dir.strip() else str(DEFAULT_OUTPUT_DIR)
        rules = cfg.get("pronunciation_rules", {})
        self.pronunciation_rules: dict[str, str] = rules if isinstance(rules, dict) else {}

        self.status = tk.StringVar(value="Listo para crear audio")
        self.word_count = tk.StringVar(value="0 palabras · 0 caracteres")
        self.preset_description = tk.StringVar(value=selected.description)
        self.engine = resolve_espeak(APP_DIR)
        self._events: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._process_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._busy = False
        self._closing = False
        self._playing = False
        self._playback_token: str | None = None
        self._playback_after: str | None = None
        self._save_after: str | None = None
        self._placeholder_active = True
        self._preview_path: Path | None = None
        self._layout_after: str | None = None
        self._pronunciation_dialog: tk.Toplevel | None = None

        self._configure_style()
        self._build()
        self._bind_events()
        self._update_count()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(80, self._poll_events)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=COLORS["canvas"])
        style.configure("App.TFrame", background=COLORS["canvas"])
        style.configure("Card.TFrame", background=COLORS["card"])
        style.configure("TLabel", background=COLORS["canvas"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=COLORS["canvas"], foreground=COLORS["text"], font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", background=COLORS["canvas"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=COLORS["card"], foreground=COLORS["text"], font=("Segoe UI", 11, "bold"))
        style.configure("CardText.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Muted.TLabel", background=COLORS["canvas"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=COLORS["canvas"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("EngineOk.TLabel", background=COLORS["green_soft"], foreground=COLORS["green"], padding=(10, 6), font=("Segoe UI", 9, "bold"))
        style.configure("EngineMissing.TLabel", background=COLORS["amber_soft"], foreground=COLORS["amber"], padding=(10, 6), font=("Segoe UI", 9, "bold"))
        style.configure("Primary.TButton", background=COLORS["accent"], foreground="#ffffff", padding=(18, 11), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Primary.TButton", background=[("disabled", "#a9a7d9"), ("active", COLORS["accent_hover"])], foreground=[("disabled", "#f3f2ff")])
        style.configure("Secondary.TButton", background=COLORS["card"], foreground=COLORS["text"], padding=(15, 10), font=("Segoe UI", 10, "bold"), borderwidth=1)
        style.map("Secondary.TButton", background=[("disabled", "#f2f3f7"), ("active", "#f4f5fb")])
        style.configure("Stop.TButton", background=COLORS["card"], foreground=COLORS["red"], padding=(13, 10), font=("Segoe UI", 10, "bold"), borderwidth=1)
        style.map("Stop.TButton", background=[("disabled", "#f2f3f7"), ("active", "#fff0f0")])
        style.configure("TCombobox", padding=8, fieldbackground=COLORS["card"], background=COLORS["card"], foreground=COLORS["text"])
        style.configure("TCheckbutton", background=COLORS["card"], foreground=COLORS["text"], font=("Segoe UI", 9))
        style.configure("Voice.Horizontal.TScale", background=COLORS["accent"], troughcolor="#e8eaf3", bordercolor=COLORS["accent"], lightcolor=COLORS["accent"], darkcolor=COLORS["accent"], arrowcolor="#ffffff")
        style.map("Voice.Horizontal.TScale", background=[("active", COLORS["accent_hover"])])
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 9), background=COLORS["card"], fieldbackground=COLORS["card"])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build(self) -> None:
        self._viewport = tk.Canvas(self, bg=COLORS["canvas"], highlightthickness=0)
        self._page_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._viewport.yview)
        self._viewport.configure(yscrollcommand=self._page_scrollbar.set)
        self._viewport.pack(side="left", fill="both", expand=True)
        page = ttk.Frame(self._viewport, style="App.TFrame", padding=(26, 22, 26, 18))
        self._page = page
        self._page_window = self._viewport.create_window(0, 0, window=page, anchor="nw")
        self._viewport.bind("<Configure>", self._schedule_layout)
        page.bind("<Configure>", self._schedule_layout)

        header = ttk.Frame(page, style="App.TFrame")
        header.pack(fill="x", pady=(0, 17))
        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="ClassicVoice", style="Header.TLabel").pack(anchor="w")
        self._subtitle = ttk.Label(title_block, text="Voz clásica en español, con control total y sin salir de tu PC.", style="Subtitle.TLabel", wraplength=430)
        self._subtitle.pack(anchor="w", pady=(2, 0))
        engine_label = "Motor de voz listo" if self.engine else "Falta el motor de voz"
        engine_style = "EngineOk.TLabel" if self.engine else "EngineMissing.TLabel"
        ttk.Label(header, text=engine_label, style=engine_style).pack(side="right", anchor="center", padx=(12, 0))

        if not self.engine:
            notice = tk.Label(
                page,
                text="No se ha encontrado eSpeak NG. La instalación completa incluye el motor; al ejecutar desde el código, instálalo o colócalo en bin/espeak-ng/.",
                bg=COLORS["amber_soft"], fg=COLORS["amber"], font=("Segoe UI", 9),
                padx=12, pady=9, justify="left", wraplength=800,
            )
            notice.pack(fill="x", pady=(0, 12))

        editor = ttk.Frame(page, style="Card.TFrame", padding=16)
        editor.pack(fill="both", expand=True)
        editor_top = ttk.Frame(editor, style="Card.TFrame")
        editor_top.pack(fill="x", pady=(0, 8))
        ttk.Label(editor_top, text="Texto", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(editor_top, textvariable=self.word_count, style="CardText.TLabel").pack(side="right")
        editor_area = ttk.Frame(editor, style="Card.TFrame")
        editor_area.pack(fill="both", expand=True)
        editor_area.rowconfigure(0, weight=1)
        editor_area.columnconfigure(0, weight=1)
        self.text = tk.Text(
            editor_area,
            height=4,
            wrap="word",
            font=("Segoe UI", 11),
            undo=True,
            padx=13,
            pady=12,
            bg="#ffffff",
            fg="#8792a5",
            insertbackground=COLORS["accent"],
            selectbackground="#dcd9ff",
            selectforeground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            maxundo=100,
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(editor_area, orient="vertical", command=self.text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.insert("1.0", PLACEHOLDER)
        self.text.edit_modified(False)
        self._editor_hint = ttk.Label(editor, text="Ctrl + Intro: escuchar · Ctrl + S: guardar WAV · Esc: detener", style="CardText.TLabel", wraplength=650)
        self._editor_hint.pack(anchor="w", pady=(7, 0))

        settings = ttk.Frame(page, style="Card.TFrame", padding=(16, 13))
        settings.pack(fill="x", pady=(14, 0))
        ttk.Label(settings, text="Voz y salida", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))

        preset_row = ttk.Frame(settings, style="Card.TFrame")
        preset_row.pack(fill="x", pady=(0, 7))
        ttk.Label(preset_row, text="Preset", style="CardText.TLabel", width=11).pack(side="left")
        self.preset_combo = ttk.Combobox(
            preset_row,
            textvariable=self.preset_label,
            values=[preset.label for preset in PRESETS],
            state="readonly",
            width=23,
        )
        self.preset_combo.pack(side="left")
        self._preset_hint = ttk.Label(settings, textvariable=self.preset_description, style="CardText.TLabel", wraplength=650)
        self._preset_hint.pack(anchor="w", pady=(0, 7))

        self._slider(settings, "Velocidad", self.speed, 80, 300, "palabras por minuto")
        self._slider(settings, "Tono", self.pitch, 0, 99, "grave a agudo")
        self._slider(settings, "Volumen", self.volume, 0, 200, "nivel de síntesis")

        output_row = ttk.Frame(settings, style="Card.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        output_row.columnconfigure(1, weight=1)
        ttk.Label(output_row, text="Guardar en", style="CardText.TLabel", width=11).grid(row=0, column=0, sticky="w")
        self.dir_label = ttk.Label(output_row, text=self._short_dir(), style="CardText.TLabel", width=1, anchor="w")
        self.dir_label.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Button(output_row, text="Cambiar…", style="Secondary.TButton", command=self._choose_dir).grid(row=0, column=2, sticky="e")
        options_row = ttk.Frame(settings, style="Card.TFrame")
        options_row.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(options_row, text="Normalizar volumen", variable=self.normalize_audio).pack(side="left")
        self.rules_button = ttk.Button(options_row, text=f"Pronunciación · {len(self.pronunciation_rules)}", style="Secondary.TButton", command=self._open_pronunciation)
        self.rules_button.pack(side="right")

        actions = ttk.Frame(page, style="App.TFrame")
        actions.pack(fill="x", pady=(15, 7))
        self.preview_button = ttk.Button(actions, text="▶  Escuchar", style="Primary.TButton", command=self._preview)
        self.preview_button.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.save_button = ttk.Button(actions, text="Guardar WAV", style="Secondary.TButton", command=self._save)
        self.save_button.pack(side="left", expand=True, fill="x", padx=(6, 6))
        self.stop_button = ttk.Button(actions, text="Detener", style="Stop.TButton", command=self._stop, state="disabled")
        self.stop_button.pack(side="left", padx=(6, 0))

        footer = ttk.Frame(page, style="App.TFrame")
        footer.pack(fill="x")
        self._status_label = ttk.Label(footer, textvariable=self.status, style="Status.TLabel", wraplength=650)
        self._status_label.pack(anchor="w", fill="x")
        ttk.Label(footer, text=f"Versión {__version__} · Procesamiento local", style="Status.TLabel").pack(anchor="w", pady=(4, 0))

    def _schedule_layout(self, _event=None) -> None:
        if self._layout_after is None and not self._closing:
            self._layout_after = self.after_idle(self._update_layout)

    def _update_layout(self) -> None:
        self._layout_after = None
        width = max(1, self._viewport.winfo_width())
        height = max(self._page.winfo_reqheight(), self._viewport.winfo_height())
        self._viewport.itemconfigure(self._page_window, width=width, height=height)
        self._viewport.configure(scrollregion=(0, 0, width, height))
        if height > self._viewport.winfo_height():
            if not self._page_scrollbar.winfo_manager():
                self._page_scrollbar.pack(side="right", fill="y")
        else:
            self._page_scrollbar.pack_forget()
            self._viewport.yview_moveto(0)
        for label in (self._editor_hint, self._preset_hint, self._status_label):
            label.configure(wraplength=max(180, width - 90))
        self._subtitle.configure(wraplength=max(180, width - 260))

    def _slider(self, parent, label: str, variable: tk.IntVar, low: int, high: int, hint: str) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=label, style="CardText.TLabel", width=11).pack(side="left")
        scale = ttk.Scale(
            row,
            from_=low,
            to=high,
            variable=variable,
            orient="horizontal",
            command=lambda value: variable.set(round(float(value))),
            style="Voice.Horizontal.TScale",
            length=360,
            takefocus=True,
        )
        scale.pack(side="left", fill="x", expand=True, padx=(3, 8))
        ttk.Label(row, textvariable=variable, style="CardTitle.TLabel", width=4, anchor="e").pack(side="right", padx=(0, 10))
        ttk.Label(row, text=hint, style="CardText.TLabel", width=22).pack(side="right", anchor="e")

    def _bind_events(self) -> None:
        self.text.bind("<<Modified>>", self._on_text_modified)
        self.text.bind("<FocusIn>", self._clear_placeholder)
        self.text.bind("<FocusOut>", self._restore_placeholder)
        self.text.bind("<Control-a>", self._select_all_text)
        self.text.bind("<Control-A>", self._select_all_text)
        self.preset_combo.bind("<<ComboboxSelected>>", self._apply_preset)
        self.bind("<Control-Return>", self._hotkey_preview)
        self.bind("<Control-s>", self._hotkey_save)
        self.bind("<Control-S>", self._hotkey_save)
        self.bind("<Escape>", lambda _event: self._stop())
        self.bind("<MouseWheel>", self._scroll_page)
        self.bind("<FocusIn>", self._reveal_focused_control, add="+")
        for variable in (self.speed, self.pitch, self.volume, self.normalize_audio):
            variable.trace_add("write", self._schedule_config_save)

    def _select_all_text(self, _event=None):
        self._clear_placeholder()
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _clear_placeholder(self, _event=None) -> None:
        if self._placeholder_active:
            self.text.delete("1.0", "end")
            self.text.configure(fg=COLORS["text"])
            self._placeholder_active = False
            self.text.edit_modified(False)
            self.text.edit_reset()

    def _restore_placeholder(self, _event=None) -> None:
        if not self.text.get("1.0", "end-1c").strip():
            self.text.delete("1.0", "end")
            self.text.insert("1.0", PLACEHOLDER)
            self.text.configure(fg="#8792a5")
            self._placeholder_active = True
            self.text.edit_modified(False)
            self.text.edit_reset()
            self._update_count()

    def _scroll_page(self, event) -> None:
        if event.widget is self.text or not self._page_scrollbar.winfo_manager():
            return
        if isinstance(event.widget, (tk.Scale, ttk.Scale)):
            return
        self._viewport.yview_scroll(-int(event.delta / 120), "units")

    def _reveal_focused_control(self, event) -> None:
        widget = event.widget
        if widget.winfo_toplevel() is not self or not self._page_scrollbar.winfo_manager():
            return
        top = widget.winfo_rooty() - self._page.winfo_rooty()
        bottom = top + widget.winfo_height()
        visible_top = self._viewport.canvasy(0)
        visible_bottom = visible_top + self._viewport.winfo_height()
        total = max(1, self._page.winfo_height())
        if top < visible_top:
            self._viewport.yview_moveto(max(0, top - 12) / total)
        elif bottom > visible_bottom:
            self._viewport.yview_moveto((bottom + 12 - self._viewport.winfo_height()) / total)

    def _on_text_modified(self, _event=None) -> None:
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self._update_count()

    def _update_count(self) -> None:
        value = self._text_value()
        chars = f"{len(value):,}".replace(",", ".")
        self.word_count.set(f"{len(value.split())} palabras · {chars} caracteres")

    def _text_value(self) -> str:
        if self._placeholder_active:
            return ""
        return self.text.get("1.0", "end-1c").strip()

    def _preset(self) -> VoicePreset:
        label = self.preset_label.get()
        return next((preset for preset in PRESETS if preset.label == label), PRESETS[0])

    def _apply_preset(self, _event=None) -> None:
        preset = self._preset()
        self.speed.set(preset.speed)
        self.pitch.set(preset.pitch)
        self.volume.set(preset.amplitude)
        self.preset_description.set(preset.description)
        self._schedule_config_save()

    def _short_dir(self) -> str:
        value = self._last_dir
        home = str(Path.home())
        if value.casefold().startswith((home + os.sep).casefold()):
            value = "~" + value[len(home):]
        return "…" + value[-38:] if len(value) > 41 else value

    def _choose_dir(self) -> None:
        try:
            Path(self._last_dir).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        chosen = filedialog.askdirectory(title="Carpeta de guardado", initialdir=self._last_dir, parent=self)
        if chosen:
            self._last_dir = chosen
            self.dir_label.configure(text=self._short_dir())
            self._schedule_config_save()

    def _schedule_config_save(self, *_args) -> None:
        if self._closing:
            return
        if self._save_after:
            try:
                self.after_cancel(self._save_after)
            except tk.TclError:
                pass
        self._save_after = self.after(650, self._write_config)

    def _config_values(self) -> dict:
        return {
            "version": 2,
            "preset_key": self._preset().key,
            "speed": _bounded_int(self.speed.get(), self._preset().speed, 80, 300),
            "pitch": _bounded_int(self.pitch.get(), self._preset().pitch, 0, 99),
            "volume": _bounded_int(self.volume.get(), self._preset().amplitude, 0, 200),
            "normalize": bool(self.normalize_audio.get()),
            "last_dir": self._last_dir,
            "pronunciation_rules": self.pronunciation_rules,
        }

    def _write_config(self) -> None:
        self._save_after = None
        try:
            _save_config(self._config_values())
        except OSError as exc:
            if not self._closing:
                self.status.set(f"No se pudieron guardar los ajustes: {exc}")

    def _hotkey_preview(self, _event=None):
        self._preview()
        return "break"

    def _hotkey_save(self, _event=None):
        self._save()
        return "break"

    def _preview(self) -> None:
        self._start_generation("preview", None)

    def _save(self) -> None:
        if self._busy:
            return
        text = self._text_value()
        if not text:
            messagebox.showinfo("ClassicVoice", "Escribe primero el texto que quieres convertir.", parent=self)
            self.text.focus_set()
            return
        try:
            Path(self._last_dir).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Carpeta no disponible", f"No se pudo preparar la carpeta de salida.\n\n{exc}", parent=self)
            return
        selected = filedialog.asksaveasfilename(
            title="Guardar audio WAV",
            initialdir=self._last_dir,
            initialfile=_safe_filename(text),
            defaultextension=".wav",
            filetypes=[("Audio WAV", "*.wav")],
            parent=self,
        )
        if not selected:
            return
        target = Path(selected)
        if target.suffix.lower() != ".wav":
            messagebox.showinfo("Formato WAV", "ClassicVoice exporta audio WAV. Elige un nombre terminado en .wav.", parent=self)
            return
        self._last_dir = str(target.parent)
        self.dir_label.configure(text=self._short_dir())
        self._schedule_config_save()
        self._start_generation("export", target)

    def _start_generation(self, mode: str, target: Path | None) -> None:
        if self._busy:
            return
        source = self._text_value()
        if not source:
            messagebox.showinfo("ClassicVoice", "Escribe primero el texto que quieres convertir.", parent=self)
            self.text.focus_set()
            return
        if len(source) > MAX_TEXT_CHARS:
            limit = f"{MAX_TEXT_CHARS:,}".replace(",", ".")
            messagebox.showwarning(
                "Texto demasiado largo",
                f"El límite por archivo es de {limit} caracteres. Divide el texto en varios WAV para obtener resultados más estables.",
                parent=self,
            )
            return
        if not self.engine:
            messagebox.showerror(
                "Falta el motor de voz",
                "No se encuentra eSpeak NG. La instalación completa de ClassicVoice lo incluye; en una copia del código, instálalo o colócalo en bin/espeak-ng/.",
                parent=self,
            )
            return

        processed = apply_pronunciation_rules(source, self.pronunciation_rules)
        if not processed.strip():
            messagebox.showinfo("ClassicVoice", "Los reemplazos de pronunciación han dejado el texto vacío.", parent=self)
            return

        preset = self._preset()
        settings = {
            "speed": _bounded_int(self.speed.get(), preset.speed, 80, 300),
            "pitch": _bounded_int(self.pitch.get(), preset.pitch, 0, 99),
            "volume": _bounded_int(self.volume.get(), preset.amplitude, 0, 200),
            "normalize": bool(self.normalize_audio.get()),
        }
        if mode == "export" and target is None:
            return

        if self._playing:
            self._stop_playback("Preparando la voz…")
        self._remove_preview()

        self._cancel_event = threading.Event()
        self._busy = True
        self.preview_button.configure(state="disabled")
        self.save_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set("Preparando la voz…")
        self._worker = threading.Thread(
            target=self._run_generation,
            args=(mode, target, processed, preset, settings, self._cancel_event),
            name="ClassicVoice-synthesis",
            daemon=True,
        )
        self._worker.start()

    def _run_generation(
        self,
        mode: str,
        target: Path | None,
        text: str,
        preset: VoicePreset,
        settings: dict,
        cancel_event: threading.Event,
    ) -> None:
        temp_dir = Path(tempfile.gettempdir()) / "ClassicVoice"
        input_path: Path | None = None
        working_output: Path | None = None
        retain_output = False
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            job_id = uuid.uuid4().hex
            input_path = temp_dir / f"input-{job_id}.txt"
            input_path.write_text(text, encoding="utf-8", newline="\n")
            if mode == "export" and target is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                working_output = target.with_name(f".{target.stem}.{job_id}.tmp.wav")
            else:
                working_output = temp_dir / f"preview-{job_id}.wav"

            command = build_espeak_file_command(
                self.engine,
                input_path,
                working_output,
                preset,
                settings["speed"],
                settings["pitch"],
                settings["volume"],
            )
            if cancel_event.is_set():
                raise InterruptedError("cancelled")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                env=espeak_environment(APP_DIR, self.engine),
            )
            with self._process_lock:
                self._process = process
                if cancel_event.is_set():
                    try:
                        process.terminate()
                    except OSError:
                        pass
            try:
                _stdout, stderr = process.communicate(timeout=180)
            except subprocess.TimeoutExpired:
                process.kill()
                _stdout, stderr = process.communicate()
                if not cancel_event.is_set():
                    raise TimeoutError("La síntesis ha tardado demasiado. Prueba a dividir el texto en fragmentos más pequeños.")
            finally:
                with self._process_lock:
                    if self._process is process:
                        self._process = None

            if cancel_event.is_set():
                raise InterruptedError("cancelled")
            if process.returncode != 0:
                detail = stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(detail or "eSpeak NG ha terminado con un error.")
            frame_count, duration = validate_wav(working_output)
            if frame_count <= 0:
                raise ValueError("No se ha generado audio.")
            if settings["normalize"]:
                normalize_wav(working_output)
            if mode == "export" and target is not None:
                os.replace(working_output, target)
                retain_output = True
                working_output = target
            else:
                retain_output = True
            self._events.put(("done", mode, str(working_output), None, duration))
        except InterruptedError:
            self._events.put(("cancelled", mode, None, None, 0.0))
        except Exception as exc:
            self._events.put(("done", mode, None, str(exc), 0.0))
        finally:
            if input_path is not None:
                input_path.unlink(missing_ok=True)
            if working_output is not None and not retain_output:
                working_output.unlink(missing_ok=True)

    def _poll_events(self) -> None:
        if self._closing:
            return
        try:
            while True:
                event = self._events.get_nowait()
                if event[0] == "cancelled":
                    self._finish_generation(event[1], None, None, 0.0)
                elif event[0] == "done":
                    _, mode, path, error, duration = event
                    self._finish_generation(mode, path, error, duration)
        except queue.Empty:
            pass
        self.after(80, self._poll_events)

    def _finish_generation(self, mode: str, path: str | None, error: str | None, duration: float) -> None:
        self._busy = False
        self._worker = None
        self.preview_button.configure(state="normal")
        self.save_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if error:
            self.status.set("No se pudo generar el audio")
            messagebox.showerror("Síntesis fallida", error, parent=self)
            return
        if not path:
            self.status.set("Generación cancelada")
            return
        if mode == "export":
            self.status.set(f"WAV guardado correctamente · {Path(path).name}")
            return
        self._preview_path = Path(path)
        try:
            if os.name == "nt":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                self._playing = True
                self._playback_token = uuid.uuid4().hex
                token = self._playback_token
                self.stop_button.configure(state="normal")
                self.status.set("Reproduciendo vista previa")
                self._playback_after = self.after(max(500, int(duration * 1000) + 350), lambda: self._playback_finished(token))
            else:
                self.status.set(f"Vista previa generada · {Path(path).name}")
        except Exception as exc:
            self.status.set("Vista previa generada, pero no se pudo reproducir")
            self._remove_preview()
            messagebox.showerror("No se pudo reproducir", str(exc), parent=self)

    def _playback_finished(self, token: str) -> None:
        if token != self._playback_token:
            return
        self._playing = False
        self._playback_token = None
        self._playback_after = None
        self.stop_button.configure(state="disabled")
        self.status.set("Vista previa terminada")
        self._remove_preview()

    def _stop(self) -> None:
        if self._busy:
            self.status.set("Cancelando síntesis…")
            self.stop_button.configure(state="disabled")
            self._cancel_event.set()
            with self._process_lock:
                process = self._process
                if process is not None:
                    try:
                        process.terminate()
                    except OSError:
                        pass
            return
        if self._playing:
            self._stop_playback("Vista previa detenida")

    def _stop_playback(self, status: str) -> None:
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except (ImportError, RuntimeError):
            pass
        self._playing = False
        self._playback_token = None
        if self._playback_after:
            try:
                self.after_cancel(self._playback_after)
            except tk.TclError:
                pass
            self._playback_after = None
        self.stop_button.configure(state="disabled")
        self.status.set(status)
        self._remove_preview()

    def _remove_preview(self) -> None:
        if self._preview_path is not None:
            try:
                self._preview_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._preview_path = None

    def _open_pronunciation(self) -> None:
        if self._pronunciation_dialog is not None and self._pronunciation_dialog.winfo_exists():
            self._pronunciation_dialog.lift()
            return
        dialog = tk.Toplevel(self)
        self._pronunciation_dialog = dialog
        dialog.title("Diccionario de pronunciación")
        dialog.geometry("620x500")
        dialog.minsize(540, 430)
        dialog.configure(bg=COLORS["canvas"])
        dialog.transient(self)

        page = ttk.Frame(dialog, style="App.TFrame", padding=20)
        page.pack(fill="both", expand=True)
        ttk.Label(page, text="Pronunciación", style="Header.TLabel").pack(anchor="w")
        description = ttk.Label(
            page,
            text="Sustituye palabras o frases por su lectura hablada. Los cambios se aplican al generar el audio; tu texto permanece intacto.",
            style="Subtitle.TLabel",
            wraplength=560,
        )
        description.pack(anchor="w", fill="x", pady=(5, 12))
        page.bind("<Configure>", lambda event: description.configure(wraplength=max(200, event.width - 40)))

        table_card = ttk.Frame(page, style="Card.TFrame", padding=8)
        table_card.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_card, columns=("source", "spoken"), show="headings", selectmode="browse", height=3)
        tree.heading("source", text="Texto escrito")
        tree.heading("spoken", text="Se pronuncia como")
        table_card.rowconfigure(0, weight=1)
        table_card.columnconfigure(0, weight=1)
        tree.column("source", width=180, minwidth=80, anchor="w")
        tree.column("spoken", width=220, minwidth=80, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")
        table_scroll = ttk.Scrollbar(table_card, orient="vertical", command=tree.yview)
        table_scroll.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=table_scroll.set)

        fields = ttk.Frame(page, style="App.TFrame")
        fields.pack(fill="x", pady=(12, 6))
        source_var = tk.StringVar()
        spoken_var = tk.StringVar()
        ttk.Label(fields, text="Texto escrito", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(fields, text="Se pronuncia como", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=(10, 0))
        source_entry = ttk.Entry(fields, textvariable=source_var)
        spoken_entry = ttk.Entry(fields, textvariable=spoken_var)
        source_entry.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        spoken_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(4, 0))
        fields.columnconfigure(0, weight=1)
        fields.columnconfigure(1, weight=1)

        def refresh(select_source: str | None = None) -> None:
            items = tree.get_children()
            if items:
                tree.delete(*items)
            for source, spoken in self.pronunciation_rules.items():
                item = tree.insert("", "end", values=(source, spoken))
                if select_source and source.casefold() == select_source.casefold():
                    tree.selection_set(item)
                    tree.see(item)
            self.rules_button.configure(text=f"Pronunciación · {len(self.pronunciation_rules)}")

        def select_row(_event=None) -> None:
            selected_items = tree.selection()
            if selected_items:
                values = tree.item(selected_items[0], "values")
                source_var.set(values[0])
                spoken_var.set(values[1])

        def save_rule() -> None:
            source = source_var.get().strip()
            spoken = spoken_var.get().strip()
            if not source or not spoken:
                messagebox.showinfo("Pronunciación", "Completa los dos campos.", parent=dialog)
                return
            if len(source) > 80 or len(spoken) > 120:
                messagebox.showinfo("Pronunciación", "Cada regla admite hasta 80 caracteres de origen y 120 de lectura.", parent=dialog)
                return
            existing = next((key for key in self.pronunciation_rules if key.casefold() == source.casefold()), None)
            if existing is not None and existing != source:
                del self.pronunciation_rules[existing]
            self.pronunciation_rules[source] = spoken
            refresh(source)
            self._schedule_config_save()
            source_var.set("")
            spoken_var.set("")
            source_entry.focus_set()

        def remove_rule() -> None:
            selected_items = tree.selection()
            if not selected_items:
                return
            source = tree.item(selected_items[0], "values")[0]
            self.pronunciation_rules.pop(source, None)
            refresh()
            self._schedule_config_save()
            source_var.set("")
            spoken_var.set("")

        tree.bind("<<TreeviewSelect>>", select_row)
        button_row = ttk.Frame(page, style="App.TFrame")
        button_row.pack(fill="x", pady=(6, 0))
        ttk.Button(button_row, text="Añadir / actualizar", style="Secondary.TButton", command=save_rule).pack(side="left")
        ttk.Button(button_row, text="Eliminar", style="Secondary.TButton", command=remove_rule).pack(side="left", padx=8)
        ttk.Button(button_row, text="Cerrar", style="Primary.TButton", command=dialog.destroy).pack(side="right")
        refresh()
        dialog.bind("<Return>", lambda _event: save_rule())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.grab_set()
        source_entry.focus_set()
        self.wait_window(dialog)
        self._pronunciation_dialog = None

    def _close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._busy:
            self._cancel_event.set()
            with self._process_lock:
                if self._process is not None:
                    try:
                        self._process.terminate()
                    except OSError:
                        pass
        if self._playing:
            self._stop_playback("")
        self._remove_preview()
        if self._save_after:
            try:
                self.after_cancel(self._save_after)
            except tk.TclError:
                pass
        try:
            _save_config(self._config_values())
        except OSError:
            pass
        self.destroy()


def main() -> None:
    ClassicVoiceApp().mainloop()


if __name__ == "__main__":
    main()
