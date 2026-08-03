"""End-to-End test Faze 3 — kompletan tok od promene fajla do izveštaja.

Proverava ceo lanac:
promena fajla → watcher → FileActivity → atribucija → WRITE_WRITE →
završetak sesije → Git stanje → NO_COMMIT → verify artefakt → draft report → timeline

Koristi stvarni Git repozitorijum, stvarni watcher, file-based SQLite.
"""

import contextlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
from flowos.service.services.activity.service import ActivityService
from flowos.service.services.attribution.service import ActiveSession
from flowos.service.services.conflicts.service import ConflictDetectionService
from flowos.service.services.infrastructure.git_poller import GitStateReader
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.infrastructure.watcher import WatcherPipeline
from flowos.service.services.reports.service import ReportService
from flowos.service.services.sessions.completion import SessionCompletionService
from flowos.service.services.sessions.timeline import TimelineService
from flowos.service.services.verification.service import VerificationService


@pytest.fixture
def git_repo():
    """Privremeni Git repozitorijum sa stvarnim git init i verify.py."""
    with tempfile.TemporaryDirectory(prefix="flowos_e2e_") as tmp:
        repo = Path(tmp)

        # git init
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@flowos.local"],
            cwd=str(repo),
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "FlowOS Test"],
            cwd=str(repo),
            capture_output=True,
        )

        # Inicijalni commit
        (repo / "README.md").write_text("# E2E Test Repo\n")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo), capture_output=True)

        # Kreiraj scripts/verify.py
        (repo / "scripts").mkdir(exist_ok=True)
        (repo / "scripts" / "verify.py").write_text(
            "import sys; print('E2E verify OK'); sys.exit(0)\n"
        )

        # Kreiraj src folder
        (repo / "src").mkdir(exist_ok=True)

        yield repo


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    with contextlib.suppress(OSError):
        os.unlink(path)


@pytest.fixture
def engine(db_path):
    eng = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


class TestPhase3E2E:
    """Kompletan end-to-end tok Faze 3."""

    def test_full_flow_watcher_to_report(self, git_repo: Path, engine, db_path: str):
        """Kompletan tok: promena fajla → watcher → konflikt → završetak → report."""
        db = Session(engine)
        try:
            repo_str = str(git_repo)

            # 1. Kreiraj projekat
            project = Project(id="e2e-proj-001", name="E2E", repo_path=repo_str)
            db.add(project)
            db.flush()

            # 2. Kreiraj aktivnu sesiju
            session_a = AgentSession(
                id="e2e-sess-a",
                project_id=project.id,
                agent_type="claude-code",
                repo_path=repo_str,
                status="ACTIVE",
                branch_name="main",
            )
            db.add(session_a)
            db.flush()

            # 3. Sačuvaj base commit
            reader = GitStateReader(repo_str)
            git_state = reader.read_state()
            base_commit = git_state.commit_sha
            session_a.base_commit_sha = base_commit
            db.flush()
            db.commit()
            assert base_commit is not None, "Git repo mora imati bar jedan commit"

            # 4. Pokreni watcher
            events_received: list = []

            def watcher_callback(event):
                events_received.append(event)
                cb_db = Session(engine)
                try:
                    activity_svc = ActivityService(cb_db)
                    activity_svc.record_file_event(
                        file_path=event.path,
                        event_type=event.event_type,
                        project_id=project.id,
                        repo_path=repo_str,
                        active_sessions=[
                            ActiveSession(
                                session_id=session_a.id,
                                worktree_path=session_a.worktree_path,
                                repo_path=session_a.repo_path,
                            )
                        ],
                    )
                    cb_db.commit()
                except Exception:
                    cb_db.rollback()
                    raise
                finally:
                    cb_db.close()

            watcher = WatcherPipeline(callback=watcher_callback, debounce_ms=200)
            watcher.start(repo_str)
            assert watcher.is_running

            try:
                # 5. Izmeni fajl
                test_file = git_repo / "src" / "app.py"
                test_file.write_text("# E2E test modification\n")
                time.sleep(2.5)

                # 6. Potvrdi FileActivity u bazi
                check_db = Session(engine)
                try:
                    activities = (
                        check_db.query(FileActivity)
                        .filter(FileActivity.project_id == project.id)
                        .all()
                    )
                    app_events = [a for a in activities if "app.py" in a.file_path]
                    assert len(app_events) >= 1, (
                        f"Očekuje se FileActivity za app.py. "
                        f"Callback poziva: {len(events_received)}. "
                        f"Ukupno aktivnosti: {len(activities)}"
                    )
                    # 7. Potvrdi atribuciju
                    evt = app_events[0]
                    assert evt.session_id == session_a.id, (
                        f"Atribucija treba da bude sesiji {session_a.id}, "
                        f"dobijeno: {evt.session_id}, attr={evt.attribution_type}"
                    )
                finally:
                    check_db.close()

                # 8. Simuliraj drugu sesiju u istom tree-u
                session_b = AgentSession(
                    id="e2e-sess-b",
                    project_id=project.id,
                    agent_type="pi",
                    repo_path=repo_str,
                    status="ACTIVE",
                )
                db.add(session_b)
                db.flush()

                # Zabeleži aktivnost za drugu sesiju
                activity_svc = ActivityService(db)
                activity_svc.record_file_event(
                    file_path=str(test_file),
                    event_type="MODIFIED",
                    project_id=project.id,
                    repo_path=repo_str,
                    active_sessions=[
                        ActiveSession(session_id=session_a.id, repo_path=repo_str),
                        ActiveSession(session_id=session_b.id, repo_path=repo_str),
                    ],
                )
                db.commit()

                # 9. Detektuj WRITE_WRITE kroz pravi conflict callback lanac
                conflict_svc = ConflictDetectionService(db)
                activity_svc.register_conflict_callback(
                    lambda act: conflict_svc.on_file_activity(
                        act,
                        [
                            ActiveSession(session_id=session_a.id, repo_path=repo_str),
                            ActiveSession(session_id=session_b.id, repo_path=repo_str),
                        ],
                    )
                )
                # Zabeleži aktivnost za session_b na istom fajlu
                activity_svc.record_file_event(
                    file_path=str(test_file),
                    event_type="MODIFIED",
                    project_id=project.id,
                    repo_path=repo_str,
                    active_sessions=[
                        ActiveSession(session_id=session_b.id, repo_path=repo_str),
                    ],
                )
                db.commit()

                # Potvrdi WRITE_WRITE konflikt je detektovan
                ww_conflicts = (
                    db.query(Conflict)
                    .filter(
                        Conflict.project_id == project.id,
                        Conflict.conflict_type == "WRITE_WRITE",
                    )
                    .all()
                )
                assert len(ww_conflicts) >= 1, (
                    f"Očekuje se WRITE_WRITE konflikt. Dobijeno: {len(ww_conflicts)}"
                )
                ww = ww_conflicts[0]
                assert ww.conflict_key is not None, "WRITE_WRITE konflikt treba da ima conflict_key"
                assert ww.conflict_level == "HIGH"
                assert ww.first_seen_at is not None
                assert ww.last_seen_at is not None
                assert ww.occurrence_count >= 1

                # 10 + 11. Završi sesiju bez commita + očitaj Git stanje
                completion_svc = SessionCompletionService(db)
                completion_svc.complete_session(
                    session_id=session_a.id,
                    exit_code=0,
                    result_commit_sha=None,  # nema commita!
                )

                # 12. Potvrdi NO_COMMIT konflikt
                no_commit_conflicts = (
                    db.query(Conflict)
                    .filter(
                        Conflict.project_id == project.id,
                        Conflict.conflict_type == "NO_COMMIT",
                    )
                    .all()
                )
                assert len(no_commit_conflicts) == 1, (
                    f"Očekuje se NO_COMMIT konflikt. Dobijeno: {len(no_commit_conflicts)}"
                )

                # 13 + 14. Potvrdi verify artefakt
                verify_svc = VerificationService()
                result = verify_svc.run_verify(repo_str)
                assert result.success is True, (
                    f"Verify treba da prođe. exit={result.exit_code}, stderr={result.stderr}"
                )
                if result.artifact_path:
                    artifact_dir = Path(result.artifact_path)
                    assert artifact_dir.is_dir()
                    assert (artifact_dir / "stdout.txt").is_file()
                    assert (artifact_dir / "metadata.json").is_file()
                    meta = json.loads((artifact_dir / "metadata.json").read_text())
                    assert meta["status"] == "PASS"

                # 15 + 16. Kreiraj draft report i potvrdi podatke
                report_svc = ReportService(db)
                report = report_svc.create_draft(
                    session_id=session_a.id,
                    summary="E2E test sesija završena.",
                    scope="Faza 3 E2E",
                    verification_summary=f"Verify: {'PASS' if result.success else 'FAIL'}",
                    open_risks="WRITE_WRITE i NO_COMMIT detektovani",
                )
                assert report.id is not None
                assert report.status == "DRAFT"

                # 17. Potvrdi timeline sa svim očekivanim izvorima
                timeline_svc = TimelineService(db)
                tl = timeline_svc.get_timeline(
                    session_a.id, level="technical", page=1, page_size=200
                )
                assert tl["total"] >= 1, f"Timeline treba da ima bar 1 događaj. Dobijeno: {tl}"
                assert tl["level"] == "technical"
                origins = {e.get("origin") for e in tl["events"]}
                expected_origins = {"SessionEvent", "AgentReport"}
                missing = expected_origins - origins
                assert not missing, (
                    f"Timeline treba da sadrži izvore: {expected_origins}. "
                    f"Nedostaju: {missing}. Dobijeni: {origins}"
                )
                assert len(tl["events"]) <= tl["page_size"], "Paginacija nije ispoštovana"

                # Testiraj enum validaciju
                with pytest.raises(ValueError, match="Nevalidan level"):
                    timeline_svc.get_timeline(session_a.id, level="invalid_level")

                with pytest.raises(ValueError, match="page mora biti"):
                    timeline_svc.get_timeline(session_a.id, page=0)

                with pytest.raises(ValueError, match="page_size mora biti"):
                    timeline_svc.get_timeline(session_a.id, page_size=500)

                # Testiraj SUMMARY nivo — ne prikazuje raw detalje
                tl_summary = timeline_svc.get_timeline(session_a.id, level="summary")
                for e in tl_summary["events"]:
                    assert e["origin"] == "SessionEvent", (
                        f"SUMMARY ne sme prikazivati {e['origin']}: {e}"
                    )

                # Testiraj TECHNICAL nivo — prikazuje evidence
                tl_technical = timeline_svc.get_timeline(session_a.id, level="technical")
                origins = {e["origin"] for e in tl_technical["events"]}
                assert len(origins) >= 1  # bar SessionEvent

            finally:
                # 18 + 19. Ugasi watcher i potvrdi
                watcher.stop()
                assert not watcher.is_running

        finally:
            db.close()

    def test_worktree_isolation_no_conflict(self, git_repo: Path, engine, db_path: str):
        """Dve sesije u različitim worktree-ovima → nema WRITE_WRITE."""
        db = Session(engine)
        try:
            repo_str = str(git_repo)

            # Kreiraj dva worktree foldera
            wt_a = git_repo / "wt-a"
            wt_b = git_repo / "wt-b"
            wt_a.mkdir()
            wt_b.mkdir()

            project = Project(id="e2e-iso-proj", name="Worktree Isolation", repo_path=repo_str)
            db.add(project)
            db.flush()

            session_a = AgentSession(
                id="e2e-iso-a",
                project_id=project.id,
                agent_type="cc",
                repo_path=repo_str,
                worktree_path=str(wt_a),
                status="ACTIVE",
            )
            session_b = AgentSession(
                id="e2e-iso-b",
                project_id=project.id,
                agent_type="pi",
                repo_path=repo_str,
                worktree_path=str(wt_b),
                status="ACTIVE",
            )
            db.add_all([session_a, session_b])
            db.flush()
            db.commit()

            # Zabeleži aktivnosti za obe sesije — isti relativni fajl
            activity_svc = ActivityService(db)
            file_a = str(wt_a / "src" / "shared.py")
            file_b = str(wt_b / "src" / "shared.py")

            activity_svc.record_file_event(
                file_path=file_a,
                event_type="MODIFIED",
                project_id=project.id,
                repo_path=repo_str,
                active_sessions=[
                    ActiveSession(
                        session_id=session_a.id, worktree_path=str(wt_a), repo_path=repo_str
                    ),
                    ActiveSession(
                        session_id=session_b.id, worktree_path=str(wt_b), repo_path=repo_str
                    ),
                ],
            )
            activity_svc.record_file_event(
                file_path=file_b,
                event_type="MODIFIED",
                project_id=project.id,
                repo_path=repo_str,
                active_sessions=[
                    ActiveSession(
                        session_id=session_a.id, worktree_path=str(wt_a), repo_path=repo_str
                    ),
                    ActiveSession(
                        session_id=session_b.id, worktree_path=str(wt_b), repo_path=repo_str
                    ),
                ],
            )
            db.commit()

            # Detektuj konflikte
            conflict_svc = ConflictDetectionService(db)
            recent = activity_svc.get_recent_activities(project.id, minutes=30)
            active_sessions_list = [
                ActiveSession(session_id=s.id, worktree_path=s.worktree_path, repo_path=s.repo_path)
                for s in [session_a, session_b]
            ]
            conflicts = conflict_svc.detect_write_write(project.id, recent, active_sessions_list)

            # Različiti worktree-evi → nema konflikta
            assert len(conflicts) == 0, (
                f"Različiti worktree-evi ne smeju proizvesti WRITE_WRITE. "
                f"Dobijeno: {len(conflicts)}"
            )

        finally:
            db.close()
