"""Modul-Interface fuer Baki AIO."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Action:
    """Ein Menuepunkt eines Moduls.

    title   - Text im Menue
    argv    - Argumente fuer Module.run()
    prompts - (Option, Frage)-Paare, die vor dem Start abgefragt und als
              "<Option> <Antwort>" an argv angehaengt werden
    """

    title: str
    argv: list = field(default_factory=list)
    prompts: list = field(default_factory=list)


class Module(ABC):
    """Basisklasse aller Module.

    key     - Kurzname fuer die Kommandozeile (baki.py <key> ...)
    title   - Anzeigename im Menue
    actions - Menuepunkte des Moduls (siehe Action)
    """

    key: str = ""
    title: str = ""
    actions: list = []

    @abstractmethod
    def run(self, argv: list | None = None) -> int:
        """Startet das Modul mit Argumenten wie auf der Kommandozeile.

        Rueckgabe: Exit-Code (0 = ok).
        """


def ask(prompt: str) -> str:
    """input() ohne Traceback bei Strg+C / geschlossenem stdin."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def pause():
    ask("\n Weiter mit Enter ...")
