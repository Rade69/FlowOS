"""HTTP API Controllers — plan progress endpointi.

Tanke FastAPI rute. Sva poslovna logika u PlanProgressService.
Bez ORM/persistence importa.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flowos.service.services.plan_progress import (
    PlanProgressError,
    PlanProgressService,
    _criterion_to_dict,
    _event_to_dict,
    _item_to_dict,
)

router = APIRouter(tags=["Plan Progress"])


def get_session(request: Request) -> Session:
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════
# Projekat → plan progres
# ═══════════════════════════════════════════════════════════════════


@router.get("/projects/{project_id}/plan-progress")
def get_project_plan_progress(project_id: str, session: Session = Depends(get_session)):
    svc = PlanProgressService(session)
    return svc.get_project_plan_progress(project_id)


# ═══════════════════════════════════════════════════════════════════
# Plan → stavke
# ═══════════════════════════════════════════════════════════════════


@router.get("/plans/{plan_id}/items")
def list_plan_items(plan_id: str, session: Session = Depends(get_session)):
    result = PlanProgressService(session).list_plan_items_grouped(plan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Plan nije pronađen")
    return result


# ═══════════════════════════════════════════════════════════════════
# PlanItem CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/plan-items/{item_id}")
def get_plan_item(item_id: str, session: Session = Depends(get_session)):
    item = PlanProgressService(session).get_plan_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Planirana stavka nije pronađena")
    return _item_to_dict(item)


@router.patch("/plan-items/{item_id}")
def update_plan_item(item_id: str, data: dict, session: Session = Depends(get_session)):
    item = PlanProgressService(session).update_plan_item(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Planirana stavka nije pronađena")
    return _item_to_dict(item)


# ═══════════════════════════════════════════════════════════════════
# Statusne akcije
# ═══════════════════════════════════════════════════════════════════


def _do_transition(item_id: str, to_status: str, reason: str | None, session: Session):
    svc = PlanProgressService(session)
    item = svc.get_plan_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Planirana stavka nije pronađena")
    try:
        svc.validate_transition(item, to_status, reason=reason)
    except PlanProgressError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return _item_to_dict(item)


@router.post("/plan-items/{item_id}/start")
def start_item(item_id: str, body: dict = {}, session: Session = Depends(get_session)):
    return _do_transition(item_id, "IN_PROGRESS", body.get("reason"), session)


@router.post("/plan-items/{item_id}/block")
def block_item(item_id: str, body: dict = {}, session: Session = Depends(get_session)):
    return _do_transition(item_id, "BLOCKED", body.get("reason"), session)


@router.post("/plan-items/{item_id}/unblock")
def unblock_item(item_id: str, body: dict = {}, session: Session = Depends(get_session)):
    return _do_transition(item_id, "IN_PROGRESS", body.get("reason"), session)


@router.post("/plan-items/{item_id}/mark-implemented")
def mark_implemented(item_id: str, body: dict = {}, session: Session = Depends(get_session)):
    return _do_transition(item_id, "IMPLEMENTED", body.get("reason"), session)


@router.post("/plan-items/{item_id}/verify")
def verify_item(item_id: str, body: dict = {}, session: Session = Depends(get_session)):
    return _do_transition(item_id, "VERIFIED", body.get("reason"), session)


@router.post("/plan-items/{item_id}/accept")
def accept_item(item_id: str, body: dict = {}, session: Session = Depends(get_session)):
    return _do_transition(item_id, "ACCEPTED", body.get("reason"), session)


@router.post("/plan-items/{item_id}/reject")
def reject_item(item_id: str, body: dict = {}, session: Session = Depends(get_session)):
    return _do_transition(item_id, "REJECTED", body.get("reason"), session)


# ═══════════════════════════════════════════════════════════════════
# Kriterijumi
# ═══════════════════════════════════════════════════════════════════


@router.get("/plan-items/{item_id}/criteria")
def list_criteria(item_id: str, session: Session = Depends(get_session)):
    criteria = PlanProgressService(session).get_item_criteria(item_id)
    return [_criterion_to_dict(c) for c in criteria]


@router.patch("/plan-item-criteria/{criterion_id}")
def update_criterion(criterion_id: str, body: dict, session: Session = Depends(get_session)):
    c = PlanProgressService(session).update_criterion(criterion_id, body)
    if not c:
        raise HTTPException(status_code=404, detail="Kriterijum nije pronađen")
    return _criterion_to_dict(c)


# ═══════════════════════════════════════════════════════════════════
# Progres događaji
# ═══════════════════════════════════════════════════════════════════


@router.get("/plan-items/{item_id}/progress-events")
def list_progress_events(item_id: str, session: Session = Depends(get_session)):
    events = PlanProgressService(session).get_progress_events(item_id)
    return [_event_to_dict(e) for e in events]


# ═══════════════════════════════════════════════════════════════════
# Import plana
# ═══════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/import-plan")
def import_plan(project_id: str, body: dict, session: Session = Depends(get_session)):
    markdown = body.get("markdown_text", "")
    if not markdown.strip():
        raise HTTPException(status_code=400, detail="markdown_text ne sme biti prazan")
    result, _ = PlanProgressService(session).import_plan(project_id, markdown)
    return result


@router.post("/plans/{plan_id}/activate")
def activate_plan(plan_id: str, session: Session = Depends(get_session)):
    result = PlanProgressService(session).activate_plan(plan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan nije pronađen")
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result