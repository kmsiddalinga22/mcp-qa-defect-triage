"""
Unit tests for the triage_defect tool.

Run with:
    pytest tests/ -v
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.defect_triage import triage_defect, triage_defect_ai


def test_triage_defect_critical_severity():
    result = triage_defect("The app crashes and users cannot log in at all.")
    assert "Critical" in result
    assert "Defect" in result


def test_triage_defect_change_request():
    result = triage_defect("Could we add a dark mode option to the settings page?")
    assert "Change Request" in result


def test_triage_defect_high_severity():
    result = triage_defect("Payment fails when the user applies a discount coupon.")
    assert "High" in result


def test_triage_defect_low_severity():
    result = triage_defect("There's a typo in the footer label on the homepage.")
    assert "Low" in result


def test_triage_defect_empty_input():
    result = triage_defect("")
    assert "error" in result.lower()


def test_triage_defect_ai_empty_input():
    result = triage_defect_ai()
    assert "error" in result.lower()
