from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from shared.tool_base import ToolContext
from tools.pdf_tools.service import PdfMergeError, PdfMergeService


def _make_pdf(path: Path, page_sizes: list[tuple[float, float]]) -> None:
    writer = PdfWriter()
    for width, height in page_sizes:
        writer.add_blank_page(width=width, height=height)
    with path.open("wb") as file:
        writer.write(file)


def _make_service(tmp_path: Path) -> PdfMergeService:
    return PdfMergeService(
        ToolContext(
            app_name="Tools",
            root_dir=tmp_path,
            assets_dir=tmp_path,
            tools_dir=tmp_path,
        )
    )


def test_split_every_page_creates_one_pdf_per_page(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    output_dir = tmp_path / "split-output"
    output_dir.mkdir()
    _make_pdf(source_pdf, [(300, 500), (301, 501), (302, 502)])

    service = _make_service(tmp_path)
    item = service.inspect_pdf(source_pdf, document_id="doc-1")

    output_paths = service.split_every_page(item, output_dir)

    assert [path.name for path in output_paths] == [
        "source-page-001.pdf",
        "source-page-002.pdf",
        "source-page-003.pdf",
    ]
    assert all(path.exists() for path in output_paths)


def test_split_custom_ranges_creates_predictable_outputs(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    output_dir = tmp_path / "split-output"
    output_dir.mkdir()
    _make_pdf(source_pdf, [(300, 500), (301, 501), (302, 502), (303, 503), (304, 504)])

    service = _make_service(tmp_path)
    item = service.inspect_pdf(source_pdf, document_id="doc-1")
    ranges = service.parse_page_ranges("1-3,5", page_count=item.page_count)

    output_paths = service.split_by_ranges(item, output_dir, ranges)

    assert [path.name for path in output_paths] == [
        "source-pages-001-003.pdf",
        "source-page-005.pdf",
    ]
    first_reader = PdfReader(str(output_paths[0]))
    second_reader = PdfReader(str(output_paths[1]))
    assert len(first_reader.pages) == 3
    assert len(second_reader.pages) == 1


def test_range_parser_supports_pages_and_ranges(tmp_path: Path) -> None:
    service = _make_service(tmp_path)

    ranges = service.parse_page_ranges("1-3,5,8-10", page_count=10)

    assert [(page_range.start_page, page_range.end_page) for page_range in ranges] == [
        (1, 3),
        (5, 5),
        (8, 10),
    ]


@pytest.mark.parametrize(
    "ranges_text,page_count,error_text",
    [
        ("", 5, "Enter at least one page range."),
        ("a", 5, "Invalid page value"),
        ("0", 5, "Page numbers start at 1."),
        ("6", 5, "exceeds source page count"),
        ("5-2", 5, "Range start must be before end"),
    ],
)
def test_invalid_ranges_fail_cleanly(
    tmp_path: Path,
    ranges_text: str,
    page_count: int,
    error_text: str,
) -> None:
    service = _make_service(tmp_path)

    with pytest.raises(PdfMergeError, match=error_text):
        service.parse_page_ranges(ranges_text, page_count=page_count)


def test_split_preserves_page_size_and_order(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    output_dir = tmp_path / "split-output"
    output_dir.mkdir()
    _make_pdf(source_pdf, [(300, 500), (301, 501), (302, 502), (303, 503)])

    service = _make_service(tmp_path)
    item = service.inspect_pdf(source_pdf, document_id="doc-1")
    ranges = service.parse_page_ranges("2-3,4", page_count=item.page_count)

    output_paths = service.split_by_ranges(item, output_dir, ranges)

    first_reader = PdfReader(str(output_paths[0]))
    second_reader = PdfReader(str(output_paths[1]))
    first_sizes = [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in first_reader.pages
    ]
    second_sizes = [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in second_reader.pages
    ]
    assert first_sizes == [(301.0, 501.0), (302.0, 502.0)]
    assert second_sizes == [(303.0, 503.0)]
