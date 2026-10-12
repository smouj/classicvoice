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
    VoiceLanguage,
    app_data_dir,
    app_resource_dir,
    apply_pronunciation_rules,
    build_espeak_file_command,
    espeak_environment,
    discover_voice_languages,
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
        self.geometry("1100x720")
        self.minsize(860, 620)
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
        self.speed = tk.IntVar(value=_bounded_int(cfg.get("speed"), selected.speed, 80, 450))
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
        self.languages = discover_voice_languages(self.engine, APP_DIR)
        saved_language = str(cfg.get("language_code", "es"))
        selected_language = next((language for language in self.languages if language.code == saved_language), self.languages[0] if self.languages else None)
        self._language_code = selected_language.code if selected_language else "es"
        self.language_label = tk.StringVar(value=selected_language.label if selected_language else "Motor no disponible")
        all_rules = cfg.get("pronunciation_by_language", {})
        self._rules_by_language = {}
        if isinstance(all_rules, dict):
            for code, mapping in all_rules.items():
                if isinstance(code, str) and isinstance(mapping, dict):
                    self._rules_by_language[code] = {str(key).strip()[:80]: str(value).strip()[:120] for key, value in mapping.items() if str(key).strip() and str(value).strip()}
        self._rules_by_language.setdefault(str(cfg.get("language_code", "es")), self.pronunciation_rules)
        self.pronunciation_rules = self._rules_by_language.setdefault(self._language_code, {})
        self._numeric_inputs: list[tuple[tk.StringVar, tk.IntVar, int, int]] = []
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
        style.configure("TCombobox", padding=(8, 5), fieldbackground=COLORS["card"], background=COLORS["card"], foreground=COLORS["text"])
        style.map("TCombobox", fieldbackground=[("readonly", COLORS["card"])], selectbackground=[("readonly", COLORS["card"])], selectforeground=[("readonly", COLORS["text"])])
        style.configure("Quiet.TButton", background=COLORS["card"], foreground=COLORS["text"], padding=(10, 6), font=("Segoe UI", 9), borderwidth=1)
        style.map("Quiet.TButton", background=[("active", "#f4f5fb")])
        style.configure("TNotebook", background=COLORS["card"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 7), font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", COLORS["accent"]), ("!selected", "#e8eaf3")], foreground=[("selected", "#ffffff"), ("!selected", COLORS["muted"])])
        style.configure("TSpinbox", padding=3, fieldbackground=COLORS["card"], font=("Segoe UI", 10))
        style.configure("Voice.Horizontal.TProgressbar", background=COLORS["accent"], troughcolor=COLORS["canvas"], bordercolor=COLORS["canvas"], lightcolor=COLORS["canvas"], darkcolor=COLORS["canvas"], borderwidth=0, thickness=3)
        style.configure("TCheckbutton", background=COLORS["card"], foreground=COLORS["text"], font=("Segoe UI", 9))
        style.configure("Voice.Horizontal.TScale", background=COLORS["accent"], troughcolor="#e8eaf3", bordercolor=COLORS["accent"], lightcolor=COLORS["accent"], darkcolor=COLORS["accent"], arrowcolor="#ffffff")
        style.map("Voice.Horizontal.TScale", background=[("active", COLORS["accent_hover"])])
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 9), background=COLORS["card"], fieldbackground=COLORS["card"])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build(self) -> None:
        page = ttk.Frame(self, style="App.TFrame", padding=(20, 16, 20, 12))
        page.pack(fill="both", expand=True)
        self._page = page
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)

        header = ttk.Frame(page, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="ClassicVoice", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self._subtitle = ttk.Label(header, text="Texto a voz en varios idiomas. Local, sencillo y en WAV.", style="Subtitle.TLabel")
        self._subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))
        engine_ready = bool(self.engine and self.languages)
        ttk.Label(header, text="Motor de voz listo" if engine_ready else "Motor no disponible", style="EngineOk.TLabel" if engine_ready else "EngineMissing.TLabel").grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        body = ttk.Frame(page, style="App.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=3, minsize=320, uniform="panels")
        body.columnconfigure(1, weight=2, minsize=320, uniform="panels")

        editor = ttk.Frame(body, style="Card.TFrame", padding=14)
        editor.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        editor.rowconfigure(2, weight=1)
        editor.columnconfigure(0, weight=1)
        editor_top = ttk.Frame(editor, style="Card.TFrame")
        editor_top.grid(row=0, column=0, sticky="ew")
        ttk.Label(editor_top, text="Texto", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(editor_top, text="Importar TXT…", style="Quiet.TButton", command=self._import_text).pack(side="right")
        ttk.Label(editor, textvariable=self.word_count, style="CardText.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 8))
        editor_area = ttk.Frame(editor, style="Card.TFrame")
        editor_area.grid(row=2, column=0, sticky="nsew")
        editor_area.rowconfigure(0, weight=1)
        editor_area.columnconfigure(0, weight=1)
        self.text = tk.Text(
            editor_area, height=5, width=1, wrap="word", font=("Segoe UI", 11), undo=True,
            padx=12, pady=10, bg=COLORS["card"], fg="#8792a5",
            insertbackground=COLORS["accent"], selectbackground="#dcd9ff", selectforeground=COLORS["text"],
            relief="flat", highlightthickness=1, highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"], maxundo=100,
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(editor_area, orient="vertical", command=self.text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.insert("1.0", PLACEHOLDER)
        self.text.edit_modified(False)
        self._editor_hint = ttk.Label(editor, text="Ctrl + Intro: escuchar · Ctrl + S: guardar · Esc: detener", style="CardText.TLabel", wraplength=340)
        self._editor_hint.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        editor.bind("<Configure>", lambda event: self._editor_hint.configure(wraplength=max(180, event.width - 28)))

        settings = ttk.Frame(body, style="Card.TFrame", padding=12)
        settings.grid(row=0, column=1, sticky="nsew")
        settings.columnconfigure(0, weight=1)
        settings.rowconfigure(0, weight=1)
        self.settings_tabs = ttk.Notebook(settings)
        self.settings_tabs.grid(row=0, column=0, sticky="nsew")
        voice = ttk.Frame(self.settings_tabs, style="Card.TFrame", padding=(12, 8))
        output = ttk.Frame(self.settings_tabs, style="Card.TFrame", padding=(12, 10))
        self.settings_tabs.add(voice, text="Voz")
        self.settings_tabs.add(output, text="Salida")
        voice.columnconfigure(0, weight=1)
        ttk.Label(voice, text="Idioma del texto", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.language_combo = ttk.Combobox(voice, textvariable=self.language_label, values=[language.label for language in self.languages], state="readonly" if self.languages else "disabled", width=1)
        self.language_combo.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        ttk.Label(voice, text="Estilo de voz", style="CardTitle.TLabel").grid(row=2, column=0, sticky="w")
        self.preset_combo = ttk.Combobox(voice, textvariable=self.preset_label, values=[preset.label for preset in PRESETS], state="readonly", width=1)
        self.preset_combo.grid(row=3, column=0, sticky="ew", pady=(4, 5))
        self._preset_hint = ttk.Label(voice, textvariable=self.preset_description, style="CardText.TLabel", wraplength=260)
        self._preset_hint.grid(row=4, column=0, sticky="ew", pady=(0, 2))
        self._slider(voice, "Velocidad", self.speed, 80, 450, "palabras/min", 5)
        self._slider(voice, "Tono", self.pitch, 0, 99, "grave → agudo", 6)
        self._slider(voice, "Volumen", self.volume, 0, 200, "%", 7)
        ttk.Button(voice, text="Restablecer voz", style="Quiet.TButton", command=self._apply_preset).grid(row=8, column=0, sticky="ew", pady=(8, 0))
        voice.bind("<Configure>", lambda event: self._preset_hint.configure(wraplength=max(180, event.width - 24)))

        output.columnconfigure(0, weight=1)
        ttk.Label(output, text="Carpeta de salida", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.dir_label = ttk.Label(output, text=self._short_dir(), style="CardText.TLabel", wraplength=260)
        self.dir_label.grid(row=1, column=0, sticky="ew", pady=(6, 10))
        folder_actions = ttk.Frame(output, style="Card.TFrame")
        folder_actions.grid(row=2, column=0, sticky="ew")
        folder_actions.columnconfigure((0, 1), weight=1)
        ttk.Button(folder_actions, text="Cambiar…", style="Quiet.TButton", command=self._choose_dir).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(folder_actions, text="Abrir carpeta", style="Quiet.TButton", command=self._open_output_folder).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Separator(output).grid(row=3, column=0, sticky="ew", pady=16)
        ttk.Checkbutton(output, text="Normalizar volumen", variable=self.normalize_audio).grid(row=4, column=0, sticky="w")
        ttk.Label(output, text="Fija el pico del WAV. Desactívalo para conservar el volumen elegido.", style="CardText.TLabel", wraplength=260).grid(row=5, column=0, sticky="ew", pady=(6, 16))
        self.rules_button = ttk.Button(output, text=f"Pronunciación · {len(self.pronunciation_rules)}", style="Secondary.TButton", command=self._open_pronunciation)
        self.rules_button.grid(row=6, column=0, sticky="ew")
        ttk.Label(output, text="Las reglas se guardan por idioma. El texto original permanece intacto.", style="CardText.TLabel", wraplength=260).grid(row=7, column=0, sticky="ew", pady=(8, 0))
        output.bind("<Configure>", lambda event: [child.configure(wraplength=max(180, event.width - 24)) for child in output.winfo_children() if isinstance(child, ttk.Label)])

        actions = ttk.Frame(page, style="App.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(12, 8))
        actions.columnconfigure((0, 1), weight=1)
        self.preview_button = ttk.Button(actions, text="▶  Escuchar", style="Primary.TButton", command=self._preview)
        self.preview_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.save_button = ttk.Button(actions, text="Guardar WAV", style="Secondary.TButton", command=self._save)
        self.save_button.grid(row=0, column=1, sticky="ew", padx=6)
        self.stop_button = ttk.Button(actions, text="Detener", style="Stop.TButton", command=self._stop, state="disabled")
        self.stop_button.grid(row=0, column=2, padx=(6, 0))
        self._progress = ttk.Progressbar(actions, mode="determinate", value=0, length=1, style="Voice.Horizontal.TProgressbar")
        self._progress.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))

        footer = ttk.Frame(page, style="App.TFrame")
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self._status_label = ttk.Label(footer, textvariable=self.status, style="Status.TLabel", width=1, anchor="w")
        self._status_label.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Label(footer, text=f"v{__version__} · Local", style="Status.TLabel").grid(row=0, column=1, sticky="e")

    def _slider(self, parent, label: str, variable: tk.IntVar, low: int, high: int, hint: str, row_number: int) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.grid(row=row_number, column=0, sticky="ew", pady=(3, 0))
        row.columnconfigure(0, weight=1)
        ttk.Label(row, text=f"{label} · {hint}", style="CardText.TLabel").grid(row=0, column=0, sticky="w")
        value = tk.StringVar(value=str(variable.get()))
        self._numeric_inputs.append((value, variable, low, high))
        variable.trace_add("write", lambda *_args: value.set(str(variable.get())))
        number = ttk.Spinbox(row, from_=low, to=high, textvariable=value, width=5, command=lambda: self._commit_number(value, variable, low, high))
        number.grid(row=0, column=1, sticky="e")
        number.bind("<FocusOut>", lambda _event: self._commit_number(value, variable, low, high))
        number.bind("<Return>", lambda _event: self._commit_number(value, variable, low, high))
        scale = ttk.Scale(row, from_=low, to=high, variable=variable, orient="horizontal", command=lambda number: variable.set(round(float(number))), style="Voice.Horizontal.TScale", length=1, takefocus=True)
        scale.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    def _commit_number(self, value: tk.StringVar, variable: tk.IntVar, low: int, high: int) -> None:
        number = _bounded_int(value.get(), variable.get(), low, high)
        variable.set(number)
        value.set(str(number))

    def _language(self) -> VoiceLanguage | None:
        return next((language for language in self.languages if language.code == self._language_code), None)

    def _apply_language(self, _event=None) -> None:
        language = next((language for language in self.languages if language.label == self.language_label.get()), None)
        if language is None:
            return
        self._rules_by_language[self._language_code] = self.pronunciation_rules
        self._language_code = language.code
        self.pronunciation_rules = self._rules_by_language.setdefault(language.code, {})
        self.rules_button.configure(text=f"Pronunciación · {len(self.pronunciation_rules)}")
        self.status.set(f"Idioma: {language.name}")
        self._schedule_config_save()

    def _import_text(self) -> None:
        selected = filedialog.askopenfilename(title="Importar texto", filetypes=[("Texto", "*.txt"), ("Todos los archivos", "*.*")], parent=self)
        if not selected:
            return
        try:
            with Path(selected).open("rb") as source:
                raw = source.read(MAX_TEXT_CHARS * 4 + 5)
            if len(raw) > MAX_TEXT_CHARS * 4 + 4:
                raise ValueError("El archivo es demasiado grande para una lectura.")
            encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            content = raw.decode(encoding)
            if len(content) > MAX_TEXT_CHARS:
                raise ValueError(f"El archivo supera el límite de {MAX_TEXT_CHARS:,} caracteres.")
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("No se pudo importar", f"Utiliza un TXT en UTF-8 o UTF-16.\n\n{exc}", parent=self)
            return
        self._clear_placeholder()
        self.text.configure(autoseparators=False)
        try:
            self.text.edit_separator()
            self.text.delete("1.0", "end")
            self.text.insert("1.0", content)
            self.text.edit_separator()
        finally:
            self.text.configure(autoseparators=True)
        self._update_count()
        self.text.focus_set()
        self.status.set(f"Texto importado · {len(content):,} caracteres")

    def _open_output_folder(self) -> None:
        try:
            folder = Path(self._last_dir)
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(folder))
            else:
                messagebox.showinfo("Carpeta de salida", str(folder), parent=self)
        except OSError as exc:
            messagebox.showerror("Carpeta no disponible", str(exc), parent=self)

    def _bind_events(self) -> None:
        self.text.bind("<<Modified>>", self._on_text_modified)
        self.text.bind("<FocusIn>", self._clear_placeholder)
        self.text.bind("<FocusOut>", self._restore_placeholder)
        self.text.bind("<Control-a>", self._select_all_text)
        self.text.bind("<Control-A>", self._select_all_text)
        self.preset_combo.bind("<<ComboboxSelected>>", self._apply_preset)
        self.language_combo.bind("<<ComboboxSelected>>", self._apply_language)
        self.bind("<Control-Return>", self._hotkey_preview)
        self.bind("<Control-s>", self._hotkey_save)
        self.bind("<Control-S>", self._hotkey_save)
        self.bind("<Control-o>", lambda _event: self._import_text())
        self.bind("<Escape>", lambda _event: self._stop())
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
        self._rules_by_language[self._language_code] = self.pronunciation_rules
        return {
            "version": 3,
            "language_code": self._language_code,
            "preset_key": self._preset().key,
            "speed": _bounded_int(self.speed.get(), self._preset().speed, 80, 450),
            "pitch": _bounded_int(self.pitch.get(), self._preset().pitch, 0, 99),
            "volume": _bounded_int(self.volume.get(), self._preset().amplitude, 0, 200),
            "normalize": bool(self.normalize_audio.get()),
            "last_dir": self._last_dir,
            "pronunciation_by_language": self._rules_by_language,
        }

    def _write_config(self) -> None:
        self._save_after = None
        try:
            _save_config(self._config_values())
        except OSError as exc:
            if not self._closing:
                self.status.set("No se pudieron guardar los ajustes")

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
        language = self._language()
        if language is None:
            messagebox.showerror("Idiomas no disponibles", "No se pudo leer el catálogo de voces. Reinstala el paquete completo de ClassicVoice.", parent=self)
            return
        for value, variable, low, high in self._numeric_inputs:
            self._commit_number(value, variable, low, high)

        processed = apply_pronunciation_rules(source, self.pronunciation_rules)
        if not processed.strip():
            messagebox.showinfo("ClassicVoice", "Los reemplazos de pronunciación han dejado el texto vacío.", parent=self)
            return

        preset = self._preset()
        settings = {
            "speed": _bounded_int(self.speed.get(), preset.speed, 80, 450),
            "language": language,
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
        self._progress.configure(mode="indeterminate")
        self._progress.start(12)
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
                language=settings.get("language"),
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
        self._progress.stop()
        self._progress.configure(mode="determinate", value=0)
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
            self.status.set(f"WAV guardado correctamente · {duration:.1f} s")
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
                self.status.set("Vista previa generada")
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
            text=f"Reglas para {self._language().name if self._language() else 'el idioma seleccionado'}. Sustituye palabras o frases por su lectura hablada; tu texto permanece intacto.",
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
