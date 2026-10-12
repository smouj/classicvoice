from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import uuid

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
    discover_voice_languages,
    resolve_espeak,
)
from .workflows import (
    SynthesisCancelled,
    merge_wav_files,
    normalize_voice_profiles,
    read_text_document,
    safe_audio_stem,
    split_book_text,
    synthesize_text_to_wav,
)
from .natural_engine import (
    KOKORO_MODEL_BYTES,
    KOKORO_MODEL_VERSION,
    KOKORO_VOICES_BYTES,
    canonical_language,
    install_kokoro_model,
    kokoro_runtime_available,
    model_is_installed,
    remove_kokoro_model,
    synthesize_kokoro_to_wav,
    voices_for_language,
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
        self._classic_preset_key = selected.key

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
        default_engine = (
            "kokoro"
            if kokoro_runtime_available()
            and model_is_installed(DATA_DIR / "models" / f"kokoro-{KOKORO_MODEL_VERSION}")
            else "espeak"
        )
        self.tts_engine = str(cfg.get("tts_engine", default_engine))
        if self.tts_engine not in {"espeak", "kokoro"}:
            self.tts_engine = "espeak"
        self.natural_voice = str(cfg.get("natural_voice", "ef_dora"))
        self.engine = resolve_espeak(APP_DIR)
        self._all_languages = discover_voice_languages(self.engine, APP_DIR)
        self.languages = self._languages_for_engine(self.tts_engine)
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
        self.voice_profiles = normalize_voice_profiles(cfg.get("voice_profiles", {}))
        self._numeric_inputs: list[tuple[tk.StringVar, tk.IntVar, int, int]] = []
        self._events: queue.Queue = queue.Queue()
        self._poll_after: str | None = None
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
        self._voice_profile_dialog: tk.Toplevel | None = None
        self._batch_dialog: tk.Toplevel | None = None
        self._batch_tree: ttk.Treeview | None = None
        self._batch_output_display: tk.StringVar | None = None
        self._batch_files: list[Path] = []
        self._batch_progress: ttk.Progressbar | None = None
        self._batch_status: tk.StringVar | None = None
        self._batch_start_button: ttk.Button | None = None
        self._batch_stop_button: ttk.Button | None = None
        self._natural_settings_dialog: tk.Toplevel | None = None
        self._natural_settings_status: tk.StringVar | None = None
        self._natural_settings_progress: ttk.Progressbar | None = None
        self._natural_settings_action: ttk.Button | None = None
        self._natural_installing = False
        self._natural_cancel_event = threading.Event()
        self._model_worker: threading.Thread | None = None
        self._natural_model_dir = DATA_DIR / "models" / f"kokoro-{KOKORO_MODEL_VERSION}"
        self._pitch_controls: tuple[tk.Widget, ...] = ()
        self._volume_controls: tuple[tk.Widget, ...] = ()

        self._configure_style()
        self._build()
        self._refresh_engine_controls()
        self._bind_events()
        self._update_count()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._poll_after = self.after(80, self._poll_events)

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
        self._engine_status_badge = ttk.Label(
            header,
            text="Motor de voz listo" if engine_ready else "Motor no disponible",
            style="EngineOk.TLabel" if engine_ready else "EngineMissing.TLabel",
        )
        self._engine_status_badge.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

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
        ttk.Button(editor_top, text="Lote / libro…", style="Quiet.TButton", command=self._open_batch_dialog).pack(side="right", padx=(6, 0))
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
        voice_heading = ttk.Frame(voice, style="Card.TFrame")
        voice_heading.grid(row=0, column=0, sticky="ew")
        voice_heading.columnconfigure(0, weight=1)
        ttk.Label(voice_heading, text="Idioma del texto", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.engine_mode_button = ttk.Button(voice_heading, text="Motor: Clásico", style="Quiet.TButton", command=self._open_tts_settings)
        self.engine_mode_button.grid(row=0, column=1, sticky="e")
        self.language_combo = ttk.Combobox(voice, textvariable=self.language_label, values=[language.label for language in self.languages], state="readonly" if self.languages else "disabled", width=1)
        self.language_combo.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        self._voice_group_label = ttk.Label(voice, text="Estilo de voz", style="CardTitle.TLabel")
        self._voice_group_label.grid(row=2, column=0, sticky="w")
        self.preset_combo = ttk.Combobox(voice, textvariable=self.preset_label, values=[preset.label for preset in PRESETS], state="readonly", width=1)
        self.preset_combo.grid(row=3, column=0, sticky="ew", pady=(4, 5))
        self._preset_hint = ttk.Label(voice, textvariable=self.preset_description, style="CardText.TLabel", wraplength=260)
        self._preset_hint.grid(row=4, column=0, sticky="ew", pady=(0, 2))
        self._speed_hint_label, _speed_widgets = self._slider(voice, "Velocidad", self.speed, 80, 450, "palabras/min", 5)
        self._pitch_label, self._pitch_controls = self._slider(voice, "Tono", self.pitch, 0, 99, "grave → agudo", 6)
        self._volume_label, self._volume_controls = self._slider(voice, "Volumen", self.volume, 0, 200, "%", 7)
        self._reset_voice_button = ttk.Button(voice, text="Restablecer estilo", style="Quiet.TButton", command=self._reset_voice)
        self._reset_voice_button.grid(row=8, column=0, sticky="ew", pady=(8, 0))
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
        ttk.Button(output, text="Mis perfiles de voz…", style="Quiet.TButton", command=self._open_voice_profiles).grid(row=8, column=0, sticky="ew", pady=(12, 0))
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

    def _languages_for_engine(self, engine: str) -> tuple[VoiceLanguage, ...]:
        if engine != "kokoro":
            return self._all_languages
        return tuple(language for language in self._all_languages if canonical_language(language.code))

    def _refresh_engine_controls(self) -> None:
        self.languages = self._languages_for_engine(self.tts_engine)
        values = [language.label for language in self.languages]
        self.language_combo.configure(values=values, state="readonly" if values else "disabled")
        language = next((item for item in self.languages if item.code == self._language_code), None)
        if language is None and self.languages:
            language = next((item for item in self.languages if item.code == "es"), self.languages[0])
            self._language_code = language.code
        self.language_label.set(language.label if language else "Motor no disponible")
        self._rules_by_language.setdefault(self._language_code, self.pronunciation_rules)
        self.pronunciation_rules = self._rules_by_language[self._language_code]
        self.rules_button.configure(text=f"Pronunciación · {len(self.pronunciation_rules)}")

        if self.tts_engine == "kokoro":
            available = voices_for_language(self._language_code)
            valid_ids = {voice_id for voice_id, _label in available}
            if self.natural_voice not in valid_ids and available:
                self.natural_voice = available[0][0]
            labels = [label for _voice_id, label in available]
            label_by_id = dict((voice_id, label) for voice_id, label in available)
            self.preset_combo.configure(values=labels, state="readonly" if labels else "disabled")
            self.preset_label.set(label_by_id.get(self.natural_voice, ""))
            self._voice_group_label.configure(text="Voz natural")
            self.preset_description.set("Voz neuronal predefinida · Kokoro procesa el texto localmente.")
            self._speed_hint_label.configure(text="Velocidad · 80 lenta · 145 normal · 450 rápida")
            self._reset_voice_button.configure(text="Restablecer voz natural")
            self._pitch_label.configure(text="Tono · no disponible en Kokoro")
            self._volume_label.configure(text="Volumen · normalización en Salida")
            for control in self._pitch_controls + self._volume_controls:
                control.configure(state="disabled")
            self.engine_mode_button.configure(text="Motor: Natural")
            if not kokoro_runtime_available():
                status, style = "Motor natural no incluido", "EngineMissing.TLabel"
            elif model_is_installed(self._natural_model_dir):
                status, style = "Voz neuronal local lista", "EngineOk.TLabel"
            else:
                status, style = "Voz natural · instala el modelo", "EngineMissing.TLabel"
        else:
            presets_by_key = {preset.key: preset for preset in PRESETS}
            classic_preset = presets_by_key.get(self._classic_preset_key, PRESETS[0])
            self.preset_combo.configure(values=[preset.label for preset in PRESETS], state="readonly")
            self.preset_label.set(classic_preset.label)
            self.preset_description.set(classic_preset.description)
            self._voice_group_label.configure(text="Estilo de voz")
            self._speed_hint_label.configure(text="Velocidad · palabras/min")
            self._reset_voice_button.configure(text="Restablecer estilo")
            self._pitch_label.configure(text="Tono · grave → agudo")
            self._volume_label.configure(text="Volumen · %")
            for control in self._pitch_controls + self._volume_controls:
                control.configure(state="normal")
            self.engine_mode_button.configure(text="Motor: Clásico")
            status, style = ("Motor de voz listo", "EngineOk.TLabel") if self.engine and self.languages else ("Motor no disponible", "EngineMissing.TLabel")
        self._engine_status_badge.configure(text=status, style=style)

    def _set_tts_engine(self, engine: str) -> None:
        if engine not in {"espeak", "kokoro"} or self._busy:
            return
        if engine == self.tts_engine:
            return
        if self.tts_engine == "espeak":
            self._classic_preset_key = self._preset().key
        self._rules_by_language[self._language_code] = self.pronunciation_rules
        self.tts_engine = engine
        self._refresh_engine_controls()
        if engine == "kokoro":
            self.status.set("Motor natural local · Kokoro")
        else:
            self.status.set("Motor clásico local · eSpeak NG")
        self._schedule_config_save()

    def _open_tts_settings(self) -> None:
        if self._natural_settings_dialog is not None and self._natural_settings_dialog.winfo_exists():
            self._natural_settings_dialog.lift()
            return
        dialog = tk.Toplevel(self)
        self._natural_settings_dialog = dialog
        dialog.title("Motor de voz · ClassicVoice")
        dialog.geometry("540x405")
        dialog.minsize(500, 365)
        dialog.configure(bg=COLORS["canvas"])
        dialog.transient(self)
        page = ttk.Frame(dialog, style="App.TFrame", padding=18)
        page.pack(fill="both", expand=True)
        page.columnconfigure(0, weight=1)
        ttk.Label(page, text="Motor de voz", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            page,
            text="Elige una voz clásica ligera o una voz neuronal con una entonación más natural. Ambos motores procesan el texto en este PC.",
            style="Subtitle.TLabel",
            wraplength=490,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 12))

        options = ttk.Frame(page, style="Card.TFrame", padding=12)
        options.grid(row=2, column=0, sticky="ew")
        options.columnconfigure(0, weight=1)
        engine_choice = tk.StringVar(value=self.tts_engine)
        ttk.Radiobutton(
            options,
            text="Clásico · eSpeak NG",
            value="espeak",
            variable=engine_choice,
            command=lambda: self._set_tts_engine(engine_choice.get()),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            options,
            text="Rápido y ligero · 130 idiomas · controles de tono y volumen.",
            style="CardText.TLabel",
            wraplength=440,
        ).grid(row=1, column=0, sticky="ew", padx=(24, 0), pady=(2, 10))
        ttk.Radiobutton(
            options,
            text="Natural · Kokoro 82M",
            value="kokoro",
            variable=engine_choice,
            state="normal" if kokoro_runtime_available() else "disabled",
            command=lambda: self._set_tts_engine(engine_choice.get()),
        ).grid(row=2, column=0, sticky="w")
        ttk.Label(
            options,
            text="Voces predefinidas en nueve idiomas · descarga de 136 MiB.",
            style="CardText.TLabel",
            wraplength=440,
        ).grid(row=3, column=0, sticky="ew", padx=(24, 0), pady=(2, 0))

        self._natural_settings_status = tk.StringVar()
        self._natural_settings_status_label = ttk.Label(page, textvariable=self._natural_settings_status, style="Status.TLabel", wraplength=490)
        self._natural_settings_status_label.grid(row=3, column=0, sticky="ew", pady=(12, 4))
        self._natural_settings_progress = ttk.Progressbar(page, mode="determinate", value=0, maximum=100, style="Voice.Horizontal.TProgressbar")
        self._natural_settings_progress.grid(row=4, column=0, sticky="new")
        actions = ttk.Frame(page, style="App.TFrame")
        actions.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(0, weight=1)
        self._natural_settings_action = ttk.Button(actions, style="Secondary.TButton", command=self._natural_model_action)
        self._natural_settings_action.grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Cerrar", style="Primary.TButton", command=dialog.destroy).grid(row=0, column=1, sticky="e")
        self._refresh_natural_settings()
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.bind("<Destroy>", lambda event: self._clear_natural_settings_dialog(dialog, event), add="+")

    def _refresh_natural_settings(self) -> None:
        if self._natural_settings_status is None or self._natural_settings_action is None:
            return
        if self._natural_installing:
            self._natural_settings_status.set("Preparando la descarga… Puedes cancelar desde este botón.")
            self._natural_settings_action.configure(text="Cancelar descarga", state="normal")
        elif not kokoro_runtime_available():
            self._natural_settings_status.set("Esta compilación no incluye el runtime Kokoro. Actualiza ClassicVoice desde GitHub.")
            self._natural_settings_action.configure(text="Motor no disponible", state="disabled")
        elif model_is_installed(self._natural_model_dir):
            self._natural_settings_status.set("Modelo instalado · 136 MiB · después de descargarlo, la síntesis funciona sin Internet.")
            self._natural_settings_action.configure(text="Eliminar modelo neuronal", state="normal")
        else:
            self._natural_settings_status.set("El modelo aún no está instalado. Descarga única de unos 136 MiB desde GitHub; se verifica por SHA-256.")
            self._natural_settings_action.configure(text="Descargar e instalar · 136 MiB", state="normal")

    def _clear_natural_settings_dialog(self, dialog, event) -> None:
        if event.widget is dialog:
            self._natural_settings_dialog = None
            self._natural_settings_status = None
            self._natural_settings_action = None
            self._natural_settings_progress = None

    def _natural_model_action(self) -> None:
        if self._natural_installing:
            self._natural_cancel_event.set()
            if self._natural_settings_status is not None:
                self._natural_settings_status.set("Cancelando; se eliminarán los archivos parciales…")
            if self._natural_settings_action is not None:
                self._natural_settings_action.configure(state="disabled")
            return
        if not kokoro_runtime_available():
            self._refresh_natural_settings()
            return
        if self._busy:
            messagebox.showinfo("Síntesis en curso", "Detén o espera a que termine la síntesis antes de cambiar el modelo.", parent=self._natural_settings_dialog)
            return
        if model_is_installed(self._natural_model_dir):
            if not messagebox.askyesno(
                "Eliminar modelo neuronal",
                "¿Eliminar solo el modelo Kokoro que descargó ClassicVoice? Se liberarán unos 136 MiB.",
                parent=self._natural_settings_dialog,
            ):
                return
            if self.tts_engine == "kokoro":
                self._set_tts_engine("espeak")
            try:
                remove_kokoro_model(self._natural_model_dir)
            except OSError as exc:
                messagebox.showerror("No se pudo eliminar el modelo", str(exc), parent=self._natural_settings_dialog)
            self._refresh_natural_settings()
            self._refresh_engine_controls()
            return
        self._natural_installing = True
        self._natural_cancel_event = threading.Event()
        if self._natural_settings_progress is not None:
            self._natural_settings_progress.configure(value=0)
        self._refresh_natural_settings()
        self._model_worker = threading.Thread(
            target=self._install_natural_model_worker,
            args=(self._natural_cancel_event,),
            name="ClassicVoice-model-install",
            daemon=True,
        )
        self._model_worker.start()

    def _install_natural_model_worker(self, cancel_event: threading.Event) -> None:
        try:
            install_kokoro_model(
                self._natural_model_dir,
                cancel_event,
                lambda name, current, total: self._events.put(("natural_model_progress", name, current, total)),
            )
            self._events.put(("natural_model_installed",))
        except SynthesisCancelled:
            self._events.put(("natural_model_cancelled",))
        except Exception as exc:
            self._events.put(("natural_model_failed", str(exc)))

    def _slider(self, parent, label: str, variable: tk.IntVar, low: int, high: int, hint: str, row_number: int) -> tuple[ttk.Label, tuple[tk.Widget, ...]]:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.grid(row=row_number, column=0, sticky="ew", pady=(3, 0))
        row.columnconfigure(0, weight=1)
        caption = ttk.Label(row, text=f"{label} · {hint}", style="CardText.TLabel")
        caption.grid(row=0, column=0, sticky="w")
        value = tk.StringVar(value=str(variable.get()))
        self._numeric_inputs.append((value, variable, low, high))
        variable.trace_add("write", lambda *_args: value.set(str(variable.get())))
        number = ttk.Spinbox(row, from_=low, to=high, textvariable=value, width=5, command=lambda: self._commit_number(value, variable, low, high))
        number.grid(row=0, column=1, sticky="e")
        number.bind("<FocusOut>", lambda _event: self._commit_number(value, variable, low, high))
        number.bind("<Return>", lambda _event: self._commit_number(value, variable, low, high))
        scale = ttk.Scale(row, from_=low, to=high, variable=variable, orient="horizontal", command=lambda number: variable.set(round(float(number))), style="Voice.Horizontal.TScale", length=1, takefocus=True)
        scale.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        return caption, (number, scale)

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
        if self.tts_engine == "kokoro":
            self._refresh_engine_controls()
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

    def _open_batch_dialog(self) -> None:
        if self._batch_dialog is not None and self._batch_dialog.winfo_exists():
            self._batch_dialog.lift()
            return
        dialog = tk.Toplevel(self)
        self._batch_dialog = dialog
        dialog.title("ClassicVoice - Audiolibros")
        dialog.geometry("700x500")
        dialog.minsize(600, 430)
        dialog.configure(bg=COLORS["canvas"])
        dialog.transient(self)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        page = ttk.Frame(dialog, style="App.TFrame", padding=18)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)
        ttk.Label(page, text="Lotes y audiolibros", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            page,
            text="Añade varios TXT o Markdown. Los títulos de capítulo se separan automáticamente; los textos largos se dividen para mantener una generación estable.",
            style="Subtitle.TLabel",
            wraplength=640,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 12))

        list_card = ttk.Frame(page, style="Card.TFrame", padding=8)
        list_card.grid(row=2, column=0, sticky="nsew")
        list_card.rowconfigure(0, weight=1)
        list_card.columnconfigure(0, weight=1)
        self._batch_tree = ttk.Treeview(list_card, columns=("path",), show="headings", selectmode="extended", height=7)
        self._batch_tree.heading("path", text="Archivos en el lote")
        self._batch_tree.column("path", anchor="w", width=540)
        self._batch_tree.grid(row=0, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(list_card, orient="vertical", command=self._batch_tree.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self._batch_tree.configure(yscrollcommand=list_scroll.set)

        toolbar = ttk.Frame(page, style="App.TFrame")
        toolbar.grid(row=3, column=0, sticky="ew", pady=(8, 10))
        ttk.Button(toolbar, text="Añadir TXT o Markdown…", style="Quiet.TButton", command=self._batch_add_files).pack(side="left")
        ttk.Button(toolbar, text="Quitar seleccionados", style="Quiet.TButton", command=self._batch_remove_files).pack(side="left", padx=(8, 0))

        output_row = ttk.Frame(page, style="App.TFrame")
        output_row.grid(row=4, column=0, sticky="ew")
        output_row.columnconfigure(0, weight=1)
        self._batch_output_dir = tk.StringVar(value=self._last_dir)
        self._batch_output_display = tk.StringVar(value=self._format_user_path(self._last_dir))
        ttk.Label(output_row, text="Destino", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(output_row, textvariable=self._batch_output_display, style="CardText.TLabel", width=1).grid(row=1, column=0, sticky="ew", pady=(3, 0))
        ttk.Button(output_row, text="Cambiar…", style="Quiet.TButton", command=self._batch_choose_dir).grid(row=0, column=1, rowspan=2, sticky="e", padx=(8, 0))

        self._batch_merge = tk.BooleanVar(value=True)
        ttk.Checkbutton(page, text="Crear también un WAV continuo con todos los capítulos", variable=self._batch_merge).grid(row=5, column=0, sticky="w", pady=(8, 0))
        self._batch_status = tk.StringVar(value="Se usará la voz y los ajustes seleccionados en la ventana principal.")
        ttk.Label(page, textvariable=self._batch_status, style="Status.TLabel", wraplength=640).grid(row=6, column=0, sticky="ew", pady=(8, 0))
        self._batch_progress = ttk.Progressbar(page, mode="determinate", style="Voice.Horizontal.TProgressbar")
        self._batch_progress.grid(row=7, column=0, sticky="ew", pady=(6, 8))

        actions = ttk.Frame(page, style="App.TFrame")
        actions.grid(row=8, column=0, sticky="ew")
        ttk.Button(actions, text="Cerrar", style="Secondary.TButton", command=dialog.destroy).pack(side="right")
        self._batch_stop_button = ttk.Button(actions, text="Detener", style="Stop.TButton", command=self._stop, state="disabled")
        self._batch_stop_button.pack(side="right", padx=(0, 8))
        self._batch_start_button = ttk.Button(actions, text="Crear audio", style="Primary.TButton", command=self._start_batch_generation)
        self._batch_start_button.pack(side="right", padx=(0, 8))
        self._batch_files = []
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.bind("<Destroy>", self._batch_dialog_destroyed, add="+")

    def _batch_dialog_destroyed(self, event) -> None:
        if event.widget is self._batch_dialog:
            self._batch_dialog = None
            self._batch_files = []
            self._batch_tree = None
            self._batch_progress = None
            self._batch_status = None
            self._batch_start_button = None
            self._batch_stop_button = None
            self._batch_output_display = None

    def _batch_add_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Añadir textos al lote",
            filetypes=[("Textos TXT y Markdown", "*.txt *.md"), ("Todos los archivos", "*.*")],
            parent=self._batch_dialog,
        )
        existing = {str(path).casefold() for path in self._batch_files}
        for value in selected:
            path = Path(value)
            if path.suffix.casefold() not in {".txt", ".md"} or str(path).casefold() in existing:
                continue
            self._batch_files.append(path)
            self._batch_tree.insert("", "end", iid=str(len(self._batch_files) - 1), values=(str(path),))
            existing.add(str(path).casefold())
        self._batch_status.set(f"{len(self._batch_files)} archivo(s) en la cola.")

    def _batch_remove_files(self) -> None:
        selected = {int(item) for item in self._batch_tree.selection()}
        if not selected:
            return
        self._batch_files = [path for index, path in enumerate(self._batch_files) if index not in selected]
        for item in self._batch_tree.get_children():
            self._batch_tree.delete(item)
        for index, path in enumerate(self._batch_files):
            self._batch_tree.insert("", "end", iid=str(index), values=(str(path),))
        self._batch_status.set(f"{len(self._batch_files)} archivo(s) en la cola.")

    def _batch_choose_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Carpeta para los capítulos WAV", initialdir=self._batch_output_dir.get(), parent=self._batch_dialog)
        if chosen:
            self._batch_output_dir.set(chosen)
            self._batch_output_display.set(self._format_user_path(chosen))

    @staticmethod
    def _format_user_path(value: str) -> str:
        path = str(value)
        home = str(Path.home())
        if path.casefold() == home.casefold():
            return "~"
        if path.casefold().startswith((home + os.sep).casefold()):
            path = "~" + path[len(home):]
        return f"…{path[-56:]}" if len(path) > 60 else path

    def _start_batch_generation(self) -> None:
        if self._busy:
            return
        if not self._batch_files:
            messagebox.showinfo("Lote vacío", "Añade uno o varios archivos TXT o Markdown.", parent=self._batch_dialog)
            return
        if not self._language():
            messagebox.showerror("Idioma no disponible", "No se pudo cargar el idioma seleccionado.", parent=self._batch_dialog)
            return
        if self.tts_engine == "kokoro" and not kokoro_runtime_available():
            messagebox.showerror("Motor natural no disponible", "Actualiza ClassicVoice desde GitHub para instalar el runtime Kokoro.", parent=self._batch_dialog)
            return
        if self.tts_engine == "kokoro" and not model_is_installed(self._natural_model_dir):
            messagebox.showerror("Modelo no instalado", "Descarga primero la voz neuronal desde el botón «Motor: Natural».", parent=self._batch_dialog)
            return
        if self.tts_engine == "espeak" and not self.engine:
            messagebox.showerror("Motor de voz no disponible", "No se encuentra eSpeak NG o no se pudo cargar su catálogo de idiomas.", parent=self._batch_dialog)
            return
        for value, variable, low, high in self._numeric_inputs:
            self._commit_number(value, variable, low, high)
        preset = self._preset()
        settings = {
            "speed": _bounded_int(self.speed.get(), preset.speed, 80, 450),
            "language": self._language(),
            "pitch": _bounded_int(self.pitch.get(), preset.pitch, 0, 99),
            "volume": _bounded_int(self.volume.get(), preset.amplitude, 0, 200),
            "normalize": bool(self.normalize_audio.get()),
            "tts_engine": self.tts_engine,
            "natural_voice": self.natural_voice,
        }
        output_dir = Path(self._batch_output_dir.get()).expanduser()
        self._cancel_event = threading.Event()
        self._busy = True
        self.preview_button.configure(state="disabled")
        self.save_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._batch_start_button.configure(state="disabled")
        self._batch_stop_button.configure(state="normal")
        self._batch_progress.configure(mode="indeterminate")
        self._batch_progress.start(12)
        self._batch_status.set("Preparando capítulos…")
        self.status.set("Preparando lote de audio…")
        self._worker = threading.Thread(
            target=self._run_batch_generation,
            args=(tuple(self._batch_files), output_dir, bool(self._batch_merge.get()), preset, settings, dict(self.pronunciation_rules), self._cancel_event),
            name="ClassicVoice-batch",
            daemon=True,
        )
        self._worker.start()

    def _run_batch_generation(self, files, output_dir, merge_book, preset, settings, rules, cancel_event) -> None:
        staged_paths: list[Path] = []
        published_paths: list[Path] = []
        working_dir: Path | None = None
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            working_dir = Path(tempfile.mkdtemp(prefix=".classicvoice-batch-", dir=output_dir))
            jobs: list[tuple[str, str]] = []
            used_stems: set[str] = set()
            total_chars = 0
            for source_path in files:
                if cancel_event.is_set():
                    raise SynthesisCancelled("cancelled")
                text = read_text_document(source_path)
                total_chars += len(text)
                if total_chars > 5_000_000:
                    raise ValueError("El lote supera los cinco millones de caracteres. Divide el trabajo en varios lotes para mantener un uso de memoria moderado.")
                chapters = split_book_text(text, source_path.stem)
                if not chapters:
                    raise ValueError(f"{source_path.name} no contiene texto para generar.")
                for chapter in chapters:
                    chapter_title = safe_audio_stem(chapter.title)
                    stem = safe_audio_stem(f"{source_path.stem} - {chapter_title}")
                    candidate = stem
                    suffix = 2
                    while candidate.casefold() in used_stems or (output_dir / f"{candidate}.wav").exists():
                        candidate = f"{stem} ({suffix})"
                        suffix += 1
                    used_stems.add(candidate.casefold())
                    jobs.append((candidate, apply_pronunciation_rules(chapter.text, rules)))
            if not jobs:
                raise ValueError("No hay capítulos con texto para sintetizar.")
            total = len(jobs)
            self._events.put(("batch_total", total))
            for index, (stem, text) in enumerate(jobs, start=1):
                if cancel_event.is_set():
                    raise SynthesisCancelled("cancelled")
                if not text.strip():
                    raise ValueError(f"El capítulo «{stem}» queda vacío al aplicar las reglas de pronunciación.")
                staged_path = working_dir / f"{index:04d}.wav"
                duration = self._synthesize_text_to_wav(text, staged_path, preset, settings, cancel_event)
                staged_paths.append(staged_path)
                self._events.put(("batch_progress", index, total, stem, duration))
            combined_staged: Path | None = None
            combined_target: Path | None = None
            if merge_book:
                combined_staged = working_dir / "audiolibro.wav"
                _frames, _seconds = merge_wav_files(staged_paths, combined_staged)
                combined_stem = safe_audio_stem(files[0].stem if len(files) == 1 else "Audiolibro")
                merged_target = self._unique_audio_target(output_dir, combined_stem, used_stems)
                combined_target = merged_target
                final_plan = list(zip(staged_paths, [output_dir / f"{stem}.wav" for stem, _text in jobs]))
                final_plan.append((combined_staged, merged_target))
            else:
                final_plan = list(zip(staged_paths, [output_dir / f"{stem}.wav" for stem, _text in jobs]))
            if cancel_event.is_set():
                raise SynthesisCancelled("cancelled")
            combined_final: Path | None = None
            for staged, target in final_plan:
                target = self._reserve_audio_target(output_dir, target)
                staged.rename(target)
                published_paths.append(target)
                if staged == combined_staged:
                    combined_final = target
            self._events.put(("batch_done", tuple(str(path) for path in published_paths), str(combined_final) if combined_final else None))
        except SynthesisCancelled:
            for path in published_paths:
                path.unlink(missing_ok=True)
            self._events.put(("batch_cancelled",))
        except Exception as exc:
            for path in published_paths:
                path.unlink(missing_ok=True)
            self._events.put(("batch_failed", str(exc)))
        finally:
            self._track_process(None)
            if working_dir is not None:
                import shutil
                shutil.rmtree(working_dir, ignore_errors=True)

    @staticmethod
    def _unique_audio_target(output_dir: Path, stem: str, reserved: set[str]) -> Path:
        base = safe_audio_stem(stem)
        candidate = base
        suffix = 2
        while candidate.casefold() in reserved or (output_dir / f"{candidate}.wav").exists():
            candidate = f"{base} ({suffix})"
            suffix += 1
        reserved.add(candidate.casefold())
        return output_dir / f"{candidate}.wav"

    @staticmethod
    def _reserve_audio_target(output_dir: Path, target: Path) -> Path:
        candidate = target
        suffix = 2
        while candidate.exists():
            candidate = target.with_name(f"{target.stem} ({suffix}){target.suffix}")
            suffix += 1
        return candidate

    def _track_process(self, process: subprocess.Popen | None) -> None:
        with self._process_lock:
            self._process = process

    def _synthesize_text_to_wav(self, text, output, preset, settings, cancel_event) -> float:
        if settings.get("tts_engine", self.tts_engine) == "kokoro":
            language = settings.get("language")
            if language is None:
                raise ValueError("Selecciona un idioma compatible con la voz natural.")
            return synthesize_kokoro_to_wav(
                text,
                output,
                settings.get("natural_voice", self.natural_voice),
                language.code,
                settings["speed"],
                settings.get("normalize", True),
                cancel_event,
                self._natural_model_dir,
                APP_DIR,
            )
        if not self.engine:
            raise RuntimeError("No se encuentra eSpeak NG.")
        return synthesize_text_to_wav(self.engine, APP_DIR, text, output, preset, settings, cancel_event, self._track_process)

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
        if self.tts_engine == "kokoro":
            available = voices_for_language(self._language_code)
            self.natural_voice = next((voice_id for voice_id, label in available if label == self.preset_label.get()), self.natural_voice)
            self.preset_description.set("Voz neuronal predefinida · Kokoro procesa el texto localmente.")
            self._schedule_config_save()
            return
        preset = self._preset()
        self._classic_preset_key = preset.key
        self.speed.set(preset.speed)
        self.pitch.set(preset.pitch)
        self.volume.set(preset.amplitude)
        self.preset_description.set(preset.description)
        self._schedule_config_save()

    def _reset_voice(self) -> None:
        if self.tts_engine != "kokoro":
            self._apply_preset()
            return
        available = voices_for_language(self._language_code)
        if not available:
            return
        self.natural_voice = available[0][0]
        self.speed.set(145)
        self._refresh_engine_controls()
        self.status.set("Voz natural restablecida")
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
            "version": 5,
            "language_code": self._language_code,
            "tts_engine": self.tts_engine,
            "natural_voice": self.natural_voice,
            "preset_key": self._classic_preset_key,
            "speed": _bounded_int(self.speed.get(), self._preset().speed, 80, 450),
            "pitch": _bounded_int(self.pitch.get(), self._preset().pitch, 0, 99),
            "volume": _bounded_int(self.volume.get(), self._preset().amplitude, 0, 200),
            "normalize": bool(self.normalize_audio.get()),
            "last_dir": self._last_dir,
            "pronunciation_by_language": self._rules_by_language,
            "voice_profiles": self.voice_profiles,
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
        if self.tts_engine == "kokoro" and not kokoro_runtime_available():
            messagebox.showerror("Motor natural no disponible", "Actualiza ClassicVoice desde GitHub para instalar el runtime Kokoro.", parent=self)
            return
        if self.tts_engine == "kokoro" and not model_is_installed(self._natural_model_dir):
            messagebox.showinfo("Modelo no instalado", "Abre «Motor: Natural» y descarga la voz neuronal para usarla sin conexión.", parent=self)
            return
        if self.tts_engine == "espeak" and not self.engine:
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
            "tts_engine": self.tts_engine,
            "natural_voice": self.natural_voice,
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
        working_output: Path | None = None
        retain_output = False
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            job_id = uuid.uuid4().hex
            if mode == "export" and target is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                working_output = target.with_name(f".{target.stem}.{job_id}.tmp.wav")
            else:
                working_output = temp_dir / f"preview-{job_id}.wav"
            duration = self._synthesize_text_to_wav(text, working_output, preset, settings, cancel_event)
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
            if working_output is not None and not retain_output:
                working_output.unlink(missing_ok=True)

    def _poll_events(self) -> None:
        if self._closing:
            return
        try:
            while True:
                event = self._events.get_nowait()
                if event[0] == "natural_model_progress":
                    _, name, current, total = event
                    if self._natural_settings_status is not None:
                        label = "modelo" if name == "modelo" else "paquete de voces"
                        self._natural_settings_status.set(f"Descargando {label}: {current / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MiB…")
                    if self._natural_settings_progress is not None:
                        completed = current if name == "modelo" else KOKORO_MODEL_BYTES + current
                        total_bytes = KOKORO_MODEL_BYTES + KOKORO_VOICES_BYTES
                        self._natural_settings_progress.configure(value=completed / total_bytes * 100)
                elif event[0] == "natural_model_installed":
                    self._natural_installing = False
                    self._model_worker = None
                    self._refresh_engine_controls()
                    self._refresh_natural_settings()
                    self.status.set("Voz natural lista · síntesis local activada")
                elif event[0] == "natural_model_cancelled":
                    self._natural_installing = False
                    self._model_worker = None
                    self._refresh_natural_settings()
                    self._refresh_engine_controls()
                    if not self._closing:
                        self.status.set("Descarga del modelo cancelada")
                elif event[0] == "natural_model_failed":
                    self._natural_installing = False
                    self._model_worker = None
                    self._refresh_natural_settings()
                    self._refresh_engine_controls()
                    self.status.set("No se pudo instalar el modelo neuronal")
                    if not self._closing and self._natural_settings_dialog is not None:
                        messagebox.showerror("No se pudo instalar la voz natural", event[1], parent=self._natural_settings_dialog)
                elif event[0] == "batch_total":
                    total = event[1]
                    if self._batch_progress is not None:
                        self._batch_progress.stop()
                        self._batch_progress.configure(mode="determinate", maximum=total, value=0)
                    if self._batch_status is not None:
                        self._batch_status.set(f"Generando {total} capítulos…")
                elif event[0] == "batch_progress":
                    _, index, total, title, duration = event
                    if self._batch_progress is not None:
                        self._batch_progress.configure(mode="determinate", maximum=total, value=index)
                    if self._batch_status is not None:
                        self._batch_status.set(f"Capítulo {index} de {total}: {title} · {duration:.1f} s")
                elif event[0] == "batch_done":
                    self._finish_batch("done", event[1], event[2] if len(event) > 2 else None)
                elif event[0] == "batch_cancelled":
                    self._finish_batch("cancelled")
                elif event[0] == "batch_failed":
                    self._finish_batch("failed", error=event[1])
                elif event[0] == "cancelled":
                    self._finish_generation(event[1], None, None, 0.0)
                elif event[0] == "done":
                    _, mode, path, error, duration = event
                    self._finish_generation(mode, path, error, duration)
        except queue.Empty:
            pass
        self._poll_after = self.after(80, self._poll_events)

    def _finish_batch(self, result: str, outputs=(), combined: str | None = None, error: str | None = None) -> None:
        self._progress.stop()
        self._progress.configure(mode="determinate", value=0)
        self._busy = False
        self._worker = None
        self.preview_button.configure(state="normal")
        self.save_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if self._batch_progress is not None:
            self._batch_progress.stop()
            self._batch_progress.configure(mode="determinate", value=0)
        if self._batch_start_button is not None:
            self._batch_start_button.configure(state="normal")
        if self._batch_stop_button is not None:
            self._batch_stop_button.configure(state="disabled")
        if result == "done":
            count = len(outputs)
            self.status.set(f"Lote terminado · {count} archivos WAV")
            message = f"Se crearon {count} archivos WAV en:\n{self._batch_output_dir.get()}"
            if combined:
                message += f"\n\nAudiolibro completo: {Path(combined).name}"
            if self._batch_status is not None:
                self._batch_status.set(f"Terminado · {count} WAV creados correctamente.")
            if not self._closing and self._batch_dialog is not None:
                messagebox.showinfo("Lote terminado", message, parent=self._batch_dialog)
        elif result == "cancelled":
            self.status.set("Lote cancelado · no se publicaron archivos incompletos")
            if self._batch_status is not None:
                self._batch_status.set("Proceso detenido. Se eliminaron los archivos temporales del lote.")
        else:
            self.status.set("No se pudo completar el lote")
            if self._batch_status is not None:
                self._batch_status.set("No se pudo completar el lote.")
            if error and not self._closing:
                messagebox.showerror("Lote fallido", error, parent=self._batch_dialog if self._batch_dialog is not None else self)

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

    def _open_voice_profiles(self) -> None:
        if self._voice_profile_dialog is not None and self._voice_profile_dialog.winfo_exists():
            self._voice_profile_dialog.lift()
            return
        dialog = tk.Toplevel(self)
        self._voice_profile_dialog = dialog
        dialog.title("Perfiles de voz · ClassicVoice")
        dialog.geometry("540x430")
        dialog.minsize(480, 360)
        dialog.configure(bg=COLORS["canvas"])
        dialog.transient(self)
        page = ttk.Frame(dialog, style="App.TFrame", padding=18)
        page.pack(fill="both", expand=True)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)
        ttk.Label(page, text="Mis perfiles de voz", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            page,
            text="Guarda y reutiliza los ajustes locales de ClassicVoice. Los perfiles guardan idioma, estilo, controles y reglas de pronunciación; no clonan una voz grabada.",
            style="Subtitle.TLabel",
            wraplength=490,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 12))
        list_frame = ttk.Frame(page, style="Card.TFrame", padding=8)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        profiles = tk.Listbox(list_frame, exportselection=False, relief="flat", highlightthickness=1, highlightbackground=COLORS["border"], activestyle="dotbox", font=("Segoe UI", 10))
        profiles.grid(row=0, column=0, sticky="nsew")
        profile_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=profiles.yview)
        profile_scroll.grid(row=0, column=1, sticky="ns")
        profiles.configure(yscrollcommand=profile_scroll.set)

        def refresh(selected_name: str | None = None) -> None:
            profiles.delete(0, "end")
            for name in sorted(self.voice_profiles, key=str.casefold):
                profiles.insert("end", name)
                if selected_name and name == selected_name:
                    profiles.selection_set("end")
                    profiles.see("end")

        def selected_name() -> str | None:
            selection = profiles.curselection()
            return profiles.get(selection[0]) if selection else None

        def save_current() -> None:
            name = simpledialog.askstring("Guardar perfil", "Nombre del perfil (hasta 36 caracteres):", parent=dialog)
            if name is None:
                return
            name = name.strip()[:36]
            if not name or any(ord(char) < 32 for char in name):
                messagebox.showinfo("Perfil", "Escribe un nombre válido para el perfil.", parent=dialog)
                return
            existing = next((key for key in self.voice_profiles if key.casefold() == name.casefold()), None)
            if existing and not messagebox.askyesno("Reemplazar perfil", f"¿Actualizar el perfil «{existing}» con los ajustes actuales?", parent=dialog):
                return
            if existing is None and len(self.voice_profiles) >= 24:
                messagebox.showinfo("Límite de perfiles", "ClassicVoice permite guardar hasta 24 perfiles. Elimina uno para guardar otro.", parent=dialog)
                return
            self.voice_profiles.pop(existing, None) if existing else None
            self.voice_profiles[name] = {
                "tts_engine": self.tts_engine,
                "natural_voice": self.natural_voice,
                "language_code": self._language_code,
                "preset_key": self._classic_preset_key,
                "speed": _bounded_int(self.speed.get(), self._preset().speed, 80, 450),
                "pitch": _bounded_int(self.pitch.get(), self._preset().pitch, 0, 99),
                "volume": _bounded_int(self.volume.get(), self._preset().amplitude, 0, 200),
                "normalize": bool(self.normalize_audio.get()),
                "pronunciation_rules": dict(self.pronunciation_rules),
            }
            self._schedule_config_save()
            refresh(name)

        def apply_selected() -> None:
            name = selected_name()
            profile = self.voice_profiles.get(name) if name else None
            if profile is None:
                messagebox.showinfo("Perfil", "Selecciona un perfil de la lista.", parent=dialog)
                return
            requested_engine = profile["tts_engine"]
            target_languages = self._languages_for_engine(requested_engine)
            language = next((item for item in target_languages if item.code == profile["language_code"]), None)
            if language is None:
                messagebox.showinfo("Idioma no disponible", "El motor guardado en este perfil no contiene ese idioma.", parent=dialog)
                return
            if requested_engine == "kokoro" and not kokoro_runtime_available():
                messagebox.showinfo("Motor no disponible", "Esta compilación no incluye el motor natural guardado en este perfil.", parent=dialog)
                return
            self._set_tts_engine(requested_engine)
            preset = next((item for item in PRESETS if item.key == profile["preset_key"]), PRESETS[0])
            self._classic_preset_key = preset.key
            self.language_label.set(language.label)
            self._apply_language()
            if self.tts_engine == "kokoro":
                self.natural_voice = profile["natural_voice"]
                self._refresh_engine_controls()
            else:
                self.preset_label.set(preset.label)
                self.preset_description.set(preset.description)
            self.speed.set(profile["speed"])
            self.pitch.set(profile["pitch"])
            self.volume.set(profile["volume"])
            self.normalize_audio.set(profile["normalize"])
            self.pronunciation_rules = dict(profile["pronunciation_rules"])
            self._rules_by_language[self._language_code] = self.pronunciation_rules
            self.rules_button.configure(text=f"Pronunciación · {len(self.pronunciation_rules)}")
            self._schedule_config_save()
            self.status.set(f"Perfil aplicado · {name}")
            dialog.destroy()

        def delete_selected() -> None:
            name = selected_name()
            if name and messagebox.askyesno("Eliminar perfil", f"¿Eliminar el perfil «{name}»?", parent=dialog):
                self.voice_profiles.pop(name, None)
                self._schedule_config_save()
                refresh()

        actions = ttk.Frame(page, style="App.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Guardar ajustes actuales…", style="Quiet.TButton", command=save_current).pack(side="left")
        ttk.Button(actions, text="Eliminar", style="Secondary.TButton", command=delete_selected).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Usar perfil", style="Primary.TButton", command=apply_selected).pack(side="right")
        refresh()
        if self.voice_profiles:
            profiles.selection_set(0)
        dialog.bind("<Return>", lambda _event: apply_selected())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.bind("<Destroy>", lambda event: setattr(self, "_voice_profile_dialog", None) if event.widget is dialog else None, add="+")

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
        if self._natural_installing:
            self._natural_cancel_event.set()
        if self._poll_after:
            try:
                self.after_cancel(self._poll_after)
            except tk.TclError:
                pass
            self._poll_after = None
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
