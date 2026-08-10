"""GUI regresioni test za import-plan response shape."""


def test_import_plan_refreshes_plan_progress_after_success(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    from flowos.gui.composition_root import FlowOsGui

    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")

    class FakeApi:
        def __init__(self):
            self.posts = []
            self.refreshed = []

        def _post(self, path, body, callback):
            self.posts.append((path, body))
            callback({"plan_id": "draft-plan"})

        def get_plan_progress(self, project_id):
            self.refreshed.append(project_id)

    fake_api = FakeApi()
    gui = FlowOsGui.__new__(FlowOsGui)
    gui._window = object()
    gui._api = fake_api
    gui._active_project_id = "project-1"

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(plan_file), "Markdown (*.md)"),
    )

    gui._on_import_plan()

    assert fake_api.posts == [("/projects/project-1/import-plan", {"markdown": "# Plan\n"})]
    assert fake_api.refreshed == ["project-1"]
