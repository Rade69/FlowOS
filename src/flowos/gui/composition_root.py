"""FlowOS GUI Composition Root.

Jedno mesto gde se eksplicitno konstruišu sve zavisnosti:
View → Controller → Services.

Ne koristiti dependency-injection framework. Svaka zavisnost
se prosleđuje eksplicitno kroz konstruktor.
"""

# Placeholder — popunjava se u fazi 1-2 kada GUI dobije stvarne ekrane
# from flowos.gui.services.client import GuiApiClient
# from flowos.gui.controllers.overview import OverviewController
# from flowos.gui.views.overview import OverviewView
#
# def create_main_window():
#     api_client = GuiApiClient()
#     overview_controller = OverviewController(api_client)
#     overview_view = OverviewView(overview_controller)
#     ...


def create_main_window():
    """Vraća glavni prozor aplikacije."""
    raise NotImplementedError("GUI nije implementiran u fazi 0")
