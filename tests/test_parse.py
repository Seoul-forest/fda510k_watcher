"""Unit tests for HTML parsing logic in fda_510k_html_watch.py."""
import re
import sys
from pathlib import Path

# Allow importing from project root without installing
sys.path.insert(0, str(Path(__file__).parent.parent))

from fda_510k_html_watch import parse_results, iso


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_table(*rows):
    """Build a minimal FDA-style results HTML page."""
    row_html = "\n".join(rows)
    return f"""
    <html><body>
    <table>
      <tr>
        <th>Device Name</th>
        <th>Applicant</th>
        <th>510(k) Number</th>
        <th>Decision Date</th>
      </tr>
      {row_html}
    </table>
    </body></html>
    """


# ---------------------------------------------------------------------------
# iso()
# ---------------------------------------------------------------------------

def test_iso_converts_8digit():
    assert iso("20240101") == "2024-01-01"


def test_iso_passthrough_other():
    assert iso("01/01/2024") == "01/01/2024"
    assert iso("") == ""
    assert iso(None) == ""


# ---------------------------------------------------------------------------
# parse_results()
# ---------------------------------------------------------------------------

def test_parse_results_empty_html():
    assert parse_results("<html><body></body></html>") == []


def test_parse_results_no_table():
    assert parse_results("<html><body><p>No results</p></body></html>") == []


def test_parse_results_finds_k_number():
    html = _make_table(
        "<tr>"
        "<td>Test Device</td>"
        "<td>Acme Corp</td>"
        "<td><a href='/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K240001'>K240001</a></td>"
        "<td>01/15/2024</td>"
        "</tr>"
    )
    results = parse_results(html)
    assert len(results) == 1
    assert results[0]["k_number"] == "K240001"


def test_parse_results_skips_rows_without_k_number():
    html = _make_table(
        "<tr><td>No Link Row</td><td>Corp</td><td>---</td><td>20240101</td></tr>"
    )
    results = parse_results(html)
    assert results == []


def test_parse_results_multiple_rows():
    html = _make_table(
        "<tr>"
        "<td>Device A</td><td>Corp A</td>"
        "<td><a href='/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K240001'>K240001</a></td>"
        "<td>01/15/2024</td>"
        "</tr>",
        "<tr>"
        "<td>Device B</td><td>Corp B</td>"
        "<td><a href='/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K240002'>K240002</a></td>"
        "<td>01/16/2024</td>"
        "</tr>",
    )
    results = parse_results(html)
    k_numbers = [r["k_number"] for r in results]
    assert "K240001" in k_numbers
    assert "K240002" in k_numbers


def test_parse_results_detail_url_absolute():
    html = _make_table(
        "<tr>"
        "<td>Device</td><td>Corp</td>"
        "<td><a href='/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K240001'>K240001</a></td>"
        "<td>20240101</td>"
        "</tr>"
    )
    results = parse_results(html)
    assert results[0]["detail_url"].startswith("https://")
