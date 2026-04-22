from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from shared.tool_base import ToolContext
from tools.pdf_tools.models import PdfMergeItem, PdfPageItem, PdfPageRange


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

    def parse_page_ranges(
        self,
        ranges_text: str,
        *,
        page_count: int,
    ) -> list[PdfPageRange]:
        cleaned = ranges_text.strip()
        if not cleaned:
            raise PdfMergeError("Enter at least one page range.")

        ranges: list[PdfPageRange] = []
        seen_pages: set[int] = set()
        for token in cleaned.split(","):
            part = token.strip()
            if not part:
                raise PdfMergeError("Page ranges contain an empty segment.")

            if "-" in part:
                start_text, end_text = [piece.strip() for piece in part.split("-", 1)]
                if not start_text or not end_text:
                    raise PdfMergeError(f"Invalid page range: {part}")
                if not start_text.isdigit() or not end_text.isdigit():
                    raise PdfMergeError(f"Invalid page range: {part}")
                start_page = int(start_text)
                end_page = int(end_text)
                if start_page == 0 or end_page == 0:
                    raise PdfMergeError("Page numbers start at 1.")
                if start_page > end_page:
                    raise PdfMergeError(f"Range start must be before end: {part}")
            else:
                if not part.isdigit():
                    raise PdfMergeError(f"Invalid page value: {part}")
                start_page = int(part)
                end_page = start_page
                if start_page == 0:
                    raise PdfMergeError("Page numbers start at 1.")

            if end_page > page_count:
                raise PdfMergeError(
                    f"Page range {part} exceeds source page count of {page_count}."
                )

            page_range = PdfPageRange(start_page=start_page, end_page=end_page)
            duplicates = seen_pages.intersection(page_range.page_numbers)
            if duplicates:
                duplicate_list = ", ".join(str(page) for page in sorted(duplicates))
                raise PdfMergeError(
                    f"Page ranges overlap or repeat pages: {duplicate_list}"
                )

            seen_pages.update(page_range.page_numbers)
            ranges.append(page_range)

        return ranges

    def split_every_page(
        self,
        source_item: PdfMergeItem,
        output_dir: Path,
    ) -> tuple[Path, ...]:
        ranges = [
            PdfPageRange(start_page=page_number, end_page=page_number)
            for page_number in range(1, source_item.page_count + 1)
        ]
        return self.split_by_ranges(source_item, output_dir, ranges)

    def split_by_ranges(
        self,
        source_item: PdfMergeItem,
        output_dir: Path,
        ranges: list[PdfPageRange],
    ) -> tuple[Path, ...]:
        if not ranges:
            raise PdfMergeError("Add at least one page range before split.")

        resolved_path = self._validate_source_path(source_item.source_path)
        resolved_output_dir = self._validate_output_dir(output_dir)
        file_padding = max(3, len(str(source_item.page_count)))

        planned_outputs = [
            resolved_output_dir / self._split_output_name(
                resolved_path.stem,
                page_range,
                file_padding=file_padding,
            )
            for page_range in ranges
        ]
        duplicates = {
            path.name for path in planned_outputs if planned_outputs.count(path) > 1
        }
        if duplicates:
            duplicate_text = ", ".join(sorted(duplicates))
            raise PdfMergeError(f"Split output names would collide: {duplicate_text}")
        for output_path in planned_outputs:
            if output_path.exists():
                raise PdfMergeError(
                    f"Split output already exists: {output_path}"
                )

        handle = resolved_path.open("rb")
        try:
            reader = PdfReader(handle)
            if len(reader.pages) != source_item.page_count:
                raise PdfMergeError(
                    f"Source PDF changed since load: {resolved_path.name}"
                )

            written_paths: list[Path] = []
            for page_range, output_path in zip(ranges, planned_outputs, strict=True):
                writer = PdfWriter()
                for page_number in page_range.page_numbers:
                    writer.add_page(reader.pages[page_number - 1])
                with output_path.open("wb") as output_file:
                    writer.write(output_file)
                written_paths.append(output_path)
        except (OSError, PdfReadError) as error:
            raise PdfMergeError(
                f"Split failed for source PDF: {resolved_path.name}"
            ) from error
        finally:
            handle.close()

        return tuple(written_paths)

    @staticmethod
    def suggested_output_path(items: list[PdfMergeItem]) -> Path | None:
        if not items:
            return None
        first_path = items[0].source_path
        return first_path.with_name(f"{first_path.stem}-merged.pdf")

    @staticmethod
    def suggested_split_output_dir(source_item: PdfMergeItem | None) -> Path | None:
        if source_item is None:
            return None
        return source_item.source_path.parent

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

    @staticmethod
    def _validate_output_dir(output_dir: Path) -> Path:
        normalized_output_dir = output_dir.expanduser()
        if not normalized_output_dir.exists():
            raise PdfMergeError(
                f"Output folder does not exist: {normalized_output_dir}"
            )
        if not normalized_output_dir.is_dir():
            raise PdfMergeError(
                f"Output path is not a folder: {normalized_output_dir}"
            )
        return normalized_output_dir.resolve()

    @staticmethod
    def _split_output_name(
        source_stem: str,
        page_range: PdfPageRange,
        *,
        file_padding: int,
    ) -> str:
        if page_range.start_page == page_range.end_page:
            page_text = f"{page_range.start_page:0{file_padding}d}"
            return f"{source_stem}-page-{page_text}.pdf"

        start_text = f"{page_range.start_page:0{file_padding}d}"
        end_text = f"{page_range.end_page:0{file_padding}d}"
        return f"{source_stem}-pages-{start_text}-{end_text}.pdf"
