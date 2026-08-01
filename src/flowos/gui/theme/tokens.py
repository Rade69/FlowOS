"""FlowOS GUI Design Tokens — jedini izvor vizuelnih vrednosti.

Sve boje, spacing, radius, font veličine i semantički tokeni
definisani su ovde. Ni jedan widget ne sme imati hardkodovane
hex vrednosti ili piksel dimenzije.
"""

# Spacing (px)
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_XXL = 32

# Border radius (px)
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8
RADIUS_XL = 12

# Font sizes (px)
FONT_XS = 11
FONT_SM = 12
FONT_MD = 13
FONT_LG = 14
FONT_XL = 18
FONT_XXL = 24

# Minimalne širine panela
SIDEBAR_MIN_WIDTH = 220
SIDEBAR_DEFAULT_WIDTH = 260
DETAIL_PANEL_MIN_WIDTH = 300

# Statusne boje — tačne vrednosti iz mockupa
COLOR_SUCCESS = "#2D9F4E"
COLOR_WARNING = "#D9A40E"
COLOR_DANGER = "#D93A3A"
COLOR_INFO = "#3A7AD9"
COLOR_MUTED = "#8C8C8C"

# Neutralne — Tamna tema (Catppuccin Mocha)
COLOR_BG_PRIMARY = "#1E1E2E"
COLOR_BG_SECONDARY = "#181825"
COLOR_BG_TERTIARY = "#11111B"
COLOR_BG_CARD = "#252536"
COLOR_BG_HOVER = "#313244"
COLOR_TEXT_PRIMARY = "#CDD6F4"
COLOR_TEXT_SECONDARY = "#A6ADC8"
COLOR_TEXT_MUTED = "#6C7086"
COLOR_BORDER = "#45475A"
COLOR_BORDER_ACTIVE = "#89B4FA"

# Semantičke (Catppuccin)
COLOR_BLUE = "#89B4FA"
COLOR_GREEN = "#A6E3A1"
COLOR_YELLOW = "#F9E2AF"
COLOR_RED = "#F38BA8"
COLOR_PURPLE = "#CBA6F7"
COLOR_TEAL = "#94E2D5"

# Statusne boje
COLOR_STATUS_NOT_STARTED = "#585B70"
COLOR_STATUS_IN_PROGRESS = "#F9E2AF"
COLOR_STATUS_BLOCKED = "#F38BA8"
COLOR_STATUS_IMPLEMENTED = "#CBA6F7"
COLOR_STATUS_VERIFIED = "#94E2D5"
COLOR_STATUS_ACCEPTED = "#A6E3A1"
COLOR_STATUS_REJECTED = "#EBA0AC"

# Panel dimenzije
SIDEBAR_MIN_WIDTH = 220
SIDEBAR_DEFAULT_WIDTH = 240
RIGHT_PANEL_MIN_WIDTH = 340
RIGHT_PANEL_DEFAULT_WIDTH = 380
TOPBAR_HEIGHT = 52
FOOTER_HEIGHT = 28


def status_color(level: str) -> str:
    """Vraća semantičku boju za nivo upozorenja/statusa."""
    return {
        "HIGH": COLOR_DANGER,
        "MEDIUM": COLOR_WARNING,
        "INFO": COLOR_INFO,
        "LOW": COLOR_MUTED,
    }.get(level, COLOR_MUTED)


def attribution_color(confidence: str) -> str:
    """Vraća boju za nivo pouzdanosti atribucije."""
    return {
        "WORKTREE": COLOR_SUCCESS,
        "SOLE_ACTIVE": COLOR_INFO,
        "HINT": COLOR_WARNING,
        "UNATTRIBUTED": COLOR_MUTED,
        "USER": COLOR_MUTED,
    }.get(confidence, COLOR_MUTED)
