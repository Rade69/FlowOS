"""FlowOS GUI — centralne mape prevoda (srpski jezik).

Svi widgeti moraju koristiti ove mape.
Interni enum nazivi ostaju na engleskom u kodu i bazi.
"""

# Statusi planiranih stavki
STATUS_LABELS: dict[str, str] = {
    "NOT_STARTED": "Nije započeto",
    "IN_PROGRESS": "U toku",
    "BLOCKED": "Blokirano",
    "IMPLEMENTED": "Implementirano",
    "VERIFIED": "Provjereno",
    "ACCEPTED": "Prihvaćeno",
    "REJECTED": "Odbijeno",
    "NEEDS_REVIEW": "Potreban pregled",
    "ACTIVE": "Aktivna",
    "COMPLETED": "Završena",
    "INTERRUPTED": "Prekinuta",
    "READY": "Spremno",
    "UNKNOWN": "Nepoznato stanje",
}

# Navigacija i nazivi ekrana
UI_LABELS: dict[str, str] = {
    "overview": "Pregled",
    "projects": "Projekti",
    "plan": "Plan",
    "sessions": "Sesije",
    "tasks": "Zadaci",
    "agents": "Agenti",
    "worktrees": "Radna stabla",
    "conflicts": "Konflikti",
    "reports": "Izvještaji",
    "settings": "Postavke",
    "resume": "Nastavak rada",
    "external_activity": "Vanjska aktivnost",
    "reconciliation": "Usklađivanje stanja",
    "evidence": "Dokazi",
    "acceptance_criteria": "Kriterijumi prihvatanja",
    "dirty_tree": "Radno stablo sa neupisanim promjenama",
    "failing_test": "Neuspješan test",
    "lifecycle_test": "Test životnog ciklusa",
}

# Ostali pojmovi
OTHER_LABELS: dict[str, str] = {
    "watcher": "Posmatrač",
    "active": "aktivan",
    "service": "Servis",
    "database": "Baza",
    "branch": "Grana",
    "commit": "Commit",
    "timeline": "Vremenska linija",
    "where_stopped": "Gdje si stao",
    "next_step": "Sljedeći konkretan korak",
    "confidence": "Pouzdanost",
    "preconditions": "Prije nastavka provjeriti",
    "active_project": "Aktivni projekat",
    "active_sessions": "Aktivne sesije",
    "progress": "Napredak po planu",
    "recent_activity": "Nedavna aktivnost",
    "plan_item_details": "Detalji stavke plana",
    "external_changes": "Promjene van FlowOS-a",
    "open_timeline": "Otvori vremensku liniju",
    "continue_work": "Nastavi rad",
    "open_report": "Otvori izvještaj",
    "new_session": "Nova sesija",
    "add_task": "Dodaj zadatak",
    "import_plan": "Uvezi plan",
    "review_changes": "Pregledaj vanjske promjene",
    "open_log": "Otvori dnevnik",
    "connected": "Povezano sa servisom",
    "offline": "Offline — prikaz posljednjeg poznatog stanja",
}


def status_label(status: str) -> str:
    """Vraća prevedeni status ili original ako prevod ne postoji."""
    return STATUS_LABELS.get(status, status)


def ui_label(key: str) -> str:
    """Vraća prevedeni UI pojam ili original."""
    return UI_LABELS.get(key, OTHER_LABELS.get(key, key))