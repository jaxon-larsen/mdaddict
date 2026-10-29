"""Compatibility boundary around the unmodified, stdlib-only OMML parser."""
from copy import deepcopy
import re
from pathlib import Path
import subprocess
import tempfile
import zipfile

from mdaddict._vendor.omml2latex import convert_omml


MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_ELEMENTS = frozenset("acc bar box borderBox d eqArr f func groupChr limLow limUpp m nary phant rad sPre sSub sSubSup sSup r".split())
_ARGS = frozenset("e num den deg sub sup lim fName".split())
_CHILDREN = {
    "oMath": _ELEMENTS,
    "oMathPara": {"oMath", "oMathParaPr"},
    "r": {"rPr", "t"},
    "t": set(),
    "f": {"fPr", "num", "den"},
    "rad": {"radPr", "deg", "e"},
    "sSup": {"sSupPr", "e", "sup"},
    "sSub": {"sSubPr", "e", "sub"},
    "sSubSup": {"sSubSupPr", "e", "sub", "sup"},
    "sPre": {"sPrePr", "e", "sub", "sup"},
    "nary": {"naryPr", "e", "sub", "sup"},
    "d": {"dPr", "e"}, "eqArr": {"eqArrPr", "e"},
    "m": {"mPr", "mr"}, "mr": {"e"},
    "func": {"funcPr", "fName", "e"},
    "limLow": {"limLowPr", "e", "lim"}, "limUpp": {"limUppPr", "e", "lim"},
    **{tag: {tag + "Pr", "e"} for tag in ("acc", "bar", "box", "borderBox", "groupChr", "phant")},
    **{tag: _ELEMENTS | {"argPr", "ctrlPr"} for tag in _ARGS},
}
_ESCAPES = {"\\": r"\backslash{}", "$": r"\$", "%": r"\%", "#": r"\#",
            "&": r"\&", "_": r"\_", "{": r"\{", "}": r"\}",
            "^": r"\textasciicircum{}", "~": r"\textasciitilde{}"}


def convert_equation(node) -> str:
    """Reject unknown content before upstream can silently drop it; keep input intact."""
    pending, count = [(node, 0)], 0
    while pending:
        current, depth = pending.pop()
        count += 1
        if count > 10_000 or depth > 100:
            raise ValueError("Office equation exceeds structural limits")
        tag = current.tag
        if not isinstance(tag, str) or not tag.startswith("{" + MATH_NS + "}"):
            raise ValueError(f"Unsupported Office math element: {tag}")
        local = tag.rsplit("}", 1)[-1]
        allowed = _CHILDREN.get(local)
        if allowed is None:
            raise ValueError(f"Unsupported Office math element: {local}")
        for child in current:
            child_name = child.tag.rsplit("}", 1)[-1] if isinstance(child.tag, str) else ""
            if child_name not in allowed:
                raise ValueError(f"Unsupported Office math element in {local}: {child_name}")
            # Run/argument/shape properties contain application formatting, not
            # mathematical content. Upstream reads the supported OMML properties.
            if not child_name.endswith("Pr"):
                pending.append((child, depth + 1))
    copied = deepcopy(node)
    texts = list(copied.iter("{" + MATH_NS + "}t"))
    trailing_space = bool(texts and (texts[-1].text or "").endswith("\u00a0"))
    if trailing_space:
        texts[-1].text = texts[-1].text.rstrip("\u00a0")
    for text in texts:
        text.text = "".join(_ESCAPES.get(char, char) for char in (text.text or ""))
    result = convert_omml(copied)
    # Only remove a redundant group around a single ASCII base, never a
    # multi-token group or command argument (e.g. the denominator of a fraction).
    result = re.sub(r"(?<![\\\w}])\{([A-Za-z0-9])\}(?=[_^])", r"\1", result)
    if not isinstance(result, str) or not result.strip("$ \n"):
        raise ValueError("Office equation produced empty output")
    return " ".join(result.splitlines()) + (" " if trailing_space else "")


def convert_with_pandoc(engine, entries) -> dict:
    """Batch unsupported equations through the established Office-math reader."""
    from lxml import etree
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paragraphs = []
    for number, (_, node) in enumerate(entries):
        paragraphs.append(f"<w:p><w:r><w:t>MDADDICTEQ{number:06d}</w:t></w:r></w:p>")
        paragraphs.append("<w:p>" + etree.tostring(node, encoding="unicode") + "</w:p>")
    document = f'<w:document xmlns:w="{ns}"><w:body>' + "".join(paragraphs) + "</w:body></w:document>"
    with tempfile.TemporaryDirectory(prefix="mdaddict-math-") as directory:
        path = Path(directory) / "equations.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
            archive.writestr("word/document.xml", document)
        # Dollar math avoids GFM code wrappers around matrices and inline
        # expressions with a trailing TeX space from an Office NBSP.
        run = subprocess.run(["pandoc", "--sandbox", str(path), "-f", "docx", "-t", "gfm+tex_math_dollars-tex_math_gfm", "--wrap=none"],
            capture_output=True, encoding="utf-8", timeout=engine.options.timeout)
    if run.returncode:
        raise RuntimeError("Office math conversion failed: " + run.stderr[-500:])
    if run.stderr.strip():
        engine.warn("PPTX Office math: " + run.stderr.strip()[:500])
    stdout = re.sub(r"\$`+([^`\n]+)`+\$", r"$\1$", run.stdout)
    pieces = re.split(r"MDADDICTEQ\d{6}", stdout)[1:]
    if len(pieces) != len(entries):
        raise RuntimeError("Office math conversion lost equation markers")
    by_node = {}
    for (_, node), piece in zip(entries, pieces):
        piece = piece.strip()
        if not piece:
            engine.warn("PPTX Office math: empty equation conversion")
            piece = "[Office equation unresolved]"
        # Pandoc emits a terminal TeX '\ ' for an Office NBSP, sometimes
        # dropping its space into '\$'. Move either form outside the closing
        # delimiter only at this source-proven boundary. Literal dollars and
        # row separators stay intact; following prose keeps its separation.
        native_text = "".join(node.xpath(".//*[local-name()='t']/text()"))
        if native_text.endswith("\u00a0") and piece.startswith("$") and piece.count("$") == 2:
            piece = re.sub(r"(?<!\\)\\[ \t\u00a0]*\$$", "$ ", piece)
        # Keep inline matrices on one Markdown line; TeX row separators survive.
        by_node[node] = " ".join(piece.splitlines())
    return by_node

