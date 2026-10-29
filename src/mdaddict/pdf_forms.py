"""Read-only canonical-field/widget inspection. Never reattach or flatten forms.

Appearance text comparison is deliberately limited to simple standard-font
streams. Unknown encodings remain review issues, never an assumed agreement.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path


def _object_id(value) -> str:
    ref = getattr(value, "indirect_reference", None) or value
    return f"{ref.idnum}:{ref.generation}" if hasattr(ref, "idnum") else f"direct:{id(value)}"


def _resolve(value):
    return value.get_object() if hasattr(value, "get_object") else value


def _value(value):
    value = _resolve(value)
    if isinstance(value, list):
        return [_value(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _inherit(node, key):
    seen = set()
    while isinstance(node, dict):
        identity = _object_id(node)
        if identity in seen or len(seen) > 100:
            raise ValueError("Cyclic/deep field inheritance")
        seen.add(identity)
        if key in node:
            return _resolve(node[key])
        node = _resolve(node.get("/Parent"))
    return None


def _name(node):
    names, seen = [], set()
    while isinstance(node, dict):
        identity = _object_id(node)
        if identity in seen or len(seen) > 100:
            raise ValueError("Cyclic/deep field names")
        seen.add(identity)
        if node.get("/T"):
            names.insert(0, str(node["/T"]))
        node = _resolve(node.get("/Parent"))
    return ".".join(names)


def _appearance_text(stream, reader):
    from pypdf.generic import ContentStream
    stream = _resolve(stream)
    if not hasattr(stream, "get_data"):
        return None
    fonts = _resolve(stream.get("/Resources", {})).get("/Font", {})
    fonts = _resolve(fonts)
    if not fonts:
        return None
    for font in fonts.values():
        font = _resolve(font)
        if font.get("/Subtype") != "/Type1" or str(font.get("/BaseFont")) not in {
                "/Helvetica", "/Helvetica-Bold", "/Times-Roman", "/Courier"}:
            return None
        encoding = _resolve(font.get("/Encoding"))
        if isinstance(encoding, dict) and encoding.get("/Differences"):
            code = 0
            for item in encoding["/Differences"]:
                if isinstance(item, int):
                    code = item
                else:
                    if 32 <= code <= 126 and (code, str(item)) not in {(39, "/quotesingle"), (96, "/grave")}:
                        return None
                    code += 1
    parts = []
    for operands, operator in ContentStream(stream, reader).operations:
        if operator in {b"Tj", b"'", b'"'}:
            value = operands[-1]
            if not isinstance(value, str) or any(ord(c) > 126 for c in value):
                return None
            parts.append(value)
        elif operator == b"TJ":
            for value in operands[0]:
                if isinstance(value, str):
                    parts.append(value)
                elif not isinstance(value, (int, float)):
                    return None
    return "".join(parts) if parts else None


def inspect_forms(path: Path) -> dict:
    from pypdf import PdfReader
    # Permissive path: pypdf alone. Skip the heavy field walk when the catalog
    # has no AcroForm and no page widget annotations.
    reader = PdfReader(path, strict=False)
    root = _resolve(reader.trailer.get("/Root", {}))
    has_acro = isinstance(root, dict) and root.get("/AcroForm") is not None
    if not has_acro:
        orphan = False
        for page in reader.pages:
            annots = _resolve(page.get("/Annots", [])) or []
            for annot in annots:
                annot = _resolve(annot)
                if isinstance(annot, dict) and annot.get("/Subtype") == "/Widget":
                    orphan = True
                    break
            if orphan:
                break
        if not orphan:
            return {"schema_version":1,"has_forms":False,"fields":[],"widgets":[],"issues":[]}
    form = _resolve(reader.trailer["/Root"].get("/AcroForm", {}))
    fields, widgets, issues = [], [], []
    canonical, field_by_id, names = set(), {}, defaultdict(list)

    def problem(code, message, page=None):
        issues.append({"code": code, "message": message, "page": page})

    def walk(ref, ancestors=frozenset(), inherited_name=""):
        node = _resolve(ref)
        identity = _object_id(ref)
        if identity in ancestors or len(ancestors) > 100 or len(canonical) >= 10000:
            raise ValueError("Cyclic/oversized field tree")
        if identity in canonical:
            problem("pdf_form_conflict", "Field occurs more than once in canonical tree")
            return
        canonical.add(identity)
        name = ".".join(v for v in (inherited_name, str(node.get("/T", ""))) if v)
        if "/T" in node or ("/FT" in node and "/Parent" not in node):
            row = {"object_id": identity, "name": name, "type": str(_inherit(node, "/FT") or ""),
                   "value": _value(_inherit(node, "/V"))}
            fields.append(row)
            field_by_id[identity] = row
            names[name].append(identity)
        for child in node.get("/Kids", []):
            walk(child, ancestors | {identity}, name)

    try:
        for ref in form.get("/Fields", []):
            walk(ref)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        problem("pdf_form_structure_unresolved", str(error))
    for name, identities in names.items():
        if name and len(identities) > 1:
            problem("pdf_form_conflict", f"Distinct canonical objects share field name {name!r}")
    if form.get("/XFA") is not None:
        problem("pdf_form_unsupported", "XFA form is not interpreted; rendered content may differ")
    for page_number, page in enumerate(reader.pages, 1):
        for ref in page.get("/Annots", []):
            node = _resolve(ref)
            if node.get("/Subtype") != "/Widget":
                continue
            if len(widgets) >= 10000:
                problem("pdf_form_structure_unresolved", "Widget limit exceeded", page_number)
                break
            try:
                identity, name = _object_id(ref), _name(node)
                value, field_type = _value(_inherit(node, "/V")), str(_inherit(node, "/FT") or "")
                parent = _resolve(node.get("/Parent"))
                bound = identity in canonical or (parent is not None and _object_id(parent) in canonical)
                if not bound:
                    problem("pdf_form_orphan", f"Widget {identity} is absent from canonical field tree", page_number)
                if name in names and not bound:
                    problem("pdf_form_conflict", f"Unrelated widget shares canonical field name {name!r}", page_number)
                parent_value = _value(_inherit(parent, "/V")) if parent else value
                if parent and "/V" in node and value != parent_value:
                    problem("pdf_form_conflict", f"Widget and parent values disagree for {name!r}", page_number)
                normal = _resolve(_resolve(node.get("/AP", {})).get("/N"))
                row = {"object_id": identity, "name": name, "type": field_type, "value": value,
                       "page": page_number, "rect": [_value(v) for v in node.get("/Rect", [])],
                       "canonical": bound, "appearance_available": bool(normal), "appearance_status": "not_checked"}
                if field_type == "/Sig":
                    problem("pdf_form_unsupported", f"Signature field {name!r} not interpreted", page_number)
                elif field_type not in {"/Tx", "/Ch", "/Btn"}:
                    problem("pdf_form_unsupported", f"Unsupported field type {field_type!r}", page_number)
                elif not normal:
                    problem("pdf_form_appearance_review", f"Missing appearance for {name!r}", page_number)
                elif field_type == "/Btn":
                    # Radio groups legitimately have Off appearances on unselected widgets.
                    state = str(node.get("/AS", "/Off"))
                    row["appearance_state"] = state
                    flags = int(_inherit(node, "/Ff") or 0)
                    radio = bool(flags & (1 << 15))
                    row["radio"] = radio
                    good = state in normal and (state == value or (radio and state == "/Off"))
                    row["appearance_status"] = "agreement" if good else "mismatch"
                else:
                    visible = _appearance_text(normal, reader)
                    row["appearance_text"] = visible
                    expected = value
                    if field_type == "/Ch":
                        for option in _inherit(node, "/Opt") or []:
                            if isinstance(option, list) and str(option[0]) == value:
                                expected = str(option[1])
                    if visible is None or isinstance(expected, list):
                        problem("pdf_form_appearance_review", f"Appearance encoding requires source review for {name!r}", page_number)
                    else:
                        row["appearance_status"] = "agreement" if visible == expected else "mismatch"
                if row["appearance_status"] == "mismatch":
                    problem("pdf_form_appearance_mismatch", f"Stored value and appearance disagree for {name!r}", page_number)
                widgets.append(row)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                problem("pdf_form_structure_unresolved", str(error), page_number)
    radio_groups = defaultdict(list)
    for widget in widgets:
        if widget.get("radio"):
            radio_groups[widget["name"]].append(widget)
    for group in radio_groups.values():
        value = group[0]["value"]
        selected = [w for w in group if w["appearance_state"] != "/Off"]
        good = (not selected if value is None or value=="/Off" else bool(selected) and all(w["appearance_state"]==value for w in selected))
        if not good:
            for widget in group:
                widget["appearance_status"] = "mismatch"
                problem("pdf_form_appearance_mismatch", f"Radio-group selection disagrees with stored value for {widget['name']!r}", widget["page"])
    # Canonical data without a widget must not acquire an invented page location.
    located = {w["name"] for w in widgets if w["canonical"]}
    for row in fields:
        if row["name"] not in located and row["value"] is not None:
            problem("pdf_form_unlocated", f"Canonical field {row['name']!r} has no located widget")
    return {"schema_version": 1, "has_forms": bool(form or widgets), "fields": fields,
            "widgets": widgets, "issues": issues}


def load_forms(engine, path):
    from mdaddict.strategy import ExtractionIssue, SourceLocator
    data = inspect_forms(path)
    engine.pdf_forms = data
    for item in data["issues"]:
        page = item["page"]
        engine.issues.append(ExtractionIssue(item["code"], item["message"],
            SourceLocator("page", page) if page else SourceLocator(), [f"page:{page}"] if page else [],
            "review" if item["code"] == "pdf_form_appearance_review" else "unresolved"))
    return data


def form_markdown(data, page):
    rows = [w for w in data["widgets"] if w["page"] == page and w["type"] in {"/Tx", "/Ch", "/Btn"}]
    if not rows:
        return ""
    # JSON quoting avoids interpreting stored field strings as markup or instructions.
    return "\n\n### Stored form values (appearance recorded separately)\n\n" + "\n".join(
        f"- {json.dumps(w['name'], ensure_ascii=False)}: {json.dumps(w['value'], ensure_ascii=False)}"
        for w in rows)
