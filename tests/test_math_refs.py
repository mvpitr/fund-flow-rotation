"""Traceability audit (quant-protocol State 3): every @math_ref in the code must
resolve to a real \\label{eq:...} in the canonical paper.

Keeps theory and implementation in sync: if an equation label is renamed or removed
from docs/fund-flow-rotation.tex, the @math_ref pointing at it fails here.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PAPER = REPO / "docs" / "fund-flow-rotation.tex"

LABEL_RE = re.compile(r"\\label\{(eq:[a-z_]+)\}")
MATHREF_RE = re.compile(r"@math_ref\s+(eq:[a-z_]+)")


def paper_labels():
    return set(LABEL_RE.findall(PAPER.read_text()))


def code_refs():
    """Every (file, label) pair referenced via @math_ref across the repo's Python."""
    refs = []
    for py in REPO.glob("*.py"):
        for label in MATHREF_RE.findall(py.read_text()):
            refs.append((py.name, label))
    return refs


def test_every_math_ref_resolves_to_a_paper_label():
    labels = paper_labels()
    dangling = [(f, lbl) for f, lbl in code_refs() if lbl not in labels]
    assert not dangling, f"@math_ref labels with no \\label in the paper: {dangling}"


def test_traceability_is_actually_in_use():
    # Guard against the audit silently passing because nothing is tagged.
    assert code_refs(), "no @math_ref tags found in any module"


def test_paper_has_labels():
    assert paper_labels(), f"no eq labels found in {PAPER}"
