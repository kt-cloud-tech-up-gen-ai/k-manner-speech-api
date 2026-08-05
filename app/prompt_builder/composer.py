from pathlib import Path
from typing import Iterable

import yaml


class PromptComposer:
    def __init__(self, prompt_root: str | Path = "prompts"):
        raw_root = Path(prompt_root)
        if raw_root.is_absolute():
            self.root = raw_root.resolve()
        else:
            start = Path(__file__).resolve().parent
            for parent in [start, *start.parents]:
                candidate = parent / raw_root
                if candidate.exists():
                    self.root = candidate.resolve()
                    break
            else:
                self.root = (Path.cwd() / raw_root).resolve()

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

    def load_bundle(self, name: str) -> list[dict]:
        """묶음 YAML에 정의된 개별 프롬프트를 모두 불러온다.

        묶음 YAML은 ``bundles/<name>.yaml`` 경로에 두며, 각 항목은
        ``category``와 ``name``을 가져야 한다.
        """
        path = self.root / "bundles" / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(path)

        with path.open("r", encoding="utf-8") as f:
            bundle = yaml.safe_load(f)

        if not isinstance(bundle, dict):
            raise ValueError(f"{path} is not a valid bundle yaml.")

        items = bundle.get("prompts")
        if not isinstance(items, list):
            raise ValueError(f"{path} has no valid prompts list.")

        prompts: list[dict] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"{path} prompts[{index}] is not an object.")

            category = item.get("category")
            prompt_name = item.get("name")
            if not isinstance(category, str) or not isinstance(prompt_name, str):
                raise ValueError(
                    f"{path} prompts[{index}] must have string category and name."
                )

            prompts.append(self.load(category, prompt_name))

        return prompts

    def compose_bundle(self, name: str) -> str:
        """묶음 YAML을 읽고, 포함된 프롬프트를 우선순위에 따라 합성한다."""
        return self.compose_by_priority(self.load_bundle(name))

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
