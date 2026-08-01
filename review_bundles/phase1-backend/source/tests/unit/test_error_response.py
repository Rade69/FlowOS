"""Unit testovi za ApiErrorResponse."""

import uuid

from flowos.shared.contracts.errors import ApiErrorResponse


class TestApiErrorResponse:
    def test_auto_generates_correlation_id(self):
        r = ApiErrorResponse(code="TEST_ERROR", message="Test greška")
        assert r.correlation_id is not None
        # Mora biti validan UUID
        uuid.UUID(r.correlation_id)

    def test_correlation_id_is_unique(self):
        ids = set()
        for _ in range(100):
            r = ApiErrorResponse(code="E", message="M")
            ids.add(r.correlation_id)
        assert len(ids) == 100  # Svi jedinstveni

    def test_explicit_correlation_id(self):
        cid = "550e8400-e29b-41d4-a716-446655440000"
        r = ApiErrorResponse(code="ERROR", message="Msg", correlation_id=cid)
        assert r.correlation_id == cid

    def test_full_response(self):
        r = ApiErrorResponse(
            code="VALIDATION_ERROR",
            message="Nedostaje obavezno polje.",
            details={"field": "name", "reason": "prazno"},
        )
        assert r.code == "VALIDATION_ERROR"
        assert r.message == "Nedostaje obavezno polje."
        assert r.details == {"field": "name", "reason": "prazno"}
        assert r.correlation_id is not None

    def test_model_dump_json(self):
        cid = "00000000-0000-0000-0000-000000000001"
        r = ApiErrorResponse(code="E", message="M", correlation_id=cid)
        data = r.model_dump()
        assert data == {
            "code": "E",
            "message": "M",
            "details": None,
            "correlation_id": cid,
        }
