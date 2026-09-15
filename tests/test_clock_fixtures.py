import json
from fractions import Fraction
from pathlib import Path


def test_renderer_clock_vectors_against_exact_python_rationals():
    cases = json.loads((Path(__file__).parent / "fixtures/clock.json").read_text())
    for row in cases["frames"]:
        clock = row["clock"]
        exact = Fraction(row["frame"] * clock["sampleRate"] * clock["fpsDen"], clock["fpsNum"])
        assert exact.numerator // exact.denominator == row["sample"]
    for row in cases["events"]:
        clock = row["clock"]
        exact = Fraction(row["sample"] * clock["fpsNum"], clock["sampleRate"] * clock["fpsDen"])
        assert -(-exact.numerator // exact.denominator) == row["frame"]
