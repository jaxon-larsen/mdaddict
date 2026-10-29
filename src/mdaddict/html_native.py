"""Optional Markdownify fast path with the existing complex-HTML fallback."""
from importlib.util import find_spec
from pathlib import Path
import re


def convert_html(engine, path: Path) -> tuple[str, str]:
    if find_spec("markdownify") is None:
        return engine._pandoc(path), "pandoc"
    from bs4 import BeautifulSoup
    from markdownify import MarkdownConverter

    soup = BeautifulSoup(engine._text(path), "html.parser")
    for element in soup.find_all(["script", "style", "head"]):
        element.decompose()
    # These controls fail with plain Markdownify. Keep the established reader
    # rather than flatten math, nested tables, merged cells or embedded objects.
    complex_content = soup.find(["math", "svg", "object", "iframe", "embed"]) is not None
    for table in soup.find_all("table"):
        cells = table.find_all(["td", "th"])
        engine.check_cells(len(cells))
        complex_content |= table.find("table") is not None or any(
            str(cell.get(attr, "1")) != "1" for cell in cells for attr in ("colspan", "rowspan"))
        complex_content |= any("|" in code.get_text() for code in table.find_all("code"))
    # Markdownify 1.2.3 always uses a three-backtick pre fence and leaves pipes
    # inside code spans unescaped. Those cases need the existing writer.
    complex_content |= any("```" in pre.get_text() for pre in soup.find_all("pre"))
    complex_content |= bool(re.search(r"\$[^\n$]+\$|\\\(|\\\[", soup.get_text()))
    if complex_content:
        return engine._pandoc(path), "pandoc"

    class Converter(MarkdownConverter):
        def convert_img(self, el, text, parent_tags):
            return engine.describe_image(None, el.get("alt", ""), f"image {el.get('src', '')}")

    converter = Converter(heading_style="ATX", sub_symbol="<sub>", sup_symbol="<sup>", escape_misc=True)
    return converter.convert_soup(soup), "markdownify"
