from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from shared.tool_base import ToolContext
from tools.pdf_tools.models import PdfMergeItem, PdfPageItem


class PdfMergeError(ValueError):
    """Raised when PDF merge cannot complete safely."""


class PdfMergeService:
    def __init__(self, context: ToolContext) -> None:
        self.context = context

    def inspect_pdf(self, source_path: Path, *, document_id: str) -> PdfMergeItem:
        resolved_path = self._validate_source_path(source_path)
        try:
            reader = PdfReader(str(resolved_path))
        except (OSError, PdfReadError) as error:
            raise PdfMergeError(
                f"Could not read PDF file: {resolved_path.name}"
            ) from error

        page_count = len(reader.pages)
        if page_count <= 0:
            raise PdfMergeError(f"PDF has no pages: {resolved_path.name}")

        return PdfMergeItem(
            document_id=document_id,
            source_path=resolved_path,
            display_name=resolved_path.name,
            page_count=page_count,
        )

    def merge_pdfs(
        self,
        items: list[PdfMergeItem],
        output_path: Path,
    ) -> Path:
        return self.merge_page_sequence(
            pages=[
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
                        for item in items
                        for page_index in range(item.page_count)
                    ),
                    start=1,
                )
            ],
            output_path=output_path,
        )

    def merge_page_sequence(
        self,
        pages: list[PdfPageItem],
        output_path: Path,
    ) -> Path:
        if not pages:
            raise PdfMergeError("Add at least one PDF before merge.")

        normalized_output = self._validate_output_path(output_path)
        writer = PdfWriter()
        readers_by_path: dict[Path, PdfReader] = {}
        open_handles: list[object] = []
        try:
            for page in pages:
                resolved_path = self._validate_source_path(page.source_path)
                reader = readers_by_path.get(resolved_path)
                if reader is None:
                    handle = resolved_path.open("rb")
                    open_handles.append(handle)
                    reader = PdfReader(handle)
                    if len(reader.pages) <= 0:
                        raise PdfMergeError(f"PDF has no pages: {resolved_path.name}")
                    readers_by_path[resolved_path] = reader

                if not (0 <= page.original_page_index < len(reader.pages)):
                    raise PdfMergeError(
                        f"Page {page.original_page_number} is out of range for {resolved_path.name}"
                    )

                writer.add_page(reader.pages[page.original_page_index])

            with normalized_output.open("wb") as output_file:
                writer.write(output_file)
        except (OSError, PdfReadError) as error:
            raise PdfMergeError(
                f"Merge failed for output file: {normalized_output}"
            ) from error
        finally:
            for handle in open_handles:
                handle.close()

        return normalized_output

    @staticmethod
    def suggested_output_path(items: list[PdfMergeItem]) -> Path | None:
        if not items:
            return None
        first_path = items[0].source_path
        return first_path.with_name(f"{first_path.stem}-merged.pdf")

    @staticmethod
    def _validate_source_path(source_path: Path) -> Path:
        resolved_path = source_path.expanduser().resolve()
        if not resolved_path.exists() or not resolved_path.is_file():
            raise PdfMergeError(f"PDF file not found: {resolved_path}")
        if resolved_path.suffix.lower() != ".pdf":
            raise PdfMergeError(f"Unsupported file type: {resolved_path.name}")
        return resolved_path

    @staticmethod
    def _validate_output_path(output_path: Path) -> Path:
        normalized_output = output_path.expanduser()
        if normalized_output.suffix.lower() != ".pdf":
            normalized_output = normalized_output.with_suffix(".pdf")

        if normalized_output.exists():
            raise PdfMergeError(f"Output file already exists: {normalized_output}")
        if not normalized_output.parent.exists():
            raise PdfMergeError(
                f"Output folder does not exist: {normalized_output.parent}"
            )
        return normalized_output
