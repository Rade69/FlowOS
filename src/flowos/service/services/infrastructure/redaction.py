"""Centralna deterministička redakcija tajni (FLOW-1109).

Jedna mala reusable komponenta koja sprečava da poznate osjetljive
vrijednosti (prvenstveno FLOW-1107 runtime bearer token) završe u trajnim
FlowOS logovima, dijagnostičkim outputima ili FlowOS-generisanim
artefaktima.

Pravila:
- SAMO deterministička zamjena poznatih secret vrijednosti — nema LLM/ML,
  nema fuzzy/semantic detekcije, nema mrežnih poziva.
- Boundary-based: tajna smije postojati u memoriji; redakcija se primjenjuje
  prije trajnog upisa (log/diagnostic/artifact).
- Canonical replacement je tačno ``[REDACTED]``.
- Za dictionary/JSON-like strukture rediguju se vrijednosti za jasno
  osjetljive ključeve (case-insensitive), ne za proizvoljne "key"/"id" riječi.
"""

from __future__ import annotations

REDACTED = "[REDACTED]"

# Kanonski osjetljivi ključevi (case-insensitive tačan match).
SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "token",
        "access_token",
        "api_key",
        "apikey",
        "secret",
        "password",
    }
)

# Env-style sufiksi (case-insensitive): CLAUDE_API_KEY, ANTHROPIC_API_KEY,
# OPENAI_API_KEY, DEEPSEEK_API_KEY, *_ACCESS_TOKEN, *_SECRET, *_PASSWORD.
SENSITIVE_KEY_SUFFIXES = (
    "_api_key",
    "_apikey",
    "_token",
    "_access_token",
    "_secret",
    "_password",
)

# Kratke vrijednosti se ne registruju kao tajna da ne bi slučajno redigovale
# cijeli tekst (npr. tajna dužine 1 bi zamijenila svako pojavljivanje tog
# karaktera). FLOW-1107 token je secrets.token_urlsafe(32) — znatno duži.
_MIN_SECRET_LENGTH = 8


class Redactor:
    """Deterministički redaktor poznatih tajni i osjetljivih ključeva."""

    def __init__(self, secrets: object = ()) -> None:
        self._secrets: list[str] = []
        for secret in secrets if isinstance(secrets, (list, tuple, set)) else ():
            self.register_secret(secret)

    def register_secret(self, secret: object) -> None:
        """Registruje poznatu tajnu vrijednost (None/empty/kratko se ignoriše)."""
        if (
            isinstance(secret, str)
            and len(secret) >= _MIN_SECRET_LENGTH
            and secret not in self._secrets
        ):
            self._secrets.append(secret)

    def clear(self) -> None:
        """Uklanja sve registrovane tajne (za test teardown)."""
        self._secrets.clear()

    def redact_text(self, text: str | None) -> str:
        """Zamjenjuje sve poznate tajne u tekstu sa ``[REDACTED]``.

        Ne mutira ulaz (``str.replace`` vraća novi string). Podržava više
        tajni u istom tekstu i tajnu na početku/kraju/više puta.
        """
        if not text:
            return ""
        result = text
        for secret in self._secrets:
            result = result.replace(secret, REDACTED)
        return result

    def redact_mapping(self, data: dict) -> dict:
        """Rediguje vrijednosti osjetljivih ključeva (rekurzivno, bez mutacije)."""
        result: dict = {}
        for key, value in data.items():
            if self._is_sensitive_key(key):
                result[key] = REDACTED
            elif isinstance(value, dict):
                result[key] = self.redact_mapping(value)
            elif isinstance(value, list):
                result[key] = [
                    self.redact_mapping(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                result[key] = value
        return result

    @staticmethod
    def _is_sensitive_key(key: object) -> bool:
        lowered = str(key).lower()
        if lowered in SENSITIVE_KEYS:
            return True
        return lowered.endswith(SENSITIVE_KEY_SUFFIXES)


# Process-wide default redactor — jedan izvor istine za production boundary
# (logging formatter, verification artifact store). Runtime token se
# registruje pri startup-u (composition_root lifespan).
_default_redactor = Redactor()


def register_secret(secret: object) -> None:
    """Registruje tajnu u process-wide redactor (npr. runtime bearer token)."""
    _default_redactor.register_secret(secret)


def redact_text(text: str | None) -> str:
    """Process-wide redakcija teksta."""
    return _default_redactor.redact_text(text)


def redact_mapping(data: dict) -> dict:
    """Process-wide redakcija mapping/structured data."""
    return _default_redactor.redact_mapping(data)


def reset_redactor() -> None:
    """Čisti process-wide redactor (test teardown)."""
    _default_redactor.clear()
