"""GUI testovi za PlanProgressView statusnu oznaku (FLOW-1106-F1).

Proverava da label plana prati canonical plan status:
ACTIVE -> "Aktivni plan", DRAFT -> "Nacrt plana", prazan rezultat -> neutralna poruka.
"""

import pytest


@pytest.fixture
def view(qtbot):
    from flowos.gui.views.plan_progress import PlanProgressView

    w = PlanProgressView()
    qtbot.addWidget(w)
    return w


def _render(view, plan_status: str, plan_title: str = "Test Plan") -> None:
    view.render(
        {
            "plan_status": plan_status,
            "plan_title": plan_title,
            "phases": [],
            "total": 0,
            "completed": 0,
            "blocked": 0,
        }
    )


def test_t1_active_plan_label(view):
    _render(view, "ACTIVE")
    assert view._plan_label.text() == "Aktivni plan: Test Plan"


def test_t2_draft_plan_label(view):
    _render(view, "DRAFT")
    assert view._plan_label.text() == "Nacrt plana: Test Plan"
    # DRAFT više ne sme biti predstavljen kao aktivan.
    assert "Aktivni" not in view._plan_label.text()


def test_t3_empty_result_label(view):
    _render(view, "", plan_title="")
    assert view._plan_label.text() == "Nema aktivnog plana"
