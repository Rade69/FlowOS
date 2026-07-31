"""FlowOS test suite — zajednička konfiguracija.

Koristi pytest sa pytest-qt, pytest-asyncio i coverage pluginovima.
"""

import sys
from pathlib import Path

# Dodaj src/ u Python path za import flowos modula
_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
