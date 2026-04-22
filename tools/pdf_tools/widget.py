from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSignalBlocker, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.file_drop_card import FileDropCard
from shared.tool_base import ToolContext
from tools.pdf_tools.models import (
    PDF_ACTION_MERGE,
    PDF_ACTION_SPLIT,
    ORDER_MODE_PAGE,
    ORDER_MODE_PDF,
    PdfMergeItem,
    PdfMergeState,
    PdfSplitState,
    SPLIT_MODE_CUSTOM,
    SPLIT_MODE_EVERY_PAGE,
)
from tools.pdf_tools.service import PdfMergeError, PdfMergeService


@dataclass(frozen=True)
class SplitDropSelection:
    source_pdf_path: Path | None
    output_dir_path: Path | None
    skipped_items: list[str]


def classify_split_drop_paths(paths: list[Path]) -> SplitDropSelection:
    source_pdf_path: Path | None = None
    output_dir_path: Path | None = None
    skipped_items: list[str] = []

    for raw_path in paths:
        resolved_path = raw_path.expanduser().resolve()
        display_name = resolved_path.name or str(resolved_path)

        if not resolved_path.exists():
            skipped_items.append(f"{display_name}: missing item")
            continue
        if resolved_path.is_dir():
            if output_dir_path is None:
                output_dir_path = resolved_path
            else:
                skipped_items.append(f"{display_name}: extra folder ignored")
            continue
        if resolved_path.is_file():
            if resolved_path.suffix.lower() != ".pdf":
                skipped_items.append(f"{display_name}: not a PDF")
                continue
            if source_pdf_path is None:
                source_pdf_path = resolved_path
            else:
                skipped_items.append(f"{display_name}: extra PDF ignored")
            continue

        skipped_items.append(f"{display_name}: unsupported item")

    return SplitDropSelection(
        source_pdf_path=source_pdf_path,
        output_dir_path=output_dir_path,
        skipped_items=skipped_items,
    )


class PdfToolsWidget(QWidget):
    def __init__(self, context: ToolContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.service = PdfMergeService(context)
        self.merge_state = PdfMergeState()
        self.split_state = PdfSplitState()
        self.active_action = PDF_ACTION_MERGE

        self._build_ui()
        self._refresh_ui()

    def _build_ui(self) -> None:
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header_panel = QFrame()
        header_panel.setObjectName("workspacePanel")
        header_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        header_layout = QVBoxLayout(header_panel)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(10)

        title = QLabel("PDF workspace")
        title.setObjectName("workspaceTitle")

        subtitle = QLabel(
            "Merge and Split are live now. Convert stays visible as the next action."
        )
        subtitle.setObjectName("panelBody")
        subtitle.setWordWrap(True)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.action_buttons: dict[str, QPushButton] = {}
        for action_key, label, enabled in (
            (PDF_ACTION_MERGE, "Merge", True),
            (PDF_ACTION_SPLIT, "Split", True),
            ("convert", "Convert", False),
        ):
            button = QPushButton(label)
            button.setObjectName("modeTab")
            button.setCheckable(True)
            button.setEnabled(enabled)
            if action_key in (PDF_ACTION_MERGE, PDF_ACTION_SPLIT):
                button.clicked.connect(
                    lambda checked=False, action=action_key: self._set_active_action(action)
                )
                self.action_buttons[action_key] = button
            action_row.addWidget(button)
        action_row.addStretch(1)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addLayout(action_row)
        layout.addWidget(header_panel)

        self.action_stack = QStackedWidget()
        self.action_stack.addWidget(self._build_merge_workspace())
        self.action_stack.addWidget(self._build_split_workspace())
        layout.addWidget(self.action_stack, 1)

    def _build_merge_workspace(self) -> QWidget:
        page = QWidget()
        body = QHBoxLayout(page)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        left_panel = QFrame()
        left_panel.setObjectName("workspacePanel")
        left_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        left_title = QLabel("Merge queue")
        left_title.setObjectName("panelTitle")

        left_subtitle = QLabel(
            "Add PDFs, reorder them, remove any item, then save merged output."
        )
        left_subtitle.setObjectName("panelBody")
        left_subtitle.setWordWrap(True)

        self.merge_drop_card = FileDropCard(
            accepted_type_text="PDF files",
            multi_file=True,
        )
        self.merge_drop_card.clicked.connect(self._choose_pdf_files)
        self.merge_drop_card.paths_dropped.connect(self._add_pdf_paths)
        self.merge_drop_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        file_button_row = QHBoxLayout()
        file_button_row.setSpacing(8)

        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.setObjectName("secondaryButton")
        self.remove_button.clicked.connect(self._remove_selected_item)

        file_button_row.addWidget(self.remove_button)
        file_button_row.addStretch(1)

        self.pdf_list = QListWidget()
        self.pdf_list.setObjectName("pdfList")
        self.pdf_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pdf_list.currentRowChanged.connect(self._refresh_reorder_buttons)

        reorder_row = QHBoxLayout()
        reorder_row.setSpacing(8)

        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.setObjectName("secondaryButton")
        self.move_up_button.clicked.connect(lambda: self._move_selected_item(-1))

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.setObjectName("secondaryButton")
        self.move_down_button.clicked.connect(lambda: self._move_selected_item(1))

        reorder_row.addWidget(self.move_up_button)
        reorder_row.addWidget(self.move_down_button)
        reorder_row.addStretch(1)

        self.queue_summary_label = QLabel("No PDFs selected.")
        self.queue_summary_label.setObjectName("mutedLabel")
        self.queue_summary_label.setWordWrap(True)

        left_layout.addWidget(left_title)
        left_layout.addWidget(left_subtitle)
        left_layout.addWidget(self.merge_drop_card)
        left_layout.addLayout(file_button_row)
        left_layout.addWidget(self.pdf_list, 1)
        left_layout.addLayout(reorder_row)
        left_layout.addWidget(self.queue_summary_label)
        body.addWidget(left_panel, 1)

        right_panel = QFrame()
        right_panel.setObjectName("workspacePanel")
        right_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)

        self.pdf_mode_button = QPushButton("PDF Order")
        self.pdf_mode_button.setObjectName("modeTab")
        self.pdf_mode_button.setCheckable(True)
        self.pdf_mode_button.clicked.connect(
            lambda checked=False: self._set_order_mode(ORDER_MODE_PDF)
        )

        self.page_mode_button = QPushButton("Page Order")
        self.page_mode_button.setObjectName("modeTab")
        self.page_mode_button.setCheckable(True)
        self.page_mode_button.clicked.connect(
            lambda checked=False: self._set_order_mode(ORDER_MODE_PAGE)
        )

        mode_row.addWidget(self.pdf_mode_button)
        mode_row.addWidget(self.page_mode_button)
        mode_row.addStretch(1)

        self.mode_summary_label = QLabel()
        self.mode_summary_label.setObjectName("panelBody")
        self.mode_summary_label.setWordWrap(True)

        self.page_mode_note = QLabel(
            "Page moves and deletes affect merged output only. Source PDFs stay untouched."
        )
        self.page_mode_note.setObjectName("mutedLabel")
        self.page_mode_note.setWordWrap(True)

        self.page_table = QTableWidget(0, 4)
        self.page_table.setObjectName("pageTable")
        self.page_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.page_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.page_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.page_table.setAlternatingRowColors(True)
        self.page_table.verticalHeader().setVisible(False)
        self.page_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.page_table.setHorizontalHeaderLabels(
            ["Output", "Source PDF", "Original Page", "Source Path"]
        )
        header = self.page_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.page_table.itemSelectionChanged.connect(self._refresh_page_move_buttons)

        page_move_row = QHBoxLayout()
        page_move_row.setSpacing(8)

        self.page_move_up_button = QPushButton("Move Page Up")
        self.page_move_up_button.setObjectName("secondaryButton")
        self.page_move_up_button.clicked.connect(lambda: self._move_selected_page(-1))

        self.page_move_down_button = QPushButton("Move Page Down")
        self.page_move_down_button.setObjectName("secondaryButton")
        self.page_move_down_button.clicked.connect(lambda: self._move_selected_page(1))

        self.page_delete_button = QPushButton("Delete Page")
        self.page_delete_button.setObjectName("secondaryButton")
        self.page_delete_button.clicked.connect(self._delete_selected_page)

        self.page_target_position_edit = QLineEdit()
        self.page_target_position_edit.setObjectName("timeSpin")
        self.page_target_position_edit.setPlaceholderText("Pos")
        self.page_target_position_edit.setMaximumWidth(84)

        self.page_move_to_position_button = QPushButton("Move to Position")
        self.page_move_to_position_button.setObjectName("secondaryButton")
        self.page_move_to_position_button.clicked.connect(
            self._move_selected_page_to_position
        )

        self.page_reset_button = QPushButton("Reset Page Order")
        self.page_reset_button.setObjectName("secondaryButton")
        self.page_reset_button.clicked.connect(self._reset_page_order)

        page_move_row.addWidget(self.page_move_up_button)
        page_move_row.addWidget(self.page_move_down_button)
        page_move_row.addWidget(self.page_delete_button)
        page_move_row.addWidget(self.page_target_position_edit)
        page_move_row.addWidget(self.page_move_to_position_button)
        page_move_row.addWidget(self.page_reset_button)
        page_move_row.addStretch(1)

        output_panel = QFrame()
        output_panel.setObjectName("pdfOutputPanel")
        output_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        output_layout = QGridLayout(output_panel)
        output_layout.setContentsMargins(14, 14, 14, 14)
        output_layout.setHorizontalSpacing(8)
        output_layout.setVerticalSpacing(8)

        output_title = QLabel("Output")
        output_title.setObjectName("panelTitle")

        output_hint = QLabel(
            "Writer copies/imports PDF pages directly. No rasterization. No image conversion."
        )
        output_hint.setObjectName("panelBody")
        output_hint.setWordWrap(True)

        path_label = QLabel("Save as")
        path_label.setObjectName("mutedLabel")

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setObjectName("workspaceInput")
        self.output_path_edit.setPlaceholderText("Choose output PDF location")
        self.output_path_edit.textChanged.connect(self._on_output_path_changed)

        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.setObjectName("secondaryButton")
        self.output_browse_button.clicked.connect(self._choose_output_path)

        self.merge_button = QPushButton("Merge PDFs")
        self.merge_button.setObjectName("primaryButton")
        self.merge_button.clicked.connect(self._merge_pdfs)

        self.status_label = QLabel("Status: add PDF files to start.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        output_layout.addWidget(output_title, 0, 0, 1, 2)
        output_layout.addWidget(output_hint, 1, 0, 1, 2)
        output_layout.addWidget(path_label, 2, 0)
        output_layout.addWidget(self.output_path_edit, 3, 0)
        output_layout.addWidget(self.output_browse_button, 3, 1)
        output_layout.addWidget(self.merge_button, 4, 0, 1, 2)
        output_layout.addWidget(self.status_label, 5, 0, 1, 2)

        right_layout.addLayout(mode_row)
        right_layout.addWidget(self.mode_summary_label)
        right_layout.addWidget(self.page_mode_note)
        right_layout.addWidget(self.page_table, 1)
        right_layout.addLayout(page_move_row)
        right_layout.addWidget(output_panel)
        body.addWidget(right_panel, 1)
        return page

    def _build_split_workspace(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        source_panel = QFrame()
        source_panel.setObjectName("workspacePanel")
        source_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(16, 16, 16, 16)
        source_layout.setSpacing(10)

        source_title = QLabel("Split source")
        source_title.setObjectName("panelTitle")

        source_subtitle = QLabel(
            "Choose one PDF, pick split mode, then write new PDFs into output folder. Source file stays untouched."
        )
        source_subtitle.setObjectName("panelBody")
        source_subtitle.setWordWrap(True)

        self.split_drop_card = FileDropCard(
            accepted_type_text="PDF files",
            multi_file=False,
        )
        self.split_drop_card.clicked.connect(self._choose_split_pdf)
        self.split_drop_card.paths_dropped.connect(self._handle_split_drop_from_zone)
        self.split_drop_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self.split_file_label = QLabel("No PDF selected")
        self.split_file_label.setObjectName("workspaceTitle")

        self.split_path_label = QLabel("Source path: -")
        self.split_path_label.setObjectName("panelBody")
        self.split_path_label.setWordWrap(True)

        self.split_page_count_label = QLabel("Page count: -")
        self.split_page_count_label.setObjectName("mutedLabel")

        source_layout.addWidget(source_title)
        source_layout.addWidget(source_subtitle)
        source_layout.addWidget(self.split_drop_card)
        source_layout.addWidget(self.split_file_label)
        source_layout.addWidget(self.split_path_label)
        source_layout.addWidget(self.split_page_count_label)
        source_layout.addStretch(1)
        layout.addWidget(source_panel, 1)

        split_panel = QFrame()
        split_panel.setObjectName("workspacePanel")
        split_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        split_layout = QVBoxLayout(split_panel)
        split_layout.setContentsMargins(16, 16, 16, 16)
        split_layout.setSpacing(10)

        split_title = QLabel("Split options")
        split_title.setObjectName("panelTitle")

        split_hint = QLabel(
            "Split writes new PDFs by importing original pages directly. No rasterization. Existing output files fail safely."
        )
        split_hint.setObjectName("panelBody")
        split_hint.setWordWrap(True)

        self.split_every_button = QPushButton("Every Page")
        self.split_every_button.setObjectName("modeTab")
        self.split_every_button.setCheckable(True)
        self.split_every_button.clicked.connect(
            lambda checked=False: self._set_split_mode(SPLIT_MODE_EVERY_PAGE)
        )

        self.split_custom_button = QPushButton("Custom Ranges")
        self.split_custom_button.setObjectName("modeTab")
        self.split_custom_button.setCheckable(True)
        self.split_custom_button.clicked.connect(
            lambda checked=False: self._set_split_mode(SPLIT_MODE_CUSTOM)
        )

        split_mode_row = QHBoxLayout()
        split_mode_row.setSpacing(8)
        split_mode_row.addWidget(self.split_every_button)
        split_mode_row.addWidget(self.split_custom_button)
        split_mode_row.addStretch(1)

        split_output_label = QLabel("Output folder")
        split_output_label.setObjectName("mutedLabel")

        split_output_row = QHBoxLayout()
        split_output_row.setSpacing(8)

        self.split_output_dir_edit = QLineEdit()
        self.split_output_dir_edit.setObjectName("workspaceInput")
        self.split_output_dir_edit.setPlaceholderText("Choose output folder")
        self.split_output_dir_edit.textChanged.connect(self._on_split_output_dir_changed)

        self.split_output_browse_button = QPushButton("Browse")
        self.split_output_browse_button.setObjectName("secondaryButton")
        self.split_output_browse_button.clicked.connect(self._choose_split_output_dir)

        split_output_row.addWidget(self.split_output_dir_edit, 1)
        split_output_row.addWidget(self.split_output_browse_button)

        self.split_ranges_label = QLabel("Custom page ranges")
        self.split_ranges_label.setObjectName("mutedLabel")

        self.split_ranges_edit = QLineEdit()
        self.split_ranges_edit.setObjectName("workspaceInput")
        self.split_ranges_edit.setPlaceholderText("Examples: 1-3,5,8-10")
        self.split_ranges_edit.textChanged.connect(self._on_split_ranges_changed)

        self.split_ranges_hint = QLabel(
            "Ranges use 1-based pages. Examples: 1-3 | 1-3,5 | 1-3,5,8-10"
        )
        self.split_ranges_hint.setObjectName("mutedLabel")
        self.split_ranges_hint.setWordWrap(True)

        self.split_button = QPushButton("Split PDF")
        self.split_button.setObjectName("primaryButton")
        self.split_button.clicked.connect(self._split_pdf)

        self.split_status_label = QLabel("Status: choose one PDF to split.")
        self.split_status_label.setObjectName("statusLabel")
        self.split_status_label.setWordWrap(True)

        split_layout.addWidget(split_title)
        split_layout.addWidget(split_hint)
        split_layout.addLayout(split_mode_row)
        split_layout.addWidget(split_output_label)
        split_layout.addLayout(split_output_row)
        split_layout.addWidget(self.split_ranges_label)
        split_layout.addWidget(self.split_ranges_edit)
        split_layout.addWidget(self.split_ranges_hint)
        split_layout.addWidget(self.split_button)
        split_layout.addWidget(self.split_status_label)
        split_layout.addStretch(1)
        layout.addWidget(split_panel, 1)
        return page

    def _choose_pdf_files(self) -> None:
        file_names, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF files",
            "",
            "PDF files (*.pdf);;All files (*.*)",
        )
        if file_names:
            self._add_pdf_paths([Path(name) for name in file_names])

    def _add_pdf_paths(self, paths: list[Path]) -> None:
        added = 0
        skipped: list[str] = []
        known_paths = {item.source_path for item in self.merge_state.items}

        for path in paths:
            try:
                resolved_path = path.expanduser().resolve()
                if resolved_path in known_paths:
                    skipped.append(f"{resolved_path.name}: already in queue")
                    continue
                item = self.service.inspect_pdf(
                    resolved_path,
                    document_id=uuid4().hex,
                )
            except PdfMergeError as error:
                skipped.append(str(error))
                continue

            self.merge_state.add_item(item)
            known_paths.add(item.source_path)
            added += 1

        if added and self.merge_state.output_path is None:
            suggested = self.service.suggested_output_path(self.merge_state.items)
            if suggested is not None:
                self.merge_state.output_path = suggested

        self._refresh_ui()
        status_parts: list[str] = []
        status_kind = "info"
        if added:
            status_parts.append(
                f"Loaded {added} PDF file(s). Queue now has {len(self.merge_state.items)} document(s)."
            )
            status_kind = "success"
        if skipped:
            status_parts.append("Skipped: " + " | ".join(skipped[-4:]))
            if not added:
                status_kind = "error"
        if status_parts:
            self._set_status(" ".join(status_parts), status_kind)

    def _remove_selected_item(self) -> None:
        row = self.pdf_list.currentRow()
        if row < 0:
            self._set_status("Select PDF in queue first.", "error")
            return
        removed = self.merge_state.remove_item_at(row)
        if not self.merge_state.items:
            self.merge_state.output_path = None
        self._refresh_ui()
        self._set_status(f"Removed {removed.display_name} from merge queue.")

    def _move_selected_item(self, delta: int) -> None:
        row = self.pdf_list.currentRow()
        if row < 0:
            self._set_status("Select PDF in queue first.", "error")
            return
        target_row = row + delta
        if not self.merge_state.move_item(row, target_row):
            return
        self._refresh_ui(selected_row=target_row)
        self._set_status("PDF order updated.", "success")

    def _set_order_mode(self, mode: str) -> None:
        self.merge_state.order_mode = mode
        self._refresh_mode_buttons()
        self._refresh_page_table()
        self._refresh_page_move_buttons()

    def _set_active_action(self, action: str) -> None:
        self.active_action = action
        self._refresh_action_buttons()

    def _choose_split_pdf(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF to split",
            "",
            "PDF files (*.pdf);;All files (*.*)",
        )
        if not file_name:
            return

        self._load_split_source_pdf(Path(file_name))

    def _load_split_source_pdf(self, path: Path) -> PdfMergeItem | None:
        try:
            item = self.service.inspect_pdf(path, document_id=uuid4().hex)
        except PdfMergeError as error:
            self._set_split_status(str(error), "error")
            return None

        self.split_state.source_item = item
        if self.split_state.output_dir is None:
            suggested_dir = self.service.suggested_split_output_dir(item)
            if suggested_dir is not None:
                self.split_state.output_dir = suggested_dir
        self._refresh_split_workspace()
        return item

    def _choose_split_output_dir(self) -> None:
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose split output folder",
            self.split_output_dir_edit.text().strip(),
        )
        if not selected_dir:
            return
        with QSignalBlocker(self.split_output_dir_edit):
            self.split_output_dir_edit.setText(selected_dir)
        self.split_state.output_dir = Path(selected_dir)
        self._refresh_split_button()

    def _on_split_output_dir_changed(self, text: str) -> None:
        cleaned = text.strip()
        self.split_state.output_dir = Path(cleaned) if cleaned else None
        self._refresh_split_button()

    def _on_split_ranges_changed(self, text: str) -> None:
        self.split_state.custom_ranges_text = text
        self._refresh_split_button()

    def _set_split_mode(self, mode: str) -> None:
        self.split_state.split_mode = mode
        self._refresh_split_mode_buttons()
        self._refresh_split_button()

    def _handle_split_drop(self, paths: list[Path]) -> bool:
        selection = classify_split_drop_paths(paths)
        status_parts: list[str] = []
        status_kind = "info"

        loaded_item = None
        if selection.source_pdf_path is not None:
            loaded_item = self._load_split_source_pdf(selection.source_pdf_path)
            if loaded_item is not None:
                status_parts.append(f"Loaded {loaded_item.display_name} for split.")
                status_kind = "success"
            else:
                status_kind = "error"

        if selection.output_dir_path is not None:
            self.split_state.output_dir = selection.output_dir_path
            self._refresh_split_workspace()
            status_parts.append(f"Output folder set to {selection.output_dir_path}")
            if status_kind != "error":
                status_kind = "success"

        if selection.skipped_items:
            status_parts.append("Ignored: " + " | ".join(selection.skipped_items[-4:]))
            if not status_parts[:-1]:
                status_kind = "error"

        if not status_parts:
            self._set_split_status(
                "Drop a PDF to load split source, or drop a folder to set output.",
                "error",
            )
            return False

        self._set_split_status(" ".join(status_parts), status_kind)
        return loaded_item is not None or selection.output_dir_path is not None

    def _handle_split_drop_from_zone(self, paths: list[Path]) -> None:
        self._handle_split_drop(paths)

    def _split_pdf(self) -> None:
        source_item = self.split_state.source_item
        if source_item is None:
            self._set_split_status("Choose one PDF to split first.", "error")
            return
        if self.split_state.output_dir is None:
            self._set_split_status("Choose output folder first.", "error")
            return

        try:
            if self.split_state.split_mode == SPLIT_MODE_EVERY_PAGE:
                output_paths = self.service.split_every_page(
                    source_item,
                    self.split_state.output_dir,
                )
            else:
                ranges = self.service.parse_page_ranges(
                    self.split_state.custom_ranges_text,
                    page_count=source_item.page_count,
                )
                output_paths = self.service.split_by_ranges(
                    source_item,
                    self.split_state.output_dir,
                    ranges,
                )
        except PdfMergeError as error:
            self._set_split_status(str(error), "error")
            return

        self.split_state.last_output_paths = output_paths
        self._set_split_status(
            f"Created {len(output_paths)} split PDF(s) in {self.split_state.output_dir}",
            "success",
        )
        response = QMessageBox.question(
            self,
            "Split complete",
            f"Created {len(output_paths)} PDF file(s) in:\n{self.split_state.output_dir}\n\nOpen containing folder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if response == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.split_state.output_dir))
            )

    def _choose_output_path(self) -> None:
        suggested = self.output_path_edit.text().strip()
        if not suggested and self.merge_state.items:
            fallback = self.service.suggested_output_path(self.merge_state.items)
            suggested = str(fallback) if fallback is not None else ""

        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save merged PDF as",
            suggested,
            "PDF files (*.pdf);;All files (*.*)",
        )
        if not selected_path:
            return
        normalized_path = Path(selected_path)
        if normalized_path.suffix.lower() != ".pdf":
            normalized_path = normalized_path.with_suffix(".pdf")

        with QSignalBlocker(self.output_path_edit):
            self.output_path_edit.setText(str(normalized_path))
        self.merge_state.output_path = normalized_path
        self._refresh_merge_button()

    def _on_output_path_changed(self, text: str) -> None:
        cleaned = text.strip()
        self.merge_state.output_path = Path(cleaned) if cleaned else None
        self._refresh_merge_button()

    def _merge_pdfs(self) -> None:
        if self.merge_state.output_path is None:
            self._set_status("Choose output PDF path first.", "error")
            return
        if self.merge_state.order_mode == ORDER_MODE_PAGE and not self.merge_state.pages:
            self._set_status(
                "Page Order merge has no pages left. Reset page order or add PDFs first.",
                "error",
            )
            return
        try:
            if self.merge_state.order_mode == ORDER_MODE_PAGE:
                output_path = self.service.merge_page_sequence(
                    self.merge_state.pages,
                    self.merge_state.output_path,
                )
            else:
                output_path = self.service.merge_pdfs(
                    self.merge_state.items,
                    self.merge_state.output_path,
                )
        except PdfMergeError as error:
            self._set_status(str(error), "error")
            return

        self.merge_state.last_output_path = output_path
        self._set_status(f"Merged {len(self.merge_state.items)} PDF(s) into {output_path}", "success")
        response = QMessageBox.question(
            self,
            "Merge complete",
            f"Merged PDF saved to:\n{output_path}\n\nOpen containing folder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if response == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path.parent)))

    def _refresh_ui(self, *, selected_row: int | None = None) -> None:
        self._refresh_action_buttons()
        self._refresh_pdf_list(selected_row=selected_row)
        self._refresh_mode_buttons()
        self._refresh_page_table()
        self._refresh_output_path()
        self._refresh_merge_button()
        self._refresh_page_move_buttons()
        self._refresh_split_workspace()

    def _refresh_pdf_list(self, *, selected_row: int | None = None) -> None:
        self.pdf_list.clear()
        for index, item in enumerate(self.merge_state.items, start=1):
            list_item = QListWidgetItem()
            list_item.setToolTip(str(item.source_path))
            widget = self._build_pdf_item_widget(index, item)
            list_item.setSizeHint(widget.sizeHint())
            self.pdf_list.addItem(list_item)
            self.pdf_list.setItemWidget(list_item, widget)

        if selected_row is None and self.merge_state.items:
            selected_row = min(self.pdf_list.currentRow(), len(self.merge_state.items) - 1)
            if selected_row < 0:
                selected_row = 0

        if selected_row is not None and 0 <= selected_row < self.pdf_list.count():
            self.pdf_list.setCurrentRow(selected_row)

        document_count = len(self.merge_state.items)
        total_pages = self.merge_state.total_pages
        if document_count == 0:
            self.queue_summary_label.setText("No PDFs selected.")
            self.merge_drop_card.set_empty_state(
                title="Click to add or drop PDFs",
                subtitle="Build your merge queue with one or more PDF files.",
                caption="Accepts: PDF files | Multiple files",
            )
        else:
            self.queue_summary_label.setText(
                f"{document_count} PDF(s) queued | {total_pages} total page(s)"
            )
            self.merge_drop_card.set_loaded_state(
                title=f"{document_count} PDF(s) queued",
                subtitle=f"{total_pages} total page(s) ready to merge",
                caption="Click or drop more PDFs to add to queue.",
            )
        self._refresh_reorder_buttons()

    def _build_pdf_item_widget(
        self,
        output_order: int,
        item: PdfMergeItem,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("pdfQueueCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel(f"{output_order}. {item.display_name}")
        title.setObjectName("pdfQueueTitle")
        title.setToolTip(str(item.source_path))

        meta = QLabel(f"{item.page_count} page(s)")
        meta.setObjectName("mutedLabel")

        path = QLabel(str(item.source_path))
        path.setObjectName("pdfQueuePath")
        path.setWordWrap(True)
        path.setToolTip(str(item.source_path))

        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addWidget(path)
        return card

    def _refresh_reorder_buttons(self) -> None:
        row = self.pdf_list.currentRow()
        has_selection = row >= 0
        self.remove_button.setEnabled(has_selection)
        self.move_up_button.setEnabled(has_selection and row > 0)
        self.move_down_button.setEnabled(
            has_selection and 0 <= row < len(self.merge_state.items) - 1
        )

    def _refresh_mode_buttons(self) -> None:
        self.pdf_mode_button.setChecked(self.merge_state.order_mode == ORDER_MODE_PDF)
        self.page_mode_button.setChecked(self.merge_state.order_mode == ORDER_MODE_PAGE)
        if self.merge_state.order_mode == ORDER_MODE_PAGE:
            self.mode_summary_label.setText(
                "Page order mode controls actual merged output. Select row to move, delete from output, jump to position, or reset from current PDF queue."
            )
            self.page_mode_note.show()
        else:
            self.mode_summary_label.setText(
                "PDF order mode controls actual merge output now. Reorder whole documents in left queue."
            )
            self.page_mode_note.hide()

    def _refresh_page_table(self) -> None:
        selected_row = self._selected_page_row()
        pages = self.merge_state.pages
        self.page_table.setRowCount(len(pages))
        for row, page in enumerate(pages):
            values = (
                str(page.output_order),
                page.source_document_name,
                str(page.original_page_number),
                str(page.source_path),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(str(page.source_path))
                self.page_table.setItem(row, column, item)
        self.page_table.setColumnHidden(3, self.merge_state.order_mode != ORDER_MODE_PAGE)
        if 0 <= selected_row < len(pages):
            self.page_table.selectRow(selected_row)
        elif len(pages) > 0:
            if self.merge_state.order_mode == ORDER_MODE_PAGE:
                self.page_table.selectRow(0)
            else:
                self.page_table.clearSelection()

    def _move_selected_page(self, delta: int) -> None:
        if self.merge_state.order_mode != ORDER_MODE_PAGE:
            self._set_status("Switch to Page Order mode to move individual pages.", "error")
            return

        row = self._selected_page_row()
        if row < 0:
            self._set_status("Select page row first.", "error")
            return

        target_row = row + delta
        if not self.merge_state.move_page(row, target_row):
            return

        self._refresh_page_table()
        self.page_table.selectRow(target_row)
        self._refresh_page_move_buttons()
        self._set_status("Page output order updated.", "success")

    def _delete_selected_page(self) -> None:
        if self.merge_state.order_mode != ORDER_MODE_PAGE:
            self._set_status("Switch to Page Order mode to delete output pages.", "error")
            return

        row = self._selected_page_row()
        if row < 0:
            self._set_status("Select page row first.", "error")
            return

        removed_page = self.merge_state.delete_page(row)
        if removed_page is None:
            self._set_status("Could not delete selected page.", "error")
            return

        next_row = min(row, len(self.merge_state.pages) - 1)
        self._refresh_page_table()
        if next_row >= 0:
            self.page_table.selectRow(next_row)
        self._refresh_page_move_buttons()
        self._set_status(
            f"Removed page {removed_page.original_page_number} from output order only.",
            "success",
        )

    def _move_selected_page_to_position(self) -> None:
        if self.merge_state.order_mode != ORDER_MODE_PAGE:
            self._set_status("Switch to Page Order mode to move pages by position.", "error")
            return

        row = self._selected_page_row()
        if row < 0:
            self._set_status("Select page row first.", "error")
            return

        target_text = self.page_target_position_edit.text().strip()
        if not target_text:
            self._set_status("Enter target output position first.", "error")
            return
        if not target_text.isdigit():
            self._set_status("Target output position must be a whole number.", "error")
            return

        target_position = int(target_text)
        if target_position < 1:
            self._set_status("Target output position must be at least 1.", "error")
            return
        if target_position > len(self.merge_state.pages):
            self._set_status(
                f"Target output position must be between 1 and {len(self.merge_state.pages)}.",
                "error",
            )
            return

        if not self.merge_state.move_page_to_position(row, target_position):
            self._set_status("Could not move page to that output position.", "error")
            return

        self._refresh_page_table()
        self.page_table.selectRow(target_position - 1)
        self._refresh_page_move_buttons()
        self._set_status(
            f"Moved selected page to output position {target_position}.",
            "success",
        )

    def _reset_page_order(self) -> None:
        self.merge_state.reset_page_order()
        self._refresh_page_table()
        self._refresh_page_move_buttons()
        self._set_status("Page order reset from current PDF queue.", "success")

    def _refresh_output_path(self) -> None:
        current_text = self.output_path_edit.text().strip()
        desired_text = ""
        if self.merge_state.output_path is not None:
            desired_text = str(self.merge_state.output_path)
        elif not current_text and self.merge_state.items:
            suggested = self.service.suggested_output_path(self.merge_state.items)
            if suggested is not None:
                self.merge_state.output_path = suggested
                desired_text = str(suggested)

        if desired_text != current_text:
            with QSignalBlocker(self.output_path_edit):
                self.output_path_edit.setText(desired_text)

    def _refresh_merge_button(self) -> None:
        self.merge_button.setEnabled(
            bool(self.merge_state.items) and self.merge_state.output_path is not None
            and (
                self.merge_state.order_mode != ORDER_MODE_PAGE
                or bool(self.merge_state.pages)
            )
        )

    def _refresh_page_move_buttons(self) -> None:
        selected_row = self._selected_page_row()
        page_mode_active = self.merge_state.order_mode == ORDER_MODE_PAGE
        has_selection = 0 <= selected_row < len(self.merge_state.pages)
        page_count = len(self.merge_state.pages)
        self.page_move_up_button.setEnabled(page_mode_active and has_selection and selected_row > 0)
        self.page_move_down_button.setEnabled(
            page_mode_active
            and has_selection
            and selected_row < len(self.merge_state.pages) - 1
        )
        self.page_delete_button.setEnabled(page_mode_active and has_selection)
        self.page_target_position_edit.setEnabled(page_mode_active and page_count > 0)
        if page_mode_active and has_selection:
            self.page_target_position_edit.setText(str(selected_row + 1))
        self.page_move_to_position_button.setEnabled(
            page_mode_active and has_selection and page_count > 0
        )
        self.page_reset_button.setEnabled(page_mode_active and bool(self.merge_state.items))

    def _refresh_action_buttons(self) -> None:
        self.action_buttons[PDF_ACTION_MERGE].setChecked(
            self.active_action == PDF_ACTION_MERGE
        )
        self.action_buttons[PDF_ACTION_SPLIT].setChecked(
            self.active_action == PDF_ACTION_SPLIT
        )
        self.action_stack.setCurrentIndex(
            0 if self.active_action == PDF_ACTION_MERGE else 1
        )

    def _refresh_split_workspace(self) -> None:
        source_item = self.split_state.source_item
        if source_item is None:
            self.split_file_label.setText("No PDF selected")
            self.split_path_label.setText("Source path: -")
            self.split_page_count_label.setText("Page count: -")
            self.split_drop_card.set_empty_state(
                title="Click to select or drop a PDF",
                subtitle="Drop a folder to set output",
                caption="Accepts: PDF files | Single file",
            )
        else:
            self.split_file_label.setText(source_item.display_name)
            self.split_path_label.setText(f"Source path: {source_item.source_path}")
            self.split_page_count_label.setText(f"Page count: {source_item.page_count}")
            self.split_drop_card.set_loaded_state(
                title=source_item.display_name,
                subtitle=f"{source_item.page_count} page(s) loaded",
                caption="Click or drop another PDF to replace. Drop a folder to set output.",
            )

        desired_output_dir = ""
        if self.split_state.output_dir is not None:
            desired_output_dir = str(self.split_state.output_dir)
        elif source_item is not None:
            suggested_dir = self.service.suggested_split_output_dir(source_item)
            if suggested_dir is not None:
                self.split_state.output_dir = suggested_dir
                desired_output_dir = str(suggested_dir)

        current_output_dir = self.split_output_dir_edit.text().strip()
        if current_output_dir != desired_output_dir:
            with QSignalBlocker(self.split_output_dir_edit):
                self.split_output_dir_edit.setText(desired_output_dir)

        if self.split_ranges_edit.text() != self.split_state.custom_ranges_text:
            with QSignalBlocker(self.split_ranges_edit):
                self.split_ranges_edit.setText(self.split_state.custom_ranges_text)

        self._refresh_split_mode_buttons()
        self._refresh_split_button()

    def _refresh_split_mode_buttons(self) -> None:
        is_every_page = self.split_state.split_mode == SPLIT_MODE_EVERY_PAGE
        self.split_every_button.setChecked(is_every_page)
        self.split_custom_button.setChecked(not is_every_page)
        self.split_ranges_label.setVisible(not is_every_page)
        self.split_ranges_edit.setVisible(not is_every_page)
        self.split_ranges_hint.setVisible(not is_every_page)

    def _refresh_split_button(self) -> None:
        has_source = self.split_state.source_item is not None
        has_output_dir = self.split_state.output_dir is not None
        if self.split_state.split_mode == SPLIT_MODE_CUSTOM:
            has_ranges = bool(self.split_state.custom_ranges_text.strip())
        else:
            has_ranges = True
        self.split_button.setEnabled(has_source and has_output_dir and has_ranges)

    def _selected_page_row(self) -> int:
        selection_model = self.page_table.selectionModel()
        if selection_model is None:
            return -1
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            return -1
        return selected_rows[0].row()

    def _set_status(self, message: str, kind: str = "info") -> None:
        object_name = {
            "success": "successLabel",
            "error": "errorLabel",
        }.get(kind, "statusLabel")
        self.status_label.setObjectName(object_name)
        self.status_label.setText(message)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_split_status(self, message: str, kind: str = "info") -> None:
        object_name = {
            "success": "successLabel",
            "error": "errorLabel",
        }.get(kind, "statusLabel")
        self.split_status_label.setObjectName(object_name)
        self.split_status_label.setText(message)
        self.split_status_label.style().unpolish(self.split_status_label)
        self.split_status_label.style().polish(self.split_status_label)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            super().dropEvent(event)
            return
        paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
        if self.active_action == PDF_ACTION_SPLIT:
            if self._handle_split_drop(paths):
                event.acceptProposedAction()
                return
        else:
            pdf_paths = [path for path in paths if path.suffix.lower() == ".pdf"]
            if pdf_paths:
                self._add_pdf_paths(pdf_paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)
