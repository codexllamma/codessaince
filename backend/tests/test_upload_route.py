import io
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_upload_doc_missing_file():
    response = client.post("/api/jobs/upload-doc")
    assert response.status_code == 422  # Validation error (missing file)


def test_upload_doc_with_pdf(tmp_path: Path):
    # Use existing test PDF or create mock PDF
    pdf_path = Path("ocr_engine/complex_layout_test.pdf")
    if not pdf_path.exists():
        pytest.skip("complex_layout_test.pdf not found")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    response = client.post(
        "/api/jobs/upload-doc",
        files={"file": ("circular.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"lang": "en"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "extracted_facts" in data
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0
    assert "raw_text" in data
    assert len(data["raw_text"]) > 0
