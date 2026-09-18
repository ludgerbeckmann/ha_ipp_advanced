# IPP Advanced

[![Validate](https://github.com/ludgerbeckmann/ha_ipp_advanced/actions/workflows/validate.yml/badge.svg)](https://github.com/ludgerbeckmann/ha_ipp_advanced/actions/workflows/validate.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/ludgerbeckmann/ha_ipp_advanced.svg)](https://github.com/ludgerbeckmann/ha_ipp_advanced/releases/)
[![GitHub license](https://img.shields.io/github/license/ludgerbeckmann/ha_ipp_advanced.svg)](https://github.com/ludgerbeckmann/ha_ipp_advanced/blob/main/LICENSE)

Custom Home Assistant Integration auf Basis der Core-`ipp`-Integration – mit
dem entscheidenden Unterschied, dass Sensorwerte (Tonerstand, Tintenstand,
Druckerstatus etc.) **erhalten bleiben**, wenn der Drucker ausgeschaltet oder
über das Netzwerk nicht erreichbar ist, statt in `unavailable` zu fallen.

## Warum diese Integration?

Die offizielle `ipp`-Integration wirft bei einem Verbindungsfehler
`UpdateFailed`, wodurch alle zugehörigen Entities `unavailable` werden. In
Dashboards äußert sich das als Fehler-Kacheln, sobald ein Drucker einfach nur
im Standby/ausgeschaltet ist – was bei Tintenstrahl- und Laserdruckern im
Heimnetz der Normalfall ist.

**IPP Advanced** löst das auf zwei Ebenen:

1. **Laufzeit-Cache:** Der `DataUpdateCoordinator` behält den zuletzt
   erfolgreich gelesenen Druckerzustand und gibt ihn bei einem
   Verbindungsfehler einfach weiter, statt einen Fehler zu werfen.
2. **Neustart-Persistenz:** Über `RestoreEntity` wird beim Neustart von Home
   Assistant der letzte bekannte Sensorwert aus der Recorder-Datenbank
   wiederhergestellt, bis der erste erfolgreiche Poll wieder frische Daten
   liefert.

Ein zusätzlicher Statuswert `offline_cached` macht transparent, wenn ein
angezeigter Wert nicht live, sondern zwischengespeichert ist.

## Installation

### Über HACS (empfohlen)

1. HACS → Integrationen → Menü (⋮) → *Benutzerdefinierte Repositories*
2. Repository-URL eintragen, Kategorie *Integration*
3. "IPP Advanced" installieren
4. Home Assistant neu starten

### Manuell

1. Diesen Ordner nach `config/custom_components/ipp_advanced/` kopieren
2. Home Assistant neu starten

## Einrichtung

**Einstellungen → Geräte & Dienste → Integration hinzufügen → „IPP Advanced"**
und Host/IP des Druckers eingeben. Für jeden Drucker separat wiederholen.

## Entities

- Ein Sensor pro Verbrauchsmaterial (z. B. `sensor.drucker_wohnzimmer_toner_schwarz`)
  mit Füllstand in %
- Ein Status-Sensor pro Drucker (`idle` / `processing` / `stopped` /
  `offline_cached`)

## Aktionen

- **IPP-Attribute abfragen** (`ipp_advanced.attribute_dump`): Fragt beim
  ausgewählten Drucker direkt alle über IPP gemeldeten Attribute ab - auch
  solche, die diese Integration sonst nicht in eigenen Sensoren abbildet -
  und gibt sie als Ergebnis zurück. Aufrufbar über
  **Entwicklerwerkzeuge → Aktionen**, Ziel: das gewünschte Drucker-Gerät.
  Nutzt die ohnehin schon laufende Verbindung der Integration, es ist also
  kein zusätzliches Gerät, kein SSH und keine separate Skript-Installation
  nötig.

## Bekannte Einschränkungen

- Wurde der Drucker seit dem letzten HA-Neustart noch nie erfolgreich
  ausgelesen, gibt es keinen wiederherstellbaren Wert – die Entity ist dann
  vorübergehend `unavailable`, bis der erste erfolgreiche Poll stattfindet.
- Dieses Projekt ist ein unabhängiger Fork/Neuentwicklung auf Basis der
  `pyipp`-Bibliothek und nicht mit der Home-Assistant-Core-Integration
  verknüpft; API-Änderungen an `pyipp` müssen manuell nachgezogen werden.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
