"""Deterministički ingestion agent_reports Markdown artefakata u AgentReport v2.

Servis je jedinstvena ulazna tačka za startup scan i watcher događaje. Ne
pokreće watcher, ne koristi LLM i oslanja se samo na strict YAML front matter,
stabilni source identity i istorijske SessionTaskBinding segmente.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import (
    AgentSession,
    SessionTaskBinding,
    Task,
)
from flowos.service.services.infrastructure.persistence.plan_models import PlanItem
from flowos.service.services.infrastructure.persistence.report_models import AgentReport
from flowos.service.services.reports.front_matter import (
    AgentReportFrontMatter,
    AgentReportFrontMatterError,
    AgentReportFrontMatterErrorCode,
    AgentReportFrontMatterParser,
)
from flowos.service.services.reports.service import ReportService
from flowos.service.services.workflow.ledger import WorkflowLedgerService


class AgentReportIngestionOutcome(StrEnum):
    INGESTED = "INGESTED"
    ALREADY_INGESTED = "ALREADY_INGESTED"
    INVALID = "INVALID"
    LEGACY_NO_FRONT_MATTER = "LEGACY_NO_FRONT_MATTER"
    NEEDS_IDENTITY = "NEEDS_IDENTITY"
    NEEDS_LINK = "NEEDS_LINK"
    IMMUTABLE_CONFLICT = "IMMUTABLE_CONFLICT"
    IGNORED = "IGNORED"


@dataclass(frozen=True)
class AgentReportIngestionResult:
    outcome: AgentReportIngestionOutcome
    source_path: str
    source_report_id: str | None = None
    report_db_id: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class _BindingCandidate:
    binding_id: str
    logical_target: tuple[str, str]


class AgentReportIngestionService:
    """Ingestuje canonical agent report Markdown fajlove bez heuristika."""

    def __init__(
        self, session: Session, parser: AgentReportFrontMatterParser | None = None
    ) -> None:
        self._session = session
        self._parser = parser or AgentReportFrontMatterParser()

    def ingest_file(
        self,
        path: str | Path,
        *,
        project_id: str,
        repo_path: str,
    ) -> AgentReportIngestionResult:
        source_path = normalize_source_path(path)
        if not is_agent_report_markdown_path(source_path, repo_path):
            return AgentReportIngestionResult(
                outcome=AgentReportIngestionOutcome.IGNORED,
                source_path=source_path,
                message="Fajl nije direktni agent_reports/*.md kandidat.",
            )

        try:
            content = Path(source_path).read_bytes()
        except OSError as exc:
            return AgentReportIngestionResult(
                outcome=AgentReportIngestionOutcome.INVALID,
                source_path=source_path,
                message=f"Report fajl se ne može pročitati: {exc}",
            )

        content_sha256 = hashlib.sha256(content).hexdigest()
        try:
            markdown = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            return AgentReportIngestionResult(
                outcome=AgentReportIngestionOutcome.INVALID,
                source_path=source_path,
                message=f"Report fajl nije validan UTF-8: {exc}",
            )

        try:
            front_matter = self._parser.parse_text(markdown)
        except AgentReportFrontMatterError as exc:
            return AgentReportIngestionResult(
                outcome=self._outcome_for_parser_error(exc.code),
                source_path=source_path,
                message=exc.message,
            )

        identity_result = self._check_identity(front_matter, source_path, content_sha256)
        if identity_result is not None:
            return identity_result

        session_obj = self._resolve_session(front_matter.session_id, project_id)
        if session_obj is None:
            return AgentReportIngestionResult(
                outcome=AgentReportIngestionOutcome.NEEDS_LINK,
                source_path=source_path,
                source_report_id=front_matter.report_id,
                message="Report nema pouzdanu sesiju za dati projekat.",
            )

        binding_ids = self._resolve_binding_ids(front_matter)
        if binding_ids is None:
            return AgentReportIngestionResult(
                outcome=AgentReportIngestionOutcome.NEEDS_LINK,
                source_path=source_path,
                source_report_id=front_matter.report_id,
                message="tasks tokeni se ne mogu jednoznačno povezati sa istorijskim bindingom.",
            )

        try:
            report = ReportService(self._session).create_draft(
                session_obj.id,
                report_type=front_matter.report_type,
                work_status=front_matter.work_status,
                source_report_id=front_matter.report_id,
                source_path=source_path,
                source_content_sha256=content_sha256,
            )
            report_service = ReportService(self._session)
            for binding_id in binding_ids:
                report_service.link_report_to_binding(report.id, binding_id)
            self._session.flush()
            WorkflowLedgerService(self._session).append_implementation_completed_from_report(
                report.id
            )
        except IntegrityError as exc:
            if not self._is_source_identity_integrity_error(exc):
                raise
            self._session.rollback()
            return AgentReportIngestionResult(
                outcome=AgentReportIngestionOutcome.IMMUTABLE_CONFLICT,
                source_path=source_path,
                source_report_id=front_matter.report_id,
                message="DB source identity unique constraint je odbio konkurentni unos.",
            )

        return AgentReportIngestionResult(
            outcome=AgentReportIngestionOutcome.INGESTED,
            source_path=source_path,
            source_report_id=front_matter.report_id,
            report_db_id=report.id,
        )

    def _check_identity(
        self,
        front_matter: AgentReportFrontMatter,
        source_path: str,
        content_sha256: str,
    ) -> AgentReportIngestionResult | None:
        existing_by_id = (
            self._session.query(AgentReport)
            .filter(AgentReport.source_report_id == front_matter.report_id)
            .first()
        )
        if existing_by_id:
            if (
                existing_by_id.source_path == source_path
                and existing_by_id.source_content_sha256 == content_sha256
            ):
                return AgentReportIngestionResult(
                    outcome=AgentReportIngestionOutcome.ALREADY_INGESTED,
                    source_path=source_path,
                    source_report_id=front_matter.report_id,
                    report_db_id=existing_by_id.id,
                )
            return AgentReportIngestionResult(
                outcome=AgentReportIngestionOutcome.IMMUTABLE_CONFLICT,
                source_path=source_path,
                source_report_id=front_matter.report_id,
                report_db_id=existing_by_id.id,
                message="source_report_id već postoji sa drugom putanjom ili sadržajem.",
            )

        existing_by_path = (
            self._session.query(AgentReport)
            .filter(
                AgentReport.source_path == source_path,
                AgentReport.source_report_id.is_not(None),
            )
            .first()
        )
        if existing_by_path and existing_by_path.source_report_id != front_matter.report_id:
            return AgentReportIngestionResult(
                outcome=AgentReportIngestionOutcome.IMMUTABLE_CONFLICT,
                source_path=source_path,
                source_report_id=front_matter.report_id,
                report_db_id=existing_by_path.id,
                message="source_path već pripada drugom source_report_id.",
            )
        return None

    def _resolve_session(self, session_id: str, project_id: str) -> AgentSession | None:
        if session_id == "unknown":
            return None
        session_obj = self._session.get(AgentSession, session_id)
        if not session_obj or session_obj.project_id != project_id:
            return None
        return session_obj

    def _resolve_binding_ids(self, front_matter: AgentReportFrontMatter) -> list[str] | None:
        if front_matter.tasks == ("unassigned",):
            return []

        bindings = (
            self._session.query(SessionTaskBinding)
            .filter(SessionTaskBinding.session_id == front_matter.session_id)
            .order_by(SessionTaskBinding.started_at.asc(), SessionTaskBinding.id.asc())
            .all()
        )
        resolved: list[str] = []
        for token in front_matter.tasks:
            candidates = self._candidates_for_token(token, bindings)
            logical_targets = {candidate.logical_target for candidate in candidates}
            if not candidates or len(logical_targets) != 1:
                return None
            for candidate in candidates:
                if candidate.binding_id not in resolved:
                    resolved.append(candidate.binding_id)
        return resolved

    def _candidates_for_token(
        self, token: str, bindings: list[SessionTaskBinding]
    ) -> list[_BindingCandidate]:
        candidates: list[_BindingCandidate] = []
        for binding in bindings:
            task = self._session.get(Task, binding.task_id) if binding.task_id else None
            plan_item_id = binding.plan_item_id or (task.plan_item_id if task else None)
            plan_item = self._session.get(PlanItem, plan_item_id) if plan_item_id else None

            if binding.task_id == token:
                candidates.append(_BindingCandidate(binding.id, ("task", binding.task_id)))
            if plan_item_id and token == plan_item_id:
                candidates.append(_BindingCandidate(binding.id, ("plan_item", plan_item_id)))
            if plan_item and token == plan_item.item_key:
                candidates.append(_BindingCandidate(binding.id, ("plan_item", plan_item.id)))
        return candidates

    @staticmethod
    def _outcome_for_parser_error(
        code: AgentReportFrontMatterErrorCode,
    ) -> AgentReportIngestionOutcome:
        if code == AgentReportFrontMatterErrorCode.LEGACY_NO_FRONT_MATTER:
            return AgentReportIngestionOutcome.LEGACY_NO_FRONT_MATTER
        if code == AgentReportFrontMatterErrorCode.NEEDS_IDENTITY:
            return AgentReportIngestionOutcome.NEEDS_IDENTITY
        return AgentReportIngestionOutcome.INVALID

    @staticmethod
    def _is_source_identity_integrity_error(exc: IntegrityError) -> bool:
        message = str(getattr(exc, "orig", exc))
        return (
            "agent_reports.source_report_id" in message
            or "agent_reports.source_path" in message
            or "ix_agent_reports_source_report_id" in message
            or "ix_agent_reports_source_path" in message
        )


def normalize_source_path(path: str | Path) -> str:
    """Vraća normalizovanu apsolutnu putanju za source artifact."""
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def is_agent_report_markdown_path(path: str | Path, repo_path: str | Path) -> bool:
    """Dozvoljava samo direktne <repo_path>/agent_reports/*.md artefakte."""
    candidate = Path(normalize_source_path(path))
    reports_dir = Path(normalize_source_path(Path(repo_path) / "agent_reports"))
    return candidate.suffix.lower() == ".md" and candidate.parent == reports_dir
