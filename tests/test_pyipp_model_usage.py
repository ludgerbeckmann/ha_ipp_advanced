"""Statischer Abgleich: greifen wir nur auf Felder zu, die pyipp's
Datenmodelle (Printer/Info/State/Marker) tatsächlich besitzen?

Direkter Hintergrund: `device_info` griff früher auf
`printer.info.marker_types` zu - ein Feld, das in pyipp nie existiert hat
(das richtige Feld heißt `manufacturer`). Das ließ Home Assistant beim
Registrieren jeder Entity mit einem AttributeError abstürzen, sodass der
Eintrag am Ende ganz ohne Entities dastand (siehe Git-Historie). Ein
einfacher Import-/Syntax-Check (`py_compile`) findet solche Tippfehler
nicht, weil sie erst zur Laufzeit beim tatsächlichen Attributzugriff
auffallen.

Dieser Test durchsucht den Quellcode nach `printer.info.<x>`,
`printer.<x>` und `marker.<x>`-Zugriffen und prüft jeden gefundenen
Namen gegen die echten Dataclass-Felder der installierten pyipp-Version.
Bewusst ein einfacher Regex-Abgleich statt einer vollständigen
AST-Analyse - reicht für den hier relevanten Fehlerfall und bleibt leicht
nachvollziehbar.
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import re

import pytest
from pyipp.models import Info, Marker, Printer, State

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "ipp_advanced"

# Attribute/Methoden, die zwar über "printer."/"marker." aufgerufen werden,
# aber keine Dataclass-Felder sind (z.B. Methoden).
EXTRA_ALLOWED = {
    Printer: {"as_dict", "update_from_dict", "from_dict", "merge_marker_data", "merge_uri_data"},
    Info: {"from_dict"},
}


def _field_names(model: type) -> set[str]:
    return {f.name for f in fields(model)} | EXTRA_ALLOWED.get(model, set())


def _find_attribute_accesses(pattern: str) -> set[str]:
    found: set[str] = set()
    for path in COMPONENT_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        found.update(re.findall(pattern, text))
    return found


def test_printer_info_attributes_exist():
    used = _find_attribute_accesses(r"\bprinter\.info\.([a-zA-Z_][a-zA-Z0-9_]*)")
    allowed = _field_names(Info)
    unknown = used - allowed
    assert not unknown, (
        f"printer.info.<x> wird mit unbekannten Feldern verwendet: {unknown} "
        f"- gueltige Info-Felder: {sorted(allowed)}"
    )


def test_printer_state_attributes_exist():
    used = _find_attribute_accesses(r"\bprinter\.state\.([a-zA-Z_][a-zA-Z0-9_]*)")
    allowed = _field_names(State)
    unknown = used - allowed
    assert not unknown, (
        f"printer.state.<x> wird mit unbekannten Feldern verwendet: {unknown} "
        f"- gueltige State-Felder: {sorted(allowed)}"
    )


def test_printer_top_level_attributes_exist():
    # Schliesst "info"/"state" bewusst mit ein - das sind ebenfalls echte
    # Printer-Felder, kollidiert nicht mit den beiden Tests oben.
    used = _find_attribute_accesses(r"\bprinter\.([a-zA-Z_][a-zA-Z0-9_]*)")
    allowed = _field_names(Printer)
    unknown = used - allowed
    assert not unknown, (
        f"printer.<x> wird mit unbekannten Feldern verwendet: {unknown} "
        f"- gueltige Printer-Felder: {sorted(allowed)}"
    )


def test_marker_attributes_exist():
    used = _find_attribute_accesses(r"\bmarker\.([a-zA-Z_][a-zA-Z0-9_]*)")
    allowed = _field_names(Marker)
    unknown = used - allowed
    assert not unknown, (
        f"marker.<x> wird mit unbekannten Feldern verwendet: {unknown} "
        f"- gueltige Marker-Felder: {sorted(allowed)}"
    )


@pytest.mark.parametrize(
    "used_dir",
    [pytest.param(COMPONENT_DIR, id="custom_components/ipp_advanced")],
)
def test_component_dir_exists(used_dir: Path):
    # Schuetzt die obigen Tests davor, durch einen falschen Pfad
    # stillschweigend nichts zu pruefen.
    assert used_dir.is_dir()
    assert (used_dir / "sensor.py").is_file()
