"""Report Service — kreiranje, ažuriranje i izvoz izveštaja.

Report je strukturisani zapis o agentskoj sesiji koji prati
agent_report_template.md. Markdown export je format za čuvanje
kompletnog izveštaja kao artefakta.
"""

import contextlib
import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.report_models import AgentReport


class ReportService:
    """Upravljanje agentskim izveštajima."""

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
    ) -> AgentReport:
        """Kreira draft izveštaja za sesiju."""
        report = AgentReport(
            session_id=session_id,
            agent_job_id=agent_job_id,
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
            setattr(report, key, value)

        report.updated_at = datetime.now(tz=UTC)
        self._session.flush()
        return report

    def set_verdict(
        self,
        report_id: str,
        verdict: str,
        notes: str | None = None,
    ) -> AgentReport | None:
        """Postavlja korisnički verdict sa audit zapisom.

        Args:
            report_id: ID izveštaja.
            verdict: ACCEPTED, NEEDS_WORK, ili REJECTED.
            notes: Opcione napomene korisnika.

        Returns:
            Ažurirani AgentReport ili None.

        Audit zapis sadrži: ko, kada, vrednost, razlog, prethodna vrednost.
        """
        allowed = {"ACCEPTED", "NEEDS_WORK", "REJECTED"}
        if verdict not in allowed:
            raise ValueError(f"Nedozvoljen verdict: {verdict}. Dozvoljeni: {sorted(allowed)}")

        report = self._session.get(AgentReport, report_id)
        if not report:
            return None

        # Kreiraj audit zapis
        previous_verdict = report.user_verdict
        previous_status = report.status
        audit_entry = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "report_id": report_id,
            "previous_verdict": previous_verdict,
            "new_verdict": verdict,
            "previous_status": previous_status,
            "new_status": "FINAL",
            "actor": "user",
            "notes": notes,
        }

        # Dodaj u listu audit zapisa
        try:
            audit_list: list[dict] = json.loads(report.verdict_audit_json or "[]")
        except (json.JSONDecodeError, TypeError):
            audit_list = []
        audit_list.append(audit_entry)
        report.verdict_audit_json = json.dumps(audit_list, ensure_ascii=False)

        report.user_verdict = verdict
        report.user_notes = notes
        report.status = "FINAL"
        report.updated_at = datetime.now(tz=UTC)
        self._session.flush()
        return report

    def get_report(self, report_id: str) -> AgentReport | None:
        """Vraća izveštaj po ID-ju."""
        return self._session.get(AgentReport, report_id)

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
