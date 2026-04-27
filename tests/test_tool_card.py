from __future__ import annotations

from app.core.tool_registry import ToolManifest
from app.ui.widgets.tool_card import ToolCard


def test_tool_card_tags_do_not_include_version_prefix() -> None:
    manifest = ToolManifest(
        id="pdf_tools",
        name="PDF Tools",
        description="PDF workflows",
        entry_point="tools.pdf_tools.tool:PdfToolsTool",
        version="0.4.0",
        category="PDF",
        tags=("pdf", "merge", "split", "convert"),
    )

    assert ToolCard._format_tags(manifest) == "pdf, merge, split, convert"


def test_tool_card_uses_category_when_no_tags_exist() -> None:
    manifest = ToolManifest(
        id="demo",
        name="Demo",
        description="Demo tool",
        entry_point="demo.tool:DemoTool",
        version="9.9.9",
        category="Utility",
        tags=(),
    )

    assert ToolCard._format_tags(manifest) == "utility"
