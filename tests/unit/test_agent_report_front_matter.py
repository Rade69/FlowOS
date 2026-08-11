"""Unit testovi za strict AgentReport YAML front matter parser."""

import pytest

from flowos.service.services.reports.front_matter import (
    AgentReportFrontMatterError,
    AgentReportFrontMatterErrorCode,
    AgentReportFrontMatterParser,
)

VALID_REPORT_ID = "11111111-1111-4111-8111-111111111111"
VALID_SESSION_ID = "22222222-2222-4222-8222-222222222222"


def _front_matter(**overrides: object) -> str:
    values = {
        "flowos_report_version": 1,
        "report_id": VALID_REPORT_ID,
        "session_id": VALID_SESSION_ID,
        "report_type": "implementation",
        "work_status": "completed",
        "tasks": ["FLOW-017"],
        "created_at": "2026-08-11T15:30:00+02:00",
    }
    values.update(overrides)
    lines = ["---"]
    for key, value in values.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {item}" for item in value)
        elif value is None:
            continue
        else:
            lines.append(f"{key}: {value}")
    lines.extend(["---", "", "# Body"])
    return "\n".join(lines)


def _expect_error(markdown: str, code: AgentReportFrontMatterErrorCode):
    with pytest.raises(AgentReportFrontMatterError) as exc:
        AgentReportFrontMatterParser().parse_text(markdown)
    assert exc.value.code == code


def test_valid_yaml_front_matter():
    parsed = AgentReportFrontMatterParser().parse_text(_front_matter())

    assert parsed.report_id == VALID_REPORT_ID
    assert parsed.session_id == VALID_SESSION_ID
    assert parsed.report_type == "implementation"
    assert parsed.work_status == "completed"
    assert parsed.tasks == ("FLOW-017",)


def test_no_front_matter_is_legacy():
    _expect_error("# Legacy\n\nBody", AgentReportFrontMatterErrorCode.LEGACY_NO_FRONT_MATTER)


def test_invalid_yaml_is_invalid():
    _expect_error("---\nflowos_report_version: [\n---", AgentReportFrontMatterErrorCode.INVALID)


def test_duplicate_key_is_invalid():
    markdown = _front_matter() + "\n"
    markdown = markdown.replace(
        "report_type: implementation",
        "report_type: implementation\nreport_type: fix",
    )
    _expect_error(markdown, AgentReportFrontMatterErrorCode.INVALID)


def test_unknown_extra_field_is_invalid():
    _expect_error(_front_matter(extra_field="nope"), AgentReportFrontMatterErrorCode.INVALID)


def test_missing_report_id_needs_identity():
    _expect_error(_front_matter(report_id=None), AgentReportFrontMatterErrorCode.NEEDS_IDENTITY)


def test_invalid_uuid_report_id_is_invalid():
    _expect_error(_front_matter(report_id="not-a-uuid"), AgentReportFrontMatterErrorCode.INVALID)


def test_naive_created_at_is_invalid():
    _expect_error(
        _front_matter(created_at="2026-08-11T15:30:00"),
        AgentReportFrontMatterErrorCode.INVALID,
    )


def test_invalid_work_status_is_invalid():
    _expect_error(_front_matter(work_status="verified"), AgentReportFrontMatterErrorCode.INVALID)


@pytest.mark.parametrize("report_type", ["implementation", "fix"])
def test_implementation_and_fix_require_work_status(report_type: str):
    _expect_error(
        _front_matter(report_type=report_type, work_status=None),
        AgentReportFrontMatterErrorCode.INVALID,
    )


def test_review_without_work_status_is_valid():
    parsed = AgentReportFrontMatterParser().parse_text(
        _front_matter(report_type="review", work_status=None)
    )

    assert parsed.report_type == "review"
    assert parsed.work_status is None


def test_unassigned_with_other_task_is_invalid():
    _expect_error(
        _front_matter(tasks=["unassigned", "FLOW-017"]),
        AgentReportFrontMatterErrorCode.INVALID,
    )
