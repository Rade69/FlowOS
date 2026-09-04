"""FlowOS GUI Composition Root.

Jedno mesto gde se eksplicitno konstruišu sve GUI zavisnosti:
MainWindow → View instances → Controller → GuiApiClient

Ne koristiti dependency-injection framework.
Svaka zavisnost se prosleđuje eksplicitno kroz konstruktor.
"""

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtNetwork import QNetworkRequest
from PySide6.QtWidgets import QVBoxLayout, QWidget

try:
    from PySide6.QtWebSockets import QWebSocket

    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

from flowos.gui.controllers.agents import AgentsController
from flowos.gui.controllers.overview import OverviewController
from flowos.gui.controllers.plan import PlanController
from flowos.gui.controllers.system import SystemController
from flowos.gui.services.client import GuiApiClient
from flowos.gui.views.overview_skeleton import (
    BG_PRIMARY,
    RED,
    SPACING_XXL,
    MainWindow,
    RecentActivityWidget,
)
from flowos.gui.views.pages import (
    AgentsPage,
    ConflictsPage,
    ProjectsPage,
    ReportsPage,
    SettingsPage,
    TasksPage,
)
from flowos.gui.views.plan_progress import CurrentPhaseView, PlanProgressView, StatusSummaryBar
from flowos.gui.views.project_resume import (
    AttentionPanel,
    PlanItemDetailsView,
    ReconciliationView,
    ResumeHeroView,
)
from flowos.gui.views.sessions import SessionsView
from flowos.gui.views.worktrees import WorktreesView


class FlowOsGui:
    """Glavni GUI objekat — poseduje MainWindow i orkestrira View → Controller tok."""

    def __init__(
        self,
        window: MainWindow,
        controller: OverviewController | None = None,
        api: GuiApiClient | None = None,
        views: dict | None = None,
        plan_controller: PlanController | None = None,
        agents_controller: AgentsController | None = None,
        system_controller: SystemController | None = None,
    ):
        self._window = window
        self._controller = controller
        self._api = api
        self._plan_controller = plan_controller
        self._agents_controller = agents_controller
        self._system_controller = system_controller
        self._active_project_id: str | None = None
        self._active_project_repo_path: str | None = None
        self._active_project_generation: int = 0
        self._refresh_timer: QTimer | None = None
        self._projects: list[dict] = []

        self._resume_hero = views.get("resume_hero") if views else None
        self._status_bar = views.get("status_bar") if views else None
        self._current_phase = views.get("current_phase") if views else None
        self._sessions_overview = views.get("sessions_overview") if views else None
        self._plan_page_view = views.get("plan_page") if views else None
        self._reconciliation_view = views.get("reconciliation") if views else None
        self._sessions_page_view = views.get("sessions_page") if views else None
        self._worktrees_page_view = views.get("worktrees_page") if views else None
        self._activity_view = views.get("activity") if views else None
        self._attention_panel = views.get("attention") if views else None
        self._agents_page = views.get("agents_page") if views else None
        self._conflicts_page = views.get("conflicts_page") if views else None
        self._projects_page = views.get("projects_page") if views else None
        self._details_view = views.get("details") if views else None
        self._tasks_page = views.get("tasks_page") if views else None

        self._ws: QWebSocket | None = None
        if controller:
            self._wire_controller()
            self._start_auto_refresh()
            self._connect_ws()
            QTimer.singleShot(500, controller.check_health)
            QTimer.singleShot(800, controller.load_projects)

    def show(self) -> None:
        self._window.show()

    # ── Wiring ──────────────────────────────────────────

    def _wire_controller(self) -> None:
        ctrl = self._controller
        if ctrl is None:
            return
        ctrl.health_updated.connect(self._on_health)
        ctrl.projects_loaded.connect(self._on_projects)
        ctrl.plan_progress_loaded.connect(self._on_plan_progress)
        ctrl.resume_loaded.connect(self._on_resume)
        ctrl.sessions_loaded.connect(self._on_sessions)
        ctrl.error_occurred.connect(self._on_error)
        if self._plan_controller:
            self._plan_controller.import_failed.connect(ctrl.error_occurred.emit)
            self._plan_controller.import_succeeded.connect(self._on_plan_imported)
        if self._agents_controller:
            self._agents_controller.tracking_failed.connect(ctrl.error_occurred.emit)
        if self._system_controller:
            self._system_controller.shutdown_allowed.connect(self._do_shutdown_confirm)
            self._system_controller.shutdown_blocked.connect(self._show_shutdown_blocked_dialog)
            self._system_controller.shutdown_failed.connect(self._quit_app)
            self._system_controller.reports_folder_open_failed.connect(ctrl.error_occurred.emit)
            self._window.reports_folder_requested.connect(
                lambda: self._system_controller.open_reports_folder(
                    str(Path(self._active_project_repo_path or Path.cwd()) / "agent_reports")
                )
            )

        # KORAK 5: selekcija plan stavke → API poziv za detalje
        if self._current_phase:
            self._current_phase.item_selected.connect(self._load_plan_item_details)

        # Agents page
        if self._agents_page:
            self._agents_page.scan_requested.connect(
                lambda: self._api.scan_agents() if self._api else None
            )
            self._agents_page.track_requested.connect(self._track_agent)

        if self._api:
            api = self._api
            api.timeline_received.connect(self._on_timeline)
            api.agents_scanned.connect(self._on_agents_scanned)
            api.projects_received.connect(self._on_projects_page)
            api.project_created.connect(self._on_project_created)
            api.plan_item_received.connect(self._on_plan_item_received)
            if self._worktrees_page_view:
                api.worktrees_received.connect(self._on_worktrees)
                self._worktrees_page_view.refresh_requested.connect(self._refresh_worktrees)
                self._worktrees_page_view.integrate_requested.connect(
                    lambda wid: api.prepare_integration(wid)
                )
                self._worktrees_page_view.cleanup_requested.connect(
                    lambda wid: api.cleanup_worktree(wid)
                )

        self._wire_topbar()
        self._window.page_changed.connect(self._on_page_changed)
        self._window.shutdown_requested.connect(self._on_shutdown_requested)

        # ResumeHero: Nastavi rad → prebaci na Plan stranicu
        if self._resume_hero:
            self._resume_hero.continue_requested.connect(lambda: self._window._on_navigate("Plan"))

        # AttentionPanel: klik → navigiraj na odgovarajuću stranicu
        if self._attention_panel:
            self._attention_panel.item_activated.connect(self._window._on_navigate)

        # PlanProgressView: uvoz plana
        if self._plan_page_view:
            self._plan_page_view.import_requested.connect(self._on_import_plan)

    def _wire_topbar(self) -> None:
        """Povezuje TopBar signale na orkestraciju (izdvojeno radi testiranja wiring-a)."""
        self._window.topbar.refresh_requested.connect(lambda: self._refresh_all())
        self._window.topbar.project_selected.connect(self._on_project_selected)
        self._window.topbar.add_project_requested.connect(self._on_add_project)

    def _on_page_changed(self, page_name: str) -> None:
        if page_name == "Agenti" and self._api:
            self._api.scan_agents()

    def _on_shutdown_requested(self) -> None:
        """Poziva se kad korisnik klikne 'Zaustavi sve i ugasi FlowOS'."""
        if not self._system_controller:
            self._quit_app()
            return
        self._system_controller.request_shutdown()

    def _show_shutdown_blocked_dialog(self, active_count: int) -> None:
        from PySide6.QtWidgets import QMessageBox

        msg = QMessageBox(self._window)
        msg.setWindowTitle("FlowOS — Gašenje")
        msg.setText(f"Postoji {active_count} aktivnih sesija.")
        msg.setInformativeText("Gašenje će prekinuti agentske procese.")
        btn_wait = msg.addButton("Zatvori samo GUI", QMessageBox.ButtonRole.AcceptRole)
        btn_kill = msg.addButton("Prekini sesije i ugasi", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Odustani", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked is btn_wait:
            self._window.close()
        elif clicked is btn_kill:
            self._do_shutdown_confirm()
        # cancel: ništa

    def _do_shutdown_confirm(self) -> None:
        """Šalje shutdown/confirm zahtev servisu i gasi GUI."""
        if self._api:
            with suppress(Exception):
                self._api.confirm_shutdown(lambda _data: None)
        self._quit_app()

    def _quit_app(self) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            app.quit()

    def _on_import_plan(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(self._window, "Uvezi plan", "", "Markdown (*.md)")
        if path and self._plan_controller and self._active_project_id:
            # FLOW-1201: ne povećavaj generation prije importa. Pending odgovori
            # trenutne generacije smiju normalno završiti; full refresh ide
            # tek kroz import_succeeded -> _on_plan_imported.
            self._plan_controller.import_plan(self._active_project_id, path)

    def _on_plan_imported(self, project_id: str) -> None:
        """Posle uspješnog importa pokreće novi kompletan project-data batch."""
        if project_id == self._active_project_id:
            self._load_project_data(project_id)

    def _refresh_worktrees(self) -> None:
        """Worktrees refresh je full project refresh — ne orfuje druge resurse."""
        if self._active_project_id:
            self._load_project_data(self._active_project_id)

    def _load_plan_item_details(self, item_id: str) -> None:
        if self._api:
            self._api.get_plan_item(item_id)

    def _track_agent(self, pid: int, agent_type: str) -> None:
        """Kreira EXTERNAL_TRACKED sesiju za detektovani agentski proces."""
        if not self._agents_controller or not self._active_project_id:
            return
        self._agents_controller.track_agent(
            self._active_project_id,
            self._active_project_repo_path or "",
            pid,
            agent_type,
        )

    def _start_auto_refresh(self) -> None:
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_all)
        self._refresh_timer.start(10000)

    def _refresh_all(self) -> None:
        if not self._controller:
            return
        self._controller.check_health()
        if self._active_project_id:
            self._load_project_data(self._active_project_id)
        else:
            self._controller.load_projects()

    # ── Controller callbacks ────────────────────────────

    def _on_health(self, ok: bool, uptime: str) -> None:
        self._window.set_status(connected=ok)

    def _on_projects(self, projects: list) -> None:
        self._projects = projects
        self._window.topbar.set_projects(projects)
        if not projects:
            self._active_project_id = None
            self._active_project_repo_path = None
            self._window.set_project_info(None)
            self._window.set_topbar_info(project="")
            self._window.topbar.set_active_project(None)
            self._clear_project_screens()
            return
        if self._active_project_id is None:
            # Startup / prvi load: zadržano postojeće ponašanje — najnoviji projekat
            # (backend vraća listu po created_at DESC) postaje aktivan.
            self._select_project(projects[0].get("id", ""))
        else:
            self._sync_project_ui()

    def _project_by_id(self, project_id: str) -> dict | None:
        for p in self._projects:
            if p.get("id") == project_id:
                return p
        return None

    def _select_project(self, project_id: str) -> None:
        proj = self._project_by_id(project_id)
        if proj is None:
            return
        self._active_project_id = project_id
        self._active_project_repo_path = proj.get("repo_path", "")
        self._clear_project_screens()
        self._window.set_project_info(
            {"name": proj.get("name", ""), "last_activity": proj.get("updated_at", "")}
        )
        self._window.set_topbar_info(project=proj.get("name", ""))
        self._window.topbar.set_active_project(project_id)
        self._load_project_data(project_id)

    def _sync_project_ui(self) -> None:
        proj = self._project_by_id(self._active_project_id or "")
        if proj is None:
            if self._projects:
                self._select_project(self._projects[0].get("id", ""))
            return
        self._window.set_project_info(
            {"name": proj.get("name", ""), "last_activity": proj.get("updated_at", "")}
        )
        self._window.set_topbar_info(project=proj.get("name", ""))
        self._window.topbar.set_active_project(proj.get("id", ""))

    def _begin_generation(self) -> int:
        """Monotono rastuća project-data generacija; svaki load batch dobija novu."""
        self._active_project_generation += 1
        return self._active_project_generation

    def _load_project_data(self, project_id: str) -> None:
        generation = self._begin_generation()
        if self._controller:
            self._controller.load_plan_progress(project_id, generation)
            self._controller.load_resume(project_id, generation)
            self._controller.load_sessions(project_id, generation)
        if self._api:
            self._api.fetch_worktrees(project_id, generation)
            self._api.get_timeline(project_id, generation)
        if self._tasks_page:
            self._tasks_page.set_project_id(project_id)

    def _clear_project_screens(self) -> None:
        """Čisti project-scoped ekrane prije prebacivanja (stale-data zaštita)."""
        if self._plan_page_view:
            self._plan_page_view.render(None)
        if self._current_phase:
            self._current_phase.render([])
        if self._status_bar:
            self._status_bar.render({})
        if self._sessions_overview:
            self._sessions_overview.render([])
        if self._sessions_page_view:
            self._sessions_page_view.render([])
        if self._resume_hero:
            self._resume_hero.render(None)
        if self._activity_view:
            self._activity_view.render([])
        if self._worktrees_page_view:
            self._worktrees_page_view.render([])
        if self._attention_panel:
            self._attention_panel.render({})
        if self._details_view:
            self._details_view.render(None)
        if self._reconciliation_view:
            self._reconciliation_view.render(None)
        if self._tasks_page:
            self._tasks_page.set_project_id(None)

    def _on_project_selected(self, project_id: str) -> None:
        if project_id and project_id != self._active_project_id:
            self._select_project(project_id)

    def _on_add_project(self) -> None:
        if not self._api:
            return
        from PySide6.QtWidgets import QFileDialog, QInputDialog

        name, ok = QInputDialog.getText(self._window, "Dodaj projekat", "Ime projekta:")
        if not ok or not name.strip():
            return
        repo_path = QFileDialog.getExistingDirectory(self._window, "Izaberi repo direktorijum")
        if not repo_path:
            return
        self._api.create_project(name.strip(), repo_path)

    def _on_project_created(self, data) -> None:
        if isinstance(data, dict) and "error" in data:
            return  # greška već prikazana kroz error_occurred signal
        if self._controller:
            self._controller.load_projects()

    def _on_plan_progress(self, data: tuple) -> None:
        project_id, generation, payload = data
        if project_id != self._active_project_id or generation != self._active_project_generation:
            return  # FLOW-1201: zakašnjeli odgovor (drugi projekat ili starija generacija)

        # Plan stranica (puna tabela)
        if self._plan_page_view:
            self._plan_page_view.render(payload)

        # Pregled — CurrentPhaseView
        phases = payload.get("phases", [])
        if self._current_phase:
            self._current_phase.render(phases)

        # StatusSummaryBar
        if self._status_bar:
            counts: dict[str, int] = {}
            for ph in phases:
                for it in ph.get("items", []):
                    s = it.get("status", "NOT_STARTED")
                    counts[s] = counts.get(s, 0) + 1
            self._status_bar.render(counts)

        # Sidebar
        plan_title = payload.get("plan_title", "")
        if plan_title and self._active_project_id:
            self._window._sidebar.set_project_info({"plan_title": plan_title})

        # Topbar — faza
        phases = payload.get("phases", [])
        active_phase = ""
        for ph in phases:
            items = ph.get("items", [])
            statuses = {it.get("status", "NOT_STARTED") for it in items}
            if statuses != {"NOT_STARTED"}:
                active_phase = f"{ph.get('phase_key', '')} · {ph.get('title', '')}"
                break
        if active_phase:
            self._window.set_topbar_info(phase=active_phase)

        # AttentionPanel
        if self._attention_panel:
            self._attention_panel.render({"blocked_items": payload.get("blocked", 0)})

    def _on_plan_item_received(self, data: dict) -> None:
        if isinstance(data, dict) and "error" not in data and self._details_view:
            self._details_view.render(data)

    def _on_sessions(self, data: tuple) -> None:
        project_id, generation, sessions = data
        if project_id != self._active_project_id or generation != self._active_project_generation:
            return  # FLOW-1201: zakašnjeli odgovor (drugi projekat ili starija generacija)
        if self._sessions_overview:
            self._sessions_overview.render(sessions)
        if self._sessions_page_view:
            self._sessions_page_view.render(sessions)
        self._window.set_status(connected=True, sessions=len(sessions))
        self._window.set_topbar_info(sessions=len(sessions))

    def _on_resume(self, data: tuple) -> None:
        project_id, generation, payload = data
        if project_id != self._active_project_id or generation != self._active_project_generation:
            return  # FLOW-1201: zakašnjeli odgovor (drugi projekat ili starija generacija)
        if self._resume_hero:
            self._resume_hero.render(payload)
        if not self._reconciliation_view:
            return
        ws_state = payload.get("workspace_state", {})
        if ws_state and ws_state.get("reconciliation_status") not in (None, "CURRENT"):
            self._reconciliation_view.render(
                {
                    "new_commits": ws_state.get("external_commits", 0),
                    "dirty_files": ws_state.get("external_dirty", 0),
                    "current_branch": ws_state.get("last_known_branch", ""),
                }
            )
        else:
            self._reconciliation_view.render(None)

    def _on_error(self, msg: str) -> None:
        self._window.set_status(connected=False, sessions=-1)
        self._window._statusbar._health.setText(f"⚠ {msg}")
        self._window._statusbar._health.setStyleSheet(
            f"color: {RED}; border: none; background: transparent;"
        )

    def _on_timeline(self, data: tuple) -> None:
        project_id, generation, items = data
        if project_id != self._active_project_id or generation != self._active_project_generation:
            return  # FLOW-1201: zakašnjeli odgovor (drugi projekat ili starija generacija)
        if self._activity_view:
            self._activity_view.render(items)

    def _on_worktrees(self, data: tuple) -> None:
        project_id, generation, items = data
        if project_id != self._active_project_id or generation != self._active_project_generation:
            return  # FLOW-1201: zakašnjeli odgovor (drugi projekat ili starija generacija)
        if self._worktrees_page_view:
            self._worktrees_page_view.render(items)

    def _on_agents_scanned(self, data: dict) -> None:
        if self._agents_page:
            self._agents_page.render(data)

    def _on_projects_page(self, projects: list) -> None:
        if self._projects_page:
            self._projects_page.render(projects)

    def _connect_ws(self) -> None:
        """Povezuje se na WebSocket za real-time događaje.

        FLOW-1107: token se šalje kroz Authorization header na handshake
        zahtjevu (QNetworkRequest), nikad kroz URL query string.
        """
        if not HAS_WEBSOCKET:
            return

        port = 9100
        if self._api:
            port = int(self._api.base_url.split(":")[-1]) if ":" in self._api.base_url else 9100

        req = QNetworkRequest(QUrl(f"ws://127.0.0.1:{port}/ws"))
        if self._api and self._api.token:
            req.setRawHeader(b"Authorization", f"Bearer {self._api.token}".encode())

        self._ws = QWebSocket()
        self._ws.textMessageReceived.connect(self._on_ws_message)
        self._ws.open(req)

    def _on_ws_message(self, raw: str) -> None:
        import json

        try:
            msg = json.loads(raw)
            event_type = msg.get("type", "")

            if (
                event_type
                in ("session.completed", "plan_progress.updated", "project.resume.updated")
                or event_type == "conflict.created"
                or event_type == "reconciliation.created"
            ):
                self._refresh_all()
        except Exception:
            pass


# ── Factory ──────────────────────────────────────────────────────


def _wrap_in_page(widget: QWidget) -> QWidget:
    w = QWidget()
    w.setStyleSheet(f"background: {BG_PRIMARY};")
    lo = QVBoxLayout(w)
    lo.setContentsMargins(SPACING_XXL, SPACING_XXL, SPACING_XXL, SPACING_XXL)
    lo.addWidget(widget)
    lo.addStretch()
    return w


def create_gui(use_live: bool = True) -> FlowOsGui:
    """Konstruiše sve GUI objekte i povezuje ih."""
    window = MainWindow()

    # View instances
    resume_hero = ResumeHeroView()
    status_bar = StatusSummaryBar()
    current_phase = CurrentPhaseView()
    sessions_overview = SessionsView()
    activity_view = RecentActivityWidget()
    details_view = PlanItemDetailsView()
    reconciliation_view = ReconciliationView()
    attention_panel = AttentionPanel()

    # Stranice
    plan_page_view = PlanProgressView()
    sessions_page_view = SessionsView()
    worktrees_page_view = WorktreesView()
    agents_page = AgentsPage()
    conflicts_page = ConflictsPage()
    projects_page = ProjectsPage()
    tasks_page = TasksPage()

    # Layout — Pregled
    window.set_central_widgets(
        [resume_hero, status_bar, current_phase, sessions_overview, activity_view]
    )
    window.set_right_widgets([attention_panel, details_view, reconciliation_view])

    # Layout — namenske stranice
    window.set_page_widget("Projekti", _wrap_in_page(projects_page))
    window.set_page_widget("Plan", _wrap_in_page(plan_page_view))
    window.set_page_widget("Sesije", _wrap_in_page(sessions_page_view))
    window.set_page_widget("Zadaci", _wrap_in_page(tasks_page))
    window.set_page_widget("Agenti", _wrap_in_page(agents_page))
    window.set_page_widget("Radna stabla", _wrap_in_page(worktrees_page_view))
    window.set_page_widget("Konflikti", _wrap_in_page(conflicts_page))
    window.set_page_widget("Izvještaji", _wrap_in_page(ReportsPage()))
    window.set_page_widget("Postavke", _wrap_in_page(SettingsPage()))

    # API + Controller (samo u live modu)
    controller = None
    plan_controller = None
    agents_controller = None
    system_controller = None
    api = None
    if use_live:
        connection = ensure_service_running()
        api = GuiApiClient(base_url=f"http://127.0.0.1:{connection.port}", token=connection.token)
        controller = OverviewController(api)
        plan_controller = PlanController(api)
        agents_controller = AgentsController(api)
        system_controller = SystemController(api)

    return FlowOsGui(
        window=window,
        controller=controller,
        api=api,
        plan_controller=plan_controller,
        agents_controller=agents_controller,
        system_controller=system_controller,
        views={
            "resume_hero": resume_hero,
            "status_bar": status_bar,
            "current_phase": current_phase,
            "sessions_overview": sessions_overview,
            "plan_page": plan_page_view,
            "reconciliation": reconciliation_view,
            "sessions_page": sessions_page_view,
            "worktrees_page": worktrees_page_view,
            "activity": activity_view,
            "attention": attention_panel,
            "agents_page": agents_page,
            "conflicts_page": conflicts_page,
            "projects_page": projects_page,
            "tasks_page": tasks_page,
            "details": details_view,
        },
    )


def _service_descriptor_path() -> Path:
    from flowos.service.services.infrastructure.app_paths import get_runtime_dir

    return get_runtime_dir() / "service.json"


class ServiceStartupError(RuntimeError):
    """Backend servis nije postao zdrav unutar dozvoljenog perioda."""


@dataclass(frozen=True)
class ServiceConnection:
    """Potvrđena konekcija ka tekućoj FlowOS servis instanci (FLOW-1107).

    `port` i `token` se UVIJEK čitaju iz istog descriptor snapshot-a — nikad
    port jedne instance sa tokenom neke druge (npr. stale/prethodne).
    """

    port: int
    token: str


def _read_descriptor() -> ServiceConnection | None:
    """Čita port+token iz runtime descriptor-a atomski, ili None ako nije validan."""
    import json

    path = _service_descriptor_path()
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    port = data.get("port")
    token = data.get("token")
    if not (isinstance(port, int) and 1024 <= port <= 65535):
        return None
    if not (isinstance(token, str) and token):
        return None
    return ServiceConnection(port=port, token=token)


def _is_service_healthy(port: int) -> bool:
    import httpx

    try:
        resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def ensure_service_running() -> ServiceConnection:
    """Obezbeđuje pokrenut FlowOS servis i vraća potvrđenu konekciju (port+token).

    Redoslijed:
    1. Ako descriptor već postoji i /health je zdrav, ponovo koristi taj (port, token).
    2. Inače pokreće servis kroz trenutni Python environment.
    3. Čeka da servis upiše NOVI descriptor i postane zdrav.
    4. Vraća (port, token) iz TOG istog descriptor čitanja — nikad mješavinu
       starog i novog stanja.

    Raises:
        ServiceStartupError: ako servis ne postane zdrav u bounded periodu.
    """
    import subprocess
    import sys
    import time

    existing = _read_descriptor()
    if existing is not None and _is_service_healthy(existing.port):
        return existing

    proc = subprocess.Popen(
        [sys.executable, "-m", "flowos.service.app"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise ServiceStartupError(
                f"FlowOS servis se ugasio pri pokretanju (exit code {proc.returncode})."
            )
        candidate = _read_descriptor()
        if candidate is not None and _is_service_healthy(candidate.port):
            return candidate
        time.sleep(0.5)

    raise ServiceStartupError("FlowOS servis nije postao zdrav unutar 30 sekundi.")
