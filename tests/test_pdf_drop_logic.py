from __future__ import annotations

from pathlib import Path

from tools.pdf_tools.widget import classify_split_drop_paths


def test_classify_split_drop_paths_picks_first_pdf_and_folder(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    selection = classify_split_drop_paths([source_pdf, output_dir])

    assert selection.source_pdf_path == source_pdf.resolve()
    assert selection.output_dir_path == output_dir.resolve()
    assert selection.skipped_items == []


def test_classify_split_drop_paths_ignores_extra_pdf_and_non_pdf(tmp_path: Path) -> None:
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    note_file = tmp_path / "note.txt"
    first_pdf.write_bytes(b"%PDF-1.4\n")
    second_pdf.write_bytes(b"%PDF-1.4\n")
    note_file.write_text("hello", encoding="utf-8")

    selection = classify_split_drop_paths([first_pdf, second_pdf, note_file])

    assert selection.source_pdf_path == first_pdf.resolve()
    assert selection.output_dir_path is None
    assert selection.skipped_items == [
        "second.pdf: extra PDF ignored",
        "note.txt: not a PDF",
    ]


def test_classify_split_drop_paths_reports_missing_items(tmp_path: Path) -> None:
    missing_pdf = tmp_path / "missing.pdf"

    selection = classify_split_drop_paths([missing_pdf])

    assert selection.source_pdf_path is None
    assert selection.output_dir_path is None
    assert selection.skipped_items == ["missing.pdf: missing item"]
