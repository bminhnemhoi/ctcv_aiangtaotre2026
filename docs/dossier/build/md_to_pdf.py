"""Render a standalone Markdown document to DOCX and PDF (A4, Times New Roman).

Used for dossier components that are not the MẪU 3 form itself, e.g. the AI declaration:

    uv run python docs/dossier/build/md_to_pdf.py docs/dossier/out/06_KeKhaiAI.md

The conversion reuses ``md2docx.render_markdown`` (tables, lists, headings, bold) and the PDF
export of ``build_dossier`` (LibreOffice, else Microsoft Word on Windows).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_dossier import convert_to_pdf  # noqa: E402
from md2docx import RenderContext, render_markdown  # noqa: E402

BODY_FONT = "Times New Roman"
BODY_SIZE_PT = 12
MARGIN_CM = 2.0


def _new_document() -> Document:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(MARGIN_CM))
    style = doc.styles["Normal"]
    style.font.name = BODY_FONT
    style.font.size = Pt(BODY_SIZE_PT)
    return doc


def convert(
    markdown_path: Path, out_dir: Path, *, pdf: bool = True, keep_title: bool = False
) -> tuple[Path, Path | None]:
    """Write ``<stem>.docx`` (and ``<stem>.pdf``) next to each other in ``out_dir``.

    ``keep_title`` renders the H1 as a centred title instead of dropping it.
    """
    doc = _new_document()
    ctx = RenderContext(
        base_dir=markdown_path.parent,
        figures_dir=markdown_path.parent,
        skip_h1=not keep_title,
    )
    report = render_markdown(doc, markdown_path.read_text(encoding="utf-8"), ctx)
    body = doc.element.body
    anchor = body[-1]  # keep the trailing sectPr last
    for element in report.elements:
        anchor.addprevious(element)
    out_dir.mkdir(parents=True, exist_ok=True)
    docx_path = out_dir / f"{markdown_path.stem}.docx"
    doc.save(str(docx_path))
    pdf_path = convert_to_pdf(docx_path, out_dir)[0] if pdf else None
    return docx_path, pdf_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument(
        "--out", type=Path, default=None, help="thư mục đầu ra (mặc định: cùng file)"
    )
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args(argv)
    docx_path, pdf_path = convert(
        args.markdown, args.out or args.markdown.parent, pdf=not args.no_pdf
    )
    print(f"DOCX: {docx_path}")
    print(f"PDF:  {pdf_path or 'chưa xuất được (cần LibreOffice hoặc Microsoft Word)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
