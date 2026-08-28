"""Regresioni testovi za FlowOsGui → PlanController import tok."""


def test_import_plan_delegates_to_plan_controller(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    from flowos.gui.composition_root import FlowOsGui

    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")

    class PlanControllerSpy:
        def __init__(self):
            self.calls = []

        def import_plan(self, project_id, file_path):
            self.calls.append((project_id, file_path))

    class DirectApiCallForbidden:
        def _post(self, *_args, **_kwargs):
            raise AssertionError("composition_root ne smije direktno pozvati _api._post")

    controller = PlanControllerSpy()
    gui = FlowOsGui.__new__(FlowOsGui)
    gui._window = object()
    gui._api = DirectApiCallForbidden()
    gui._plan_controller = controller
    gui._active_project_id = "project-1"

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(plan_file), "Markdown (*.md)"),
    )

    gui._on_import_plan()

    assert controller.calls == [("project-1", str(plan_file))]


def test_plan_controller_reads_markdown_text_and_refreshes_progress(tmp_path):
    from flowos.gui.controllers.plan import PlanController

    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")

    class FakeApi:
        def __init__(self):
            self.imports = []
            self.refreshed = []

        def import_plan(self, project_id, markdown_text, on_success):
            self.imports.append((project_id, {"markdown_text": markdown_text}))
            on_success({"plan_id": "draft-plan"})

        def get_plan_progress(self, project_id):
            self.refreshed.append(project_id)

    api = FakeApi()
    controller = PlanController(api)

    controller.import_plan("project-1", str(plan_file))

    assert api.imports == [("project-1", {"markdown_text": "# Plan\n"})]
    assert api.refreshed == ["project-1"]
