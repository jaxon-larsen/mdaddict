"""Compare existing OMML converters on fixed, small source-defined controls."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
import xml.etree.ElementTree as ET

NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def run(text):
    return "<m:r><m:t>" + text + "</m:t></m:r>"


# Gold is defined from the XML operands/structure before calling any converter.
CASES = [
    ("fraction", "<m:f><m:num>" + run("x+1") + "</m:num><m:den>" + run("2") + "</m:den></m:f>", [r"\frac{x+1}{2}"]),
    ("square-root", '<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>' + run("x+1") + "</m:e></m:rad>", [r"\sqrt{x+1}"]),
    # Reviewed equivalent spellings: braces around the single base x do not
    # change the source's script ownership. No general algebraic normalization.
    ("superscript", "<m:sSup><m:e>" + run("x") + "</m:e><m:sup>" + run("2") + "</m:sup></m:sSup>", ["x^{2}", "{x}^{2}"]),
    ("subscript", "<m:sSub><m:e>" + run("x") + "</m:e><m:sub>" + run("i") + "</m:sub></m:sSub>", ["x_{i}", "{x}_{i}"]),
    ("sub-and-super", "<m:sSubSup><m:e>" + run("x") + "</m:e><m:sub>" + run("i") + "</m:sub><m:sup>" + run("2") + "</m:sup></m:sSubSup>", ["x_{i}^{2}", "{x}_{i}^{2}"]),
    ("matrix", "<m:m><m:mr><m:e>" + run("a") + "</m:e><m:e>" + run("b") + "</m:e></m:mr><m:mr><m:e>" + run("c") + "</m:e><m:e>" + run("d") + "</m:e></m:mr></m:m>", [r"\begin{matrix}a&b\\c&d\end{matrix}"]),
]


def main(args):
    sys.path.insert(0, str(args.reference_root.resolve() / "engine/tools"))
    from evaluate_fidelity import normalize_math
    from omml2latex import convert_omml
    from lxml import etree
    from docling.backend.docx.latex.omml import oMath2Latex as docling_math
    from dwml.omml import oMath2Latex as dwml_math
    candidates = {
        "omml2latex": lambda xml: convert_omml(ET.fromstring(xml)),
        "docling-omml": lambda xml: str(docling_math(etree.fromstring(xml.encode()))),
        "dwml": lambda xml: str(dwml_math(etree.fromstring(xml.encode()))),
    }
    results = []
    for name, convert in candidates.items():
        rows = []
        for case, fragment, expected in CASES:
            xml = f'<m:oMath xmlns:m="{NAMESPACE}">{fragment}</m:oMath>'
            try:
                times = []
                for _ in range(20):
                    start = time.perf_counter()
                    output = convert(xml)
                    times.append((time.perf_counter() - start) * 1000)
                rows.append({"case": case, "xml": xml, "expected": expected, "output": output,
                             "normalized_match": normalize_math(output) in [normalize_math(x) for x in expected],
                             "median_ms": statistics.median(times)})
            except Exception as error:
                rows.append({"case": case, "xml": xml, "expected": expected, "error": str(error)})
        results.append({"backend": name, "cases": rows})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in results:
        print(json.dumps({"backend": row["backend"], "cases": [{k: v for k, v in case.items() if k != "xml"} for case in row["cases"]]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    main(parser.parse_args())
