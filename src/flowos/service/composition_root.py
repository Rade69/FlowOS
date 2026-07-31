"""FlowOS Service Composition Root.

Jedno mesto gde se eksplicitno konstruišu sve zavisnosti:
API Controllers → Backend Services → Infrastructure.

Ne koristiti dependency-injection framework. Svaka zavisnost
se prosleđuje eksplicitno kroz konstruktor.
"""

# Placeholder — popunjava se u fazi 1
# from flowos.service.services.projects import ProjectService
# from flowos.service.controllers.http.projects import create_projects_router
#
# def create_app() -> FastAPI:
#     project_service = ProjectService(session_factory)
#     app = FastAPI()
#     app.include_router(create_projects_router(project_service))
#     return app


def create_app():
    """Vraća konfigurisanu FastAPI aplikaciju."""
    raise NotImplementedError("Backend nije implementiran u fazi 0")
