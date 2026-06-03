import app.main as main
from fastapi.testclient import TestClient


def test_parse_endpoint_csv():
    csv_bytes = b"question,correct_answer,difficulty\nCapital of Japan?,Tokyo,easy\n"
    with TestClient(main.app) as client:
        resp = client.post(
            "/parse",
            files={"file": ("questions.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["questions"]) == 1
    assert body["questions"][0]["correct_answer"] == "Tokyo"
    assert body["errors"] == []


def test_parse_text_endpoint():
    with TestClient(main.app) as client:
        resp = client.post(
            "/parse-text",
            json={"text": "Capital of Japan? | Tokyo", "format": "auto"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["questions"]) == 1
    assert body["questions"][0]["correct_answer"] == "Tokyo"


def test_parse_endpoint_reports_errors():
    csv_bytes = b"foo,bar\n1,2\n"
    with TestClient(main.app) as client:
        resp = client.post(
            "/parse",
            files={"file": ("bad.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 200
    assert resp.json()["questions"] == []
    assert resp.json()["errors"]
