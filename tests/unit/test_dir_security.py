"""FLOW-1108 — testovi za `dir_security.py` i njegovo wiring u pozivaoce.

Dokazuje da centralni ACL hardening primitiv:
- radi i za nov i za već postojeći direktorijum;
- ne guta security failure;
- odbija proizvoljne (repo/project) putanje;
- se poziva iz RuntimeManager/engine/logging/schema_repair na granici
  kreiranja direktorijuma, NE u hot path-u;
- ne uvodi shell=True niti lomi putanje sa razmacima;
- ostaje bezopasan na non-Windows platformama.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from flowos.service.services.infrastructure import dir_security
from flowos.service.services.infrastructure.dir_security import (
    DirectoryHardeningError,
    ensure_private_directory,
    harden_existing_directory,
)

WIN = sys.platform == "win32"


@pytest.fixture
def temp_root(tmp_path):
    """Podleže `tests/unit`-ovom `tmp_path` — pod `tempfile.gettempdir()`,
    pa je unutar `dir_security`-jeve hardenable-root allowlist-e."""
    return tmp_path


class TestHardenablePathValidation:
    """J: repo/project putanje se NE prihvataju."""

    def test_repo_root_rejected(self):
        repo_root = Path(__file__).resolve().parents[2]
        with pytest.raises(ValueError):
            ensure_private_directory(repo_root / "definitely-not-flowos-owned")

    def test_repo_file_parent_rejected(self):
        with pytest.raises(ValueError):
            harden_existing_directory(Path(__file__).resolve().parent)

    def test_user_home_root_rejected(self):
        with pytest.raises(ValueError):
            ensure_private_directory(Path.home())

    def test_flowos_appdata_path_accepted_without_raising_validation(self, monkeypatch):
        """Ne pravimo stvarne izmjene na pravom %LOCALAPPDATA%/FlowOS — samo
        dokazujemo da validacija NE odbija tu putanju (mkdir/ACL su
        monkeypatch-ovani da ne dirn stvarni sistem)."""
        calls = []
        monkeypatch.setattr(dir_security, "_apply_windows_acl", lambda p: calls.append(p))
        monkeypatch.setattr(Path, "mkdir", lambda self, **kw: None)

        root = dir_security.get_flowos_root()
        ensure_private_directory(root / "probe-subdir")
        # Provjera nije bacila ValueError — dovoljno je da stigosmo dovde.

    def test_temp_dir_path_accepted(self, temp_root):
        """OS temp direktorijum (npr. pytest tmp_path) je hardenable — ne
        smije se odbiti, jer bi to pokvarilo postojeće RuntimeManager testove
        koji koriste `tempfile.TemporaryDirectory()` za DESCRIPTOR_DIR."""
        target = temp_root / "runtime"
        ensure_private_directory(target)
        assert target.is_dir()


class TestFailClosed:
    """G: ACL/security failure se NE guta."""

    def test_acl_failure_propagates(self, temp_root, monkeypatch):
        def _boom(path):
            raise DirectoryHardeningError("simulated icacls failure")

        monkeypatch.setattr(dir_security, "_apply_windows_acl", _boom)
        target = temp_root / "should-fail"

        with pytest.raises(DirectoryHardeningError):
            ensure_private_directory(target)

    def test_sid_lookup_failure_raises_not_silently_ignored(self, temp_root, monkeypatch):
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        def _boom():
            raise OSError("no SID for you")

        monkeypatch.setattr(dir_security, "_current_user_sid_string", _boom)
        target = temp_root / "sid-fail"
        target.mkdir()

        with pytest.raises(DirectoryHardeningError):
            dir_security._apply_windows_acl(target)

    def test_icacls_nonzero_exit_raises(self, temp_root, monkeypatch):
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        monkeypatch.setattr(dir_security, "_current_user_sid_string", lambda: "S-1-5-21-0-0-0-1")

        class _FakeResult:
            returncode = 3
            stdout = ""
            stderr = "access denied"

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult())
        target = temp_root / "icacls-fail"
        target.mkdir()

        with pytest.raises(DirectoryHardeningError):
            dir_security._apply_windows_acl(target)


class TestLocaleIndependentFailClosed:
    """REV-1108-M1: fail-closed zavisi ISKLJUČIVO od exit code-a, ne od
    lokalizovanog icacls teksta."""

    @staticmethod
    def _fake_run(monkeypatch, returncode, stdout="", stderr=""):
        class _Result:
            pass

        result = _Result()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: result)

    def test_returncode_zero_succeeds(self, temp_root, monkeypatch):
        self._fake_run(
            monkeypatch, 0, stdout="Successfully processed 4 files; Failed processing 0 files"
        )
        dir_security._run_icacls(["icacls", str(temp_root)], temp_root)

    def test_returncode_zero_unknown_text_succeeds(self, temp_root, monkeypatch):
        """Nepoznat (nelokalizovan/arbitraran) tekst + exit 0 nije failure."""
        self._fake_run(
            monkeypatch,
            0,
            stdout="Erfolgreich verarbeitet: 4 Dateien; Fehler: 0 Dateien",
            stderr="Zugriff verweigert",
        )
        dir_security._run_icacls(["icacls", str(temp_root)], temp_root)

    def test_returncode_nonzero_unknown_text_raises(self, temp_root, monkeypatch):
        self._fake_run(
            monkeypatch,
            5,
            stdout="Успјешно обрађено 0 датотека; Неуспјешно 1 датотека",
            stderr="Приступ је одбијен",
        )
        with pytest.raises(DirectoryHardeningError):
            dir_security._run_icacls(["icacls", str(temp_root)], temp_root)

    def test_returncode_nonzero_raises(self, temp_root, monkeypatch):
        self._fake_run(monkeypatch, 3)
        with pytest.raises(DirectoryHardeningError):
            dir_security._run_icacls(["icacls", str(temp_root)], temp_root)


class TestExistingDirectoryHardened:
    """F: postojeći direktorijum se hardenuje, ne samo novokreiran."""

    def test_already_existing_directory_still_triggers_acl(self, temp_root, monkeypatch):
        target = temp_root / "pre-existing"
        target.mkdir()  # već postoji PRIJE poziva ensure_private_directory

        calls = []
        monkeypatch.setattr(dir_security, "_apply_windows_acl", lambda p: calls.append(p))

        ensure_private_directory(target)

        if WIN:
            assert calls == [target.resolve()]

    def test_existing_files_remain_openable_after_hardening(self, temp_root):
        """Regresioni test: hardenovanje direktorijuma sa VEĆ postojećim
        fajlovima/poddirektorijumima NE SMIJE ih učiniti nepristupačnim.

        Prvobitna implementacija je primjenjivala (OI)(CI) container-inherit
        grant flagove DIREKTNO na fajlove preko jednog `/T` icacls poziva —
        icacls je prijavljivao uspjeh (exit=0), ali je rezultat bio prazan,
        potpuno nepristupačan ACL na svakom postojećem fajlu (dokazano
        probom protiv stvarnog %LOCALAPPDATA%/FlowOS/logs/flowos-service.log
        — vlasnik fajla je izgubio čak i read pristup). Ovaj test dokazuje
        da POPRAVLJENA dvokoračna implementacija ne ponavlja taj bag.
        """
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        target = temp_root / "pre-populated"
        target.mkdir()
        existing_file = target / "existing.log"
        existing_file.write_text("already here before hardening\n")
        nested_dir = target / "nested"
        nested_dir.mkdir()
        nested_file = nested_dir / "inner.txt"
        nested_file.write_text("nested content\n")

        ensure_private_directory(target)

        # Stvaran open() za append — ne samo icacls tekstualni izlaz.
        with open(existing_file, "a", encoding="utf-8") as f:
            f.write("appended after hardening\n")
        with open(nested_file, "a", encoding="utf-8") as f:
            f.write("appended after hardening\n")

        assert "already here before hardening" in existing_file.read_text()
        assert "appended after hardening" in existing_file.read_text()

    def test_harden_existing_directory_does_not_create(self, temp_root, monkeypatch):
        """harden_existing_directory ne kreira direktorijum — samo hardenuje
        ono što pozivalac (npr. schema_repair) već sam kreirao."""
        target = temp_root / "must-already-exist"
        calls = []
        monkeypatch.setattr(dir_security, "_apply_windows_acl", lambda p: calls.append(p))

        harden_existing_directory(target)

        assert not target.exists()
        if WIN:
            assert calls == [target.resolve()]


class TestNonWindowsBehaviorPreserved:
    """K: non-Windows izvršavanje ostaje podržano — samo mkdir, bez ACL poziva."""

    def test_non_windows_skips_acl(self, temp_root, monkeypatch):
        monkeypatch.setattr(dir_security.sys, "platform", "linux")
        calls = []
        monkeypatch.setattr(dir_security, "_apply_windows_acl", lambda p: calls.append(p))

        target = temp_root / "linux-style"
        ensure_private_directory(target)

        assert target.is_dir()
        assert calls == []


class TestSubprocessSafety:
    """L: path sa razmacima ostaje jedan bezbjedan argument; nema shell=True."""

    def test_path_with_spaces_is_single_argument_no_shell(self, temp_root, monkeypatch):
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        monkeypatch.setattr(dir_security, "_current_user_sid_string", lambda: "S-1-5-21-0-0-0-1")

        calls = []

        class _FakeResult:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def _fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return _FakeResult()

        monkeypatch.setattr(subprocess, "run", _fake_run)

        target = temp_root / "dir with spaces in name"
        target.mkdir()
        dir_security._apply_windows_acl(target)

        # _apply_windows_acl radi u DVA icacls poziva (§ dir_security modul
        # docstring) — provjeravamo OBA za bezbjedno prosleđivanje putanje.
        assert len(calls) == 2
        path_str = str(target)
        wildcard_str = str(target / "*")

        for cmd, kwargs in calls:
            assert isinstance(cmd, list)
            assert kwargs.get("shell", False) is False
            # Putanja (ili putanja+wildcard) je JEDAN element liste, ne razbijena.
            assert (path_str in cmd) or (wildcard_str in cmd)
            # Nijedan pojedinačni argument ne smije sadržati razmak OSIM same
            # putanje — dokazuje da nije spojeno u jedan shell string.
            non_path_args_with_space = [
                a for a in cmd if a not in (path_str, wildcard_str) and " " in a
            ]
            assert non_path_args_with_space == []

    def test_no_continue_on_error_flag(self, temp_root, monkeypatch):
        """REV-1108-M1: /C se ne koristi — fail-closed se oslanja na exit code,
        ne na lokalizovan tekst."""
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        monkeypatch.setattr(dir_security, "_current_user_sid_string", lambda: "S-1-5-21-0-0-0-1")
        captured = []

        class _FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        def _fake_run(cmd, **kwargs):
            captured.append(cmd)
            return _FakeResult()

        monkeypatch.setattr(subprocess, "run", _fake_run)
        target = temp_root / "no-C-flag"
        target.mkdir()
        dir_security._apply_windows_acl(target)

        assert len(captured) == 2
        for cmd in captured:
            assert "/C" not in cmd


class TestJunctionSafety:
    """§16: hardening ne smije 'iscuriti' kroz directory junction u cilj."""

    def test_icacls_command_includes_no_follow_link_flag(self, temp_root, monkeypatch):
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        monkeypatch.setattr(dir_security, "_current_user_sid_string", lambda: "S-1-5-21-0-0-0-1")
        captured = {}

        class _FakeResult:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def _fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _FakeResult()

        monkeypatch.setattr(subprocess, "run", _fake_run)
        target = temp_root / "junction-safety-check"
        target.mkdir()
        dir_security._apply_windows_acl(target)

        assert "/L" in captured["cmd"]

    def test_real_junction_target_unaffected(self, temp_root):
        """Empirijska potvrda: hardenovanje direktorijuma koji sadrži
        junction NE mijenja ACL junction cilja."""
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        real_target = temp_root / "real-target"
        real_target.mkdir()
        parent = temp_root / "parent-with-junction"
        parent.mkdir()
        junction = parent / "junction-link"

        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(real_target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(f"mklink /J nije uspio u ovom okruženju: {result.stderr}")

        before = subprocess.run(["icacls", str(real_target)], capture_output=True, text=True).stdout

        dir_security._apply_windows_acl(parent)

        after = subprocess.run(["icacls", str(real_target)], capture_output=True, text=True).stdout
        assert before == after


class TestRuntimeWiring:
    """A + H: RuntimeManager.write_descriptor hardenuje PRIJE upisa descriptora."""

    def test_write_descriptor_invokes_hardening(self, temp_root, monkeypatch):
        from flowos.service.services.infrastructure import runtime as runtime_module

        mgr = runtime_module.RuntimeManager()
        mgr.DESCRIPTOR_DIR = temp_root / "runtime"
        mgr.DESCRIPTOR_FILE = mgr.DESCRIPTOR_DIR / "service.json"

        calls = []
        real_ensure = runtime_module.ensure_private_directory

        def _spy(path):
            calls.append(path)
            return real_ensure(path)

        monkeypatch.setattr(runtime_module, "ensure_private_directory", _spy)

        mgr.write_descriptor(9100)

        assert calls == [mgr.DESCRIPTOR_DIR]
        assert mgr.DESCRIPTOR_FILE.exists()

    def test_descriptor_not_written_if_hardening_fails(self, temp_root, monkeypatch):
        from flowos.service.services.infrastructure import runtime as runtime_module

        mgr = runtime_module.RuntimeManager()
        mgr.DESCRIPTOR_DIR = temp_root / "runtime"
        mgr.DESCRIPTOR_FILE = mgr.DESCRIPTOR_DIR / "service.json"

        def _boom(path):
            raise DirectoryHardeningError("hardening failed before descriptor write")

        monkeypatch.setattr(runtime_module, "ensure_private_directory", _boom)

        with pytest.raises(DirectoryHardeningError):
            mgr.write_descriptor(9100)

        assert not mgr.DESCRIPTOR_FILE.exists()

    def test_descriptor_not_written_on_icacls_nonzero_failure(self, temp_root, monkeypatch):
        """REV-1108-M1: icacls non-zero failure → write_descriptor fail-closed,
        NE upisuje ni service.json ni .tmp (locale-independent)."""
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        from flowos.service.services.infrastructure import runtime as runtime_module

        mgr = runtime_module.RuntimeManager()
        mgr.DESCRIPTOR_DIR = temp_root / "runtime"
        mgr.DESCRIPTOR_FILE = mgr.DESCRIPTOR_DIR / "service.json"

        monkeypatch.setattr(dir_security, "_current_user_sid_string", lambda: "S-1-5-21-0-0-0-1")

        class _Failure:
            returncode = 5
            stdout = "непознати локализовани излаз"
            stderr = "приступ одбијен"

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Failure())

        with pytest.raises(DirectoryHardeningError):
            mgr.write_descriptor(9100)

        assert not mgr.DESCRIPTOR_FILE.exists()
        assert not mgr.DESCRIPTOR_FILE.with_suffix(".tmp").exists()


class TestDatabaseDirectoryWiring:
    """B: get_data_directory() hardenuje direktorijum koji drži .db/-wal/-shm."""

    def test_get_data_directory_invokes_hardening(self, monkeypatch):
        from flowos.service.services.infrastructure.persistence import engine as engine_module

        calls = []
        monkeypatch.setattr(engine_module, "ensure_private_directory", lambda p: calls.append(p))

        result = engine_module.get_data_directory()

        expected = Path.home() / "AppData" / "Local" / "FlowOS" / "data"
        assert calls == [expected]
        assert result == expected


class TestLogsDirectoryWiring:
    """C: setup_logging() hardenuje default log_dir, ne custom override."""

    def test_setup_logging_default_invokes_hardening(self, temp_root, monkeypatch):
        """Preusmjerava LOCALAPPDATA na tmp_path — ne diramo stvaran korisnički
        %LOCALAPPDATA%/FlowOS/logs niti ostavljamo otvoren fajl handle tamo."""
        import logging as stdlib_logging

        from flowos.service.services.infrastructure import logging as logging_module

        monkeypatch.setenv("LOCALAPPDATA", str(temp_root))
        calls = []
        real_ensure = logging_module.ensure_private_directory

        def _spy(path):
            calls.append(path)
            return real_ensure(path)

        monkeypatch.setattr(logging_module, "ensure_private_directory", _spy)

        root = logging_module.setup_logging(console=False)
        for h in list(root.handlers):
            h.close()
            root.removeHandler(h)
        stdlib_logging.getLogger("flowos").handlers.clear()

        assert len(calls) == 1
        assert calls[0] == temp_root / "FlowOS" / "logs"

    def test_setup_logging_custom_dir_skips_hardening(self, temp_root, monkeypatch):
        from flowos.service.services.infrastructure import logging as logging_module

        calls = []
        monkeypatch.setattr(logging_module, "ensure_private_directory", lambda p: calls.append(p))

        logging_module.setup_logging(log_dir=temp_root / "custom-logs", console=False)

        assert calls == []


class TestBackupDirectoryWiring:
    """D: schema-repair backup direktorijum se hardenuje odmah nakon kreiranja."""

    def test_create_schema_backup_invokes_hardening(self, temp_root, monkeypatch):
        import sqlite3

        from flowos.service.services.infrastructure.persistence import schema_repair

        db_path = temp_root / "flowos.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        calls = []
        real_harden = schema_repair.harden_existing_directory

        def _spy(path):
            calls.append(path)
            return real_harden(path)

        monkeypatch.setattr(schema_repair, "harden_existing_directory", _spy)

        result = schema_repair.create_schema_backup(db_path)

        assert len(calls) == 1
        assert calls[0] == result.path

    def test_schema_backup_not_written_on_icacls_nonzero_failure(self, temp_root, monkeypatch):
        """REV-1108-M1: non-zero icacls failure sprečava upis backup sadržaja."""
        if not WIN:
            pytest.skip("Windows-specific ACL kod")

        import sqlite3

        from flowos.service.services.infrastructure.persistence import schema_repair

        db_path = temp_root / "flowos.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        monkeypatch.setattr(dir_security, "_current_user_sid_string", lambda: "S-1-5-21-0-0-0-1")

        class _Failure:
            returncode = 5
            stdout = "непознати локализовани излаз"
            stderr = "приступ одбијен"

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Failure())

        with pytest.raises(DirectoryHardeningError):
            schema_repair.create_schema_backup(db_path)

        backups_root = db_path.parent / "backups"
        copied = list(backups_root.rglob("flowos.db")) if backups_root.exists() else []
        assert copied == []


class TestHotPathNotInvoked:
    """I: hardening se NE izvršava po svakom request-u/hot-path operaciji."""

    def test_repeated_requests_do_not_reinvoke_hardening(self, monkeypatch, tmp_path):
        """create_app()/lifespan poziva setup_logging() TAČNO jednom (startup
        granica). LOCALAPPDATA je preusmjeren na tmp_path da REALNI hardening
        poziv (ne mockovan) nikad ne dirne stvaran korisnički profil niti
        ostavi otvoren fajl handle van test izolacije."""
        import logging as stdlib_logging
        import os

        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine

        import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
        import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
        import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
        import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
        from flowos.service.composition_root import create_app
        from flowos.service.services.infrastructure import logging as logging_module
        from flowos.service.services.infrastructure.persistence.base import Base

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

        class _RT:
            def __init__(self):
                self.pid = os.getpid()
                self.port = 9199
                self.token = "hot-path-test-token"

            def acquire_lock(self):
                pass

            def release_lock(self):
                pass

            def delete_descriptor(self):
                pass

        db_path = tmp_path / "hotpath.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        app = create_app(_RT(), engine=engine)

        calls = []
        real_ensure = logging_module.ensure_private_directory

        def _spy(path):
            calls.append(path)
            return real_ensure(path)

        monkeypatch.setattr(logging_module, "ensure_private_directory", _spy)

        try:
            with TestClient(app) as client:
                baseline = len(calls)
                assert baseline == 1  # tačno jedan poziv na lifespan startup

                for _ in range(5):
                    client.get("/health")
                    client.get("/projects", headers={"Authorization": "Bearer hot-path-test-token"})

                assert len(calls) == baseline, (
                    "ACL hardening se pozvao tokom običnih HTTP zahtjeva — "
                    "mora se dešavati samo na startup/init granici, ne u hot path-u."
                )
        finally:
            for h in list(stdlib_logging.getLogger("flowos").handlers):
                h.close()
            stdlib_logging.getLogger("flowos").handlers.clear()


@pytest.mark.skipif(not WIN, reason="Real Windows ACL probe — samo na Windows-u")
class TestRealWindowsAclProbe:
    """§15: stvaran ACL hardening na PRIVREMENOM test direktorijumu.

    Ne dira stvaran user profile/repo ACL — radi isključivo u tmp_path.
    """

    def test_real_hardening_restricts_to_expected_principals(self, temp_root):
        import win32api
        import win32security

        target = temp_root / "real-acl-probe"
        target.mkdir()
        (target / "nested-file.txt").write_text("x")

        dir_security._apply_windows_acl(target)

        result = subprocess.run(["icacls", str(target)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        output = result.stdout

        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
        )
        sid, _ = win32security.GetTokenInformation(token, win32security.TokenUser)
        user_sid_str = win32security.ConvertSidToStringSid(sid)

        # Trenutni korisnik zadržava pristup.
        assert user_sid_str in output or "radovan" in output.lower()
        # Everyone / Users / Authenticated Users nemaju namjerno širok grant.
        assert "Everyone" not in output
        assert "BUILTIN\\Users" not in output
        assert "Authenticated Users" not in output

    def test_real_hardening_is_idempotent(self, temp_root):
        target = temp_root / "idempotent-probe"
        target.mkdir()

        dir_security._apply_windows_acl(target)
        first = subprocess.run(["icacls", str(target)], capture_output=True, text=True).stdout
        dir_security._apply_windows_acl(target)
        second = subprocess.run(["icacls", str(target)], capture_output=True, text=True).stdout

        assert first == second
