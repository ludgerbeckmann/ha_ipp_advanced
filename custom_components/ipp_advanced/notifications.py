"""Benachrichtigungen bei bestimmten Druckerzuständen (leere Tinte,
Papierstau, ...) - Push über frei wählbare notify-Ziele und/oder eine
dauerhafte Benachrichtigung in Home Assistant, konfigurierbar je Drucker
über den Options Flow (siehe config_flow.py).

Funktionsweise: Nach jedem Coordinator-Update wird neu ermittelt, welche
der (in den Optionen aktivierten) Probleme gerade vorliegen. Nur beim
*Wechsel* von "nicht vorhanden" zu "vorhanden" wird tatsächlich
benachrichtigt (sonst gäbe es bei jedem Poll erneut eine Meldung, solange
z.B. der Toner leer bleibt). Beim Wechsel zurück auf "nicht vorhanden"
wird die zugehörige dauerhafte Benachrichtigung automatisch geschlossen.
"""
from __future__ import annotations

from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_NOTIFY_PERSISTENT,
    CONF_NOTIFY_REASONS,
    CONF_NOTIFY_TARGETS,
    DEFAULT_NOTIFY_PERSISTENT,
    DOMAIN,
    NOTIFY_REASON_COVER_OPEN,
    NOTIFY_REASON_MARKER_EMPTY,
    NOTIFY_REASON_MARKER_LOW,
    NOTIFY_REASON_MEDIA_EMPTY,
    NOTIFY_REASON_MEDIA_JAM,
    NOTIFY_REASON_PRINTER_STOPPED,
    NOTIFY_REASON_PRINTER_UNREACHABLE,
)
from .coordinator import IPPAdvancedDataUpdateCoordinator

NOTIFICATION_TITLE = "IPP Advanced"


def _reason_active(reasons: str | list[str] | None, keyword: str) -> bool:
    """True, wenn IPPs printer-state-reasons das Schlüsselwort enthält.

    pyipp liefert reasons als einzelnen String oder (wenn der Drucker
    mehrere Gründe gleichzeitig meldet) als Liste - und hängt je nach
    Schweregrad z.B. "-warning"/"-error" an ("media-empty-warning"),
    daher ein einfacher Teilstring-Vergleich statt Gleichheit.
    """
    if not reasons:
        return False
    values = reasons if isinstance(reasons, list) else [reasons]
    return any(keyword in value for value in values)


class IPPAdvancedNotificationManager:
    """Erkennt neu aufgetretene/behobene Probleme und verschickt dafür
    Benachrichtigungen gemäß der in den Options Flow ausgewählten Ziele
    und Gründe."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: IPPAdvancedDataUpdateCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._active: dict[str, str] = {}

    def _printer_name(self) -> str:
        printer = self.coordinator.data.printer if self.coordinator.data else None
        return (printer.info.name if printer else None) or self.entry.title

    def _collect_active_issues(self) -> dict[str, str]:
        """Aktuell vorliegende, aktivierte Probleme als {issue_key: Meldungstext}."""
        data = self.coordinator.data
        if data is None or data.printer is None:
            return {}
        printer = data.printer
        enabled = set(self.entry.options.get(CONF_NOTIFY_REASONS, []))
        if not enabled:
            return {}
        name = self._printer_name()
        issues: dict[str, str] = {}

        if NOTIFY_REASON_PRINTER_UNREACHABLE in enabled and not data.last_update_success:
            issues[NOTIFY_REASON_PRINTER_UNREACHABLE] = f"{name} ist nicht erreichbar."

        if NOTIFY_REASON_PRINTER_STOPPED in enabled and printer.state.printer_state == "stopped":
            reason = printer.state.message or printer.state.reasons or "unbekannter Grund"
            issues[NOTIFY_REASON_PRINTER_STOPPED] = f"{name} hat gestoppt: {reason}."

        if NOTIFY_REASON_MEDIA_EMPTY in enabled and _reason_active(
            printer.state.reasons, "media-empty"
        ):
            issues[NOTIFY_REASON_MEDIA_EMPTY] = f"{name}: Papier ist leer."

        if NOTIFY_REASON_MEDIA_JAM in enabled and _reason_active(
            printer.state.reasons, "media-jam"
        ):
            issues[NOTIFY_REASON_MEDIA_JAM] = f"{name}: Papierstau."

        if NOTIFY_REASON_COVER_OPEN in enabled and (
            _reason_active(printer.state.reasons, "cover-open")
            or _reason_active(printer.state.reasons, "door-open")
        ):
            issues[NOTIFY_REASON_COVER_OPEN] = f"{name}: Abdeckung ist offen."

        for marker in printer.markers:
            if marker.level < 0:
                continue  # Füllstand unbekannt - siehe sensor.py.
            if NOTIFY_REASON_MARKER_EMPTY in enabled and marker.level == 0:
                issues[f"{NOTIFY_REASON_MARKER_EMPTY}:{marker.marker_id}"] = (
                    f"{name}: {marker.name} ist leer."
                )
            elif NOTIFY_REASON_MARKER_LOW in enabled and marker.level <= marker.low_level:
                issues[f"{NOTIFY_REASON_MARKER_LOW}:{marker.marker_id}"] = (
                    f"{name}: {marker.name} wird knapp ({marker.level}%)."
                )

        return issues

    @callback
    def async_handle_update(self) -> None:
        """Nach jedem Coordinator-Update aufrufen."""
        new_issues = self._collect_active_issues()
        old_keys = set(self._active)
        new_keys = set(new_issues)

        for key in new_keys - old_keys:
            self._async_notify(key, new_issues[key])
        for key in old_keys - new_keys:
            self._async_resolve(key)

        self._active = new_issues

    @callback
    def async_unload(self) -> None:
        """Beim Entladen des Eintrags alle noch offenen dauerhaften
        Benachrichtigungen dieses Druckers schließen."""
        for key in list(self._active):
            self._async_resolve(key)

    def _persistent_id(self, key: str) -> str:
        return f"{DOMAIN}_{self.entry.entry_id}_{key}"

    def _async_notify(self, key: str, message: str) -> None:
        if self.entry.options.get(CONF_NOTIFY_PERSISTENT, DEFAULT_NOTIFY_PERSISTENT):
            async_create(self.hass, message, title=NOTIFICATION_TITLE, notification_id=self._persistent_id(key))

        for target in self.entry.options.get(CONF_NOTIFY_TARGETS, []):
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {"entity_id": target, "message": message, "title": NOTIFICATION_TITLE},
                    blocking=False,
                ),
                name=f"ipp_advanced_notify_{key}",
            )

    def _async_resolve(self, key: str) -> None:
        async_dismiss(self.hass, self._persistent_id(key))
