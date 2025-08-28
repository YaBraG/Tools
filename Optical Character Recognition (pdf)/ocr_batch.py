
#!/usr/bin/env python3
"""
Batch OCR for scanned PDFs (Spanish-focused) using OCRmyPDF + Tesseract.

Example usage (Windows PowerShell):
    python ocr_batch.py --input "C:\data\scans" --outdir "C:\data\searchable" --lang "spa+eng" --jobs 4

Example usage (macOS/Linux):
    python3 ocr_batch.py --input "/Users/me/scans" --outdir "/Users/me/searchable" --lang "spa+eng"

Dependencies:
    1) Tesseract OCR (install and include language packs, e.g., spa for Spanish)
       - Windows: https://github.com/UB-Mannheim/tesseract/wiki
       - Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-spa
       - macOS (Homebrew): brew install tesseract; brew install tesseract-lang

    2) OCRmyPDF (Python):
       pip install ocrmypdf

What this script does (high quality settings):
    - Ensures a hidden text layer even if the PDF already has text (--force-ocr).
    - Auto-rotation and deskew to fix crooked scans.
    - Remove background noise for cleaner visual appearance.
    - Optimize PDF size using --optimize 3 (lossless/reasonable compression).
    - Creates PDF/A-2b compliant outputs for archival/search stability.
    - Logs progress to a per-file .log alongside the output PDF.
"""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def build_ocrmypdf_cmd(
    input_pdf: Path,
    output_pdf: Path,
    lang: str,
    jobs: int,
    tesseract_timeout: int,
    max_image_mp: int,
    skip_text: bool,
    sidecar: bool,
    pdfa: str,
    extra_tesseract_cfg: str | None,
    keep_temporary_files: bool,
    optimize: int,
    clean_final: bool,
    remove_background: bool,
    rotate_pages: bool,
    deskew: bool,
    force_ocr: bool,
) -> list[str]:
    """
    Construct a robust OCRmyPDF command with quality/cleanup options.
    """
    cmd = [
        sys.executable, "-m", "ocrmypdf",
        "--language", lang,
        "--jobs", str(jobs),
        "--tesseract-timeout", str(tesseract_timeout),
        "--max-image-mpixels", str(max_image_mp),
        "--optimize", str(optimize),
        "--output-type", pdfa,           # pdfa-2 default
        "--pdf-renderer", "sandwich",    # keep original look + overlay text
    ]

    # Cleanup / quality improvements
    if rotate_pages:
        cmd.append("--rotate-pages")
    if deskew:
        cmd.append("--deskew")
    if remove_background:
        cmd.append("--remove-background")
    if clean_final:
        cmd.append("--clean-final")
    if force_ocr:
        cmd.append("--force-ocr")
    if skip_text:
        cmd.append("--skip-text")

    if sidecar:
        # Writes recognized text to a .txt file next to output PDF
        sidecar_path = output_pdf.with_suffix(".txt")
        cmd += ["--sidecar", str(sidecar_path)]

    if extra_tesseract_cfg:
        # Allow passing a user-supplied Tesseract config file for psm/oem tweaks
        cmd += ["--tesseract-config", extra_tesseract_cfg]

    if keep_temporary_files:
        cmd.append("--keep-temporary-files")

    # Input/Output at end
    cmd += [str(input_pdf), str(output_pdf)]
    return cmd


def find_pdfs(input_path: Path) -> list[Path]:
    """
    Return a list of PDF files. If input_path is a file, return [input_path].
    If it's a folder, recurse and return all *.pdf found.
    """
    if input_path.is_file():
        return [input_path]
    pdfs = sorted([p for p in input_path.rglob("*.pdf") if p.is_file()])
    return pdfs


def run_ocr_for_file(cmd: list[str], log_path: Path) -> int:
    """
    Run OCRmyPDF for a single file, streaming output to a log.
    Returns the process return code.
    """
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] Starting OCR:\n")
        log.write("Command:\n")
        log.write(" ".join(shlex.quote(c) for c in cmd) + "\n\n")
        log.flush()

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        # Stream logs
        for line in proc.stdout:
            log.write(line)
        proc.wait()

        log.write(f"\n[{datetime.now().isoformat(sep=' ', timespec='seconds')}] Finished with code {proc.returncode}\n")
        return proc.returncode


def main():
    parser = argparse.ArgumentParser(description="Batch OCR scanned PDFs into searchable PDFs (Spanish-focused).")
    parser.add_argument("--input", required=True, help="Path to a PDF file or a folder containing PDFs.")
    parser.add_argument("--outdir", required=True, help="Output folder for searchable PDFs.")
    parser.add_argument("--lang", default="spa+eng", help="Tesseract language(s). Default: spa+eng (Spanish+English).")
    parser.add_argument("--jobs", type=int, default=max(os.cpu_count() - 1, 1), help="Parallel OCR workers. Default: CPU-1.")
    parser.add_argument("--timeout", type=int, default=1800, help="Tesseract timeout per page (seconds). Default: 1800 (30 min).")
    parser.add_argument("--max-mp", type=int, default=256, help="Max image megapixels to process. Default: 256.")
    parser.add_argument("--psm-oem-config", default=None,
                        help="Optional path to a Tesseract config file to control PSM/OEM (e.g., set psm=1 for multi-column).")
    parser.add_argument("--skip-text", action="store_true",
                        help="Skip pages that already contain searchable text (faster). Omit to guarantee re-OCR (--force-ocr default).")
    parser.add_argument("--sidecar", action="store_true", help="Also write recognized text to a .txt file next to each output PDF.")
    parser.add_argument("--pdfa", default="pdfa-2", choices=["pdf", "pdfa-1", "pdfa-2", "pdfa-3"],
                        help="Output type. Default: pdfa-2 (recommended).")
    parser.add_argument("--optimize", type=int, default=3, choices=[0,1,2,3], help="PDF optimization level. Default: 3 (max).")
    parser.add_argument("--clean-final", action="store_true",
                        help="Extra page cleaning after OCR. Can improve low-quality scans.")
    parser.add_argument("--remove-background", action="store_true",
                        help="Remove noisy backgrounds for better compression/readability.")
    parser.add_argument("--no-rotate", action="store_true", help="Disable auto-rotation.")
    parser.add_argument("--no-deskew", action="store_true", help="Disable deskew.")
    parser.add_argument("--no-force", action="store_true", help="Do NOT force OCR if text is detected.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary working files for debugging.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output if it already exists.")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    pdfs = find_pdfs(input_path)
    if not pdfs:
        print("No PDFs found.", file=sys.stderr)
        sys.exit(2)

    # Defaults tuned for high accuracy on messy scans
    rotate_pages = not args.no_rotate
    deskew = not args.no_deskew
    force_ocr = not args.no_force

    # Process files one-by-one to limit memory spikes on huge PDFs
    total = len(pdfs)
    failures = []

    for i, pdf in enumerate(pdfs, start=1):
        rel = pdf.name
        out_pdf = outdir / rel
        out_pdf.parent.mkdir(parents=True, exist_ok=True)

        # Skip if already exists (unless overwrite)
        if out_pdf.exists() and not args.overwrite:
            print(f"[{i}/{total}] Skipping existing: {out_pdf}")
            continue

        # Log path next to output
        log_path = out_pdf.with_suffix(".log")

        print(f"[{i}/{total}] OCR: {pdf} -> {out_pdf}")
        cmd = build_ocrmypdf_cmd(
            input_pdf=pdf,
            output_pdf=out_pdf,
            lang=args.lang,
            jobs=args.jobs,
            tesseract_timeout=args.timeout,
            max_image_mp=args.max_mp,
            skip_text=args.skip_text,
            sidecar=args.sidecar,
            pdfa=args.pdfa,
            extra_tesseract_cfg=args.psm_oem_config,
            keep_temporary_files=args.keep_temp,
            optimize=args.optimize,
            clean_final=args.clean_final,
            remove_background=args.remove_background,
            rotate_pages=rotate_pages,
            deskew=deskew,
            force_ocr=force_ocr
        )

        # Run and log
        code = run_ocr_for_file(cmd, log_path)
        if code != 0:
            failures.append((pdf, code))
            # If partial file exists and we failed, remove it to avoid confusion
            try:
                if out_pdf.exists():
                    out_pdf.unlink()
            except Exception:
                pass

    if failures:
        print("\nSome files failed:")
        for pdf, code in failures:
            print(f" - {pdf} (exit code {code})")
        sys.exit(1)

    print("\nAll done!")
    sys.exit(0)


if __name__ == "__main__":
    main()



