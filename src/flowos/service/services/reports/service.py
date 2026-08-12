"""Report Service — kreiranje, ažuriranje i izvoz izveštaja.

Report je strukturisani zapis o agentskoj sesiji koji prati
agent_report_template.md. Markdown export je format za čuvanje
kompletnog izveštaja kao artefakta.
"""

import contextlib
import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.report_models import (
    AgentReport,
    AgentReportBindingLink,
)


class ReportService:
    """Upravljanje agentskim izveštajima."""

    _WORK_STATUSES = {"completed", "partial", "blocked"}

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_draft(
        self,
        session_id: str,
        *,
        scope: str | None = None,
        summary: str | None = None,
        commit_shas: list[str] | None = None,
        changed_files: list[str] | None = None,
        verification_summary: str | None = None,
        open_risks: str | None = None,
        agent_job_id: str | None = None,
        report_type: str | None = None,
        work_status: str | None = None,
        source_report_id: str | None = None,
        source_path: str | None = None,
        source_content_sha256: str | None = None,
    ) -> AgentReport:
        """Kreira draft izveštaja za sesiju."""
        self._validate_work_status(work_status)
        report = AgentReport(
            session_id=session_id,
            agent_job_id=agent_job_id,
            report_type=report_type,
            work_status=work_status,
            source_report_id=source_report_id,
            source_path=source_path,
            source_content_sha256=source_content_sha256,
            status="DRAFT",
            scope=scope,
            summary=summary,
            commit_shas_json=json.dumps(commit_shas) if commit_shas else None,
            changed_files_json=json.dumps(changed_files) if changed_files else None,
            verification_summary=verification_summary,
            open_risks=open_risks,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(report)
        self._session.flush()
        return report

    # Polja dozvoljena za update_report (allowlista)
    _ALLOWED_UPDATE_FIELDS: set[str] = {
        "summary",
        "scope",
        "implementation_summary",
        "verification_summary",
        "open_risks",
        "follow_up",
        "where_stopped",
        "next_step",
        "resume_preconditions",
        "confidence",
        "impact_summary",
        "reproduction_summary",
        "context_used",
        "rationale",
        "untouched_scope",
        "independent_review_summary",
        "found_issues",
        "rejected_options",
        "conflicting_sources",
        "commit_shas_json",
        "changed_files_json",
        "report_type",
        "work_status",
    }

    # Polja zabranjena za update_report (samo kroz specijalizovane metode)
    _FORBIDDEN_UPDATE_FIELDS: set[str] = {
        "id",
        "session_id",
        "agent_job_id",
        "created_at",
        "updated_at",
        "user_verdict",
        "user_notes",
        "verdict_audit_json",
        "status",
    }

    def update_report(
        self,
        report_id: str,
        **fields: object,
    ) -> AgentReport | None:
        """Ažurira samo dozvoljena polja izveštaja (allowlista).

        Zabranjena polja (id, session_id, user_verdict, status, ...)
        se ne mogu menjati kroz ovu metodu.
        """
        report = self._session.get(AgentReport, report_id)
        if not report:
            return None

        for key, value in fields.items():
            if key in self._FORBIDDEN_UPDATE_FIELDS:
                raise ValueError(
                    f"Polje '{key}' ne može da se menja kroz update_report. "
                    f"Koristite specijalizovane metode (npr. set_verdict za user_verdict)."
                )
            if key not in self._ALLOWED_UPDATE_FIELDS:
                raise ValueError(f"Polje '{key}' nije na allowlisti za update_report.")
            if key == "work_status":
                self._validate_work_status(value)
            setattr(report, key, value)

        report.updated_at = datetime.now(tz=UTC)
        self._session.flush()
        return report

    def link_report_to_binding(
        self, report_id: str, session_task_binding_id: str
    ) -> AgentReportBindingLink:
        """Vezuje report samo za istorijski binding iste sesije."""
        from flowos.service.services.infrastructure.persistence.models import (
            SessionTaskBinding,
            Task,
        )

        report = self._session.get(AgentReport, report_id)
        if not report:
            raise ValueError(f"Report {report_id} ne postoji")
        binding = self._session.get(SessionTaskBinding, session_task_binding_id)
        if not binding:
            raise ValueError(f"SessionTaskBinding {session_task_binding_id} ne postoji")
        if binding.session_id != report.session_id:
            raise ValueError("Report i SessionTaskBinding moraju pripadati istoj sesiji")

        existing = (
            self._session.query(AgentReportBindingLink)
            .filter(
                AgentReportBindingLink.report_id == report_id,
                AgentReportBindingLink.session_task_binding_id == session_task_binding_id,
            )
            .first()
        )
        if existing:
            raise ValueError("Report je već povezan sa ovim SessionTaskBindingom")

        resolved_plan_item_id = binding.plan_item_id
        if not resolved_plan_item_id and binding.task_id:
            task = self._session.get(Task, binding.task_id)
            resolved_plan_item_id = task.plan_item_id if task else None

        link = AgentReportBindingLink(
            report_id=report_id,
            session_task_binding_id=session_task_binding_id,
            resolved_plan_item_id=resolved_plan_item_id,
        )
        self._session.add(link)
        self._session.flush()
        return link

    def set_verdict(
        self,
        report_id: str,
        verdict: str,
        notes: str | None = None,
        decision_id: str | None = None,
    ) -> AgentReport | None:
        """Postavlja korisnički verdict sa audit zapisom.

        Args:
            report_id: ID izveštaja.
            verdict: ACCEPTED, NEEDS_WORK, ili REJECTED.
            notes: Opcione napomene korisnika.
            decision_id: Opcioni UUID za idempotentnost odluke.

        Returns:
            Ažurirani AgentReport ili None.

        Nakon Phase 3D, authority je delegiran na WorkflowDecisionService.
        WorkflowLedgerEvent(TASK_DECISION) je canonical history korisničkih
        workflow odluka.
        """
        from flowos.service.services.workflow.decisions import WorkflowDecisionService

        return WorkflowDecisionService(self._session).record_report_decision(
            report_id=report_id,
            verdict=verdict,
            notes=notes,
            decision_id=decision_id,
        )

    def get_report(self, report_id: str) -> AgentReport | None:
        """Vraća izveštaj po ID-ju."""
        return self._session.get(AgentReport, report_id)

    def _reopen_plan_item(self, report: AgentReport) -> None:
        """Vraća samo PlanItem-e dokazive iz report bindinga u IN_PROGRESS."""
        import logging

        logger = logging.getLogger("flowos.reports")
        try:
            from flowos.service.services.infrastructure.persistence.models import SessionTaskBinding
            from flowos.service.services.infrastructure.persistence.plan_models import PlanItem
            from flowos.service.services.plan_progress import PlanProgressService

            progress_svc = PlanProgressService(self._session)
            links = (
                self._session.query(AgentReportBindingLink)
                .filter(AgentReportBindingLink.report_id == report.id)
                .order_by(AgentReportBindingLink.session_task_binding_id.asc())
                .all()
            )
            if links:
                plan_item_ids = {
                    link.resolved_plan_item_id
                    for link in links
                    if link.resolved_plan_item_id is not None
                }
            else:
                bindings = (
                    self._session.query(SessionTaskBinding)
                    .filter(
                        SessionTaskBinding.session_id == report.session_id,
                        (SessionTaskBinding.task_id.is_not(None))
                        | (SessionTaskBinding.plan_item_id.is_not(None)),
                    )
                    .order_by(SessionTaskBinding.started_at.asc(), SessionTaskBinding.id.asc())
                    .all()
                )
                if len(bindings) != 1:
                    logger.warning(
                        "ReportService: legacy report %s nema jedinstven istorijski binding; "
                        "PlanItem nije reopenovan",
                        report.id,
                    )
                    return
                binding = bindings[0]
                if binding.plan_item_id:
                    plan_item_ids = {binding.plan_item_id}
                else:
                    logger.warning(
                        "ReportService: legacy report %s nema istorijski PlanItem snapshot; "
                        "PlanItem nije reopenovan",
                        report.id,
                    )
                    return

            for plan_item_id in sorted(plan_item_ids):
                plan_item = self._session.get(PlanItem, plan_item_id)
                if not plan_item or plan_item.status not in ("IMPLEMENTED", "VERIFIED"):
                    continue
                progress_svc.validate_transition(
                    plan_item,
                    "IN_PROGRESS",
                    reason=f"Verdict: {report.user_verdict}",
                    allow_verdict_reopen=True,
                )
                logger.info(
                    "ReportService: plan_item %s → IN_PROGRESS (verdict=%s)",
                    plan_item.item_key,
                    report.user_verdict,
                )
        except Exception as e:
            logger.warning("ReportService: reopen plan_item nije uspelo: %s", e)

    def _validate_work_status(self, work_status: object) -> None:
        if work_status is not None and work_status not in self._WORK_STATUSES:
            raise ValueError(
                f"Nedozvoljen work_status: {work_status}. Dozvoljeni: {sorted(self._WORK_STATUSES)}"
            )

    def get_report_for_session(self, session_id: str) -> AgentReport | None:
        """Vraća izveštaj za datu sesiju (najnoviji)."""
        return (
            self._session.query(AgentReport)
            .filter(AgentReport.session_id == session_id)
            .order_by(AgentReport.created_at.desc())
            .first()
        )

    def list_reports(self, session_id: str | None = None, limit: int = 50) -> list[AgentReport]:
        """Vraća listu izveštaja, opciono filtriranu po sesiji."""
        q = self._session.query(AgentReport)
        if session_id:
            q = q.filter(AgentReport.session_id == session_id)
        return q.order_by(AgentReport.created_at.desc()).limit(limit).all()

    def to_markdown(self, report: AgentReport) -> str:
        """Izvoz izveštaja u Markdown format po agent_report_template.md.

        Sekcije bez sadržaja prikazuju 'Nema.'
        """

        def _val(field: str, default: str = "Nema.") -> str:
            v = getattr(report, field, None)
            if not v:
                return default
            return str(v).strip() or default

        commit_shas = []
        with contextlib.suppress(json.JSONDecodeError):
            commit_shas = json.loads(report.commit_shas_json or "[]")

        changed_files = []
        with contextlib.suppress(json.JSONDecodeError):
            changed_files = json.loads(report.changed_files_json or "[]")

        lines = [
            f"# Agent Report — {report.id[:8]}",
            "",
            f"**Datum:** {report.created_at.strftime('%Y-%m-%d') if report.created_at else 'N/A'}",
            f"**Status:** {report.status}",
            f"**Verdict:** {report.user_verdict or 'N/A'}",
            "",
            "## Scope",
            _val("scope"),
            "",
            "## Impact analiza",
            _val("impact_summary"),
            "",
            "## Reprodukcija pre izmene",
            _val("reproduction_summary"),
            "",
            "## Korišćen kontekst",
            _val("context_used"),
            "",
            "## Šta je urađeno",
            _val("summary"),
            "",
            "## Zašto",
            _val("rationale"),
            "",
            "## Kako",
            _val("implementation_summary"),
            "",
            "## Šta nije dirano",
            _val("untouched_scope"),
            "",
            "## Verifikacija",
            _val("verification_summary"),
            "",
            "## Nezavisna provjera",
            _val("independent_review_summary"),
            "",
            "## Pronađeni problemi",
            _val("found_issues"),
            "",
            "## Odbačene opcije",
            _val("rejected_options"),
            "",
            "## Konfliktni izvori",
            _val("conflicting_sources"),
            "",
            "## Commitovi",
            ", ".join(commit_shas) if commit_shas else "Nema.",
            "",
            "## Izmenjeni fajlovi",
            ", ".join(changed_files) if changed_files else "Nema.",
            "",
            "## Rizici",
            _val("open_risks"),
            "",
            "## Follow-up",
            _val("follow_up"),
            "",
            "## Potrebna korisnička potvrda",
            "Da" if report.user_confirmation_required else "Ne",
            "",
            "## Korisničke napomene",
            report.user_notes or "Nema.",
        ]
        return "\n".join(lines)
