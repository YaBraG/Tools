from __future__ import annotations

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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shared.tool_base import ToolContext
from tools.pdf_tools.models import (
    ORDER_MODE_PAGE,
    ORDER_MODE_PDF,
    PdfMergeItem,
    PdfMergeState,
)
from tools.pdf_tools.service import PdfMergeError, PdfMergeService


class PdfToolsWidget(QWidget):
    def __init__(self, context: ToolContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.service = PdfMergeService(context)
        self.state = PdfMergeState()

        self._build_ui()
        self._refresh_ui()

    def _build_ui(self) -> None:
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        header_panel = QFrame()
        header_panel.setObjectName("workspacePanel")
        header_layout = QVBoxLayout(header_panel)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(12)

        title = QLabel("PDF workspace")
        title.setObjectName("workspaceTitle")

        subtitle = QLabel(
            "Merge is live now. Split, compress, and convert stay visible as next actions."
        )
        subtitle.setObjectName("panelBody")
        subtitle.setWordWrap(True)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        for label, enabled in (
            ("Merge", True),
            ("Split", False),
            ("Compress", False),
            ("Convert", False),
        ):
            button = QPushButton(label)
            button.setObjectName("modeTab")
            button.setCheckable(True)
            button.setChecked(enabled)
            button.setEnabled(enabled)
            action_row.addWidget(button)
        action_row.addStretch(1)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addLayout(action_row)
        layout.addWidget(header_panel)

        body = QHBoxLayout()
        body.setSpacing(16)

        left_panel = QFrame()
        left_panel.setObjectName("workspacePanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)

        left_title = QLabel("Merge queue")
        left_title.setObjectName("panelTitle")

        left_subtitle = QLabel(
            "Add PDFs, reorder them, remove any item, then save merged output."
        )
        left_subtitle.setObjectName("panelBody")
        left_subtitle.setWordWrap(True)

        file_button_row = QHBoxLayout()
        file_button_row.setSpacing(10)

        self.add_button = QPushButton("Add PDFs")
        self.add_button.setObjectName("secondaryButton")
        self.add_button.clicked.connect(self._choose_pdf_files)

        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.setObjectName("secondaryButton")
        self.remove_button.clicked.connect(self._remove_selected_item)

        file_button_row.addWidget(self.add_button)
        file_button_row.addWidget(self.remove_button)
        file_button_row.addStretch(1)

        self.pdf_list = QListWidget()
        self.pdf_list.setObjectName("pdfList")
        self.pdf_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pdf_list.currentRowChanged.connect(self._refresh_reorder_buttons)

        reorder_row = QHBoxLayout()
        reorder_row.setSpacing(10)

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
        left_layout.addLayout(file_button_row)
        left_layout.addWidget(self.pdf_list, 1)
        left_layout.addLayout(reorder_row)
        left_layout.addWidget(self.queue_summary_label)
        body.addWidget(left_panel, 1)

        right_panel = QFrame()
        right_panel.setObjectName("workspacePanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)

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
            "Page moves change merged output order only. Source PDFs stay untouched."
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
        self.page_table.setHorizontalHeaderLabels(
            ["Output", "Source PDF", "Original Page", "Source Path"]
        )
        header = self.page_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.page_table.itemSelectionChanged.connect(self._refresh_page_move_buttons)

        page_move_row = QHBoxLayout()
        page_move_row.setSpacing(10)

        self.page_move_up_button = QPushButton("Move Page Up")
        self.page_move_up_button.setObjectName("secondaryButton")
        self.page_move_up_button.clicked.connect(lambda: self._move_selected_page(-1))

        self.page_move_down_button = QPushButton("Move Page Down")
        self.page_move_down_button.setObjectName("secondaryButton")
        self.page_move_down_button.clicked.connect(lambda: self._move_selected_page(1))

        page_move_row.addWidget(self.page_move_up_button)
        page_move_row.addWidget(self.page_move_down_button)
        page_move_row.addStretch(1)

        output_panel = QFrame()
        output_panel.setObjectName("pdfOutputPanel")
        output_layout = QGridLayout(output_panel)
        output_layout.setContentsMargins(16, 16, 16, 16)
        output_layout.setHorizontalSpacing(10)
        output_layout.setVerticalSpacing(10)

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

        layout.addLayout(body, 1)

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
        known_paths = {item.source_path for item in self.state.items}

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

            self.state.add_item(item)
            known_paths.add(item.source_path)
            added += 1

        if added and self.state.output_path is None:
            suggested = self.service.suggested_output_path(self.state.items)
            if suggested is not None:
                self.state.output_path = suggested

        self._refresh_ui()
        status_parts: list[str] = []
        status_kind = "info"
        if added:
            status_parts.append(
                f"Loaded {added} PDF file(s). Queue now has {len(self.state.items)} document(s)."
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
        removed = self.state.remove_item_at(row)
        if not self.state.items:
            self.state.output_path = None
        self._refresh_ui()
        self._set_status(f"Removed {removed.display_name} from merge queue.")

    def _move_selected_item(self, delta: int) -> None:
        row = self.pdf_list.currentRow()
        if row < 0:
            self._set_status("Select PDF in queue first.", "error")
            return
        target_row = row + delta
        if not self.state.move_item(row, target_row):
            return
        self._refresh_ui(selected_row=target_row)
        self._set_status("PDF order updated.", "success")

    def _set_order_mode(self, mode: str) -> None:
        self.state.order_mode = mode
        self._refresh_mode_buttons()
        self._refresh_page_table()
        self._refresh_page_move_buttons()

    def _choose_output_path(self) -> None:
        suggested = self.output_path_edit.text().strip()
        if not suggested and self.state.items:
            fallback = self.service.suggested_output_path(self.state.items)
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
        self.state.output_path = normalized_path
        self._refresh_merge_button()

    def _on_output_path_changed(self, text: str) -> None:
        cleaned = text.strip()
        self.state.output_path = Path(cleaned) if cleaned else None
        self._refresh_merge_button()

    def _merge_pdfs(self) -> None:
        if self.state.output_path is None:
            self._set_status("Choose output PDF path first.", "error")
            return
        try:
            if self.state.order_mode == ORDER_MODE_PAGE:
                output_path = self.service.merge_page_sequence(
                    self.state.pages,
                    self.state.output_path,
                )
            else:
                output_path = self.service.merge_pdfs(
                    self.state.items,
                    self.state.output_path,
                )
        except PdfMergeError as error:
            self._set_status(str(error), "error")
            return

        self.state.last_output_path = output_path
        self._set_status(f"Merged {len(self.state.items)} PDF(s) into {output_path}", "success")
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
        self._refresh_pdf_list(selected_row=selected_row)
        self._refresh_mode_buttons()
        self._refresh_page_table()
        self._refresh_output_path()
        self._refresh_merge_button()
        self._refresh_page_move_buttons()

    def _refresh_pdf_list(self, *, selected_row: int | None = None) -> None:
        self.pdf_list.clear()
        for index, item in enumerate(self.state.items, start=1):
            list_item = QListWidgetItem()
            list_item.setToolTip(str(item.source_path))
            widget = self._build_pdf_item_widget(index, item)
            list_item.setSizeHint(widget.sizeHint())
            self.pdf_list.addItem(list_item)
            self.pdf_list.setItemWidget(list_item, widget)

        if selected_row is None and self.state.items:
            selected_row = min(self.pdf_list.currentRow(), len(self.state.items) - 1)
            if selected_row < 0:
                selected_row = 0

        if selected_row is not None and 0 <= selected_row < self.pdf_list.count():
            self.pdf_list.setCurrentRow(selected_row)

        document_count = len(self.state.items)
        total_pages = self.state.total_pages
        if document_count == 0:
            self.queue_summary_label.setText("No PDFs selected.")
        else:
            self.queue_summary_label.setText(
                f"{document_count} PDF(s) queued | {total_pages} total page(s)"
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
            has_selection and 0 <= row < len(self.state.items) - 1
        )

    def _refresh_mode_buttons(self) -> None:
        self.pdf_mode_button.setChecked(self.state.order_mode == ORDER_MODE_PDF)
        self.page_mode_button.setChecked(self.state.order_mode == ORDER_MODE_PAGE)
        if self.state.order_mode == ORDER_MODE_PAGE:
            self.mode_summary_label.setText(
                "Page order mode controls actual merged output. Select page row, move up/down, interleave pages from any source PDF."
            )
            self.page_mode_note.show()
        else:
            self.mode_summary_label.setText(
                "PDF order mode controls actual merge output now. Reorder whole documents in left queue."
            )
            self.page_mode_note.hide()

    def _refresh_page_table(self) -> None:
        selected_row = self._selected_page_row()
        pages = self.state.pages
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
        self.page_table.setColumnHidden(3, self.state.order_mode != ORDER_MODE_PAGE)
        if 0 <= selected_row < len(pages):
            self.page_table.selectRow(selected_row)
        elif len(pages) > 0:
            if self.state.order_mode == ORDER_MODE_PAGE:
                self.page_table.selectRow(0)
            else:
                self.page_table.clearSelection()

    def _move_selected_page(self, delta: int) -> None:
        if self.state.order_mode != ORDER_MODE_PAGE:
            self._set_status("Switch to Page Order mode to move individual pages.", "error")
            return

        row = self._selected_page_row()
        if row < 0:
            self._set_status("Select page row first.", "error")
            return

        target_row = row + delta
        if not self.state.move_page(row, target_row):
            return

        self._refresh_page_table()
        self.page_table.selectRow(target_row)
        self._refresh_page_move_buttons()
        self._set_status("Page output order updated.", "success")

    def _refresh_output_path(self) -> None:
        current_text = self.output_path_edit.text().strip()
        desired_text = ""
        if self.state.output_path is not None:
            desired_text = str(self.state.output_path)
        elif not current_text and self.state.items:
            suggested = self.service.suggested_output_path(self.state.items)
            if suggested is not None:
                self.state.output_path = suggested
                desired_text = str(suggested)

        if desired_text != current_text:
            with QSignalBlocker(self.output_path_edit):
                self.output_path_edit.setText(desired_text)

    def _refresh_merge_button(self) -> None:
        self.merge_button.setEnabled(bool(self.state.items) and self.state.output_path is not None)

    def _refresh_page_move_buttons(self) -> None:
        selected_row = self._selected_page_row()
        page_mode_active = self.state.order_mode == ORDER_MODE_PAGE
        has_selection = 0 <= selected_row < len(self.state.pages)
        self.page_move_up_button.setEnabled(page_mode_active and has_selection and selected_row > 0)
        self.page_move_down_button.setEnabled(
            page_mode_active
            and has_selection
            and selected_row < len(self.state.pages) - 1
        )

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
        pdf_paths = [path for path in paths if path.suffix.lower() == ".pdf"]
        if pdf_paths:
            self._add_pdf_paths(pdf_paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)
