"""Read and update Decepticon's .env without disturbing its formatting."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")

PLACEHOLDERS = {
    "LITELLM_MASTER_KEY": {"sk-decepticon-master", "your-litellm-master-key-here"},
    "LITELLM_SALT_KEY": {"sk-decepticon-salt-change-me"},
    "POSTGRES_PASSWORD": {"decepticon"},
    "NEO4J_PASSWORD": {"decepticon-graph"},
}

SECRET_DEFAULTS = {
    "LITELLM_MASTER_KEY": lambda: "sk-" + secrets.token_hex(32),
    "LITELLM_SALT_KEY": lambda: "sk-" + secrets.token_hex(24),
    "POSTGRES_PASSWORD": lambda: secrets.token_hex(24),
    "NEO4J_PASSWORD": lambda: secrets.token_hex(18),
}


class EnvFile:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.lines: list[str] = []
        self.index: dict[str, int] = {}
        self.dirty = False

    # -- io ----------------------------------------------------------
    def load(self):
        self.lines, self.index, self.dirty = [], {}, False
        if not self.path or not self.path.is_file():
            return self
        text = self.path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            self.lines.append(line)
            m = LINE_RE.match(line)
            if m and not line.lstrip().startswith("#"):
                self.index[m.group(1)] = len(self.lines) - 1
        return self

    def save(self):
        if not self.path:
            return
        if not self.lines:
            self.load()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        self.dirty = False

    # -- values ------------------------------------------------------
    @staticmethod
    def _unquote(value: str) -> str:
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            return value[1:-1]
        return value.split(" #")[0].strip()

    def get(self, key: str, default: str = "") -> str:
        idx = self.index.get(key)
        if idx is None:
            return default
        m = LINE_RE.match(self.lines[idx])
        return self._unquote(m.group(2)) if m else default

    def set(self, key: str, value: str):
        line = f"{key}={value}"
        if key in self.index:
            self.lines[self.index[key]] = line
        else:
            self.lines.append(line)
            self.index[key] = len(self.lines) - 1
        self.dirty = True

    def is_placeholder(self, key: str) -> bool:
        value = self.get(key)
        if key in PLACEHOLDERS:
            return (not value) or value in PLACEHOLDERS[key]
        return (not value) or value.startswith("your-") or value.endswith("-here")

    def ensure_secrets(self) -> list[str]:
        """Replace shipped default secrets. Returns the keys that changed."""
        changed = []
        for key, factory in SECRET_DEFAULTS.items():
            if self.is_placeholder(key) or key not in self.index:
                self.set(key, factory())
                changed.append(key)
        if changed:
            self.save()
        return changed

    def configured_providers(self) -> list[str]:
        keys = {
            "ANTHROPIC_API_KEY": "Anthropic",
            "OPENAI_API_KEY": "OpenAI",
            "GEMINI_API_KEY": "Google Gemini",
            "DEEPSEEK_API_KEY": "DeepSeek",
            "OPENROUTER_API_KEY": "OpenRouter",
            "XAI_API_KEY": "xAI",
            "MISTRAL_API_KEY": "Mistral",
            "MINIMAX_API_KEY": "MiniMax",
            "NVIDIA_API_KEY": "NVIDIA NIM",
            "MOONSHOT_API_KEY": "Moonshot",
            "ZAI_API_KEY": "Z.AI",
            "DASHSCOPE_API_KEY": "DashScope",
            "GROQ_API_KEY": "Groq",
            "TOGETHER_API_KEY": "Together",
        }
        found = [name for key, name in keys.items()
                 if not self.is_placeholder(key) and self.get(key)]
        if self.get("OLLAMA_MODEL") and self.get("OLLAMA_API_BASE"):
            found.append("Ollama")
        return found
