"""Ponašajni testovi novih GUI Controllera i njihove javne API granice."""

import os


def test_agents_controller_normalizes_and_delegates_absolute_repo_path():
    from flowos.gui.controllers.agents import AgentsController

    class FakeApi:
        def __init__(self):
            self.calls = []

        def create_tracked_session(self, project_id, agent_type, repo_path, pid):
            self.calls.append((project_id, agent_type, repo_path, pid))

    api = FakeApi()
    controller = AgentsController(api)
    requested = []
    controller.tracking_requested.connect(lambda: requested.append(True))

    controller.track_agent("project-1", "H:/repo", 1234, " Claude   Code ")

    assert api.calls == [("project-1", "claude_code", "H:/repo", 1234)]
    assert requested == [True]


def test_agents_controller_rejects_relative_repo_path():
    from flowos.gui.controllers.agents import AgentsController

    class FakeApi:
        def create_tracked_session(self, *_args):
            raise AssertionError("nevalidan repo_path ne smije doći do API klijenta")

    controller = AgentsController(FakeApi())
    errors = []
    controller.tracking_failed.connect(errors.append)

    controller.track_agent("project-1", "relative/repo", 1234, "Codex")

    assert errors == ["repo_path aktivnog projekta mora biti apsolutna putanja"]


def test_system_controller_emits_each_shutdown_outcome():
    from flowos.gui.controllers.system import SystemController

    class FakeApi:
        response = None

        def prepare_shutdown(self, on_ready):
            on_ready(self.response)

    api = FakeApi()
    controller = SystemController(api)
    events = []
    controller.shutdown_allowed.connect(lambda: events.append(("allowed", None)))
    controller.shutdown_blocked.connect(lambda count: events.append(("blocked", count)))
    controller.shutdown_failed.connect(lambda: events.append(("failed", None)))

    api.response = {"active_sessions": 0}
    controller.request_shutdown()
    api.response = {"active_sessions": 2}
    controller.request_shutdown()
    api.response = None
    controller.request_shutdown()

    assert events == [("allowed", None), ("blocked", 2), ("failed", None)]


def test_system_controller_opens_reports_folder_platform_aware(tmp_path, monkeypatch):
    from flowos.gui.controllers import system as system_module
    from flowos.gui.controllers.system import SystemController

    class FakeApi:
        pass

    calls = []
    monkeypatch.setattr(system_module.subprocess, "Popen", lambda command: calls.append(command))

    controller = SystemController(FakeApi())
    for platform in ("win32", "darwin", "linux"):
        monkeypatch.setattr(system_module.sys, "platform", platform)
        controller.open_reports_folder(str(tmp_path))

    absolute_path = os.path.abspath(tmp_path)
    assert calls == [
        ["explorer", absolute_path],
        ["open", absolute_path],
        ["xdg-open", absolute_path],
    ]


def test_flowos_gui_delegates_shutdown_request():
    from flowos.gui.composition_root import FlowOsGui

    class SystemControllerSpy:
        def __init__(self):
            self.requested = False

        def request_shutdown(self):
            self.requested = True

    controller = SystemControllerSpy()
    gui = FlowOsGui.__new__(FlowOsGui)
    gui._system_controller = controller

    gui._on_shutdown_requested()

    assert controller.requested is True


def test_main_window_emits_reports_folder_request(qapp):
    from flowos.gui.views.overview_skeleton import MainWindow

    window = MainWindow()
    requests = []
    window.reports_folder_requested.connect(lambda: requests.append(True))

    window._on_action("Otvori dnevnik")

    assert requests == [True]
    window.deleteLater()
