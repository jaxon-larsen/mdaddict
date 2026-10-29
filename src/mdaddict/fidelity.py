"""Strict region patch contracts and limited transcription/verification rounds."""
from __future__ import annotations

import json
import re
from collections import Counter

from mdaddict.vision_runtime import BudgetExhausted
from mdaddict.ai import ProviderError


def parse_json(text):
    if not isinstance(text, str):
        raise ValueError("Expected JSON text")
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("Non-finite JSON value")
    value = json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def circuit_markdown(note):
    if not isinstance(note, dict) or set(note) != {"panels", "unknowns"}:
        raise ValueError("Circuit requires panels and unknowns")
    if not isinstance(note["panels"], list) or not note["panels"]:
        raise ValueError("Circuit needs at least one panel")
    if not isinstance(note["unknowns"], list) or not all(isinstance(x, str) for x in note["unknowns"]):
        raise ValueError("Circuit unknowns must be text")
    lines = ["<!-- figure: circuit -->"]
    for panel in note["panels"]:
        if not isinstance(panel, dict) or set(panel) != {"label", "wires", "steps"}:
            raise ValueError("Invalid panel")
        if not isinstance(panel["label"], str) or not isinstance(panel["wires"], list) or not isinstance(panel["steps"], list):
            raise ValueError("Invalid circuit panel fields")
        if not panel["wires"]:
            raise ValueError("Circuit panel needs visible wires")
        wires = set()
        lines.append(f"- panel: {panel['label']}")
        for wire in panel["wires"]:
            if not isinstance(wire, dict) or set(wire) != {"id", "label", "initial"} or not all(isinstance(v, str) for v in wire.values()):
                raise ValueError("Invalid wire")
            if not wire["id"] or wire["id"] in wires:
                raise ValueError("Duplicate/empty wire id")
            wires.add(wire["id"])
            lines.append(f"  - wire {wire['id']}: {wire['label']}; initial: {wire['initial']}")
        for index, step in enumerate(panel["steps"], 1):
            if not isinstance(step, dict) or set(step) != {"gate", "targets", "controls"}:
                raise ValueError("Invalid gate step")
            if not isinstance(step["gate"], str) or not step["gate"]:
                raise ValueError("Gate label required")
            for role in ("targets", "controls"):
                refs = step[role]
                if not isinstance(refs, list) or not all(isinstance(x, str) for x in refs) or len(set(refs)) != len(refs) or not set(refs) <= wires:
                    raise ValueError("Unknown/duplicate wire reference")
            if set(step["targets"]) & set(step["controls"]):
                raise ValueError("Control and target overlap")
            if not step["targets"]:
                raise ValueError("Gate step needs a target wire")
            lines.append(f"  - step {index}: {step['gate']}; targets: {', '.join(step['targets'])}; controls: {', '.join(step['controls'])}")
    lines.extend(f"- unknown: {x}" for x in note["unknowns"])
    return "\n".join(lines)


def _table_widths(text):
    """Count explicit cells, including empty edge cells and array header spans.

    This deliberately supports only flat arrays; nested tables need review.
    It establishes dimensions, not correctness of cell content or grouping.
    """
    arrays = list(re.finditer(r"\\begin\{array\}\s*\{[^{}]*\}([\s\S]*?)\\end\{array\}", text))
    if arrays:
        if len(arrays) != 1 or r"\begin" in arrays[0].group(1):
            raise ValueError("Nested/multiple table arrays need review")
        body = re.sub(r"\\(?:hline|cline\{[0-9-]+\})", "", arrays[0].group(1)).strip()
        rows = re.split(r"\\\\(?:\[[^\]]*\])?", body)
        if rows and not rows[-1].strip():
            rows.pop()
        widths = []
        for row in rows:
            cells, start, depth = [], 0, 0
            for index, char in enumerate(row):
                # Escaped ampersands/braces belong to the cell content.
                slashes = len(row[:index]) - len(row[:index].rstrip("\\"))
                if slashes % 2:
                    continue
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth < 0:
                        raise ValueError("Unbalanced array braces")
                elif char == "&" and depth == 0:
                    cells.append(row[start:index])
                    start = index + 1
            if depth:
                raise ValueError("Unbalanced array braces")
            cells.append(row[start:])
            width = 0
            for cell in cells:
                span = re.match(r"\s*\\multicolumn\{([1-9][0-9]*)\}\{[^{}]*\}\{", cell)
                if r"\multicolumn" in cell and not span:
                    raise ValueError("Malformed table column span")
                width += int(span.group(1)) if span else 1
            widths.append(width)
        return widths
    widths = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        line = line[1:]
        if line.endswith("|") and not line.endswith(r"\|"):
            line = line[:-1]
        cells = re.split(r"(?<!\\)\|", line)
        if all(re.fullmatch(r"\s*:?-+:?\s*", cell) for cell in cells):
            continue
        widths.append(len(cells))
    return widths


def validate_math_transport(text, constraints):
    """Reject suspicious transport syntax, never unescape or infer formula meaning."""
    # Literal code examples are source prose, not rendered mathematical commands.
    rendered = re.sub(r"```[\s\S]*?```|`[^`\n]*`", "", text)
    for match in re.finditer(r"(?<!\\)(\\{2,})(?=(?:frac|sqrt|left|right|rangle|langle|overline|qquad|begin|end)\b)", rendered):
        if len(match.group(1)) % 2 == 0:
            # Odd runs can be a valid row separator followed by a command.
            raise ValueError("Doubled LaTeX command requires source review; do not unescape automatically")
    count = constraints.get("math_expression_count")
    if count is not None:
        # Only a reviewed source count may impose this requirement. Delimiters
        # establish presentation boundaries, not mathematical equivalence.
        expressions = re.findall(r"\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|(?<!\$)\$(?!\$)[\s\S]*?(?<!\$)\$(?!\$)|\\\([\s\S]*?\\\)", rendered)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1 or len(expressions) != count:
            raise ValueError("Reviewed math expression count mismatch")


def validate_patch(payload, regions):
    if not isinstance(payload, dict):
        raise ValueError("Expected patch object")
    entries = payload.get("patches")
    if set(payload) != {"patches"} or not isinstance(entries, list) or len(entries) != len(regions):
        raise ValueError("Patch set must exactly cover requested regions")
    by_id = {r.id: r for r in regions}
    seen = set()
    replacements = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or entry["id"] not in by_id or entry["id"] in seen:
            raise ValueError("Unknown/duplicate region id")
        seen.add(entry["id"])
        region = by_id[entry["id"]]
        if region.kind == "circuit":
            if set(entry) != {"id", "circuit"}:
                raise ValueError("Circuit region needs structured circuit note")
            text = circuit_markdown(entry["circuit"])
            if entry["circuit"]["unknowns"] or re.search(r"\b(?:unknown|illegible|uncertain)\b", text, re.IGNORECASE):
                raise ValueError("Circuit remains unresolved: " + text)
        else:
            if set(entry) != {"id", "markdown"} or not isinstance(entry["markdown"], str):
                raise ValueError("Region needs markdown")
            text = entry["markdown"]
        if not text.strip() or "[illegible]" in text or "[too dense" in text:
            raise ValueError("Region remains illegible")
        # Links introduced by the model cannot become source assets.
        for link in re.findall(r"!?\[[^\]]*\]\([^)]+\)|https?://\S+|<img\b[^>]*>", text):
            if link not in region.text:
                raise ValueError("Invented asset/link")
        if "untrusted_diagram_" in text:
            raise ValueError("Invented diagram placeholder")
        if text.count("$") % 2 or text.count("{") != text.count("}"):
            raise ValueError("Unbalanced math delimiters")
        validate_math_transport(text, region.constraints)
        expected = region.constraints.get("glyphs")
        if expected:
            # Compare only visible alphanumerics; ignore LaTeX command names.
            actual = Counter(c for c in re.sub(r"\\[A-Za-z]+", "", text) if c.isalnum())
            if actual != Counter(c for c in expected if c.isalnum()):
                raise ValueError("Source glyph mismatch")
        shape = region.constraints.get("table_shape")
        if shape:
            widths = _table_widths(text)
            if len(widths) != shape[0] or any(width != shape[1] for width in widths):
                raise ValueError("Table shape mismatch")
        replacements.append((region, text))
    return replacements


def apply_patches(markdown, patches):
    previous_end = 0
    for region, text in sorted(patches, key=lambda p: p[0].start):
        if not 0 <= region.start <= region.end <= len(markdown) or region.start < previous_end:
            raise ValueError("Invalid or overlapping region spans")
        if markdown[region.start:region.end] != region.text:
            raise ValueError("Patch baseline changed")
        previous_end = region.end
    for region, text in sorted(patches, key=lambda p: p[0].start, reverse=True):
        markdown = markdown[:region.start] + text + markdown[region.end:]
    return markdown


def verify_decisions(payload, regions):
    if not isinstance(payload, dict):
        raise ValueError("Expected verifier object")
    entries = payload.get("decisions")
    if set(payload) != {"decisions"} or not isinstance(entries, list) or len(entries) != len(regions):
        raise ValueError("Verifier must cover exact region set")
    expected = {r.id for r in regions}
    seen = set()
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] not in expected or item["id"] in seen:
            raise ValueError("Unknown/duplicate verifier region")
        seen.add(item["id"])
        if not {"id", "status"} <= set(item) or set(item) - {"id", "status", "reason"}:
            raise ValueError("Unexpected verifier fields")
        if not isinstance(item.get("status"), str) or item["status"] not in {"pass", "fail", "uncertain"}:
            raise ValueError("Invalid verifier status")
        if "reason" in item and not isinstance(item["reason"], str):
            raise ValueError("Invalid verifier reason")
    return all(item["status"] == "pass" for item in entries)


PATCH_CONTRACT = '''Return {"patches":[{"id":"...","markdown":"..."}]} covering exactly the region IDs.
For circuit regions replace markdown with "circuit":{"panels":[{"label":"...","wires":[{"id":"w0","label":"visible label or position","initial":"visible state or not shown"}],"steps":[{"gate":"visible gate/measurement label","targets":["w0"],"controls":[]}]}],"unknowns":[]}.
Steps are left-to-right; never infer topology, gate counts, equivalence, or answers.
For math copy visible groups, using \\overline{...}; never simplify.
Keep separately displayed equations in separate math delimiters, retaining their visible figure labels.
JSON-escape LaTeX commands exactly once: after JSON decoding, Markdown must contain one backslash before each command, not two.
Preserve table headers, empty cells, dimensions and source prose.''' 


def repair_regions(runner, regions, images):
    context = [{"id": r.id, "kind": r.kind, "native": r.text, "constraints": r.constraints} for r in regions]
    prompt = PATCH_CONTRACT + "\nRegions in image order:\n" + json.dumps(context, ensure_ascii=False)
    reason = "Unresolved transcription"
    for round_index in range(2):
        key = None
        try:
            response, key = runner.request(images, prompt, "transcribe" if not round_index else "correct")
            try:
                payload = parse_json(response.text)
            except ValueError:
                if len(regions) == 1 and regions[0].kind == "page":
                    from mdaddict.extract_vision import strip_outer_markdown_fence
                    text = strip_outer_markdown_fence(response.text)
                    if text.strip():
                        patches = validate_patch({"patches": [{"id": regions[0].id, "markdown": text}]}, regions)
                    else:
                        raise
                else:
                    raise
            else:
                patches = validate_patch(payload, regions)
            if any(r.high_risk for r in regions):
                verify_prompt = ('Compare each candidate strictly with its source image. Do not solve or simplify. '
                    'Return {"decisions":[{"id":"...","status":"pass|fail|uncertain","reason":"..."}]} '
                    'for exactly these regions. Detect missing bars, altered grouping, omitted prose, '
                    'invented circuit topology and added explanation. Unknowns must be uncertain.\n' +
                    json.dumps([{"id": r.id, "candidate": text, "source_context": r.constraints.get("source_context", ""),
                                 "source": r.constraints.get("source", {}), "location": r.constraints.get("location", "")}
                                for r, text in patches], ensure_ascii=False))
                checked, verify_key = runner.request(images, verify_prompt, "verify")
                passed = verify_decisions(parse_json(checked.text), regions)
                runner.validation(verify_key, "pass" if passed else "held", checked.text)
                if not passed:
                    raise ValueError("Source verifier mismatch or uncertainty: " + checked.text)
            runner.validation(key, "pass")
            return patches, None
        except (ValueError, BudgetExhausted, ProviderError) as error:
            if isinstance(error, ProviderError) and error.configuration:
                raise
            reason = str(error)
            if key:
                runner.validation(key, "held", reason)
            if isinstance(error, (BudgetExhausted, ProviderError)):
                break
            prompt = PATCH_CONTRACT + "\nRegions:\n" + json.dumps(context, ensure_ascii=False) + "\nCorrect these failures against the images:\n" + reason
    return [], reason
