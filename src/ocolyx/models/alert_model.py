"""Alert data models."""

from dataclasses import dataclass


@dataclass
class AlertModel:
    title: str
    message: str
    active: bool = True
