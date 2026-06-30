from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pywinauto import Application, Desktop, mouse, timings
from pywinauto.keyboard import send_keys

from .config import ReportDates, render_template

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportedReport:
    report_id: str
    path: Path


class TiniAutomation:
    def __init__(self, config: dict[str, Any], dry_run: bool = False) -> None:
        self.config = config
        self.app_config = config.get("app", {})
        self.backend = self.app_config.get("backend", "win32")
        self.dry_run = dry_run
        self.action_delay = float(self.app_config.get("action_delay_seconds", 0.4))
        self.app: Application | None = None
        self.main_window = None

    def connect(self) -> None:
        title_re = self.app_config.get("title_re", ".*Sistema Integrado TINI.*")
        timeout = int(self.app_config.get("connect_timeout_seconds", 30))
        LOGGER.info("Connecting to TINI window: %s", title_re)
        timings.wait_until_passes(
            timeout,
            1,
            self._connect_once,
            title_re,
        )

    def _connect_once(self, title_re: str) -> None:
        self.app = Application(backend=self.backend).connect(title_re=title_re)
        self.main_window = self.app.window(title_re=title_re)
        self.main_window.set_focus()

    def run_report(self, report: dict[str, Any], dates: ReportDates) -> ExportedReport:
        report_id = report["id"]
        LOGGER.info("Running report %s", report_id)
        if report.get("skip_open", False):
            LOGGER.info("Skipping report open step for %s; using existing dialog", report_id)
        else:
            self._open_report(report)
        dialog = self._wait_for_dialog(report.get("window_title_re", ".*"))
        self._fill_report_dialog(dialog, report, dates)

        if self.dry_run:
            LOGGER.info("Dry-run enabled; not pressing process for %s", report_id)
            return ExportedReport(report_id, Path(""))

        self._click_button(dialog, report.get("process_button_text", "Procesar"))
        viewer = self._wait_for_report_viewer(report)
        return self._export_from_viewer(viewer, report, dates)

    def _open_report(self, report: dict[str, Any]) -> None:
        path = report.get("module_tree_path") or []
        if not path:
            raise ValueError(f"Report {report['id']} has no module_tree_path")

        if self.main_window is None:
            raise RuntimeError("Not connected")

        self.main_window.set_focus()
        tree = self._find_first_control(self.main_window, class_name_re=".*Tree.*")
        if tree is None:
            LOGGER.warning("Tree control not found; using keyboard fallback for %s", report["id"])
            self._keyboard_open_fallback(path)
            return

        for node_text in path:
            self._select_tree_item(tree, node_text)
            time.sleep(self.action_delay)
        send_keys("{ENTER}")
        time.sleep(self.action_delay)

    def _keyboard_open_fallback(self, path: list[str]) -> None:
        LOGGER.info("Keyboard fallback selected; path=%s", " > ".join(path))
        raise RuntimeError(
            "Tree control was not found. Run `python -m tini_reports.inspect` and configure selectors."
        )

    def _select_tree_item(self, tree: Any, text: str) -> None:
        try:
            item = tree.get_item(text)
            item.ensure_visible()
            item.click_input()
            return
        except Exception:
            pass

        matches = [child for child in tree.descendants() if text.lower() in child.window_text().lower()]
        if not matches:
            raise RuntimeError(f"Tree item not found: {text}")
        matches[0].click_input()

    def _wait_for_dialog(self, title_re: str) -> Any:
        desktop = Desktop(backend=self.backend)
        LOGGER.info("Waiting for report parameter dialog: %s", title_re)
        return timings.wait_until_passes(
            30,
            1,
            lambda: desktop.window(title_re=title_re).wait("visible enabled", timeout=2),
        )

    def _fill_report_dialog(self, dialog: Any, report: dict[str, Any], dates: ReportDates) -> None:
        dialog.set_focus()
        for field_name, field_config in (report.get("fields") or {}).items():
            value = render_template(field_config.get("value"), dates)
            LOGGER.info("Setting field %s=%s", field_name, value)
            self._set_field(dialog, field_config, field_name, str(value))

        for label, value in (report.get("dropdowns") or {}).items():
            self._select_dropdown(dialog, label, render_template(value, dates))
        for dropdown_config in report.get("dropdown_controls") or []:
            self._select_dropdown_control(dialog, dropdown_config, render_template(dropdown_config.get("value"), dates))

        options = report.get("options") or {}
        for radio_text in options.get("radio_texts") or []:
            self._select_radio(dialog, radio_text)
        for radio_config in options.get("radio_controls") or []:
            self._select_radio_control(dialog, radio_config)
        for checkbox_text, checked in (options.get("checkboxes") or {}).items():
            self._set_checkbox(dialog, checkbox_text, bool(checked))

    def _set_field(self, dialog: Any, field_config: dict[str, Any], field_name: str, value: str) -> None:
        control_id = field_config.get("control_id")
        if control_id is not None:
            target = self._find_by_control_id(dialog, int(control_id), class_name_re="Edit")
            if target is None:
                raise RuntimeError(f"Edit control_id not found for {field_name}: {control_id}")
        else:
            target = self._find_field_near_label(dialog, field_config.get("label", field_name))
        self._replace_text(target, value)

    def _find_field_near_label(self, dialog: Any, label: str) -> Any:
        edits = dialog.descendants(class_name_re="Edit")
        labels = [c for c in dialog.descendants() if label.lower() in c.window_text().lower()]
        if not edits:
            raise RuntimeError(f"No Edit controls found while setting {label}")
        if not labels:
            LOGGER.warning("Label %s not found; using next empty edit", label)
            return self._first_empty_edit(edits)
        else:
            label_rect = labels[0].rectangle()
            candidates = sorted(
                edits,
                key=lambda edit: abs(edit.rectangle().top - label_rect.top) + max(0, label_rect.left - edit.rectangle().left),
            )
            return candidates[0]

    def _replace_text(self, target: Any, value: str) -> None:
        target.set_focus()
        try:
            target.set_edit_text(value)
        except Exception:
            target.select()
            if value:
                target.type_keys(value, with_spaces=True, set_foreground=False)
            else:
                send_keys("{DELETE}")
        time.sleep(self.action_delay)

    def _first_empty_edit(self, edits: list[Any]) -> Any:
        for edit in edits:
            if not edit.window_text().strip():
                return edit
        return edits[0]

    def _select_dropdown(self, dialog: Any, label: str, value: str) -> None:
        combos = dialog.descendants(class_name_re="ComboBox")
        labels = [c for c in dialog.descendants() if label.lower() in c.window_text().lower()]
        if not combos:
            LOGGER.warning("No ComboBox controls found for %s", label)
            return
        target = combos[0] if not labels else min(
            combos,
            key=lambda combo: abs(combo.rectangle().top - labels[0].rectangle().top),
        )
        try:
            target.select(value)
        except Exception:
            target.set_focus()
            send_keys("^a")
            send_keys(value)
            send_keys("{ENTER}")
        time.sleep(self.action_delay)

    def _select_dropdown_control(self, dialog: Any, dropdown_config: dict[str, Any], value: str) -> None:
        control_id = dropdown_config.get("control_id")
        if control_id is None:
            raise ValueError("dropdown_controls entries require control_id")
        target = self._find_by_control_id(dialog, int(control_id), class_name_re="ComboBox")
        if target is None:
            raise RuntimeError(f"ComboBox control_id not found: {control_id}")
        try:
            target.select(value)
        except Exception:
            target.set_focus()
            send_keys("^a")
            send_keys(value)
            send_keys("{ENTER}")
        time.sleep(self.action_delay)

    def _select_radio(self, dialog: Any, text: str) -> None:
        radio = self._find_by_text(dialog, text)
        if radio is None:
            LOGGER.warning("Radio not found: %s", text)
            return
        self._click_checkable(radio)

    def _select_radio_control(self, dialog: Any, radio_config: dict[str, Any]) -> None:
        control_id = radio_config.get("control_id")
        if control_id is None:
            raise ValueError("radio_controls entries require control_id")
        radio = self._find_by_control_id(dialog, int(control_id), class_name_re="Button")
        if radio is None:
            raise RuntimeError(f"Radio/Button control_id not found: {control_id}")
        self._click_checkable(radio)

    def _click_checkable(self, control: Any) -> None:
        try:
            if hasattr(control, "get_check_state") and control.get_check_state() != 1:
                control.click_input()
            else:
                control.click_input()
        except Exception:
            control.click()

    def _set_checkbox(self, dialog: Any, text: str, checked: bool) -> None:
        checkbox = self._find_by_text(dialog, text)
        if checkbox is None:
            LOGGER.warning("Checkbox not found: %s", text)
            return
        current = checkbox.get_check_state() == 1 if hasattr(checkbox, "get_check_state") else False
        if current != checked:
            checkbox.click_input()

    def _click_button(self, window: Any, text: str) -> None:
        button = self._find_by_text(window, text)
        if button is None:
            raise RuntimeError(f"Button not found: {text}")
        LOGGER.info("Clicking button: %s", text)
        button.click_input()
        time.sleep(self.action_delay)

    def _wait_for_report_viewer(self, report: dict[str, Any]) -> Any:
        title_re = report.get("viewer_title_re") or self.config.get("export", {}).get("report_viewer_title_re", ".*")
        desktop = Desktop(backend=self.backend)
        LOGGER.info("Waiting for report viewer: %s", title_re)
        return timings.wait_until_passes(
            90,
            2,
            lambda: desktop.window(title_re=title_re).wait("visible enabled", timeout=3),
        )

    def _export_from_viewer(self, viewer: Any, report: dict[str, Any], dates: ReportDates) -> ExportedReport:
        output_dir = Path(self.config.get("paths", {}).get("output_dir", "artifacts/exports")).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_base = render_template(report.get("output_name", report["id"]), dates)
        expected = output_dir / f"{output_base}.xlsx"

        export_text = self.config.get("export", {}).get("preferred_button_text", "Excel")
        export_button = self._find_by_text(viewer, export_text)

        LOGGER.info("Exporting report %s to %s", report["id"], expected)
        before = set(output_dir.glob("*"))
        if export_button is not None:
            export_button.click_input()
        else:
            self._click_export_offset(viewer, report, export_text)
        self._handle_save_dialog(expected)
        exported = self._wait_for_new_file(output_dir, before, expected)
        return ExportedReport(report["id"], exported)

    def _click_export_offset(self, viewer: Any, report: dict[str, Any], export_text: str) -> None:
        offset = report.get("export_button_offset") or self.config.get("export", {}).get("button_offset")
        if not offset:
            raise RuntimeError(f"Export button not found in viewer: {export_text}")
        rect = viewer.rectangle()
        x = rect.left + int(offset["x"])
        y = rect.top + int(offset["y"])
        LOGGER.info("Clicking export by offset x=%s y=%s absolute=(%s,%s)", offset["x"], offset["y"], x, y)
        mouse.click(button="left", coords=(x, y))
        time.sleep(self.action_delay)

    def _handle_save_dialog(self, expected_path: Path) -> None:
        desktop = Desktop(backend=self.backend)
        try:
            dialog = timings.wait_until_passes(
                15,
                1,
                lambda: desktop.window(title_re=".*(Guardar|Save|Exportar|Excel).*").wait("visible enabled", timeout=2),
            )
        except Exception:
            LOGGER.info("No save dialog appeared; waiting for exported file")
            return

        edit = self._find_save_filename_edit(dialog)
        if edit is not None:
            edit.set_focus()
            edit.select()
            edit.type_keys(str(expected_path), with_spaces=True, set_foreground=False)
        save_button = self._find_by_text(dialog, "Guardar") or self._find_by_text(dialog, "Save")
        if save_button is not None:
            save_button.click_input()
        else:
            send_keys("{ENTER}")

    def _wait_for_new_file(self, output_dir: Path, before: set[Path], expected: Path) -> Path:
        timeout = int(self.config.get("export", {}).get("save_timeout_seconds", 90))
        deadline = time.time() + timeout
        while time.time() < deadline:
            if expected.exists() and expected.stat().st_size > 0:
                return expected
            created = [path for path in output_dir.glob("*") if path not in before and path.is_file()]
            if created:
                newest = max(created, key=lambda path: path.stat().st_mtime)
                if newest.stat().st_size > 0:
                    return newest
            time.sleep(1)
        raise TimeoutError(f"No exported file appeared in {output_dir}")

    def _find_by_text(self, root: Any, text: str) -> Any | None:
        needle = text.lower()
        for control in root.descendants():
            try:
                if needle in control.window_text().lower():
                    return control
            except Exception:
                continue
        return None

    def _find_first_control(self, root: Any, class_name_re: str) -> Any | None:
        matches = root.descendants(class_name_re=class_name_re)
        return matches[0] if matches else None

    def _find_save_filename_edit(self, dialog: Any) -> Any | None:
        edits = dialog.descendants(class_name_re="Edit")
        if not edits:
            return None
        candidates = []
        for edit in edits:
            try:
                rect = edit.rectangle()
                if rect.width() >= 100:
                    candidates.append(edit)
            except Exception:
                continue
        return max(candidates or edits, key=lambda edit: edit.rectangle().top)

    def _find_by_control_id(self, root: Any, control_id: int, class_name_re: str | None = None) -> Any | None:
        kwargs = {"class_name_re": class_name_re} if class_name_re else {}
        for control in root.descendants(**kwargs):
            try:
                if hasattr(control, "control_id") and control.control_id() == control_id:
                    return control
            except Exception:
                continue
        return None
