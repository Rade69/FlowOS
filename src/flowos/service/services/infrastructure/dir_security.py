"""FlowOS lokalni data-directory hardening (FLOW-1108).

Jedan centralni primitiv koji na Windows-u ograničava NTFS dozvole
FlowOS-owned application-data direktorijuma (runtime descriptor, SQLite
baza, logovi, schema-repair backupi) na trenutnog korisnika (stabilan SID),
SYSTEM i Administrators — uklanja Everyone/Users/Authenticated Users
grantove i prekida nasljeđivanje od roditelja.

Poziva se ISKLJUČIVO na granici kreiranja/inicijalizacije direktorijuma
(startup, prvi upis), nikad u hot path-u (API request, DB query, log write,
watcher event, WebSocket event).

Ovo NIJE encryption-at-rest, DPAPI, Credential Manager, multi-user auth ni
sandbox. Ne štiti od Administrator/SYSTEM niti od procesa koji već rade pod
istim Windows korisnikom — vidi threat model u
agent_reports/2026-08-14-FLOW-1108-local-data-protection.md.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from flowos.service.services.infrastructure.app_paths import get_flowos_root

# Well-known Windows SID-ovi (stabilni, locale-nezavisni — ne lokalizovana imena).
_SYSTEM_SID = "S-1-5-18"
_ADMINISTRATORS_SID = "S-1-5-32-544"
_EVERYONE_SID = "S-1-1-0"
_USERS_SID = "S-1-5-32-545"
_AUTHENTICATED_USERS_SID = "S-1-5-11"


class DirectoryHardeningError(RuntimeError):
    """ACL hardening nije uspio za security-sensitive direktorijum.

    Namjerno se NE guta — pozivalac (npr. RuntimeManager pri upisu descriptora
    sa API tokenom) mora fail-closed umjesto tihog nastavka u nebezbjedan
    direktorijum.
    """


def _hardenable_roots() -> tuple[Path, ...]:
    """Putanje ispod kojih centralni primitiv smije da radi.

    Uz prepoznate FlowOS application-data korijene (postojeća arhitektura ima
    dvije nezavisne, ali u praksi identične, kalkulacije %LOCALAPPDATA%/FlowOS
    putanje — app_paths.py koristi LOCALAPPDATA env var, persistence/engine.py
    koristi Path.home(); objedinjavanje je van scope-a FLOW-1108), prihvata i
    OS temp direktorijum — standardna, izolovana lokacija za test fixture-e
    (npr. postojeći `tempfile.TemporaryDirectory()` u RuntimeManager
    testovima). Repo/project/user-profile putanje NISU u ovoj listi.
    """
    return (
        get_flowos_root().resolve(),
        (Path.home() / "AppData" / "Local" / "FlowOS").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    )


def _assert_hardenable_path(path: Path) -> Path:
    """Odbija svaku putanju koja nije unutar prepoznatog hardenable root-a.

    Sprečava da centralni primitiv prihvati proizvoljan project/repo path
    (ili bilo koji drugi van FlowOS application-data/temp stabla) i nad njim
    prepiše ACL.
    """
    resolved = path.resolve()
    roots = _hardenable_roots()
    for root in roots:
        if resolved == root or root in resolved.parents:
            return resolved
    raise ValueError(
        f"ensure_private_directory/harden_existing_directory odbija putanju van "
        f"prepoznatog FlowOS/temp root-a: {path}"
    )


def _current_user_sid_string() -> str:
    """Vraća stabilan SID trenutnog Windows korisnika (ne lokalizovano ime)."""
    import win32api
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    sid, _attrs = win32security.GetTokenInformation(token, win32security.TokenUser)
    return win32security.ConvertSidToStringSid(sid)


def _run_icacls(cmd: list[str], path: Path) -> None:
    """Pokreće jedan `icacls` subprocess poziv; ne guta grešku."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DirectoryHardeningError(f"icacls poziv nije uspio za: {path}") from exc

    if result.returncode != 0:
        raise DirectoryHardeningError(
            f"icacls hardening nije uspio za {path} (exit={result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


def _apply_windows_acl(path: Path) -> None:
    """Postavlja restriktivan NTFS ACL na `path` preko `icacls` subprocess-a.

    Dozvoljeni principal-i: trenutni korisnik (SID), SYSTEM, Administrators.

    Rad u DVA koraka — VAŽNO, empirijski utvrđeno:
    1. `path` sam se hardenuje EKSPLICITNO (bez `/T`): prekida nasljeđivanje,
       postavlja (OI)(CI) inheritable grantove, uklanja Everyone/Users/
       Authenticated Users. `(OI)(CI)` flagovi su namijenjeni KONTEJNERIMA
       (propagacija na buduću djecu), ne samim fajlovima.
    2. POSTOJEĆA djeca (fajlovi/poddirektorijumi, bitno za already-postojeće
       instalacije) se resetuju preko `path\\*` wildcard-a (BEZ da dirne
       `path` sam) da ponovo naslijede TEK postavljeni ACL sa koraka 1.

       Direktna primjena `(OI)(CI)F` granta NA SAM FAJL preko `/T` rekurzije
       (jedan icacls poziv, bez dva koraka) probom je dokazano da proizvodi
       PRAZAN, potpuno nepristupačan ACL na tom fajlu (icacls "uspije" sa
       exit=0, ali fajl ostaje nedostupan čak i vlasniku) — zato se koraci
       NIKAD ne spajaju u jedan `/T` poziv sa inheritance flagovima.

    `/L` sprečava da rekurzija prati eventualni directory junction unutar
    `path` u njegov cilj — ACL izmjena ostaje ograničena na `path` stablo,
    nikad ne "iscuri" u proizvoljnu lokaciju na koju bi junction pokazivao.

    `/C` (continue-on-error) se NAMJERNO ne koristi: bez njega icacls vraća
    non-zero exit code na grešku obrade, pa fail-closed ne zavisi od
    lokalizovanog tekstualnog izlaza (REV-1108-M1).
    """
    try:
        user_sid = _current_user_sid_string()
    except Exception as exc:
        raise DirectoryHardeningError(
            f"Ne mogu odrediti SID trenutnog korisnika za ACL hardening: {path}"
        ) from exc

    grant_specs = [
        f"*{user_sid}:(OI)(CI)F",
        f"*{_SYSTEM_SID}:(OI)(CI)F",
        f"*{_ADMINISTRATORS_SID}:(OI)(CI)F",
    ]
    remove_specs = [f"*{_EVERYONE_SID}", f"*{_USERS_SID}", f"*{_AUTHENTICATED_USERS_SID}"]

    dir_cmd = [
        "icacls",
        str(path),
        "/inheritance:r",
        "/grant:r",
        *grant_specs,
        "/remove:g",
        *remove_specs,
    ]
    _run_icacls(dir_cmd, path)

    children_cmd = [
        "icacls",
        str(path / "*"),
        "/reset",
        "/T",
        "/L",
    ]
    _run_icacls(children_cmd, path)


def ensure_private_directory(path: Path) -> None:
    """Kreira (idempotentno) i hardenuje `path`.

    Radi i za novokreiran i za već postojeći direktorijum — poziva se pri
    svakom startup-u/inicijalizaciji, pa hardenuje i instalacije koje su
    prethodno postojale bez FLOW-1108 zaštite.

    Non-Windows: samo mkdir (postojeće ponašanje, bez ACL rada).

    Raises:
        ValueError: `path` nije unutar prepoznatog FlowOS data root-a.
        DirectoryHardeningError: ACL operacija nije uspjela na Windows-u.
    """
    resolved = _assert_hardenable_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        _apply_windows_acl(resolved)


def harden_existing_directory(path: Path) -> None:
    """Hardenuje direktorijum koji je pozivalac VEĆ kreirao.

    Za mjesta koja imaju sopstvenu, namjerno strogu mkdir semantiku (npr.
    collision-safe schema-repair backup sa `exist_ok=False`) i ne žele da
    tu semantiku dijele sa `ensure_private_directory`-jevim idempotentnim
    `exist_ok=True` kreiranjem. Ne kreira direktorijum, samo ga hardenuje.

    Raises:
        ValueError: `path` nije unutar prepoznatog FlowOS data root-a.
        DirectoryHardeningError: ACL operacija nije uspjela na Windows-u.
    """
    resolved = _assert_hardenable_path(path)
    if sys.platform == "win32":
        _apply_windows_acl(resolved)
