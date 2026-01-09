"""Works type classification."""
from __future__ import annotations

from typing import Iterable

from .config import WorksTypesConfig


class WorksTypeClassifier:
    def __init__(self, config: WorksTypesConfig) -> None:
        self._rules = list(config.rules)
        self._default = config.default

    def classify(self, description: str) -> str:
        desc = description.lower()
        for rule in self._rules:
            if any(pattern in desc for pattern in rule.patterns):
                return rule.name
        return self._default
