import io
from datetime import datetime
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
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
CELL = ParagraphStyle("c", fontName="LS", fontSize=6.6, leading=8)
CELLB = ParagraphStyle("cb", fontName="LSB", fontSize=6.6, leading=8)


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
            self.c.rect(x - 3, y - 1.1, 6, 2.2, stroke=1, fill=0); self.c.line(x - 3, y, x + 3, y)

    def switch_vertical(self, x, y):
        """Vertical DC breaker symbol; ratings come from the selected equipment data."""
        self.lw(0.4)
        self.c.line(x, y - 5, x, y - 3)
        self.c.line(x, y + 3, x, y + 5)
        self.c.rect(x - 2.2, y - 3, 4.4, 6, stroke=1, fill=0)
        self.c.line(x - 1.4, y - 1.6, x + 1.4, y + 1.6)
        self.lw()

    def switch(self, x, y, kind="Q"):
        """horizontal switching device occupying x-5..x+5. kind: Q breaker, S disconnector, LS switch-disconnector, K contactor"""
        c = self.c
        self.lw(0.4)
        c.line(x - 5, y, x - 3, y); c.line(x + 3, y, x + 5, y)
        c.line(x - 3, y, x + 2.6, y + 2.8)
        self.lw(0.3)
        if kind == "Q":
            c.line(x + 2.2, y - 0.8, x + 3.8, y + 0.8); c.line(x + 2.2, y + 0.8, x + 3.8, y - 0.8)
        if kind in ("S", "LS"):
            c.line(x + 3, y - 1, x + 3, y + 1)
        if kind == "LS":
            c.circle(x + 3, y + 1.6, 0.55, stroke=1, fill=0)
        if kind == "K":
            p = c.beginPath(); p.arc(x + 2.2, y - 0.8, x + 3.8, y + 0.8, 90, 180); c.drawPath(p, stroke=1, fill=0)
        self.lw()

    def rcd(self, x, y):
        self.switch(x, y, "Q")
        self.lw(0.3); self.c.ellipse(x - 8.2, y - 2.2, x - 6, y + 2.2, stroke=1, fill=0)
        self.wire(x - 7.1, y + 2.2, x - 7.1, y + 4, "ctl"); self.wire(x - 7.1, y + 4, x - 0.2, y + 4, "ctl"); self.wire(x - 0.2, y + 4, x - 0.2, y + 0.4, "ctl")
        self.text(x - 9.5, y - 4.2, "IΔ", 4.6)

    def spd(self, x, y, y_to):
        self.wire(x, y, x, y - 3)
        self.node(x, y)
        self.lw(0.3); self.c.rect(x - 1.3, y - 9, 2.6, 6, stroke=1, fill=0)
        self.c.line(x - 1.3, y - 8, x + 1.3, y - 4); self.c.line(x + 1.3, y - 4, x + 2.1, y - 4)
        self.wire(x, y - 9, x, y_to, "pe")

    def earth(self, x, y):
        self.lw(0.35, PEC)
        self.c.line(x, y, x, y - 3)
        for k, w in enumerate((3.2, 2.1, 1.0)):
            self.c.line(x - w, y - 3 - k * 0.9, x + w, y - 3 - k * 0.9)
        self.lw()

    def meter(self, x, y, label="kWh", bidir=True):
        self.lw(0.35); self.c.setFillColor(colors.white)
        self.c.rect(x - 5.5, y - 4, 11, 8, stroke=1, fill=1)
        self.text(x, y - 0.4, label, 5.6, True, anchor="c")
        if bidir:
            self.lw(0.25)
            self.c.line(x - 3, y - 2.6, x + 3, y - 2.6); self.c.line(x + 3, y - 2.6, x + 2.2, y - 2.1); self.c.line(x - 3, y - 2.6, x - 2.2, y - 3.1)

    def ct(self, x, y):
        self.lw(0.3); self.c.circle(x, y, 1.9, stroke=1, fill=0); self.lw()

    def inverter(self, cx, cy, h=13, existing=False):
        self.lw(0.45, INK, ([1.2, 0.8], 0) if existing else None)
        self.c.setFillColor(colors.white)
        self.c.rect(cx - h, cy - h, 2 * h, 2 * h, stroke=1, fill=1)
        self.lw(0.3); self.c.line(cx - h, cy - h, cx + h, cy + h)
        self.text(cx - h + 2.5, cy + h - 5.5, "=", 9, True)
        self.text(cx + h - 7, cy - h + 2.2, "~", 10, True)

    def pv(self, x1, y, w=16, h=8):
        self.lw(0.35, PV_ORANGE); self.c.setStrokeColor(PV_ORANGE); self.c.setFillColor(colors.white)
        self.c.rect(x1, y - h / 2, w, h, stroke=1, fill=1)
        self.lw(0.25); self.c.line(x1, y - h / 2, x1 + w, y + h / 2)
        for dx in (0, 2.2):
            ax, ay = x1 + w - 7 + dx, y + h / 2 + 3
            self.c.line(ax, ay, ax + 1.8, ay - 2.4); self.c.line(ax + 1.8, ay - 2.4, ax + 1.0, ay - 2.0); self.c.line(ax + 1.8, ay - 2.4, ax + 1.9, ay - 1.5)
        self.text(x1 + w - 3.5, y - h / 2 + 1, "=", 6)

    def battery(self, x, y):
        self.lw(0.4, BATTERY_GREEN)
        for k in range(2):
            yy = y - k * 2.6
            self.c.line(x - 3.2, yy, x + 3.2, yy)
            self.lw(0.9, BATTERY_GREEN); self.c.line(x - 1.6, yy - 1.2, x + 1.6, yy - 1.2); self.lw(0.4, BATTERY_GREEN)
        self.text(x + 3.8, y - 0.6, "+", 5); self.text(x + 3.8, y - 5, "−", 5)

    def enclosure(self, x1, y1, x2, y2, label, sub=""):
        self.lw(0.25, GREY, ([3, 0.8, 0.5, 0.8], 0))
        self.c.rect(x1, y1, x2 - x1, y2 - y1, stroke=1, fill=0); self.lw()
        self.text(x1 + 1, y2 - 2.6, label, 5.4, True, w=x2 - x1 - 2)
        if sub:
            self.text(x1 + 1, y2 - 4.8, sub, 4.6, color=GREY, w=x2 - x1 - 2)

    def tick(self, x, y, label):
        self.lw(0.25); self.c.line(x - 0.9, y - 1.3, x + 0.9, y + 1.3); self.lw()
        self.text(x, y - 3.4, label, 4.6, anchor="c")

    def transformer(self, cx, cy):
        self.lw(0.35); self.c.circle(cx - 1.9, cy, 3.2, stroke=1, fill=0); self.c.circle(cx + 1.9, cy, 3.2, stroke=1, fill=0); self.lw()


# ---------------------------------------------------------------- diagram
def diagram(S, rec, res, client):
    """Draws in virtual mm. Returns (width, height) via dry layout first."""
    cef = rec.get("cef") or {}
    grid = cef.get("grid") or {}
    base = res["base"]
    invs = cef.get("inverters") or []
    tri = base["grid"]["tri"]
    anti = base["grid"]["anti"]
    A = 32 if anti else 0
    rows = []
    for i, inv in enumerate(invs):
        st = base["inverters"][i]["strings"] or []
        nm = len({x["mppt"] for x in st}) or 1
        hh = max(13, 1.6 * (nm + 1))
        hs = max(len(st) * 14, 36, 2 * hh + 22) + 10
        hb = 40 if inv.get("battery_mode") == "own" else (12 if (inv.get("backup") or {}).get("enabled") else 4)
        rows.append((hs, hb + 2 * (hh - 13)))
    shared = cef.get("shared_batteries") or []
    H = 12 + sum(a + b for a, b in rows) + (46 if shared else 0) + 18
    W = 418 + A
    return W, H, lambda: _draw(S, rec, res, client, rows, W, H, A, tri, anti, grid, base, invs, shared)


def _draw(S, rec, res, client, rows, W, H, A, tri, anti, grid, base, invs, shared):
    y_pe = 8
    top = H - 12
    cys = []
    yy = top
    for hs, hb in rows:
        cys.append(yy - hs / 2 - 2)
        yy -= hs + hb
    y_shared = yy - 14
    conductors = "3L+N+PE" if tri else "L+N+PE"
    poles = "4P" if tri else "2P"
    BUS, TGQ, SPDX = 248, 262, 282
    inv_in = []
    for i, inv in enumerate(invs):
        hs, hb = rows[i]
        nmi = len({x["mppt"] for x in (base["inverters"][i]["strings"] or [])}) or 1
        hh = max(13, 1.6 * (nmi + 1))
        dd = hh - 13
        cy = cys[i] + dd
        r = base["inverters"][i]
        ac, dc = inv.get("ac") or {}, inv.get("dc") or {}
        strings = r["strings"] or []
        strings_raw = (inv.get("strings") or []) + [{}] * len(strings)
        row_bot = cy - hs / 2 - hb + 2
        pe_y = row_bot + 1.5
        # PV strings + TDC
        if strings:
            ys = [cy + (len(strings) - 1) * 7 - k * 14 for k in range(len(strings))]
            par = {}
            for k, s in enumerate(strings):
                par.setdefault(s["mppt"], []).append(k)
            fuses = max(len(v) for v in par.values()) >= 3
            S.enclosure(56, min(ys) - 13, 116, max(ys) + 13, f"-TDC{i + 1}  Cutie DC / joncțiune", "SR EN 61439-2 · IEC 62548")
            for k, s in enumerate(strings):
                y = ys[k]
                S.pv(6, y)
                S.text(6, y + 4.9, f"-PV{i + 1}.{k + 1}", 4.8, True)
                agg = strings_raw[k].get("aggregate")
                lbl = "Câmp PV total (stringuri nedefinite)" if agg else f"S{k + 1}:"
                val = f"{s['panels']}×{gv(n(inv.get('panel_w')), ' W') or '[W lipsă]'} = " + (f"{s['kwp']:g} kWp" if s['kwp'] else "[kWp lipsă]")
                if agg:
                    S.text(24, y + 3.6, lbl, 4.4, True, w=31)
                    S.text(24, y + 1.0, val, 4.8, w=31)
                else:
                    S.text(24, y + 1.2, f"{lbl} {val}", 4.8, w=31)
                S.text(24, y - 3.0, (f"Voc({base['tmin']:g}°C) {s['voc_cold']:.0f} V" if s.get("voc_cold") else "Voc [lipsă]") + " · " + (f"Isc {s['isc']:g} A" if s.get("isc") else "Isc [lipsă]"), 4.4, color=GREY, w=31)
                S.wire(22, y, 72, y, "dc")
                if fuses:
                    S.fuse(62, y)
                S.wire(2, y - 4, 6, y - 4, "pe")
            S.text(6, min(ys) - 8.5, str(inv.get("panel_model") or "[model panou lipsă]"), 4.6, color=INK if inv.get("panel_model") else RED, w=48)
            mppts = sorted(par)
            nm = len(mppts)
            for j, m in enumerate(mppts):
                ks = par[m]
                ym = ys[ks[0]]
                if len(ks) > 1:
                    S.wire(72, ys[ks[-1]], 72, ym, "dc")
                    for k in ks:
                        S.node(72, ys[k])
                yin = cy + hh - (j + 1) * 2 * hh / (nm + 1)
                S.wire(72, ym, 79, ym, "dc"); S.switch(84, ym, "LS"); S.wire(89, ym, 110, ym, "dc")
                S.text(81, ym + 3.6, f"-Q{i + 1}.D{m}", 4.4)
                S.spd(98, ym, pe_y)
                S.wire(110, ym, 110, yin, "dc"); S.wire(110, yin, 118, yin, "dc")
                S.text(111, yin + 0.8, f"M{m}", 3.8)
            sw = dc.get("switch")
            ty = max(ys) + 8.6
            S.val(58, ty - 2.6, "Separator DC: ", sw, w=56, size=4.6)
            S.val(58, ty - 4.8, "SPD DC T2 Ucpv ", n(dc.get("spd_ucpv")), " V", w=56, size=4.6)
            if fuses:
                S.val(58, ty - 7.0, "Siguranțe gPV ", n(dc.get("fuse_a")), " A / 1000 V", w=56, size=4.6)
            by = min(ys) - 11.8
            S.text(58, by + 2.2, f"-W{i + 1}.DC  {dc.get('cable_type') or 'H1Z2Z2-K'}", 4.6, True, w=56)
            S.val(58, by, "1×", n(dc.get("section")), f" mm² {dc.get('material') or 'Cu'} (+/−), L=" + (gv(n(dc.get('length_m')), ' m') or "[lipsă]"), w=56, size=4.6)
            S.wire(2, min(ys) - 4, 2, pe_y, "pe")
        # inverter
        cx = 134
        S.inverter(cx, cy, hh, existing=bool(inv.get("existing")))
        cy -= dd
        S.text(cx, cy + 22.2 + 2 * dd, f"-U{i + 1}" + ("  (existent)" if inv.get("existing") else ""), 5.4, True, anchor="c")
        S.val(cx, cy + 19.6 + 2 * dd, "", inv.get("brand_model"), anchor="c", w=48, bold=True, size=5.2)
        ph = "trifazat" if r["tri"] else ("monofazat" + (f" {inv.get('phase')}" if inv.get("phase") else ""))
        S.text(cx, cy + 17.2 + 2 * dd, f"{inv.get('type') or 'Invertor'} · {ph}", 4.8, anchor="c", w=48)
        S.val(cx, cy + 14.8 + 2 * dd, "Pn ", n(inv.get("p_nom_kw")), " kW" + (f" · Pmax {gv(n(inv.get('p_max_kw')), ' kW')}" if n(inv.get("p_max_kw")) else ""), anchor="c", w=48, size=4.8)
        S.wire(cx - 9, cy - 13, cx - 9, pe_y, "pe")
        S.text(cx - 12, cy - 16, "PE", 4.2, color=PEC, anchor="r")
        S.wire(2, pe_y, cx - 9, pe_y, "pe")
        # Battery branch: DC breaker, datasheet ratings and cable section from selected data.
        if inv.get("battery_mode") == "own":
            bt = inv.get("battery") or {}
            S.wire(cx, cy - 13, cx, cy - 16, "bat")
            S.switch_vertical(cx, cy - 19)
            S.wire(cx, cy - 22, cx, cy - 26, "bat")
            S.battery(cx, cy - 26)
            breaker_a = bt.get("breaker_a") or bt.get("fuse_a") or r["proposals"]["battery"].get("fuse_a")
            breaker_label = f"-Q{i + 1}.B " + ("integrat " if bt.get("breaker_integrated") else "")
            breaker_detail = f" A DC · {gv(n(bt.get('voltage')), ' V') or '[lipsă V]'}"
            if n(bt.get("breaker_poles")):
                breaker_detail += f" · {int(n(bt.get('breaker_poles')))}P"
            if n(bt.get("breaker_voltage_dc")):
                breaker_detail += f" · {gv(n(bt.get('breaker_voltage_dc')), ' Vdc')}"
            if n(bt.get("breaker_icu_ka")):
                breaker_detail += f" · Icu {gv(n(bt.get('breaker_icu_ka')), ' kA')}"
            S.val(cx + 6, cy - 17.2, breaker_label, breaker_a, breaker_detail, size=4.4, w=29)
            S.text(cx + 6, cy - 22.4, f"-G{i + 1} {bt.get('model') or '[model baterie lipsă]'}", 4.4, True, w=29)
            S.val(cx + 6, cy - 26.8, "Cablu ", bt.get("cable_section") or bt.get("section") or r["proposals"]["battery"].get("section"), " mm² DC", size=4.4, w=29)
            S.val(cx + 6, cy - 31.2, "I max ", bt.get("i_max"), " A", size=4.4, w=29)
        if (inv.get("backup") or {}).get("enabled"):
            b = inv["backup"]
            S.wire(cx + hh, cy - 10, 152, cy - 10); S.wire(152, cy - 10, 152, cy - 16); S.wire(152, cy - 16, 182, cy - 16)
            S.switch(187, cy - 16, "Q"); S.wire(192, cy - 16, 200, cy - 16)
            S.enclosure(176, cy - 24, 228, cy - 9, f"-TB{i + 1}  Tablou backup / EPS")
            S.val(202, cy - 16.8, "", b.get("breaker"), size=4.6, w=25)
            S.text(178, cy - 22.6, str(b.get("circuits") or "circuite EPS"), 4.2, color=GREY, w=48)
        # AC side
        ina = n(ac.get("breaker_a"))
        if ina:
            inv_in.append(ina)
        S.wire(cx + hh, cy + dd, 181, cy + dd)
        cy += dd
        S.tick(max(158, cx + hh + 12), cy, conductors if r["tri"] else "L+N+PE")
        S.text(cx + hh + 1, cy + 6.6, f"-W{i + 1}.AC  {ac.get('cable_type') or ''}".strip(), 4.6, True, w=28)
        S.val(cx + hh + 1, cy + 4.4, "", n(ac.get("section")), f" mm² {ac.get('material') or 'Cu'}" + (f", PE {gv(n(ac.get('pe_section')))}" if n(ac.get("pe_section")) else ""), size=4.4, w=28)
        S.val(cx + hh + 1, cy + 2.2, "L=", n(ac.get("length_m")), " m", size=4.4, w=28)
        S.enclosure(174, cy - 7, 230, cy + 13, f"-TFV  Tablou fotovoltaic (INV {i + 1})")
        S.switch(186, cy, "Q")
        S.wire(191, cy, 203, cy)
        S.text(182, cy + 6.4, f"-Q{i + 1}.1", 4.6, True)
        S.val(182, cy - 3.4, "C", ina, f" A {r['proposals']['ac']['poles']}" + (f" {gv(n(ac.get('icu_ka')), ' kA')}" if n(ac.get("icu_ka")) else ""), size=4.4, w=20)
        S.rcd(212, cy)
        S.wire(217, cy, BUS, cy)
        S.text(207, cy + 6.4, f"-F{i + 1}.1", 4.6, True)
        S.val(204, cy - 5.6, "", inv.get("rcd_type"), (f" {gv(n(inv.get('rcd_ma')), ' mA')}" if n(inv.get("rcd_ma")) else ""), size=4.4, w=25)
        S.node(BUS, cy)
    # Shared battery branch with separate DC breaker and visible technical data.
    for k, b in enumerate(shared):
        x = 134 + k * 30
        users = [i for i, inv in enumerate(invs) if inv.get("battery_mode") == "shared" and inv.get("shared_battery_id") == b.get("id")]
        for u in users:
            S.wire(126, cys[u] - 13, 126, y_shared + 10, "dc")
        if users:
            S.wire(126, y_shared + 10, x, y_shared + 10, "dc")
        S.wire(x, y_shared + 10, x, y_shared + 5, "dc")
        S.switch_vertical(x, y_shared + 2)
        S.wire(x, y_shared - 1, x, y_shared - 4, "dc")
        S.battery(x, y_shared - 4)
        S.text(x + 6, y_shared + 11, f"-G{len(invs) + k + 1} baterie comună", 4.5, True, w=38)
        S.val(x + 6, y_shared + 7, f"-Q{k + 1}.B ", b.get("breaker_a") or b.get("fuse_a") or battery_cable_proposal(b).get("fuse_a"),
              f" A DC · {gv(n(b.get('voltage')), ' V') or '[lipsă V]'}", size=4.2, w=38)
        S.text(x + 6, y_shared + 2.5, str(b.get("model") or "[model baterie lipsă]"), 4.2, w=38)
        S.val(x + 6, y_shared - 2, "I max ", b.get("i_max"), " A", size=4.2, w=38)
        S.val(x + 6, y_shared - 6.5, "Cablu ", b.get("cable_section") or b.get("section") or battery_cable_proposal(b).get("section"), " mm²", size=4.2, w=38)
    # busbar + TG
    if cys:
        ytop, ybot = max(cys), min(cys)
        S.lw(1.3); S.c.line(BUS, ytop + 5, BUS, ybot - 12); S.lw()
        y = ytop
        S.enclosure(238, ybot - 22, 300, ytop + 15, "-TG  Tablou general", "existent / de completat")
        S.text(BUS - 1.5, ytop + 6, "bară 0,4 kV", 4.2, anchor="r")
        S.wire(BUS, y, TGQ - 5, y); S.switch(TGQ, y, "Q"); S.wire(TGQ + 5, y, 352.5 + A, y)
        S.text(TGQ - 4, y + 6.4, "-Q0.TG", 4.6, True)
        S.val(TGQ - 4, y - 3.4, "", n(grid.get("tg_breaker_a")), f" A {poles}", size=4.4)
        S.spd(SPDX, y, y_pe)
        S.val(SPDX + 2.4, y - 6, "-FA AC ", grid.get("spd_ac"), size=4.4, w=16)
        yc = ybot - 10
        S.node(BUS, yc); S.wire(BUS, yc, 255, yc); S.switch(260, yc, "Q"); S.wire(265, yc, 272, yc)
        S.lw(0.3); S.c.line(272, yc, 270.6, yc + 1); S.c.line(272, yc, 270.6, yc - 1); S.lw()
        S.text(255, yc - 4, "circuite consumatori existenți", 4.2, color=GREY)
        S.text(240, ybot - 20.6, "Bară PE (TG)", 4.4, color=PEC)
        S.wire(BUS, ybot - 12, BUS, ybot - 18, "pe")
        x = 300
        if anti:
            S.enclosure(302, y - 9, 330, y + 15, "-TAI  Antiinsularizare")
            S.switch(312, y, "K")
            S.lw(0.35); S.c.rect(318, y + 4, 9, 5, stroke=1, fill=0); S.lw()
            S.text(322.5, y + 5.6, "PI", 5, True, anchor="c")
            S.wire(322.5, y + 4, 322.5, y + 2, "ctl"); S.wire(322.5, y + 2, 313, y + 2, "ctl")
            anti_breaker = grid.get("anti_breaker") or base["grid"].get("anti_breaker_proposal")
            anti_relay = grid.get("anti_relay") or "model conform ATR / OD"
            S.val(304, y - 4, "-K1 ", f"{anti_breaker} A (propus)" if anti_breaker and not grid.get("anti_breaker") else anti_breaker, size=4.2, w=25)
            S.val(304, y - 6.6, "-K2 releu ", anti_relay, size=4.2, w=25)
        # smart meter
        mx = 306 + A
        if grid.get("meter"):
            if grid.get("sm_ct_ratio"):
                S.ct(mx, y)
                S.wire(mx, y + 1.9, mx, y + 6, "ctl"); S.meter(mx, y + 10, "SM", False)
                S.text(mx + 2.6, y - 4.2, f"-T1 TC {grid.get('sm_ct_ratio')}", 4.4)
            else:
                S.meter(mx, y + 10, "SM", False); S.wire(mx, y + 6, mx, y, "ctl"); S.node(mx, y)
            S.text(mx, y + 15.6, "-P2 Smart meter", 4.6, True, anchor="c")
            S.text(mx, y + 18, str(grid.get("meter")), 4.4, anchor="c", w=30)
        # column
        S.tick(326 + A, y, conductors)
        S.text(318 + A, y + 6.6, "-W0 coloană BMP→TG", 4.6, True, w=26)
        S.val(318 + A, y + 4.4, "", grid.get("column_cable") or (gv(n(grid.get("column_section")), " mm²")), size=4.4, w=26)
        if n(grid.get("column_length")):
            S.text(318 + A, y + 2.2, f"L={n(grid.get('column_length')):g} m", 4.4)
        # BMP
        S.enclosure(346 + A, y - 10, 392 + A, y + 15, "-BMP  Bloc măsură și protecție", "proprietate OD")
        mx = 358 + A
        if grid.get("ct_ratio"):
            S.ct(mx - 6, y); S.wire(mx - 6, y + 1.9, mx - 6, y + 4, "ctl"); S.wire(mx - 6, y + 4, mx - 5.5, y + 4, "ctl")
            S.text(mx - 8, y - 4.4, f"TC {grid.get('ct_ratio')}", 4.2)
        S.meter(mx, y, "kWh")
        S.text(mx, y + 5.4, "-P1 contor bidirecțional", 4.4, True, anchor="c")
        S.wire(mx + 5.5, y, 374 + A, y)
        S.switch(379 + A, y, "Q")
        S.text(375 + A, y + 6.4, "-Q0", 4.6, True)
        S.val(375 + A, y - 3.4, "", n(grid.get("bmp_a")), f" A {poles}", size=4.4)
        S.wire(384 + A, y, 402 + A, y)
        S.transformer(407 + A, y)
        S.text(402 + A, y + 7, "Rețea OD 0,4 kV", 4.8, True)
        S.text(402 + A, y - 6.4, "3F+N 50 Hz" if tri else "1F+N 50 Hz", 4.4)
        op = client.get("operator") or rec.get("operator")
        S.val(346 + A, y - 13, "OD: ", (str(op).split("—")[0].strip() if op else None), size=4.4, w=70)
        S.val(346 + A, y - 15.4, "POD: ", client.get("pod") or rec.get("pod"), size=4.4, w=70)
        S.val(346 + A, y - 17.8, "Putere aprobată: ", n(grid.get("bransament_kw")), " kW", size=4.4, w=70)
        S.val(346 + A, y - 20.2, "Ik racord: ", n(grid.get("ik_ka")), " kA", size=4.4, w=70)
        # left PE collector & earthing
        S.wire(2, top - 2, 2, y_pe, "pe")
        S.wire(2, y_pe, 340, y_pe, "pe")
        S.wire(BUS, ybot - 18, BUS, y_pe, "pe")
        S.lw(1.1, PEC); S.c.line(300, y_pe, 318, y_pe); S.lw()
        S.text(300, y_pe + 1.4, "-XPE bară principală de împământare", 4.4, color=PEC)
        S.earth(340, y_pe)
        S.text(344, y_pe - 1.6, "-E1 Priză de pământ", 4.8, True)
        S.val(344, y_pe - 4.2, "R = ", n(grid.get("grounding_ohm") or rec.get("grounding_ohm")), " Ω (măsurat)", size=4.6)
        S.val(344, y_pe - 6.6, "Sistem: ", grid.get("earthing"), size=4.6)
        S.text(4, y_pe + 1.2, "PE / echipotențializare rame PV: " + (gv(n(grid.get("bond_section")), " mm² Cu") or "≥ 6 mm² Cu"), 4.4, color=PEC)


# ---------------------------------------------------------------- page frame
def frame(S, PW, PH, rec, client, settings, res, approval, sheet, sheets, fmt, demo):
    c = S.c
    L, B, R, T = 20, 10, PW - 10, PH - 10
    S.lw(0.5); c.rect(L, B, R - L, T - B, stroke=1, fill=0); S.lw()
    tbw, tbh = 180, 44
    x0, y0 = R - tbw, B
    get = lambda k: client.get(k) or rec.get(k)
    t = res["base"]["totals"]
    kwp = f"{t['kwp']:g} kWp" if t["kwp"] else "[kWp lipsă]"
    kw = f"{t['inverters_kw']:g} kW" if t["inverters_kw"] else "[kW lipsă]"
    loc = ", ".join(str(x) for x in [get("address"), get("locality"), ("jud. " + str(get("county"))) if get("county") else None] if x)
    st = approval.get("status")
    stat = {"approved": "APROBAT — validare internă înregistrată", "stale": "APROBARE ANULATĂ — configurația s-a modificat", "draft": "CIORNĂ — neverificat / neaprobat"}.get(st, "CIORNĂ")
    if demo:
        stat = "EXEMPLU DEMONSTRATIV — nu este document de execuție"
    rows = [
        [("", f"{settings.get('company') or 'DNS HOSTESS S.R.L.'}" + (f" · Atestat ANRE {settings.get('anre_type') or ''} nr. {settings.get('anre_attest')}" if settings.get("anre_attest") else " · Atestat ANRE [lipsă]"), 180, True)],
        [("Beneficiar", get("name"), 110, False), ("Nr. proiect", get("project_no"), 70, False)],
        [("Adresă", loc or None, 110, False), ("Planșa", f"E-0{sheet} ({sheet}/{sheets})", 70, False)],
        [("Titlu", f"Schemă electrică monofilară — CEF {kwp} / {kw}" if sheet == 1 else "Tabel cabluri, aparate și verificări", 110, True), ("Format / scara", f"{fmt} orizontal · fără scară", 70, False)],
        [("Reprezentant firmă", settings.get("rep"), 110, False), ("Data", docgen.ro_date(get("doc_date") or get("date")) or datetime.now().strftime("%d.%m.%Y"), 70, False)],
        [("Revizie", str((rec.get("sld") or {}).get("revision") or 0), 180, False)],
        [("Stare", stat, 180, True)],
    ]
    rh = tbh / len(rows)
    S.lw(0.4); c.rect(x0, y0, tbw, tbh, stroke=1, fill=0)
    for ri, row in enumerate(rows):
        yy = y0 + tbh - (ri + 1) * rh
        S.lw(0.2); c.line(x0, yy, x0 + tbw, yy)
        xx = x0
        for lbl, val, w, bold in row:
            if xx > x0:
                c.line(xx, yy, xx, yy + rh)
            if lbl:
                S.text(xx + 1, yy + rh - 2.2, lbl, 4.4, color=GREY)
            color = RED if (val in (None, "") or "lipsă" in str(val) or (ri == 6 and st != "approved")) else INK
            S.text(xx + (16 if lbl else 1.5), yy + 1.6, val if val not in (None, "") else "[lipsă]", 6.2, bold, color, w=w - (17 if lbl else 3))
            xx += w
    # legend
    lw_ = x0 - L - 4
    if sheet == 1 and lw_ > 70:
        legend(S, L + 2, B, lw_, tbh)
    return (L + 2, B + tbh + 3, R - 2, T - 2)


def legend(S, x, y, w, h):
    c = S.c
    S.lw(0.3); c.rect(x, y, w, h, stroke=1, fill=0); S.lw()
    S.text(x + 2, y + h - 3.4, "LEGENDĂ — simboluri SR EN 60617 (IEC 60617), coduri SR EN 81346-2", 5.2, True, w=w - 4)
    items = [("pv", "Generator fotovoltaic (string)"), ("inv", "Invertor c.c./c.a."), ("fuse", "Siguranță fuzibilă gPV"),
             ("LS", "Separator de sarcină (DC)"), ("Q", "Întreruptor automat"), ("rcd", "Dispozitiv diferențial (DDR)"),
             ("K", "Contactor / element de decuplare"), ("spd", "Descărcător supratensiune (SPD)"), ("kwh", "Contor de energie"),
             ("ct", "Transformator de curent (TC)"), ("bat", "Baterie de acumulatori"), ("earth", "Priză de pământ"),
             ("pe", "Conductor PE / echipotențializare"), ("enc", "Tablou / carcasă")]
    cols = 3 if w > 150 else 2
    cw = (w - 4) / cols
    per = -(-len(items) // cols)
    rh = (h - 9) / per
    for k, (kind, lbl) in enumerate(items):
        col, row = k // per, k % per
        sx, sy = x + 3 + col * cw, y + h - 8 - row * rh - rh / 2 + 1
        c.saveState(); c.translate(sx + 6, sy); c.scale(0.55, 0.55)
        if kind == "pv": S.pv(-8, 0)
        elif kind == "inv": S.inverter(0, 0, 5)
        elif kind == "fuse": S.wire(-7, 0, 7, 0); S.fuse(0, 0)
        elif kind in ("LS", "Q", "K"): S.switch(0, 0, kind)
        elif kind == "rcd": S.rcd(3, 0)
        elif kind == "spd": S.lw(0.3); c.rect(-1.3, -3, 2.6, 6, stroke=1, fill=0); c.line(-1.3, -2, 1.3, 2)
        elif kind == "kwh": S.meter(0, 0)
        elif kind == "ct": S.wire(-6, 0, 6, 0); S.ct(0, 0)
        elif kind == "bat": S.battery(0, 2)
        elif kind == "earth": S.earth(0, 3)
        elif kind == "pe": S.wire(-8, 0, 8, 0, "pe")
        elif kind == "enc": S.enclosure(-8, -3, 8, 3, "")
        c.restoreState()
        S.text(sx + 14, sy - 0.8, lbl, 4.8, w=cw - 15)


def watermark(S, PW, PH, label):
    c = S.c
    c.saveState(); c.setFillColor(colors.HexColor("#c0392b")); c.setFillAlpha(0.10)
    c.translate(PW / 2, PH / 2 + 10); c.rotate(18)
    c.setFont("LSB", 26 * (PW / 297)); c.drawCentredString(0, 0, label)
    c.restoreState()


def table_page(S, area, res, rec):
    c = S.c
    x1, y1, x2, y2 = area
    W = x2 - x1
    P = lambda t, b=False: Paragraph(escape(str(t)) if t not in (None, "") else "<font color='#c0392b'>[lipsă]</font>", CELLB if b else CELL)
    blocks = []
    hdr = ["Cod", "De la → la", "Tip cablu", "Conductoare", "S (mm²)", "Mat.", "L (m)", "Ib (A)", "Iz (A)", "ΔU (%)", "Pierderi (W)", "PE (mm²)"]
    rows = [[P(h, True) for h in hdr]] + [[P(x["id"]), P(f"{x['from']} → {x['to']}"), P(x.get("type")), P(x.get("cores")), P(gv(x.get("section"))), P(x.get("material")),
                                           P(gv(x.get("length"))), P(gv(x.get("ib"))), P(gv(x.get("iz"))), P(gv(x.get("du")) or "0"), P(gv(x.get("loss")) or "—"), P(gv(x.get("pe")) or "—")] for x in res["cables"]]
    blocks.append(("LISTA CABLURILOR", rows, [14, 40, 28, 26, 14, 10, 12, 12, 12, 12, 16, 14]))
    vr = [[P(h, True) for h in ["Grup", "Mărime verificată", "Valoare", "Sursa", "Formulă / criteriu", "Rezultat"]]]
    for it in res["items"]:
        if it["ok"] is None and it["source"] != "de confirmat":
            continue
        okt = "conform" if it["ok"] else ("NECONFORM" if it["ok"] is False else "de confirmat")
        vr.append([P(it["group"]), P(it["label"]), P(it["value"]), P(it["source"]), P((it["formula"] + (" · " + it["note"] if it["note"] else "")).strip(" ·") or "—"), P(okt, it["ok"] is False)])
    blocks.append(("VERIFICĂRI ȘI APARATE DE PROTECȚIE", vr, [24, 52, 30, 18, 70, 18]))
    y = y2 - 4
    for title, rows, ws in blocks:
        S.text(x1 + 2, y, title, 7, True)
        y -= 2
        scale = (W - 4) / sum(ws)
        t = Table(rows, colWidths=[w * scale * mm for w in ws], repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#999999")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2)]))
        c.saveState(); c.scale(1 / mm, 1 / mm)
        _, h = t.wrapOn(c, (W - 4) * mm, (y - y1) * mm)
        avail = (y - y1) * mm
        if h > avail:
            parts = t.split((W - 4) * mm, avail)
            t = parts[0] if parts else t
            _, h = t.wrapOn(c, (W - 4) * mm, avail)
        t.drawOn(c, (x1 + 2) * mm, y * mm - h)
        c.restoreState()
        y -= h / mm + 6
    if res["missing"]:
        p = Paragraph("<font color='#c0392b'><b>DATE LIPSĂ (schema nu poate fi emisă ca document final):</b> " + escape("; ".join(m["label"] for m in res["missing"])) + "</font>", CELL)
        c.saveState(); c.scale(1 / mm, 1 / mm)
        _, h = p.wrapOn(c, (W - 190) * mm if y < y1 + 50 else (W - 4) * mm, 60 * mm)
        p.drawOn(c, (x1 + 2) * mm, max(y * mm - h, (y1 + 2) * mm))
        c.restoreState()


def report(rec, client, settings, res, approval) -> bytes:
    from reportlab.platypus import SimpleDocTemplate, Spacer
    from reportlab.lib.pagesizes import A4 as P4
    St = docgen.S
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=P4, leftMargin=16 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title="Raport de calcul — dimensionare CEF")
    get = lambda k: client.get(k) or rec.get(k)
    Pp = lambda t, st="p": Paragraph(t, St[st])
    C_ = lambda t, b=False: Paragraph(escape(str(t)) if t not in (None, "") else "<font color='#c0392b'>[lipsă]</font>", CELLB if b else CELL)
    def tbl(rows, ws):
        t = Table(rows, colWidths=[w * mm for w in ws], repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#999999")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t
    t = res["base"]["totals"]
    st = approval.get("status")
    out = [Pp(f"<b>{escape(settings.get('company') or 'DNS HOSTESS S.R.L.')}</b>", "small"), Spacer(1, 4),
           Pp("RAPORT DE CALCUL ȘI VALIDARE — DIMENSIONARE TEHNICĂ CEF", "h"),
           Pp(f"Beneficiar: <b>{escape(str(get('name') or '[lipsă]'))}</b> · Proiect nr. {escape(str(get('project_no') or '[lipsă]'))} · "
              f"Putere instalată DC {t['kwp']:g} kWp · AC {t['inverters_kw']:g} kW" if t["kwp"] else "Putere instalată: [date lipsă]"),
           Pp("<b>Statut:</b> " + {"approved": "validare internă înregistrată",
                                    "stale": "Aprobarea anterioară a fost anulată deoarece configurația s-a modificat."}.get(st, "PROPUNERE VERIFICABILĂ — neaprobată. Dimensionarea automată nu constituie aprobarea proiectului.")),
           Spacer(1, 4), Pp("1. Surse ale valorilor", "b"),
           Pp("<b>introdus</b> — valoare completată de utilizator; <b>catalog</b> — preluată din fișa tehnică a producătorului (catalog echipamente); "
              "<b>calculat</b> — rezultat al formulelor de mai jos; <b>de confirmat</b> — trebuie confirmată de proiectant / din documentația producătorului sau a OD."),
           Pp("2. Ipoteze de calcul", "b")]
    for h in [f"Temperatura minimă de calcul a celulelor: {res['base']['tmin']:g}°C; temperatura celulei la cald: 70°C.",
              "Curenți admisibili conform HD 60364-5-52 (Cu/PVC 70°C, 30°C ambiant); Al = 0,78·Cu; factor de corecție k introdus pentru grupare/temperatură.",
              "Rezistivitate ρ(Cu) = 0,0225 Ω·mm²/m, ρ(Al) = 0,036 Ω·mm²/m (la temperatura de funcționare); cosφ = 0,95.",
              "Cădere de tensiune admisă: DC ≤ 1 % (recomandat), AC ≤ 3 % (I7-2011).",
              "Valorile de măsurare (priză de pământ, izolație) NU sunt estimate — se preiau exclusiv din buletinele de măsurare."]:
        out.append(Pp("• " + escape(h), "li"))
    out.append(Pp("3. Date de intrare, rezultate și verificări", "b"))
    rows = [[C_(h, True) for h in ["Grup", "Mărime", "Valoare", "Sursa", "Formulă / criteriu", "Rezultat"]]]
    for it in res["items"]:
        okt = "conform" if it["ok"] else ("NECONFORM" if it["ok"] is False else ("de confirmat" if it["source"] == "de confirmat" else "—"))
        rows.append([C_(it["group"]), C_(it["label"]), C_(it["value"]), C_(it["source"]), C_((it["formula"] + (" · " + it["note"] if it["note"] else "")).strip(" ·") or "—"), C_(okt, it["ok"] is False)])
    out.append(tbl(rows, [20, 42, 24, 16, 64, 16]))
    out.append(Pp("4. Lista cablurilor", "b"))
    rows = [[C_(h, True) for h in ["Cod", "Traseu", "Tip", "S", "L (m)", "Ib (A)", "Iz (A)", "ΔU %", "P (W)"]]]
    for x in res["cables"]:
        rows.append([C_(x["id"]), C_(f"{x['from']} → {x['to']}"), C_(x.get("type")), C_(gv(x.get("section"), " mm²")), C_(gv(x.get("length"))),
                     C_(gv(x.get("ib"))), C_(gv(x.get("iz"))), C_(gv(x.get("du")) or "0"), C_(gv(x.get("loss")) or "—")])
    out.append(tbl(rows, [14, 40, 26, 16, 14, 14, 14, 14, 30]))
    out.append(Pp("5. Erori, avertizări și date lipsă", "b"))
    for e in res["errors"]:
        out.append(Pp(f"<font color='#b03a2e'><b>EROARE:</b> {escape(e)}</font>", "li"))
    for w in res["warnings"]:
        out.append(Pp(f"<font color='#b9770e'><b>ATENȚIE:</b> {escape(w)}</font>", "li"))
    for m in res["missing"]:
        out.append(Pp(f"<font color='#b03a2e'><b>LIPSĂ:</b> {escape(m['label'])}</font>", "li"))
    if not (res["errors"] or res["warnings"] or res["missing"]):
        out.append(Pp("Nu au fost identificate erori sau date lipsă."))
    out.append(Pp("6. Standarde și surse tehnice", "b"))
    out.append(tbl([[C_("Referință", True), C_("Domeniu", True)]] + [[C_(a), C_(b)] for a, b in res["standards"]] +
                   [[C_("Fișe tehnice / manuale producători"), C_("Limitele invertorului (Udc max, MPPT, Imax), panourilor (Voc, Vmp, Isc, βVoc), bateriei (Imax), cerința privind tipul DDR")]], [60, 122]))
    out.append(Spacer(1, 8))
    out.append(Pp("Rezultatele sunt o propunere de dimensionare ce trebuie confirmată de reprezentantul firmei executante înainte de utilizarea oficială.", "small"))
    doc.build(out)
    return buf.getvalue()


def drawing_header(S, PW, PH, rec, client, settings, res, approval):
    c = S.c
    company = settings.get("company") or "DNS HOSTESS S.R.L."
    totals = res["base"]["totals"]
    summary = f"CEF {totals['kwp']:g} kWp · {totals['inverters_kw']:g} kW AC" if totals["kwp"] else "CEF · date tehnice de verificat"
    title = "SCHEMĂ MONOFILARĂ"
    y = PH - 17
    S.text(22, y + 1.2, company, 7.2, True)
    S.text(22, y - 2.2, "INSTALAȚII FOTOVOLTAICE", 4.2, color=GREY)
    S.text(PW / 2, y, title, 10, True, anchor="c")
    S.text(PW / 2, y - 4.2, summary, 5, color=GREY, anchor="c")
    label = "CIORNĂ" if approval.get("status") != "approved" else "VERIFICAT INTERN"
    badge_w = 38
    bx = PW - 12 - badge_w
    S.lw(0.35, RED if label == "CIORNĂ" else BATTERY_GREEN)
    c.roundRect(bx, y - 2, badge_w, 7, 1.5, stroke=1, fill=0)
    S.text(bx + badge_w / 2, y + 0.3, label, 4.8, True, RED if label == "CIORNĂ" else BATTERY_GREEN, "c")
    S.lw(0.25, GREY)
    c.line(22, PH - 24, PW - 12, PH - 24)
    return PH - 27


def drawing_grid(S, x1, y1, x2, y2):
    c = S.c
    top = y2
    c.saveState()
    S.lw(0.4, GREY)
    c.rect(x1, y1, x2 - x1, top - y1, stroke=1, fill=0)
    cols, rows = 7, 4
    faint = colors.HexColor("#e7ebf0")
    for i in range(1, cols):
        x = x1 + (x2 - x1) * i / cols
        S.lw(0.15, faint); c.line(x, y1, x, top)
    for j in range(1, rows):
        y = y1 + (top - y1) * j / rows
        S.lw(0.15, faint); c.line(x1, y, x2, y)
    S.lw(0.25, GREY)
    for i, label in enumerate("ABCDEFG"):
        x = x1 + (x2 - x1) * (i + 0.5) / cols
        S.text(x, top + 1.2, label, 3.8, color=GREY, anchor="c")
        S.text(x, y1 - 3.6, label, 3.8, color=GREY, anchor="c")
    for j in range(rows):
        y = top - (top - y1) * (j + 0.5) / rows
        S.text(x1 - 2.1, y, str(j + 1), 3.8, color=GREY, anchor="r")
        S.text(x2 + 2.1, y, str(j + 1), 3.8, color=GREY, anchor="l")
    c.restoreState()


def render(rec, client, settings, res, approval, fmt="auto", demo=False) -> bytes:
    fmt = res["format"] if fmt not in ("A3", "A4") else fmt
    PW, PH = [x / mm for x in landscape(A3 if fmt == "A3" else A4)]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PW * mm, PH * mm))
    c.setTitle(f"Schemă monofilară — {client.get('name') or rec.get('client_name') or ''}")
    c.setAuthor(settings.get("company") or "DNS HOSTESS S.R.L.")
    c.scale(mm, mm)
    S = Sheet(c)
    area = frame(S, PW, PH, rec, client, settings, res, approval, 1, 2, fmt, demo)
    x1, y1, x2, _ = area
    plot_y2 = drawing_header(S, PW, PH, rec, client, settings, res, approval)
    drawing_grid(S, x1, y1, x2, plot_y2)
    W, H, draw = diagram(S, rec, res, client)
    s = min((x2 - x1 - 8) / W, (plot_y2 - y1 - 8) / H, 1.6)
    c.saveState(); c.translate(x1 + 4 + ((x2 - x1 - 8) - W * s) / 2, y1 + 4 + ((plot_y2 - y1 - 8) - H * s) / 2); c.scale(s, s)
    draw()
    c.restoreState()
    S.text(x1 + 2, y1 + 2, "DC fotovoltaic — portocaliu · stocare — verde · PE — verde întrerupt · valorile [lipsă] rămân de confirmat.", 4.1, color=GREY)
    if demo:
        watermark(S, PW, PH, "EXEMPLU DEMONSTRATIV")
    elif rec.get("is_test"):
        watermark(S, PW, PH, "DOSAR DE TEST — NU ESTE OFICIAL")
    elif approval.get("status") != "approved":
        watermark(S, PW, PH, "CIORNĂ — NEVERIFICAT" if approval.get("status") != "stale" else "APROBARE ANULATĂ")
    c.showPage()
    c.scale(mm, mm)
    S2 = Sheet(c)
    area = frame(S2, PW, PH, rec, client, settings, res, approval, 2, 2, fmt, demo)
    table_page(S2, area, res, rec)
    if approval.get("status") != "approved" or demo:
        watermark(S2, PW, PH, "EXEMPLU DEMONSTRATIV" if demo else "CIORNĂ — NEVERIFICAT")
    c.showPage()
    c.save()
    return buf.getvalue()


def protections(rec, res):
    cef = rec.get("cef") or {}
    grid = cef.get("grid") or {}
    base = res["base"]
    tri = base["grid"]["tri"]
    out = []
    for i, inv in enumerate(cef.get("inverters") or []):
        r = base["inverters"][i]
        ac, dc, bt = inv.get("ac") or {}, inv.get("dc") or {}, inv.get("battery") or {}
        if r["strings"]:
            out.append((f"-Q{i + 1}.D", "Separator de sarcină DC (DC-PV2)", dc.get("switch"), f"-TDC{i + 1}"))
            out.append((f"-FA{i + 1}.DC", "Descărcător SPD DC tip 2", gv(n(dc.get("spd_ucpv")), " V Ucpv"), f"-TDC{i + 1}"))
            if r["proposals"]["dc"]["fuse"]:
                out.append((f"-F{i + 1}.S", "Siguranțe gPV pe stringuri", gv(n(dc.get("fuse_a")), " A gPV"), f"-TDC{i + 1}"))
        out.append((f"-Q{i + 1}.1", "Întreruptor automat AC invertor", (f"C{gv(n(ac.get('breaker_a')))} A {r['proposals']['ac']['poles']}" + (f", Icu {gv(n(ac.get('icu_ka')))} kA" if n(ac.get("icu_ka")) else "")) if n(ac.get("breaker_a")) else None, "-TFV"))
        out.append((f"-F{i + 1}.1", "Dispozitiv diferențial (DDR)", (f"{inv.get('rcd_type')} {gv(n(inv.get('rcd_ma')), ' mA') or ''}".strip()) if inv.get("rcd_type") else None, "-TFV"))
        if inv.get("battery_mode") == "own":
            out.append((f"-Q{i + 1}.B", "Întreruptor DC baterie", f"{gv(n(bt.get('breaker_a') or bt.get('fuse_a') or r['proposals']['battery'].get('fuse_a')), ' A DC') or '[lipsă] A DC'} · {gv(n(bt.get('voltage')), ' V') or '[lipsă V]'} · cablu {gv(n(bt.get('cable_section') or bt.get('section') or r['proposals']['battery'].get('section')), ' mm²') or '[lipsă]'}", f"-G{i + 1}"))
        if (inv.get("backup") or {}).get("enabled"):
            out.append((f"-Q{i + 1}.EPS", "Întreruptor circuit backup / EPS", inv["backup"].get("breaker"), f"-TB{i + 1}"))
    for k, battery in enumerate(cef.get("shared_batteries") or []):
        rating = battery.get("breaker_a") or battery.get("fuse_a") or battery_cable_proposal(battery).get("fuse_a")
        value = f"{rating if rating not in (None, '') else '[lipsă]'} A DC · {gv(n(battery.get('voltage')), ' V') or '[lipsă V]'} · cablu {gv(n(battery.get('cable_section') or battery.get('section') or battery_cable_proposal(battery).get('section')), ' mm²') or '[lipsă]'}"
        out.append((f"-Q{len(cef.get('inverters') or []) + k + 1}.B", "Întreruptor DC baterie comună", value, f"-GC{k + 1}"))
    out.append(("-Q0.TG", "Întreruptor general TG", gv(n(grid.get("tg_breaker_a")), " A " + ("4P" if tri else "2P")), "-TG"))
    out.append(("-FA AC", "Descărcător SPD AC", grid.get("spd_ac"), "-TG"))
    if base["grid"]["anti"]:
        anti_breaker = grid.get("anti_breaker") or base["grid"].get("anti_breaker_proposal")
        breaker_value = (f"{anti_breaker} A (propus)" if anti_breaker and not grid.get("anti_breaker") else f"{anti_breaker} A" if anti_breaker else "")
        anti_relay = grid.get("anti_relay") or "model conform ATR / OD"
        out.append(("-K1/-K2", "Întreruptor motorizat cu bobină + releu protecție interfață", " / ".join(x for x in [breaker_value, anti_relay] if x) or None, "-TAI"))
    out.append(("-Q0", "Întreruptor BMP (OD)", gv(n(grid.get("bmp_a")), " A " + ("4P" if tri else "2P")), "-BMP"))
    return out


def sheet_data(rec, client, settings, res, approval):
    cef = rec.get("cef") or {}
    grid = cef.get("grid") or {}
    base = res["base"]
    t = base["totals"]
    get = lambda k: client.get(k) or rec.get(k)
    loc = ", ".join(str(x) for x in [get("address"), get("locality"), ("jud. " + str(get("county"))) if get("county") else None] if x)
    st = approval.get("status")
    status = {"approved": "Configurație verificată și aprobată.", "stale": "Aprobarea a fost anulată — configurația s-a modificat."}.get(st, "CIORNĂ — configurație neaprobată.")
    if rec.get("is_test"):
        status = "DOSAR DE TEST — date fictive, nu este document oficial. " + status
    sec = [("1. Date generale", ["Câmp", "Valoare"], [
        ["Beneficiar", get("name")], ["Loc de producere / consum", loc or None], ["POD", get("pod")], ["Operator de distribuție", get("operator")],
        ["Număr proiect", get("project_no")],
        ["Branșament", f"{grid.get('supply')}, putere aprobată {gv(n(grid.get('bransament_kw')), ' kW') or '[lipsă]'}" if grid.get("supply") else None],
        ["Putere instalată DC", gv(t["kwp"], " kWp")], ["Putere invertoare AC (nominal / maxim)", f"{t['inverters_kw']:g} / {t['inverters_kw_max']:g} kW" if t["inverters_kw"] else None],
        ["Putere maximă evacuată", gv(t["export_kw"], " kW")], ["Capacitate stocare", gv(t["storage_kwh"], " kWh") or "fără stocare"],
        ["Sistem de legare la pământ", grid.get("earthing")], ["Ik la punctul de racord", gv(n(grid.get("ik_ka")), " kA")],
        ["Priză de pământ (măsurat / admis)", f"{gv(n(grid.get('grounding_ohm') or rec.get('grounding_ohm')), ' Ω') or '[nemăsurat]'} / {gv(n(grid.get('grounding_limit') or rec.get('grounding_limit')), ' Ω') or '[nestabilit]'}"]], [70, 112])]
    eq = []
    for i, inv in enumerate(cef.get("inverters") or []):
        r = base["inverters"][i]
        eq.append([f"-U{i + 1}", f"Invertor {inv.get('type') or ''}".strip(), inv.get("brand_model"),
                   f"Pn {gv(n(inv.get('p_nom_kw')), ' kW') or '—'} · Pmax {gv(n(inv.get('p_max_kw')), ' kW') or '—'} · {'3F' if r['tri'] else '1F'} · Udc max {gv(n(inv.get('vdc_max')), ' V') or '—'} · MPPT {gv(n(inv.get('mppt_min'))) or '—'}–{gv(n(inv.get('mppt_max')), ' V') or '—'} × {gv(n(inv.get('mppt_count'))) or '—'}", "1"])
        if r["strings"]:
            eq.append([f"-PV{i + 1}", "Module fotovoltaice", inv.get("panel_model"),
                       f"{gv(n(inv.get('panel_w')), ' W') or '—'} · Voc {gv(n(inv.get('panel_voc')), ' V') or '—'} · Isc {gv(n(inv.get('panel_isc')), ' A') or '—'} · stringuri: " + " + ".join(f"{s['panels']} (MPPT{s['mppt']})" for s in r["strings"]),
                       str(sum(s["panels"] for s in r["strings"]))])
        if inv.get("battery_mode") == "own":
            bt = inv.get("battery") or {}
            eq.append([f"-G{i + 1}", "Baterie", bt.get("model"), f"{gv(r['battery_kwh'], ' kWh') or '—'} · {gv(n(bt.get('voltage')), ' V') or '—'} · cuplare {bt.get('coupling') or 'DC'} · Imax {gv(n(bt.get('i_max')), ' A') or '—'} · Q DC {gv(n(bt.get('breaker_a') or bt.get('fuse_a') or r['proposals']['battery'].get('fuse_a')), ' A') or '[lipsă]'} · cablu {gv(n(bt.get('cable_section') or bt.get('section') or r['proposals']['battery'].get('section')), ' mm²') or '[lipsă]'}", str(int(n(bt.get("modules"), 1)) or 1)])
    for k, b in enumerate(cef.get("shared_batteries") or []):
        eq.append([f"-GC{k + 1}", "Baterie comună", b.get("model"), f"{gv(n(b.get('kwh')), ' kWh/modul') or '—'} · {gv(n(b.get('voltage')), ' V') or '—'} · Imax {gv(n(b.get('i_max')), ' A') or '—'} · Q DC {gv(n(b.get('breaker_a') or b.get('fuse_a')), ' A') or '[lipsă]'} · cablu {gv(n(b.get('cable_section') or b.get('section')), ' mm²') or '[lipsă]'}", str(int(n(b.get("modules"), 1)) or 1)])
    if grid.get("meter"):
        eq.append(["-P2", "Smart meter", grid.get("meter"), f"TC {grid.get('sm_ct_ratio')}" if grid.get("sm_ct_ratio") else "conectare directă", "1"])
    eq.append(["-P1", "Contor bidirecțional OD", "proprietate OD", f"măsură prin TC {grid.get('ct_ratio')}" if grid.get("ct_ratio") else "măsură directă", "1"])
    sec.append(("2. Lista echipamentelor", ["Cod", "Echipament", "Marcă / model", "Caracteristici", "Cant."], eq, [16, 34, 46, 72, 14]))
    cb = [[x["id"], f"{x['from']} → {x['to']}", x.get("type"), x.get("cores"), f"{gv(x.get('section'))} mm² {x.get('material') or ''}" + (f", PE {gv(x.get('pe'))}" if x.get("pe") else ""),
           gv(x.get("length")), f"{gv(x.get('ib')) or '—'} / {gv(x.get('iz')) or '—'}", gv(x.get("du")) or "0"] for x in res["cables"]]
    sec.append(("3. Lista cablurilor", ["Cod", "Traseu", "Tip", "Conductoare", "Secțiune", "L (m)", "Ib / Iz (A)", "ΔU %"], cb, [14, 36, 24, 28, 30, 14, 22, 14]))
    sec.append(("4. Aparate de protecție", ["Cod", "Aparat", "Valori nominale", "Amplasare"], [list(p) for p in protections(rec, res)], [22, 70, 60, 30]))
    issues = [f"LIPSĂ: {m['label']}" for m in res["missing"]] + [f"EROARE: {e}" for e in res["errors"]]
    aps = [a for a in (approval.get("approvals") or {}).values() if a.get("valid")]
    appr = "; ".join(f"{a['name']} ({a['role_label']}, {a.get('auth') or ''}), {a['at'][:10]}" for a in aps) if aps else "neaprobat"
    return {"company": settings.get("company") or "DNS HOSTESS S.R.L.", "status": status, "sections": sec, "issues": issues, "approved_by": ""}


TS_TITLE = "FIȘĂ TEHNICĂ A INSTALAȚIEI DE PRODUCERE — ECHIPAMENTE, CABLURI ȘI PROTECȚII"
TS_NOTE = "Valorile provin din aceeași configurație ca schema monofilară și raportul de calcul (sursă unică de date). "


def tech_sheet(rec, client, settings, res, approval) -> bytes:
    from reportlab.platypus import SimpleDocTemplate, Spacer
    from reportlab.lib.pagesizes import A4 as P4
    St = docgen.S
    D = sheet_data(rec, client, settings, res, approval)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=P4, leftMargin=16 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm, title="Fișă tehnică instalație")
    Pp = lambda x, st="p": Paragraph(x, St[st])
    C_ = lambda x, b=False: Paragraph(escape(str(x)) if x not in (None, "") else "<font color='#c0392b'>[lipsă]</font>", CELLB if b else CELL)
    out = [Pp(f"<b>{escape(D['company'])}</b>", "small"), Spacer(1, 4), Pp(TS_TITLE, "h"), Pp(escape(TS_NOTE + D["status"]), "small")]
    for title, head, rows, ws in D["sections"]:
        tb = Table([[C_(h, True) for h in head]] + [[C_(c) for c in r] for r in rows], colWidths=[w * mm for w in ws], repeatRows=1)
        tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#999999")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        out += [Pp(title, "b"), tb]
    if D["issues"]:
        out.append(Pp("5. Date lipsă / neconformități", "b"))
        out += [Pp(f"<font color='#b03a2e'>{escape(x)}</font>", "li") for x in D["issues"]]
    out += [Spacer(1, 8), Pp("Document tehnic generat pentru semnarea reprezentantului firmei executante.", "small")]
    doc.build(out)
    return buf.getvalue()


def tech_sheet_docx(rec, client, settings, res, approval) -> bytes:
    from docx import Document
    from docx.shared import Pt, Mm, RGBColor
    D = sheet_data(rec, client, settings, res, approval)
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Mm(210), Mm(297)
    s.left_margin = s.right_margin = Mm(16); s.top_margin = s.bottom_margin = Mm(14)
    d.styles["Normal"].font.name = "Arial"; d.styles["Normal"].font.size = Pt(9)
    d.add_paragraph().add_run(D["company"]).bold = True
    h = d.add_paragraph(); r = h.add_run(TS_TITLE); r.bold = True; r.font.size = Pt(12)
    d.add_paragraph(TS_NOTE + D["status"]).runs[0].font.size = Pt(8)
    for title, head, rows, ws in D["sections"]:
        d.add_paragraph().add_run(title).bold = True
        tb = d.add_table(rows=1, cols=len(head)); tb.style = "Table Grid"
        for j, x in enumerate(head):
            tb.rows[0].cells[j].text = x
            tb.rows[0].cells[j].paragraphs[0].runs[0].bold = True
        for row in rows:
            cells = tb.add_row().cells
            for j, x in enumerate(row):
                cells[j].text = str(x) if x not in (None, "") else "[lipsă]"
                if x in (None, ""):
                    cells[j].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
        for row in tb.rows:
            for j, w in enumerate(ws):
                row.cells[j].width = Mm(w)
    if D["issues"]:
        d.add_paragraph().add_run("5. Date lipsă / neconformități").bold = True
        for x in D["issues"]:
            d.add_paragraph(x).runs[0].font.color.rgb = RGBColor(0xB0, 0x3A, 0x2E)
    d.add_paragraph("Document tehnic generat pentru semnarea reprezentantului firmei executante.")
    o = io.BytesIO(); d.save(o)
    return o.getvalue()


def snapshot(rec, res):
    v = {f"{it['group']} · {it['label']}": str(it["value"]) if it["value"] is not None else "—" for it in res["items"]}
    for x in res["cables"]:
        v[f"Cablu {x['id']}"] = f"{x.get('type') or ''} {gv(x.get('section'))} mm² {x.get('material') or ''}, L={gv(x.get('length')) or '—'} m, ΔU {gv(x.get('du')) or 0}%".strip()
    for code, name, val, loc in protections(rec, res):
        v[f"Protecție {code} {name}"] = str(val or "—")
    return v
