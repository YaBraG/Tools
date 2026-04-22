from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from shared.tool_base import ToolContext
from tools.pdf_tools.service import PdfMergeError, PdfMergeService


def _make_pdf(path: Path, page_sizes: list[tuple[float, float]]) -> None:
    writer = PdfWriter()
    for width, height in page_sizes:
        writer.add_blank_page(width=width, height=height)
    with path.open("wb") as file:
        writer.write(file)


def _make_image(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    image = Image.new("RGB", size, color)
    image.save(path)


def _make_service(tmp_path: Path) -> PdfMergeService:
    return PdfMergeService(
        ToolContext(
            app_name="Tools",
            root_dir=tmp_path,
            assets_dir=tmp_path,
            tools_dir=tmp_path,
        )
    )


def test_convert_pdf_to_png_creates_one_image_per_page(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    output_dir = tmp_path / "images"
    output_dir.mkdir()
    _make_pdf(source_pdf, [(300, 500), (301, 501)])

    service = _make_service(tmp_path)
    item = service.inspect_pdf(source_pdf, document_id="doc-1")

    output_paths = service.convert_pdf_to_images(
        item,
        output_dir,
        image_format="png",
        dpi=200,
    )

    assert [path.name for path in output_paths] == [
        "source-page-001.png",
        "source-page-002.png",
    ]
    assert all(path.exists() for path in output_paths)


def test_convert_pdf_to_jpg_creates_one_image_per_page(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    output_dir = tmp_path / "images"
    output_dir.mkdir()
    _make_pdf(source_pdf, [(300, 500), (301, 501), (302, 502)])

    service = _make_service(tmp_path)
    item = service.inspect_pdf(source_pdf, document_id="doc-1")

    output_paths = service.convert_pdf_to_images(
        item,
        output_dir,
        image_format="jpg",
        dpi=200,
    )

    assert [path.name for path in output_paths] == [
        "source-page-001.jpg",
        "source-page-002.jpg",
        "source-page-003.jpg",
    ]
    assert all(path.exists() for path in output_paths)


def test_convert_images_to_pdf_creates_expected_page_count(tmp_path: Path) -> None:
    first_image = tmp_path / "first.png"
    second_image = tmp_path / "second.jpg"
    output_pdf = tmp_path / "images.pdf"
    _make_image(first_image, (300, 500), (255, 0, 0))
    _make_image(second_image, (320, 520), (0, 255, 0))

    service = _make_service(tmp_path)
    first_item = service.inspect_image(first_image, image_id="img-1")
    second_item = service.inspect_image(second_image, image_id="img-2")

    pdf_path = service.convert_images_to_pdf([first_item, second_item], output_pdf)

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 2


def test_convert_existing_outputs_fail_safely(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    output_dir = tmp_path / "images"
    output_dir.mkdir()
    _make_pdf(source_pdf, [(300, 500)])
    existing_image = output_dir / "source-page-001.png"
    existing_image.write_bytes(b"already-here")

    first_image = tmp_path / "first.png"
    _make_image(first_image, (300, 500), (255, 0, 0))
    existing_pdf = tmp_path / "images.pdf"
    existing_pdf.write_bytes(b"already-here")

    service = _make_service(tmp_path)
    pdf_item = service.inspect_pdf(source_pdf, document_id="doc-1")
    image_item = service.inspect_image(first_image, image_id="img-1")

    with pytest.raises(PdfMergeError, match="already exists"):
        service.convert_pdf_to_images(
            pdf_item,
            output_dir,
            image_format="png",
            dpi=200,
        )

    with pytest.raises(PdfMergeError, match="already exists"):
        service.convert_images_to_pdf([image_item], existing_pdf)


def test_convert_invalid_file_types_fail_cleanly(tmp_path: Path) -> None:
    bad_image = tmp_path / "bad.txt"
    bad_image.write_text("not an image", encoding="utf-8")

    service = _make_service(tmp_path)

    with pytest.raises(PdfMergeError, match="Unsupported image type"):
        service.inspect_image(bad_image, image_id="bad-1")
