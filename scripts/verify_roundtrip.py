# ruff: noqa: SIM105
"""Alembic round-trip test na privremenoj bazi."""

import os
import subprocess
import sys
import tempfile


def main():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "test.db")
    url = f"sqlite:///{db}"
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"sqlalchemy.url={url}", "upgrade", "head"],
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"sqlalchemy.url={url}", "downgrade", "base"],
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"sqlalchemy.url={url}", "upgrade", "head"],
            check=True,
        )
        print("[PASS] Round-trip na privremenoj bazi")
    except Exception as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
    finally:
        try:
            os.unlink(db)
        except OSError:
            pass
        try:
            os.rmdir(d)
        except OSError:
            pass


if __name__ == "__main__":
    main()
