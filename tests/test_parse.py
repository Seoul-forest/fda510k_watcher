"""Unit tests for openFDA API query logic in fda_510k_html_watch.py."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from fda_510k_html_watch import query_openfda, iso


# ---------------------------------------------------------------------------
# iso()
# ---------------------------------------------------------------------------

def test_iso_converts_8digit():
    assert iso("20240101") == "2024-01-01"


def test_iso_passthrough_other():
    assert iso("01/01/2024") == "01/01/2024"
    assert iso("") == ""
    assert iso(None) == ""


def test_iso_passthrough_yyyy_mm_dd():
    assert iso("2024-01-15") == "2024-01-15"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(results, status_code=200):
    """Create a mock requests.Response with given results."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"results": results}
    resp.raise_for_status = MagicMock()
    return resp


def _sample_record(**overrides):
    """Build a sample openFDA 510(k) record."""
    record = {
        "k_number": "K240001",
        "device_name": "Test Device",
        "applicant": "Acme Corp",
        "product_code": "QDA",
        "decision_date": "2024-01-15",
    }
    record.update(overrides)
    return record


# ---------------------------------------------------------------------------
# query_openfda()
# ---------------------------------------------------------------------------

def test_query_openfda_returns_empty_when_no_args():
    assert query_openfda() == []


def test_query_openfda_by_product_code():
    mock_resp = _mock_response([_sample_record()])
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp) as mock_get:
        results = query_openfda(product_code="QDA")

    assert len(results) == 1
    assert results[0]["k_number"] == "K240001"
    assert results[0]["product_code"] == "QDA"
    # Verify API was called with correct search param
    call_args = mock_get.call_args
    assert 'product_code:"QDA"' in call_args[1]["params"]["search"]


def test_query_openfda_by_applicant():
    mock_resp = _mock_response([_sample_record(applicant="Lunit Inc.")])
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp) as mock_get:
        results = query_openfda(applicant="lunit")

    assert len(results) == 1
    assert results[0]["applicant"] == "Lunit Inc."
    call_args = mock_get.call_args
    assert 'applicant:"lunit"' in call_args[1]["params"]["search"]


def test_query_openfda_builds_detail_url():
    mock_resp = _mock_response([_sample_record(k_number="K250099")])
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp):
        results = query_openfda(product_code="QDA")

    assert results[0]["detail_url"] == (
        "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K250099"
    )


def test_query_openfda_multiple_results():
    records = [
        _sample_record(k_number="K240001", device_name="Device A"),
        _sample_record(k_number="K240002", device_name="Device B"),
        _sample_record(k_number="K240003", device_name="Device C"),
    ]
    mock_resp = _mock_response(records)
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp):
        results = query_openfda(product_code="QDA")

    assert len(results) == 3
    k_numbers = [r["k_number"] for r in results]
    assert k_numbers == ["K240001", "K240002", "K240003"]


def test_query_openfda_returns_all_required_fields():
    mock_resp = _mock_response([_sample_record()])
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp):
        result = query_openfda(product_code="QDA")[0]

    assert set(result.keys()) == {
        "k_number", "device_name", "applicant",
        "product_code", "decision_date", "detail_url"
    }


def test_query_openfda_handles_404():
    mock_resp = _mock_response([], status_code=404)
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp):
        results = query_openfda(product_code="NONEXIST")

    assert results == []


def test_query_openfda_handles_missing_fields():
    """API 응답에서 일부 필드가 누락되어도 빈 문자열로 처리."""
    record = {"k_number": "K240001"}  # minimal record
    mock_resp = _mock_response([record])
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp):
        results = query_openfda(product_code="QDA")

    assert len(results) == 1
    assert results[0]["device_name"] == ""
    assert results[0]["applicant"] == ""
    assert results[0]["product_code"] == ""
    assert results[0]["decision_date"] == ""


def test_query_openfda_skips_records_without_k_number():
    """k_number가 없는 레코드는 건너뛴다."""
    records = [
        _sample_record(k_number="K240001"),
        {"device_name": "Bad Record"},  # no k_number
        _sample_record(k_number="K240002"),
    ]
    mock_resp = _mock_response(records)
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp):
        results = query_openfda(product_code="QDA")

    assert len(results) == 2
    assert results[0]["k_number"] == "K240001"
    assert results[1]["k_number"] == "K240002"


def test_query_openfda_sorts_by_decision_date_desc():
    """API 호출 시 decision_date:desc 정렬을 요청한다."""
    mock_resp = _mock_response([])
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp) as mock_get:
        query_openfda(product_code="QDA")

    call_args = mock_get.call_args
    assert call_args[1]["params"]["sort"] == "decision_date:desc"


def test_query_openfda_limits_to_100():
    """API 호출 시 limit=100을 요청한다."""
    mock_resp = _mock_response([])
    with patch("fda_510k_html_watch.requests.get", return_value=mock_resp) as mock_get:
        query_openfda(product_code="QDA")

    call_args = mock_get.call_args
    assert call_args[1]["params"]["limit"] == 100


def test_query_openfda_handles_network_error():
    """네트워크 오류 시 빈 리스트를 반환한다."""
    import requests as req
    with patch("fda_510k_html_watch.requests.get", side_effect=req.exceptions.ConnectionError("timeout")):
        with patch("fda_510k_html_watch.time.sleep"):  # skip retry delays
            results = query_openfda(product_code="QDA")

    assert results == []
