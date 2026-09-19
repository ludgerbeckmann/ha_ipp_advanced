"""Tests fuer die Benachrichtigungsfunktion (notifications.py).

Deckt die Kernlogik ab: nur aktivierte Gruende werden ausgewertet, es wird
nur beim *Wechsel* zu "Problem liegt vor" benachrichtigt (nicht bei jedem
Poll erneut), und beim Beheben wird die dauerhafte Benachrichtigung wieder
geschlossen.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pyipp.models import Info, Marker, Printer, State

from custom_components.ipp_advanced.const import (
    CONF_NOTIFY_PERSISTENT,
    CONF_NOTIFY_REASONS,
    CONF_NOTIFY_TARGETS,
    NOTIFY_REASON_COVER_OPEN,
    NOTIFY_REASON_MARKER_EMPTY,
    NOTIFY_REASON_MARKER_LOW,
    NOTIFY_REASON_MEDIA_EMPTY,
    NOTIFY_REASON_MEDIA_JAM,
    NOTIFY_REASON_PRINTER_STOPPED,
    NOTIFY_REASON_PRINTER_UNREACHABLE,
)
from custom_components.ipp_advanced.coordinator import IPPAdvancedData
from custom_components.ipp_advanced.notifications import IPPAdvancedNotificationManager


def _make_printer(
    state: str = "idle",
    reasons=None,
    message=None,
    marker_level: int = 50,
    marker_low_level: int = 10,
) -> Printer:
    return Printer(
        info=Info(name="Test Printer", printer_name="test", printer_uri_supported=[], uptime=100),
        markers=[
            Marker(
                marker_id=1,
                marker_type="ink",
                name="Schwarz",
                color="#000000",
                level=marker_level,
                low_level=marker_low_level,
                high_level=100,
            )
        ],
        state=State(printer_state=state, reasons=reasons, message=message),
        uris=[],
        booted_at=None,
    )


def _make_entry(options: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(entry_id="entry123", title="Test Printer", options=options or {})


def _make_coordinator(printer: Printer | None, last_update_success: bool = True) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = IPPAdvancedData(
        printer=printer, available=True, last_update_success=last_update_success
    )
    return coordinator


def _make_manager(entry_options: dict, printer: Printer, last_update_success: bool = True):
    hass = MagicMock()
    entry = _make_entry(entry_options)
    coordinator = _make_coordinator(printer, last_update_success)
    return IPPAdvancedNotificationManager(hass, entry, coordinator), hass


def test_no_reasons_enabled_means_no_issues():
    printer = _make_printer(marker_level=0)
    manager, _hass = _make_manager({}, printer)

    assert manager._collect_active_issues() == {}


def test_marker_empty_detected_when_enabled():
    printer = _make_printer(marker_level=0)
    manager, _hass = _make_manager({CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY]}, printer)

    issues = manager._collect_active_issues()
    assert f"{NOTIFY_REASON_MARKER_EMPTY}:1" in issues


def test_marker_low_but_not_empty():
    printer = _make_printer(marker_level=5, marker_low_level=10)
    manager, _hass = _make_manager(
        {CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY, NOTIFY_REASON_MARKER_LOW]}, printer
    )

    issues = manager._collect_active_issues()
    assert f"{NOTIFY_REASON_MARKER_LOW}:1" in issues
    assert f"{NOTIFY_REASON_MARKER_EMPTY}:1" not in issues


def test_marker_level_unknown_is_ignored():
    printer = _make_printer(marker_level=-2)
    manager, _hass = _make_manager(
        {CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY, NOTIFY_REASON_MARKER_LOW]}, printer
    )

    assert manager._collect_active_issues() == {}


def test_media_empty_and_media_jam_from_state_reasons():
    printer = _make_printer(reasons="media-empty-warning")
    manager, _hass = _make_manager(
        {CONF_NOTIFY_REASONS: [NOTIFY_REASON_MEDIA_EMPTY, NOTIFY_REASON_MEDIA_JAM]}, printer
    )

    issues = manager._collect_active_issues()
    assert NOTIFY_REASON_MEDIA_EMPTY in issues
    assert NOTIFY_REASON_MEDIA_JAM not in issues


def test_state_reasons_as_list_is_supported():
    # Manche Drucker melden mehrere Gruende gleichzeitig - pyipp/der Parser
    # liefert das dann als Liste statt als einzelnen String.
    printer = _make_printer(reasons=["cover-open-warning", "media-jam-error"])
    manager, _hass = _make_manager(
        {CONF_NOTIFY_REASONS: [NOTIFY_REASON_COVER_OPEN, NOTIFY_REASON_MEDIA_JAM]}, printer
    )

    issues = manager._collect_active_issues()
    assert NOTIFY_REASON_COVER_OPEN in issues
    assert NOTIFY_REASON_MEDIA_JAM in issues


def test_printer_stopped_and_unreachable():
    printer = _make_printer(state="stopped", message="Kein Papier")
    manager, _hass = _make_manager(
        {CONF_NOTIFY_REASONS: [NOTIFY_REASON_PRINTER_STOPPED, NOTIFY_REASON_PRINTER_UNREACHABLE]},
        printer,
        last_update_success=False,
    )

    issues = manager._collect_active_issues()
    assert NOTIFY_REASON_PRINTER_STOPPED in issues
    assert NOTIFY_REASON_PRINTER_UNREACHABLE in issues


@patch("custom_components.ipp_advanced.notifications.async_dismiss")
@patch("custom_components.ipp_advanced.notifications.async_create")
def test_handle_update_notifies_only_on_new_issue(mock_create, mock_dismiss):
    printer = _make_printer(marker_level=0)
    manager, hass = _make_manager(
        {CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY], CONF_NOTIFY_TARGETS: []}, printer
    )

    manager.async_handle_update()
    assert mock_create.call_count == 1

    # Problem besteht unveraendert weiter - keine zweite Benachrichtigung.
    manager.async_handle_update()
    assert mock_create.call_count == 1
    mock_dismiss.assert_not_called()


@patch("custom_components.ipp_advanced.notifications.async_dismiss")
@patch("custom_components.ipp_advanced.notifications.async_create")
def test_handle_update_resolves_when_issue_clears(mock_create, mock_dismiss):
    printer = _make_printer(marker_level=0)
    manager, hass = _make_manager({CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY]}, printer)
    manager.async_handle_update()
    assert mock_create.call_count == 1

    # Toner wurde gewechselt - Problem ist behoben.
    manager.coordinator.data = IPPAdvancedData(
        printer=_make_printer(marker_level=80), available=True, last_update_success=True
    )
    manager.async_handle_update()

    mock_dismiss.assert_called_once()


@patch("custom_components.ipp_advanced.notifications.async_create")
def test_handle_update_sends_push_to_configured_targets(mock_create):
    printer = _make_printer(marker_level=0)
    manager, hass = _make_manager(
        {
            CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY],
            CONF_NOTIFY_TARGETS: ["notify.mobile_app_phone"],
        },
        printer,
    )

    manager.async_handle_update()

    hass.async_create_task.assert_called_once()


@patch("custom_components.ipp_advanced.notifications.async_create")
def test_persistent_notification_disabled_via_option(mock_create):
    printer = _make_printer(marker_level=0)
    manager, _hass = _make_manager(
        {CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY], CONF_NOTIFY_PERSISTENT: False}, printer
    )

    manager.async_handle_update()

    mock_create.assert_not_called()


@patch("custom_components.ipp_advanced.notifications.async_dismiss")
def test_unload_resolves_remaining_issues(mock_dismiss):
    printer = _make_printer(marker_level=0)
    manager, _hass = _make_manager({CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY]}, printer)
    with patch("custom_components.ipp_advanced.notifications.async_create"):
        manager.async_handle_update()

    manager.async_unload()

    mock_dismiss.assert_called_once()
