import io
from datetime import datetime
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
import docgen  # registers LS / LSB fonts
from cef import n, battery_cable_proposal

PT = 0.3528
INK = colors.HexColor("#111111")
RED = colors.HexColor("#c0392b")
PEC = colors.HexColor("#1e8449")
GREY = colors.HexColor("#666666")
PV_ORANGE = colors.HexColor("#d9822b")
BATTERY_GREEN = colors.HexColor("#26834a")
BACKUP_BLUE = colors.HexColor("#3066c2")
PAPER = colors.HexColor("#fbf8f2")
GRID_LINE = colors.HexColor("#e8e2d8")
CELL = ParagraphStyle("c", fontName="LS", fontSize=6.6, leading=8)
CELLB = ParagraphStyle("cb", fontName="LSB", fontSize=6.6, leading=8)


def battery_protection(battery, proposal=None):
    """Describe known DC battery protection without turning a proposal into an installed device."""
    battery = battery or {}
    proposal = proposal or {}
    breaker = n(battery.get("breaker_a"))
    fuse = n(battery.get("fuse_a"))
    proposed_fuse = n(proposal.get("fuse_a"))
    if breaker:
        return {"kind": "breaker", "rating": breaker, "source": "documentată"}
    if battery.get("breaker_integrated"):
        return {"kind": "integrated", "rating": None, "source": "integrată; calibru neconfirmat"}
    if fuse:
        return {"kind": "fuse", "rating": fuse, "source": "declarată; de verificat"}
    if proposed_fuse:
        return {"kind": "proposal", "rating": proposed_fuse, "source": "PROPUSĂ — de confirmat"}
    return {"kind": "missing", "rating": None, "source": "LIPSĂ — protecție de confirmat"}


def battery_protection_text(state):
    kind = state["kind"]
    device = {"breaker": "întreruptor DC", "integrated": "protecție integrată",
              "fuse": "siguranță fuzibilă DC", "proposal": "siguranță fuzibilă DC propusă",
              "missing": "protecție DC neidentificată"}[kind]
    rating = gv(state.get("rating"), " A")
    return f"{device}{f' {rating}' if rating else ''} — {state['source']}"


def gv(x, unit=""):
    if x in (None, "", 0) or (isinstance(x, float) and x == 0):
        return None
    if isinstance(x, float):
        x = round(x, 2)
    return f"{x:g}{unit}" if isinstance(x, (int, float)) else f"{x}{unit}"


class Sheet:
    def __init__(self, c):
        self.c = c
        self.miss = 0
        self.mirror_x = False

    # ---------- primitives (units: mm after scaling) ----------
    def lw(self, w=0.25, color=INK, dash=None):
        c = self.c
        c.setLineWidth(w); c.setStrokeColor(color); c.setDash(*(dash or ([], 0)))

    def wire(self, x1, y1, x2, y2, kind="ac"):
        if kind == "pe":
            self.lw(0.3, PEC, ([1.6, 0.8], 0))
        elif kind == "ctl":
            self.lw(0.18, GREY, ([0.8, 0.6], 0))
        elif kind == "dc":
            self.lw(0.35, PV_ORANGE)
        elif kind == "backup":
            self.lw(0.35, BACKUP_BLUE)
        elif kind == "bat":
            self.lw(0.35, BATTERY_GREEN)
        else:
            self.lw(0.4)
        self.c.line(x1, y1, x2, y2)
        self.lw()

    def text(self, x, y, s, size=5.4, bold=False, color=INK, anchor="l", w=None):
        c = self.c
        f = "LSB" if bold else "LS"
        fs = size * PT
        s = str(s)
        if w:
            while s and c.stringWidth(s, f, fs) > w:
                s = s[:-2]
        c.setFont(f, fs); c.setFillColor(color)
        if self.mirror_x:
            # The electrical layout is reversed to run from utility/grid at
            # the left to PV strings at the right. Counter-flip text locally so
            # labels remain readable while following their equipment.
            c.saveState(); c.translate(x, y); c.scale(-1, 1)
            draw = {"l": c.drawRightString, "c": c.drawCentredString, "r": c.drawString}[anchor]
            draw(0, 0, s)
            c.restoreState()
        else:
            {"l": c.drawString, "c": c.drawCentredString, "r": c.drawRightString}[anchor](x, y, s)

    def val(self, x, y, label, value, unit="", size=5.2, anchor="l", w=None, bold=False):
        v = gv(value, unit)
        if v is None:
            self.miss += 1
            self.text(x, y, f"{label}[lipsă]" if label else "[lipsă]", size, bold, RED, anchor, w)
        else:
            self.text(x, y, f"{label}{v}", size, bold, INK, anchor, w)

    def node(self, x, y):
        self.c.setFillColor(INK); self.c.circle(x, y, 0.55, stroke=0, fill=1)

    def fuse(self, x, y, vertical=False):
        self.lw(0.3)
        if vertical:
            self.c.rect(x - 1.1, y - 3, 2.2, 6, stroke=1, fill=0); self.c.line(x, y - 3, x, y + 3)
        else: