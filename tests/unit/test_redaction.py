"""FLOW-1109 — unit testovi za centralnu redaction komponentu.

Dokazuje determinističku redakciju poznatih tajni i osjetljivih ključeva,
bez mutacije ulaza i bez false-positive uništavanja običnog evidence-a.
"""

from __future__ import annotations

import uuid

from flowos.service.services.infrastructure.redaction import (
    REDACTED,
    Redactor,
)

SECRET_A = "test-secret-abc123-xyz789"
SECRET_B = "another-secret-9876-qwerty"


def _redactor(*secrets: str) -> Redactor:
    return Redactor(secrets)


def test_exact_known_secret_redaction() -> None:
    r = _redactor(SECRET_A)
    assert r.redact_text(f"Authorization: Bearer {SECRET_A}") == f"Authorization: Bearer {REDACTED}"


def test_secret_na_pocetku_i_kraju() -> None:
    r = _redactor(SECRET_A)
    assert r.redact_text(f"{SECRET_A} mid") == f"{REDACTED} mid"
    assert r.redact_text(f"mid {SECRET_A}") == f"mid {REDACTED}"


def test_secret_vise_puta_u_tekstu() -> None:
    r = _redactor(SECRET_A)
    text = f"{SECRET_A} and {SECRET_A} and {SECRET_A}"
    assert r.redact_text(text) == f"{REDACTED} and {REDACTED} and {REDACTED}"


def test_vise_razlicitih_secreta() -> None:
    r = _redactor(SECRET_A, SECRET_B)
    text = f"a={SECRET_A} b={SECRET_B}"
    assert r.redact_text(text) == f"a={REDACTED} b={REDACTED}"


def test_none_prazan_i_kratak_secret_se_ignorisu() -> None:
    r = _redactor()
    r.register_secret(None)
    r.register_secret("")
    r.register_secret("kratko")
    assert r.redact_text("kratko i nista") == "kratko i nista"


def test_structured_key_redaction() -> None:
    r = _redactor()
    data = {"token": "tajna", "project_id": "p1", "status": "ok"}
    out = r.redact_mapping(data)
    assert out["token"] == REDACTED
    assert out["project_id"] == "p1"
    assert out["status"] == "ok"


def test_structured_key_case_insensitive() -> None:
    r = _redactor()
    data = {"TOKEN": "t", "Authorization": "Bearer x", "Api_Key": "k"}
    out = r.redact_mapping(data)
    assert out["TOKEN"] == REDACTED
    assert out["Authorization"] == REDACTED
    assert out["Api_Key"] == REDACTED


def test_env_suffix_kljucevi_se_rediguju() -> None:
    r = _redactor()
    data = {"CLAUDE_API_KEY": "sk-ant-xxx", "DEEPSEEK_API_KEY": "ds-xxx", "task_id": "T-1"}
    out = r.redact_mapping(data)
    assert out["CLAUDE_API_KEY"] == REDACTED
    assert out["DEEPSEEK_API_KEY"] == REDACTED
    assert out["task_id"] == "T-1"


def test_nested_structure() -> None:
    r = _redactor()
    data = {"outer": {"token": "tajna", "nested": {"api_key": "k"}}, "list": [{"secret": "s"}]}
    out = r.redact_mapping(data)
    assert out["outer"]["token"] == REDACTED
    assert out["outer"]["nested"]["api_key"] == REDACTED
    assert out["list"][0]["secret"] == REDACTED


def test_no_mutation_of_original_mapping() -> None:
    r = _redactor()
    data = {"token": "tajna", "project_id": "p1"}
    r.redact_mapping(data)
    assert data["token"] == "tajna"  # original netaknut
    assert data["project_id"] == "p1"


def test_false_positive_preservation() -> None:
    r = _redactor(SECRET_A)
    commit_sha = "7de72ad24e36ccdb7ce9b39d43dac1c7e70e8a21"
    task_key = "FLOW-1109"
    branch = "feature/FLOW-1109-secret-redaction"
    win_path = "C:\\Users\\radovan\\FlowOS\\src\\redaction.py"
    uuid_val = str(uuid.uuid4())
    normal_stdout = "13 passed, 2 warnings in 3.2s"
    for plain in (commit_sha, task_key, branch, win_path, uuid_val, normal_stdout):
        assert r.redact_text(plain) == plain


def test_rec_tokens_kao_obicna_rijec_nije_redigovan() -> None:
    r = _redactor()
    assert r.redact_text("token je obicna rijec") == "token je obicna rijec"


def test_deterministicki_rezultat() -> None:
    r = _redactor(SECRET_A, SECRET_B)
    text = f"{SECRET_A} + {SECRET_B}"
    assert r.redact_text(text) == r.redact_text(text)
