"""persona / 시나리오 목록을 기존 프롬프트 YAML에서 읽어온다."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.prompt_builder.general_chat import composer

PERSONA_DIR = "bundles/personas"
SCENARIO_DIR = "modes"


@dataclass(frozen=True)
class Persona:
    id: str
    description: str
    voice_id: str | None


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _iter_yaml(subdir: str) -> list[Path]:
    directory = composer.root / subdir
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.yaml") if p.is_file())


@lru_cache(maxsize=1)
def list_personas() -> tuple[Persona, ...]:
    personas: list[Persona] = []
    for path in _iter_yaml(PERSONA_DIR):
        data = _read_yaml(path)
        personas.append(
            Persona(
                id=str(data.get("id") or path.stem),
                description=str(data.get("description") or ""),
                voice_id=str(data["voice_id"]) if data.get("voice_id") else None,
            )
        )
    return tuple(personas)


@lru_cache(maxsize=1)
def list_scenarios() -> tuple[Scenario, ...]:
    scenarios: list[Scenario] = []
    for path in _iter_yaml(SCENARIO_DIR):
        data = _read_yaml(path)
        scenarios.append(
            Scenario(
                id=str(data.get("id") or path.stem),
                description=str(data.get("description") or ""),
            )
        )
    return tuple(scenarios)


def find_persona(persona_id: str) -> Persona | None:
    target = persona_id.strip().lower()
    return next((p for p in list_personas() if p.id.lower() == target), None)


def find_scenario(scenario_id: str) -> Scenario | None:
    target = scenario_id.strip().lower()
    return next((s for s in list_scenarios() if s.id.lower() == target), None)


def clear_cache() -> None:
    list_personas.cache_clear()
    list_scenarios.cache_clear()
