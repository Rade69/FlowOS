"""Regresioni testovi za FlowOsGui → AgentsController tracking tok."""


def test_track_agent_delegates_to_agents_controller():
    from flowos.gui.composition_root import FlowOsGui

    class AgentsControllerSpy:
        def __init__(self):
            self.calls = []

        def track_agent(self, project_id, repo_path, pid, agent_type):
            self.calls.append((project_id, repo_path, pid, agent_type))

    class DirectApiCallForbidden:
        sessions_received = object()

        def _post(self, *_args, **_kwargs):
            raise AssertionError("composition_root ne smije direktno pozvati _api._post")

    controller = AgentsControllerSpy()
    gui = FlowOsGui.__new__(FlowOsGui)
    gui._api = DirectApiCallForbidden()
    gui._agents_controller = controller
    gui._active_project_id = "project-1"
    gui._active_project_repo_path = "H:/repo"

    gui._track_agent(1234, "Claude Code")

    assert controller.calls == [("project-1", "H:/repo", 1234, "Claude Code")]
