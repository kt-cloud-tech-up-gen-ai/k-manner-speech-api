from pathlib import Path
from typing import Iterable

import yaml


class PromptComposer:
    def __init__(self, prompt_root: str | Path = "prompts"):
        self.root = Path(prompt_root)

    def _load_yaml(self, path: Path) -> dict:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"{path} is not a valid yaml.")

        if "prompt" not in data:
            raise ValueError(f"{path} has no prompt field.")

        data.setdefault("priority", 50)
        data.setdefault("enabled", True)

        return data

    def load(
        self,
        category: str,
        name: str,
    ) -> dict:

        path = self.root / category / f"{name}.yaml"

        if not path.exists():
            raise FileNotFoundError(path)

        return self._load_yaml(path)

    def compose(self, *prompts: dict) -> str:

        enabled = [
            p for p in prompts
            if p.get("enabled", True)
        ]

        enabled.sort(key=lambda x: x.get("priority", 50), reverse=True)

        parts = []

        for prompt in enabled:
            parts.append(prompt["prompt"].strip())

        return "\n\n".join(parts)

    def compose_by_priority(
        self,
        prompts: Iterable[dict],
    ) -> str:
        ordered = [p for p in prompts if p.get("enabled", True)]
        ordered.sort(key=lambda x: x.get("priority", 50), reverse=True)
        return "\n\n".join(p["prompt"].strip() for p in ordered if p.get("prompt"))

    def compose_by_name(
        self,
        identities: Iterable[str] = (),
        personalities: Iterable[str] = (),
        styles: Iterable[str] = (),
        rules: Iterable[str] = (),
        tasks: Iterable[str] = (),
        modes: Iterable[str] = (),
    ) -> str:

        prompts = []

        for x in identities:
            prompts.append(self.load("identities", x))

        for x in personalities:
            prompts.append(self.load("personalities", x))

        for x in styles:
            prompts.append(self.load("styles", x))

        for x in rules:
            prompts.append(self.load("rules", x))

        for x in tasks:
            prompts.append(self.load("tasks", x))

        for x in modes:
            prompts.append(self.load("modes", x))

        return self.compose(*prompts)