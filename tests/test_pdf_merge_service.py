from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter

from shared.tool_base import ToolContext
from tools.pdf_tools.models import PdfMergeState
from tools.pdf_tools.service import PdfMergeService


def _make_pdf(path: Path, page_sizes: list[tuple[float, float]]) -> None:
    writer = PdfWriter()
    for width, height in page_sizes:
        writer.add_blank_page(width=width, height=height)
    with path.open("wb") as file:
        writer.write(file)


def test_merge_pdfs_keeps_page_order_and_sizes(tmp_path: Path) -> None:
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    output_pdf = tmp_path / "merged.pdf"

    _make_pdf(first_pdf, [(300, 500), (301, 501)])
    _make_pdf(second_pdf, [(612, 792)])

    context = ToolContext(
        app_name="Tools",
        root_dir=tmp_path,
        assets_dir=tmp_path,
        tools_dir=tmp_path,
    )
    service = PdfMergeService(context)

    first_item = service.inspect_pdf(first_pdf, document_id="doc-1")
    second_item = service.inspect_pdf(second_pdf, document_id="doc-2")

    merged_path = service.merge_pdfs([first_item, second_item], output_pdf)

    reader = PdfReader(str(merged_path))
    sizes = [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in reader.pages
    ]
    assert len(reader.pages) == 3
    assert sizes == [(300.0, 500.0), (301.0, 501.0), (612.0, 792.0)]


def test_merge_page_sequence_uses_custom_page_order(tmp_path: Path) -> None:
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    output_pdf = tmp_path / "custom-order.pdf"

    _make_pdf(first_pdf, [(300, 500), (301, 501)])
    _make_pdf(second_pdf, [(612, 792), (700, 900)])

    context = ToolContext(
        app_name="Tools",
        root_dir=tmp_path,
        assets_dir=tmp_path,
        tools_dir=tmp_path,
    )
    service = PdfMergeService(context)
    state = PdfMergeState()

    first_item = service.inspect_pdf(first_pdf, document_id="doc-1")
    second_item = service.inspect_pdf(second_pdf, document_id="doc-2")
    state.add_item(first_item)
    state.add_item(second_item)

    assert state.move_page(3, 1)
    assert state.move_page(2, 3)

    merged_path = service.merge_page_sequence(state.pages, output_pdf)

    reader = PdfReader(str(merged_path))
    sizes = [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in reader.pages
    ]
    assert sizes == [
        (300.0, 500.0),
        (700.0, 900.0),
        (612.0, 792.0),
        (301.0, 501.0),
    ]


def test_merge_page_sequence_supports_interleaving_sources(tmp_path: Path) -> None:
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    output_pdf = tmp_path / "interleaved.pdf"

    _make_pdf(first_pdf, [(300, 500), (301, 501)])
    _make_pdf(second_pdf, [(612, 792), (613, 793)])

    context = ToolContext(
        app_name="Tools",
        root_dir=tmp_path,
        assets_dir=tmp_path,
        tools_dir=tmp_path,
    )
    service = PdfMergeService(context)

    first_item = service.inspect_pdf(first_pdf, document_id="doc-1")
    second_item = service.inspect_pdf(second_pdf, document_id="doc-2")
    state = PdfMergeState()
    state.add_item(first_item)
    state.add_item(second_item)
    state.pages = [
        state.pages[0],
        state.pages[2],
        state.pages[1],
        state.pages[3],
    ]
    state.renumber_pages_from_current_order()

    merged_path = service.merge_page_sequence(state.pages, output_pdf)
    reader = PdfReader(str(merged_path))
    sizes = [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in reader.pages
    ]
    assert sizes == [
        (300.0, 500.0),
        (612.0, 792.0),
        (301.0, 501.0),
        (613.0, 793.0),
    ]


def test_removing_pdf_removes_its_pages_from_page_model(tmp_path: Path) -> None:
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"

    _make_pdf(first_pdf, [(300, 500), (301, 501)])
    _make_pdf(second_pdf, [(612, 792)])

    context = ToolContext(
        app_name="Tools",
        root_dir=tmp_path,
        assets_dir=tmp_path,
        tools_dir=tmp_path,
    )
    service = PdfMergeService(context)
    state = PdfMergeState()

    first_item = service.inspect_pdf(first_pdf, document_id="doc-1")
    second_item = service.inspect_pdf(second_pdf, document_id="doc-2")
    state.add_item(first_item)
    state.add_item(second_item)

    removed = state.remove_item_at(0)

    assert removed.document_id == "doc-1"
    assert len(state.pages) == 1
    assert state.pages[0].source_document_id == "doc-2"
    assert state.pages[0].output_order == 1
