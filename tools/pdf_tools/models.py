from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ORDER_MODE_PDF = "pdf"
ORDER_MODE_PAGE = "page"
ORDER_MODES = (ORDER_MODE_PDF, ORDER_MODE_PAGE)


@dataclass(frozen=True)
class PdfMergeItem:
    document_id: str
    source_path: Path
    display_name: str
    page_count: int


@dataclass(frozen=True)
class PdfPageItem:
    page_id: str
    source_path: Path
    source_document_id: str
    source_document_name: str
    original_page_index: int
    output_order: int

    @property
    def original_page_number(self) -> int:
        return self.original_page_index + 1


@dataclass
class PdfMergeState:
    items: list[PdfMergeItem] = field(default_factory=list)
    pages: list[PdfPageItem] = field(default_factory=list)
    order_mode: str = ORDER_MODE_PDF
    output_path: Path | None = None
    last_output_path: Path | None = None

    def add_item(self, item: PdfMergeItem) -> None:
        self.items.append(item)
        self.rebuild_pages()

    def remove_item_at(self, index: int) -> PdfMergeItem:
        removed = self.items.pop(index)
        self.rebuild_pages()
        return removed

    def move_item(self, source_index: int, target_index: int) -> bool:
        if not (0 <= source_index < len(self.items)):
            return False
        if not (0 <= target_index < len(self.items)):
            return False
        if source_index == target_index:
            return False
        item = self.items.pop(source_index)
        self.items.insert(target_index, item)
        self.rebuild_pages()
        return True

    def rebuild_pages(self) -> None:
        self.pages = [
            PdfPageItem(
                page_id=f"{item.document_id}:{page_index}",
                source_path=item.source_path,
                source_document_id=item.document_id,
                source_document_name=item.display_name,
                original_page_index=page_index,
                output_order=output_order,
            )
            for output_order, (item, page_index) in enumerate(
                (
                    (item, page_index)
                    for item in self.items
                    for page_index in range(item.page_count)
                ),
                start=1,
            )
        ]

    def move_page(self, source_index: int, target_index: int) -> bool:
        if not (0 <= source_index < len(self.pages)):
            return False
        if not (0 <= target_index < len(self.pages)):
            return False
        if source_index == target_index:
            return False

        page = self.pages.pop(source_index)
        self.pages.insert(target_index, page)
        self._renumber_pages()
        return True

    def renumber_pages_from_current_order(self) -> None:
        self._renumber_pages()

    @property
    def total_pages(self) -> int:
        return sum(item.page_count for item in self.items)

    def _renumber_pages(self) -> None:
        self.pages = [
            PdfPageItem(
                page_id=page.page_id,
                source_path=page.source_path,
                source_document_id=page.source_document_id,
                source_document_name=page.source_document_name,
                original_page_index=page.original_page_index,
                output_order=index,
            )
            for index, page in enumerate(self.pages, start=1)
        ]
