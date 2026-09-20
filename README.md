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

Der Status-Sensor zeigt dabei `unreachable`, sobald der aktuelle Poll
fehlgeschlagen ist - so bleibt sichtbar, dass gerade keine Verbindung
besteht, statt weiterhin einen veralteten Status wie "Leerlauf" vorzugaukeln.
Verbrauchsmaterial-Sensoren behalten in diesem Fall einfach ihren letzten
bekannten Wert.

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
- Ein Status-Sensor pro Drucker (`idle` / `printing` / `stopped` / `unreachable`)
- Ein Sensor für den Zeitpunkt des letzten bekannten Starts des Druckers
  ("Letzter Start")

## Benachrichtigungen

Über das Zahnrad-Symbol am Integrations-Eintrag (Optionen) lässt sich je
Drucker konfigurieren, bei welchen Problemen benachrichtigt werden soll:

- Tinte/Toner leer oder wird knapp (der Schwellwert für "wird knapp" ist
  über ein Dropdown wählbar: 5/10/15/20/25/30 %, unabhängig vom oft sehr
  niedrig angesetzten Herstellerwert)
- Papier leer oder Papierstau
- Abdeckung offen
- Drucker gestoppt (Fehler) oder nicht erreichbar

Für jeden ausgewählten Grund gibt es optional:

- eine **Push-Benachrichtigung** an frei wählbare `notify`-Ziele (z. B.
  `notify.mobile_app_<gerät>`)
- eine **dauerhafte Benachrichtigung** in Home Assistant (Standard: an),
  die automatisch verschwindet, sobald das Problem behoben ist

Benachrichtigt wird nur beim *Auftreten* eines Problems, nicht bei jedem
Abfrageintervall erneut, solange es weiter besteht.

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

- Der frühere separate "Verbindungsstatus"-Binärsensor wurde entfernt - der
  Status-Sensor deckt das jetzt selbst über den Wert `unreachable` ab. Beim
  Update bleibt die alte Entity als `unavailable` in der Entitätenliste
  zurück und kann manuell gelöscht werden (Einstellungen → Geräte &
  Dienste → Entitäten).
- Wurde der Drucker seit dem letzten HA-Neustart noch nie erfolgreich
  ausgelesen, gibt es keinen wiederherstellbaren Wert – die Entity ist dann
  vorübergehend `unavailable`, bis der erste erfolgreiche Poll stattfindet.
- Dieses Projekt ist ein unabhängiger Fork/Neuentwicklung auf Basis der
  `pyipp`-Bibliothek und nicht mit der Home-Assistant-Core-Integration
  verknüpft; API-Änderungen an `pyipp` müssen manuell nachgezogen werden.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
