"""HTTP API Controllers — plan progress endpointi.

Tanke FastAPI rute za rad sa planovima, stavkama, kriterijumima,
zavisnostima i statusnim akcijama. Sva poslovna logika je u
PlanProgressService i PlanImportService.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.plan_models import (
    Plan,
    PlanItem,
    PlanItemCriterion,
    PlanPhase,
    PlanProgressEvent,
)
from flowos.service.services.plan_import import PlanImportService
from flowos.service.services.plan_progress import PlanProgressError, PlanProgressService

router = APIRouter(prefix="/plans", tags=["Plan Progress"])


def get_session(request: Request) -> Session:
    """FastAPI dependency — vraća SQLAlchemy Session."""
    factory = request.app.state.session_factory
    return factory()


# ═══════════════════════════════════════════════════════════════════
# Projekat → plan progres
# ═══════════════════════════════════════════════════════════════════


@router.get("/projects/{project_id}/plan-progress")
def get_project_plan_progress(project_id: str, session: Session = Depends(get_session)):
    """Vraća sažetak napretka aktivnog plana za projekat."""
    plan = (
        session.query(Plan)
        .filter(Plan.project_id == project_id, Plan.status.in_(("ACTIVE", "DRAFT")))
        .order_by(Plan.created_at.desc())
        .first()
    )

    if not plan:
        return {
            "plan": None,
            "phases": [],
            "total_items": 0,
            "completed_items": 0,
            "blocked_items": 0,
        }

    phases = (
        session.query(PlanPhase)
        .filter(PlanPhase.plan_id == plan.id)
        .order_by(PlanPhase.sequence)
        .all()
    )

    total = 0
    completed = 0
    blocked = 0
    for phase in phases:
        items = session.query(PlanItem).filter(PlanItem.plan_phase_id == phase.id).all()
        total += len(items)
        completed += sum(1 for i in items if i.status == "ACCEPTED")
        blocked += sum(1 for i in items if i.status == "BLOCKED")
        phase.status = PlanProgressService.derive_phase_status(items)

    return {
        "plan": {
            "id": plan.id,
            "project_id": plan.project_id,
            "title": plan.title,
            "status": plan.status,
            "activated_at": plan.activated_at.isoformat() if plan.activated_at else None,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
        },
        "phases": [
            {
                "id": p.id,
                "plan_id": p.plan_id,
                "phase_key": p.phase_key,
                "title": p.title,
                "sequence": p.sequence,
                "status": p.status,
            }
            for p in phases
        ],
        "total_items": total,
        "completed_items": completed,
        "blocked_items": blocked,
    }


# ═══════════════════════════════════════════════════════════════════
# Plan → stavke
# ═══════════════════════════════════════════════════════════════════


@router.get("/{plan_id}/items")
def list_plan_items(plan_id: str, session: Session = Depends(get_session)):
    """Vraća sve stavke plana grupisane po fazama."""
    plan = session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan nije pronađen")

    phases = (
        session.query(PlanPhase)
        .filter(PlanPhase.plan_id == plan_id)
        .order_by(PlanPhase.sequence)
        .all()
    )

    result: list[dict[str, Any]] = []
    for phase in phases:
        items = (
            session.query(PlanItem)
            .filter(PlanItem.plan_phase_id == phase.id)
            .order_by(PlanItem.sequence)
            .all()
        )
        result.append(
            {
                "phase": _phase_to_dict(phase),
                "items": [_item_to_dict(i) for i in items],
            }
        )

    return result


# ═══════════════════════════════════════════════════════════════════
# PlanItem CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/items/{item_id}")
def get_plan_item(item_id: str, session: Session = Depends(get_session)):
    """Vraća pojedinačnu planiranu stavku."""
    item = session.get(PlanItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Planirana stavka nije pronađena")
    return _item_to_dict(item)


@router.patch("/items/{item_id}")
def update_plan_item(
    item_id: str,
    data: dict[str, Any],
    session: Session = Depends(get_session),
):
    """Ažurira polja planirane stavke (title, description, risk_level)."""
    item = session.get(PlanItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Planirana stavka nije pronađena")

    allowed = {"title", "description", "risk_level"}
    changed = False
    for key, value in data.items():
        if key in allowed and value is not None:
            setattr(item, key, value)
            changed = True

    if changed:
        session.commit()

    return _item_to_dict(item)


# ═══════════════════════════════════════════════════════════════════
# Statusne akcije
# ═══════════════════════════════════════════════════════════════════


def _do_transition(item_id: str, to_status: str, request: dict[str, Any], session: Session):
    """Zajednička logika za statusne akcije."""
    item = session.get(PlanItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Planirana stavka nije pronađena")

    progress = PlanProgressService(session)
    reason = request.get("reason") if request else None

    try:
        progress.validate_transition(item, to_status, reason=reason)
        session.commit()
    except PlanProgressError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return _item_to_dict(item)


@router.post("/items/{item_id}/start")
def start_item(item_id: str, body: dict[str, Any] = {}, session: Session = Depends(get_session)):
    """NOT_STARTED → IN_PROGRESS."""
    return _do_transition(item_id, "IN_PROGRESS", body, session)


@router.post("/items/{item_id}/block")
def block_item(item_id: str, body: dict[str, Any] = {}, session: Session = Depends(get_session)):
    """Bilo koji → BLOCKED."""
    return _do_transition(item_id, "BLOCKED", body, session)


@router.post("/items/{item_id}/unblock")
def unblock_item(item_id: str, body: dict[str, Any] = {}, session: Session = Depends(get_session)):
    """BLOCKED → IN_PROGRESS."""
    return _do_transition(item_id, "IN_PROGRESS", body, session)


@router.post("/items/{item_id}/mark-implemented")
def mark_implemented(
    item_id: str, body: dict[str, Any] = {}, session: Session = Depends(get_session)
):
    """IN_PROGRESS → IMPLEMENTED."""
    return _do_transition(item_id, "IMPLEMENTED", body, session)


@router.post("/items/{item_id}/verify")
def verify_item(item_id: str, body: dict[str, Any] = {}, session: Session = Depends(get_session)):
    """IMPLEMENTED → VERIFIED."""
    return _do_transition(item_id, "VERIFIED", body, session)


@router.post("/items/{item_id}/accept")
def accept_item(item_id: str, body: dict[str, Any] = {}, session: Session = Depends(get_session)):
    """VERIFIED → ACCEPTED."""
    return _do_transition(item_id, "ACCEPTED", body, session)


@router.post("/items/{item_id}/reject")
def reject_item(item_id: str, body: dict[str, Any] = {}, session: Session = Depends(get_session)):
    """VERIFIED → REJECTED."""
    return _do_transition(item_id, "REJECTED", body, session)


# ═══════════════════════════════════════════════════════════════════
# Kriterijumi
# ═══════════════════════════════════════════════════════════════════


@router.get("/items/{item_id}/criteria")
def list_criteria(item_id: str, session: Session = Depends(get_session)):
    """Vraća sve acceptance kriterijume za stavku."""
    item = session.get(PlanItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Planirana stavka nije pronađena")

    criteria = (
        session.query(PlanItemCriterion).filter(PlanItemCriterion.plan_item_id == item_id).all()
    )
    return [_criterion_to_dict(c) for c in criteria]


@router.patch("/criteria/{criterion_id}")
def update_criterion(
    criterion_id: str,
    body: dict[str, Any],
    session: Session = Depends(get_session),
):
    """Ažurira status, dokaz i opis kriterijuma."""
    criterion = session.get(PlanItemCriterion, criterion_id)
    if not criterion:
        raise HTTPException(status_code=404, detail="Kriterijum nije pronađen")

    allowed = {"status", "evidence_artifact_id", "verification_summary", "verified_by"}
    for key, value in body.items():
        if key in allowed:
            setattr(criterion, key, value)

    session.commit()
    return _criterion_to_dict(criterion)


# ═══════════════════════════════════════════════════════════════════
# Progres događaji
# ═══════════════════════════════════════════════════════════════════


@router.get("/items/{item_id}/progress-events")
def list_progress_events(item_id: str, session: Session = Depends(get_session)):
    """Vraća sve audit događaje za stavku."""
    item = session.get(PlanItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Planirana stavka nije pronađena")

    events = (
        session.query(PlanProgressEvent)
        .filter(PlanProgressEvent.plan_item_id == item_id)
        .order_by(PlanProgressEvent.occurred_at.desc())
        .limit(50)
        .all()
    )
    return [_event_to_dict(e) for e in events]


# ═══════════════════════════════════════════════════════════════════
# Import plana
# ═══════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/import")
def import_plan(project_id: str, body: dict[str, Any], session: Session = Depends(get_session)):
    """Parsira Markdown i kreira DRAFT Plan u bazi."""
    markdown = body.get("markdown_text", "")
    if not markdown.strip():
        raise HTTPException(status_code=400, detail="markdown_text ne sme biti prazan")

    svc = PlanImportService(session)
    result = svc.import_plan(
        project_id,
        markdown,
        source_artifact_id=body.get("source_artifact_id"),
    )
    session.commit()

    plan = (
        session.query(Plan)
        .filter(Plan.project_id == project_id, Plan.status == "DRAFT")
        .order_by(Plan.created_at.desc())
        .first()
    )

    return {
        "plan_id": plan.id if plan else "",
        "phases": result.stats["phases"],
        "items": result.stats["items"],
        "criteria": result.stats["criteria"],
        "dependencies": result.stats["dependencies"],
        "unclear_count": result.stats["unclear"],
        "unclear_sections": result.unclear_sections,
    }


@router.post("/{plan_id}/activate")
def activate_plan(plan_id: str, session: Session = Depends(get_session)):
    """Aktivira DRAFT plan."""
    plan = session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan nije pronađen")
    if plan.status != "DRAFT":
        raise HTTPException(
            status_code=409, detail=f"Plan nije u DRAFT statusu (trenutno: {plan.status})"
        )

    from datetime import UTC, datetime

    plan.status = "ACTIVE"
    plan.activated_at = datetime.now(tz=UTC)
    session.commit()

    return {"plan_id": plan.id, "status": "ACTIVE", "activated_at": plan.activated_at.isoformat()}


# ═══════════════════════════════════════════════════════════════════
# Serijalizacija u dict
# ═══════════════════════════════════════════════════════════════════


def _item_to_dict(item: PlanItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "plan_phase_id": item.plan_phase_id,
        "item_key": item.item_key,
        "title": item.title,
        "description": item.description,
        "sequence": item.sequence,
        "risk_level": item.risk_level,
        "status": item.status,
        "progress_source": item.progress_source,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "implemented_at": item.implemented_at.isoformat() if item.implemented_at else None,
        "verified_at": item.verified_at.isoformat() if item.verified_at else None,
        "accepted_at": item.accepted_at.isoformat() if item.accepted_at else None,
        "blocked_reason": item.blocked_reason,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _criterion_to_dict(c: PlanItemCriterion) -> dict[str, Any]:
    return {
        "id": c.id,
        "plan_item_id": c.plan_item_id,
        "criterion_key": c.criterion_key,
        "description": c.description,
        "status": c.status,
        "evidence_artifact_id": c.evidence_artifact_id,
        "verification_summary": c.verification_summary,
        "verified_at": c.verified_at.isoformat() if c.verified_at else None,
        "verified_by": c.verified_by,
    }


def _event_to_dict(e: PlanProgressEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "plan_item_id": e.plan_item_id,
        "session_id": e.session_id,
        "agent_report_id": e.agent_report_id,
        "from_status": e.from_status,
        "to_status": e.to_status,
        "reason": e.reason,
        "evidence_artifact_ids_json": e.evidence_artifact_ids_json,
        "source": e.source,
        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
    }


def _phase_to_dict(p: PlanPhase) -> dict[str, Any]:
    return {
        "id": p.id,
        "plan_id": p.plan_id,
        "phase_key": p.phase_key,
        "title": p.title,
        "sequence": p.sequence,
        "status": p.status,
    }
