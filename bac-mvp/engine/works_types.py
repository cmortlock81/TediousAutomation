"""Works type classification."""
from __future__ import annotations

from typing import Iterable

from .config import WorksTypeRule


class WorksTypeClassifier:
    def __init__(self, rules: Iterable[WorksTypeRule], default: str = "OTHER") -> None:
        self._rules = list(rules)
        self._default = default

    def classify(self, description: str) -> str:
        desc = description.lower()
        for rule in self._rules:
            if any(pattern in desc for pattern in rule.patterns):
                return rule.name
        return self._default
