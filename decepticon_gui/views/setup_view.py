"""Configuration page: model provider, keys, profile, ports, installer."""

from __future__ import annotations

import os
import shutil
import tkinter as tk
from tkinter import ttk

from .. import paths, ui
from ..envfile import EnvFile
from ..i18n import t

PROVIDERS = [
    ("Anthropic (Claude)", "ANTHROPIC_API_KEY", ""),
    ("OpenAI", "OPENAI_API_KEY", ""),
    ("Google Gemini", "GEMINI_API_KEY", ""),
    ("DeepSeek", "DEEPSEEK_API_KEY", ""),
    ("OpenRouter", "OPENROUTER_API_KEY", ""),
    ("xAI (Grok)", "XAI_API_KEY", ""),
    ("Moonshot / Kimi", "MOONSHOT_API_KEY", ""),
    ("Z.AI (GLM)", "ZAI_API_KEY", ""),
    ("DashScope (Qwen)", "DASHSCOPE_API_KEY", ""),
    ("MiniMax", "MINIMAX_API_KEY", ""),
    ("Groq", "GROQ_API_KEY", ""),
    ("Ollama (local)", "OLLAMA_MODEL", "local"),
    ("Custom OpenAI-compatible", "CUSTOM_OPENAI_API_KEY", "custom"),
]

PROFILES = [
    ("eco", "setup.profile.eco"),
    ("max", "setup.profile.max"),
    ("test", "setup.profile.test"),
]

LANGUAGES = [
    ("zh-cn", "简体中文"), ("zh-tw", "繁體中文"), ("en", "English"),
    ("ja", "日本語"), ("ko", "한국어"), ("wenyan", "文言"),
]

PORT_FIELDS = [
    ("LANGGRAPH_PORT", "LangGraph", "2024"),
    ("LITELLM_PORT", "LiteLLM", "4000"),
    ("WEB_PORT", "Web", "3000"),
    ("NEO4J_HTTP_PORT", "Neo4j HTTP", "7474"),
    ("POSTGRES_PORT", "PostgreSQL", "5432"),
]


class SetupView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=ui.COLORS["bg"])
        self.app = app
        self.port_entries = {}
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        head = tk.Frame(self, bg=ui.COLORS["bg"])
        head.pack(fill="x", pady=(0, 14))
        box = tk.Frame(head, bg=ui.COLORS["bg"])
        box.pack(side="left")
        ui.label(box, t("setup.title"), size=18, bold=True).pack(anchor="w")
        ui.label(box, t("setup.subtitle"), size=9,
                 fg=ui.COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(head, bg=ui.COLORS["bg"])
        actions.pack(side="right")
        ui.button(actions, t("common.reload"), self.on_show, "ghost").pack(
            side="left", padx=(0, 6))
        ui.button(actions, t("setup.save"), self.save, "primary").pack(side="left")

        body = tk.Frame(self, bg=ui.COLORS["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, uniform="c")
        body.columnconfigure(1, weight=2, uniform="c")
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=ui.COLORS["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = tk.Frame(body, bg=ui.COLORS["bg"])
        right.grid(row=0, column=1, sticky="nsew")

        # model card ---------------------------------------------------
        model = ui.Card(left, t("setup.model"), t("setup.model.hint"))
        model.pack(fill="x")
        row = tk.Frame(model.body, bg=ui.COLORS["panel"])
        row.pack(fill="x")
        ui.label(row, t("setup.provider"), size=9, fg=ui.COLORS["muted"]).pack(anchor="w")
        self.provider = ttk.Combobox(row, values=[p[0] for p in PROVIDERS],
                                     state="readonly", font=ui.font(9))
        self.provider.pack(fill="x", pady=(4, 10))
        self.provider.bind("<<ComboboxSelected>>", lambda e: self._provider_changed())

        key_row = tk.Frame(model.body, bg=ui.COLORS["panel"])
        key_row.pack(fill="x")
        ui.label(key_row, t("setup.apikey"), size=9, fg=ui.COLORS["muted"]).pack(anchor="w")
        entry_row = tk.Frame(key_row, bg=ui.COLORS["panel"])
        entry_row.pack(fill="x", pady=(4, 0))
        self.api_key_box, self.api_key = ui.entry(entry_row, show="•")
        self.api_key_box.pack(side="left", fill="x", expand=True)
        self.show_key = tk.BooleanVar(value=False)
        tk.Checkbutton(entry_row, text=t("setup.show"), variable=self.show_key,
                       command=self._toggle_key, font=ui.font(8),
                       bg=ui.COLORS["panel"], fg=ui.COLORS["muted"],
                       activebackground=ui.COLORS["panel"], bd=0,
                       selectcolor=ui.COLORS["panel_alt"]).pack(side="left", padx=(8, 0))

        self.extra_frame = tk.Frame(model.body, bg=ui.COLORS["panel"])
        self.extra_frame.pack(fill="x", pady=(10, 0))
        self.base_url = self._field(self.extra_frame, t("setup.base_url"))
        self.model_id = self._field(self.extra_frame, t("setup.model_id"))

        # profile ------------------------------------------------------
        profile_card = ui.Card(left, t("setup.profile"))
        profile_card.pack(fill="x", pady=(12, 0))
        self.profile_var = tk.StringVar(value="eco")
        for value, desc_key in PROFILES:
            line = tk.Frame(profile_card.body, bg=ui.COLORS["panel"])
            line.pack(fill="x", pady=2)
            tk.Radiobutton(
                line, text=value, variable=self.profile_var, value=value,
                font=ui.font(9, True), bg=ui.COLORS["panel"], fg=ui.COLORS["text"],
                activebackground=ui.COLORS["panel"], selectcolor=ui.COLORS["panel_alt"],
                bd=0, highlightthickness=0).pack(side="left")
            ui.label(line, t(desc_key), size=9, fg=ui.COLORS["muted"]).pack(
                side="left", padx=(10, 0))

        # ports --------------------------------------------------------
        ports = ui.Card(left, t("setup.ports"), t("setup.ports.hint"))
        ports.pack(fill="both", expand=True, pady=(12, 0))
        for key, name, default in PORT_FIELDS:
            line = tk.Frame(ports.body, bg=ui.COLORS["panel"])
            line.pack(fill="x", pady=3)
            ui.label(line, name, size=9).pack(side="left")
            box, entry = ui.entry(line, width=9, justify="right", font_size=8, pad_y=3)
            box.pack(side="right")
            ui.label(line, t("setup.port.default", value=default), size=8,
                     fg=ui.COLORS["muted"]).pack(side="right", padx=(0, 10))
            self.port_entries[key] = entry

        # right column -------------------------------------------------
        install = ui.Card(right, t("setup.install"))
        install.pack(fill="x")
        self.install_status = ui.label(install.body, "…", size=9,
                                       fg=ui.COLORS["muted"])
        self.install_status.pack(anchor="w", pady=(0, 8))
        ui.button(install.body, t("setup.btn.install"), self.install, "primary").pack(
            fill="x", pady=2)
        ui.button(install.body, t("setup.btn.onboard"), self.onboard, "secondary").pack(
            fill="x", pady=2)
        ui.button(install.body, t("setup.btn.env"), self.open_env, "secondary").pack(
            fill="x", pady=2)
        ui.button(install.body, t("setup.btn.home"), self.open_home, "ghost").pack(
            fill="x", pady=2)

        other = ui.Card(right, t("setup.other"))
        other.pack(fill="x", pady=(12, 0))
        line = tk.Frame(other.body, bg=ui.COLORS["panel"])
        line.pack(fill="x")
        ui.label(line, t("setup.language"), size=9).pack(side="left")
        self.language = ttk.Combobox(
            line, values=[f"{code} · {name}" for code, name in LANGUAGES],
            state="readonly", font=ui.font(9), width=16)
        self.language.pack(side="right")

        self.env_path_label = ui.label(other.body, "", size=8, fg=ui.COLORS["muted"],
                                       mono=True, wraplength=280, justify="left")
        self.env_path_label.pack(anchor="w", pady=(10, 0))

        tips = ui.Card(right, t("setup.tips.title"))
        tips.pack(fill="both", expand=True, pady=(12, 0))
        ui.label(tips.body, t("setup.tips"), size=9, fg=ui.COLORS["muted"],
                 justify="left", wraplength=270).pack(anchor="w")

    def _field(self, parent, caption):
        wrap = tk.Frame(parent, bg=ui.COLORS["panel"])
        wrap.pack(fill="x", pady=3)
        ui.label(wrap, caption, size=9, fg=ui.COLORS["muted"]).pack(anchor="w")
        box, entry = ui.entry(wrap)
        box.pack(fill="x", pady=(3, 0))
        return entry

    # ------------------------------------------------------------------
    def _toggle_key(self):
        self.api_key.configure(show="" if self.show_key.get() else "•")

    def _provider_changed(self):
        name = self.provider.get()
        entry = next((p for p in PROVIDERS if p[0] == name), None)
        if not entry:
            return
        env = self._env()
        value = env.get(entry[1])
        self.api_key.delete(0, "end")
        if value and not value.startswith("your-"):
            self.api_key.insert(0, value)
        kind = entry[2]
        if kind in ("custom", "local"):
            self.extra_frame.pack(fill="x", pady=(10, 0))
            base_key = "CUSTOM_OPENAI_API_BASE" if kind == "custom" else "OLLAMA_API_BASE"
            model_key = "CUSTOM_OPENAI_MODEL" if kind == "custom" else "OLLAMA_MODEL"
            default_base = "" if kind == "custom" else "http://host.docker.internal:11434"
            self.base_url.delete(0, "end")
            self.base_url.insert(0, env.get(base_key) or default_base)
            self.model_id.delete(0, "end")
            self.model_id.insert(0, env.get(model_key) or "")
        else:
            self.extra_frame.pack_forget()
            self.base_url.delete(0, "end")
            self.model_id.delete(0, "end")

    def _env(self):
        path = paths.env_path()
        return EnvFile(path).load() if path.is_file() else EnvFile(path)

    # ------------------------------------------------------------------
    def on_show(self):
        version = paths.installed_version()
        installed = paths.is_installed()
        if installed:
            label = t("setup.installed", version=version) if version else t("common.installed")
        else:
            label = t("common.not_installed")
        self.install_status.configure(
            text=label, fg=ui.COLORS["ok"] if installed else ui.COLORS["bad"])
        self.env_path_label.configure(
            text=t("setup.paths", env=paths.env_path(), home=paths.decepticon_home()))

        env = self._env()
        providers = env.configured_providers()
        default_name = PROVIDERS[0][0]
        if providers:
            for name, key, _kind in PROVIDERS:
                if env.get(key) and not env.is_placeholder(key):
                    default_name = name
                    break
        self.provider.set(default_name)
        self.api_key.delete(0, "end")
        entry = next((p for p in PROVIDERS if p[0] == default_name), None)
        if entry:
            value = env.get(entry[1])
            if value and not value.startswith("your-"):
                self.api_key.insert(0, value)

        profile = env.get("DECEPTICON_MODEL_PROFILE") or "eco"
        self.profile_var.set(profile if profile in ("eco", "max", "test") else "eco")

        lang = env.get("DECEPTICON_LANGUAGE") or "en"
        display = next((f"{code} · {name}" for code, name in LANGUAGES if code == lang),
                       "en · English")
        self.language.set(display)

        for key, _name, _default in PORT_FIELDS:
            value = env.get(key)
            self.port_entries[key].delete(0, "end")
            if value:
                self.port_entries[key].insert(0, value)

        self._provider_changed()

    # ------------------------------------------------------------------
    def save(self):
        path = paths.env_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() and paths.env_example_path().is_file():
            shutil.copyfile(paths.env_example_path(), path)
        env = EnvFile(path).load()
        if not env.lines:
            env.lines = ["# generated by Decepticon GUI", ""]

        name = self.provider.get()
        entry = next((p for p in PROVIDERS if p[0] == name), None)
        key_value = self.api_key.get().strip()
        if entry and key_value:
            env.set(entry[1], key_value)
            if entry[2] == "custom":
                base = self.base_url.get().strip()
                model = self.model_id.get().strip()
                if base:
                    env.set("CUSTOM_OPENAI_API_BASE", base)
                if model:
                    env.set("CUSTOM_OPENAI_MODEL", model)
            elif entry[2] == "local":
                base = self.base_url.get().strip() or "http://host.docker.internal:11434"
                env.set("OLLAMA_API_BASE", base)
                model = self.model_id.get().strip()
                if model:
                    env.set("OLLAMA_MODEL", model)

        env.set("DECEPTICON_MODEL_PROFILE", self.profile_var.get())

        lang = self.language.get().split("·")[0].strip()
        if lang:
            env.set("DECEPTICON_LANGUAGE", lang)

        for key, entry_widget in self.port_entries.items():
            value = entry_widget.get().strip()
            if value:
                env.set(key, value)

        env.save()
        changed = EnvFile(path).load().ensure_secrets()
        self.app.notify(t("setup.msg.saved_secrets") if changed else t("setup.msg.saved"), "ok")
        self.on_show()

    # ------------------------------------------------------------------
    def install(self):
        script = ("powershell -NoProfile -ExecutionPolicy Bypass -Command "
                  "\"irm https://decepticon.red/install.ps1 | iex\"")
        self.app.run_in_terminal(script)
        self.app.notify(t("setup.msg.install_started"), "muted")

    def onboard(self):
        launcher = paths.launcher_path()
        if not launcher:
            self.app.notify(t("setup.msg.need_install"), "warn")
            return
        self.app.run_in_terminal(f'"{launcher}" onboard')

    def open_env(self):
        path = paths.env_path()
        if not path.is_file():
            self.app.notify(t("setup.msg.no_env"), "warn")
            return
        os.startfile(str(path))

    def open_home(self):
        home = paths.decepticon_home()
        home.mkdir(parents=True, exist_ok=True)
        os.startfile(str(home))
