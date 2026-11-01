from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Flowable, Spacer, Paragraph
import cef as C

NAVY = colors.HexColor("#0b1f3a")
RED = colors.HexColor("#c0392b")
GREEN = colors.HexColor("#1e8449")
FILLS = {"grid": "#e8eef8", "bmp": "#f3f7ff", "anti": "#fdeff0", "tg": "#f3f7ff", "inv": "#eef4ff",
         "dc": "#fff4f2", "pv": "#fffbe8", "bat": "#effaf2", "bk": "#f5f0ff"}


def v(x, unit="", d="—"):
    return f"{x:g}{unit}" if isinstance(x, (int, float)) and x else (f"{x}{unit}" if x not in (None, "", 0) else d)


class CefDrawing(Flowable):
    def __init__(self, rec, res):
        super().__init__()
        self.rec, self.res = rec, res
        self.cef = rec.get("cef") or {}
        self.width, self.height = 273 * mm, 158 * mm

    def fit(self, s, w, font, size):
        c = self.canv
        s = str(s)
        while s and c.stringWidth(s, font, size) > w:
            s = s[:-2]
        return s

    def box(self, x, y, w, h, title, lines, kind, dashed=False):
        c = self.canv
        c.setFillColor(colors.HexColor(FILLS[kind])); c.setStrokeColor(NAVY); c.setLineWidth(0.8)
        if dashed:
            c.setDash(3, 2)
        c.roundRect(x, y, w, h, 3, stroke=1, fill=1); c.setDash()
        fs = 7.6 if w > 45 * mm else 6.6
        c.setFillColor(NAVY); c.setFont("LSB", fs); c.drawString(x + 3, y + h - fs - 2, self.fit(title, w - 6, "LSB", fs))
        c.setFillColor(colors.black); c.setFont("LS", fs - 1)
        for i, ln in enumerate(lines):
            yy = y + h - fs - 11 - i * (fs + 1.2)
            if yy < y + 2:
                break
            c.drawString(x + 3, yy, self.fit(ln, w - 6, "LS", fs - 1))

    def line(self, x1, y1, x2, y2, dc=False, color=None, label=None):
        c = self.canv
        c.setStrokeColor(color or (RED if dc else NAVY)); c.setLineWidth(1.2)
        if dc:
            c.setDash(3, 2)
        c.line(x1, y1, x2, y2); c.setDash()
        if label:
            c.setFont("LS", 5.8); c.setFillColor(colors.HexColor("#334"))
            c.drawString(min(x1, x2) + 2, (y1 + y2) / 2 - 2, self.fit(label, 60 * mm, "LS", 5.8))

    def draw(self):
        res, cef, rec = self.res, self.cef, self.rec
        g, gr = cef.get("grid") or {}, res["grid"]
        invs = cef.get("inverters") or []
        shared = [b for b in (cef.get("shared_batteries") or []) if any(i.get("shared_battery_id") == b.get("id") for i in invs)]
        tri = gr["tri"]
        poles = "4P" if tri else "2P"
        # top row
        y0, h0 = 136 * mm, 22 * mm
        self.box(0, y0, 52 * mm, h0, "REȚEA OD — " + str(rec.get("operator") or "Operator distribuție"),
                 [f"Branșament {'trifazat 3x400/230 V' if tri else 'monofazat 230 V'}, 50 Hz",
                  f"Putere aprobată: {v(gr['bransament_kw'], ' kW')}", f"POD: {rec.get('pod') or '—'}"], "grid")
        bmp_a = g.get("bmp_a") or gr.get("main_proposal")
        self.line(52 * mm, y0 + h0 / 2, 60 * mm, y0 + h0 / 2, label=None)
        self.box(60 * mm, y0, 62 * mm, h0, "BMP — măsură și protecție",
                 [f"Contor bidirecțional {'trifazat' if tri else 'monofazat'}" + (" · măsură prin TC " + str(g.get("ct_ratio")) if g.get("ct_ratio") else " · măsură directă"),
                  f"Întreruptor general: {v(bmp_a, ' A')} {poles}" + ("" if g.get("bmp_a") else " (propus)"),
                  f"Cablu coloană: {g.get('column_cable') or 'de completat'}"], "bmp")
        x = 122 * mm
        if gr["anti"]:
            self.line(x, y0 + h0 / 2, x + 8 * mm, y0 + h0 / 2)
            self.box(x + 8 * mm, y0, 66 * mm, h0, "TABLOU ANTIINSULARIZARE",
                     [f"Releu protecție interfață: {g.get('anti_relay') or 'conform ATR'}",
                      f"Element de decuplare: {g.get('anti_breaker') or 'întreruptor motorizat / contactor'}",
                      "Cerut: " + ("> 27 kW" if gr["anti_auto"] else "soluția de racordare (ATR)")], "anti")
            x += 74 * mm
        self.line(x, y0 + h0 / 2, x + 8 * mm, y0 + h0 / 2)
        self.box(x + 8 * mm, y0, 273 * mm - x - 8 * mm, h0, "SMART METER / CONTOR SISTEM",
                 [str(g.get("meter") or "Smart meter la punctul de racord (comun)"), "Montat după BMP, comunicație cu invertoarele"], "bmp")
        # TG bus
        ty, th = 104 * mm, 18 * mm
        self.line(91 * mm, y0, 91 * mm, ty + th, label=str(g.get("tg_cable") or ""))
        self.box(0, ty, 273 * mm, th, "TG — TABLOU GENERAL / TABLOU AC FOTOVOLTAIC",
                 [f"Întreruptor general TG: {g.get('tg_breaker') or 'de completat'} · SPD AC {g.get('spd_ac') or 'tip 1+2'} · "
                  f"Diferențial: {g.get('rcd') or 'conform proiect'} · Bară PE → priză de pământ R = {v(g.get('grounding_ohm') or rec.get('grounding_ohm'), ' Ω')}"], "tg")
        cols = len(invs) + len(shared)
        if not cols:
            return
        cw = 273 * mm / cols
        cx = {}
        for i, inv in enumerate(invs):
            r = res["inverters"][i] if i < len(res["inverters"]) else {}
            pa = r.get("proposals", {}).get("ac", {})
            pd = r.get("proposals", {}).get("dc", {})
            ac, dc = inv.get("ac") or {}, inv.get("dc") or {}
            bx = i * cw
            lw = cw * (0.6 if (inv.get("backup", {}).get("enabled") or inv.get("battery_mode") == "own") else 0.92)
            mid = bx + 3 * mm + lw / 2
            cx[i] = mid
            c = self.canv
            c.setFont("LS", 5.8); c.setFillColor(colors.black)
            q = f"Q{i + 1}: C{v(ac.get('breaker_a') or pa.get('breaker_a'))} A {pa.get('poles', poles)}"
            c.drawString(bx + 3 * mm, ty + 5, self.fit(q + (" (propus)" if not ac.get("breaker_a") else "") + (f" · {inv.get('rcd')}" if inv.get("rcd") else ""), cw - 6 * mm, "LS", 5.8))
            iy, ih = 72 * mm, 24 * mm
            cable = f"{ac.get('cable_type') or 'RV-K'} {v(ac.get('section') or pa.get('section'))} mm² {ac.get('material') or 'Cu'}, {v(ac.get('length_m'), ' m')}"
            self.line(mid, ty, mid, iy + ih, label=cable)
            ph = "3F" if r.get("tri") else ("1F" + (f" pe {inv.get('phase')}" if inv.get("phase") else ""))
            quantity = int(r.get("count") or inv.get("count") or 1)
            inv_label = f"INV {i + 1}" + (f" ({quantity} buc.)" if quantity > 1 else "")
            self.box(bx + 3 * mm, iy, lw, ih, f"{inv_label} — {inv.get('brand_model') or '—'}",
                     [f"{inv.get('kind') or inv.get('type') or 'Invertor'} · {ph}",
                      f"Pn {v(inv.get('p_nom_kw'), ' kW')} · Pmax {v(inv.get('p_max_kw'), ' kW')}",
                      f"Limitare: {v(inv.get('p_limit_kw'), ' kW')} · MPPT: {v(inv.get('mppt_count'))}",
                      f"Udc max {v(inv.get('vdc_max'), ' V')} · MPPT {v(inv.get('mppt_min'))}-{v(inv.get('mppt_max'), ' V')}"], "inv",
                     dashed=bool(inv.get("existing")))
            strings = r.get("strings") or []
            if strings:
                dy, dh = 42 * mm, 22 * mm
                self.line(mid, iy, mid, dy + dh, dc=True,
                          label=f"{dc.get('cable_type') or 'H1Z2Z2-K'} {v(dc.get('section') or pd.get('section'))} mm², {v(dc.get('length_m'), ' m')}")
                self.box(bx + 3 * mm, dy, lw, dh, "TABLOU DC",
                         [f"Separator DC {v(dc.get('switch') or ('%g V' % (pd.get('spd_ucpv') or 1000)))}",
                          f"SPD DC {dc.get('spd_type') or 'tip 2'} Ucpv {v(dc.get('spd_ucpv') or pd.get('spd_ucpv'), ' V')}",
                          f"Siguranțe gPV: {v(dc.get('fuse_a') or pd.get('fuse'), ' A') if (dc.get('fuse_a') or pd.get('fuse')) else pd.get('fuse_note', '—')}"], "dc")
                ns = len(strings)
                sw = (lw - (ns - 1) * 1.5 * mm) / ns
                for k, s in enumerate(strings):
                    sx = bx + 3 * mm + k * (sw + 1.5 * mm)
                    self.line(sx + sw / 2, dy, sx + sw / 2, 30 * mm, dc=True)
                    self.box(sx, 2 * mm, sw, 28 * mm, f"S{k + 1} / MPPT{s['mppt']}",
                             [f"{s['panels']}× {v(inv.get('panel_w'), ' W')}", str(inv.get("panel_model") or "")[:30],
                              f"Voc {s['voc_cold']:.0f} V@{res['tmin']:g}°C", f"Vmp {s['vmp_stc']:.0f} V", f"{s['kwp']:.2f} kWp"], "pv")
            rx = bx + 3 * mm + lw + 2 * mm
            rw = cw - lw - 7 * mm
            if inv.get("backup", {}).get("enabled"):
                b = inv["backup"]
                self.line(bx + 3 * mm + lw, iy + ih - 5 * mm, rx, iy + ih - 5 * mm)
                self.box(rx, iy + 9 * mm, rw, ih - 9 * mm, "TB BACKUP / EPS",
                         [f"Tip: {b.get('type') or 'parțial'}", f"Protecție: {b.get('breaker') or '—'}", str(b.get("circuits") or "")[:40]], "bk")
            if inv.get("battery_mode") == "own":
                bt = inv.get("battery") or {}
                bp = r.get("proposals", {}).get("battery", {})
                coupling = str(bt.get("coupling") or "").strip().upper()
                battery_x = rx + rw / 2
                battery_top = 66 * mm
                if coupling == "DC":
                    self.line(bx + 3 * mm + lw, iy + 4 * mm, battery_x, iy + 4 * mm, dc=True)
                    self.line(battery_x, iy + 4 * mm, battery_x, 73 * mm, dc=True)
                    c.setStrokeColor(RED); c.setLineWidth(0.8)
                    c.rect(battery_x - 3.5 * mm, 69 * mm, 7 * mm, 4 * mm, stroke=1, fill=0)
                    c.line(battery_x - 2 * mm, 69.5 * mm, battery_x + 2 * mm, 72.5 * mm)
                    c.setFont("LSB", 4.8); c.setFillColor(RED); c.drawCentredString(battery_x, 74 * mm, "QBAT DC")
                    self.line(battery_x, 69 * mm, battery_x, battery_top, dc=True)
                elif coupling == "AC":
                    self.line(bx + 3 * mm + lw, iy + 4 * mm, battery_x, iy + 4 * mm)
                    self.line(battery_x, iy + 4 * mm, battery_x, battery_top)
                coupling_label = coupling if coupling in ("AC", "DC") else "CUPLARE NESPECIFICATĂ"
                battery_section = bt.get("cable_section") or bp.get("section")
                battery_fuse = bt.get("fuse_a") or bp.get("fuse_a")
                switch_u = bt.get("dc_switch_voltage_v")
                switch_i = bt.get("dc_switch_current_a")
                switch_text = f"Qbat DC: {v(switch_u, ' V')} / {v(switch_i, ' A')}" if switch_u and switch_i else "Qbat DC: tensiune/curent nominal de confirmat"
                battery_lines = [
                    str(bt.get("model") or "—"),
                    f"{v(bt.get('modules'), ' mod.')} × {v(bt.get('kwh'), ' kWh')} · total {r.get('battery_kwh', 0):g} kWh",
                    f"Ubat {v(bt.get('voltage'), ' V')} · Imax {v(bt.get('i_max'), ' A')}",
                    f"Cablu DC: {v(battery_section, ' mm²')} · siguranță: {v(battery_fuse, ' A')}",
                    switch_text,
                    f"Protecție: {bt.get('protection') or 'de confirmat'}",
                ]
                self.box(rx, 36 * mm, rw, 30 * mm, f"BATERIE ({coupling_label})", battery_lines, "bat",
                         dashed=bp.get("source") != "calculated" or not (switch_u and switch_i))
        for k, b in enumerate(shared):
            bx = (len(invs) + k) * cw
            users = [i for i, inv in enumerate(invs) if inv.get("shared_battery_id") == b.get("id")]
            bp = res.get("shared_battery_proposals", {}).get(b.get("id"), {})
            coupling = str(b.get("coupling") or "").strip().upper()
            coupling_label = coupling if coupling in ("AC", "DC") else "CUPLARE NESPECIFICATĂ"
            battery_section = b.get("cable_section") or bp.get("section")
            battery_fuse = b.get("fuse_a") or bp.get("fuse_a")
            switch_u = b.get("dc_switch_voltage_v")
            switch_i = b.get("dc_switch_current_a")
            switch_text = f"Qbat DC: {v(switch_u, ' V')} / {v(switch_i, ' A')}" if switch_u and switch_i else "Qbat DC: tensiune/curent nominal de confirmat"
            self.box(bx + 3 * mm, 42 * mm, cw - 6 * mm, 30 * mm, f"BATERIE COMUNĂ ({coupling_label})",
                     [str(b.get("model") or "—"),
                      f"{v(b.get('modules'), ' mod.')} × {v(b.get('kwh'), ' kWh')} · total {v(b.get('kwh'), ' kWh')}",
                      f"Ubat {v(b.get('voltage'), ' V')} · Imax {v(b.get('i_max'), ' A')}",
                      f"Cablu DC: {v(battery_section, ' mm²')} · siguranță: {v(battery_fuse, ' A')}",
                      switch_text,
                      "Invertoare: " + ", ".join(f"INV {u + 1}" for u in users)], "bat",
                     dashed=bp.get("source") != "calculated" or not (switch_u and switch_i))
            if coupling in ("AC", "DC"):
                for j, u in enumerate(users):
                    yy = 70 * mm - j * 2.2 * mm
                    self.line(cx[u], 72 * mm, cx[u], yy, dc=coupling == "DC")
                    self.line(cx[u], yy, bx + 3 * mm, yy, dc=coupling == "DC")
        # legend
        c = self.canv
        c.setFont("LS", 6); c.setFillColor(colors.black)
        lx = 273 * mm - 70 * mm
        c.setStrokeColor(NAVY); c.line(lx, 99 * mm, lx + 6 * mm, 99 * mm); c.drawString(lx + 7 * mm, 98.3 * mm, "c.a.")
        c.setStrokeColor(RED); c.setDash(3, 2); c.line(lx + 16 * mm, 99 * mm, lx + 22 * mm, 99 * mm); c.setDash(); c.drawString(lx + 23 * mm, 98.3 * mm, "c.c.")
        c.setStrokeColor(NAVY); c.setDash(3, 2); c.rect(lx + 32 * mm, 97.6 * mm, 5 * mm, 3 * mm); c.setDash(); c.drawString(lx + 38 * mm, 98.3 * mm, "echipament existent")


def story(ctx, P, table, S):
    rec = ctx.r
    res = C.check(rec.get("cef") or {})
    t = res["totals"]
    out = [Paragraph(f"<b>{ctx.company}</b> · Atestat ANRE nr. {ctx.e('anre_attest')}", S["small"]), Spacer(1, 3),
           Paragraph(f"SCHEMĂ MONOFILARĂ — CEF {t['kwp']:g} kWp / {t['inverters_kw']:g} kW · {ctx.name}, {ctx.loc}", S["h"]),
           Spacer(1, 4), CefDrawing(dict(rec, operator=ctx.raw('operator'), pod=ctx.raw('pod'), grounding_ohm=ctx.raw('grounding_ohm')), res)]
    rows = [["INV", "Model", "Pn/Pmax/Limit (kW)", "Stringuri (panouri)", "Voc rece max / Udc max", "Isc MPPT max / Imax", "Cablu AC / Q", "Cablu DC / SPD DC", "Stocare"]]
    for i, inv in enumerate(rec.get("cef", {}).get("inverters") or []):
        r = res["inverters"][i]
        ac, dc, pa, pd = inv.get("ac") or {}, inv.get("dc") or {}, r["proposals"]["ac"], r["proposals"]["dc"]
        rows.append([str(i + 1), inv.get("brand_model") or "—", f"{v(inv.get('p_nom_kw'))}/{v(inv.get('p_max_kw'))}/{v(inv.get('p_limit_kw'))}",
                     " + ".join(str(s["panels"]) for s in r["strings"]) or "—", f"{r['voc_cold_max']:g} / {v(inv.get('vdc_max'))} V" if r.get("voc_cold_max") else f"NECONFIRMAT / {v(inv.get('vdc_max'))} V",
                     f"{r['isc_mppt_max']:g} / {v(inv.get('imax_mppt'))} A",
                     f"{v(ac.get('section') or pa.get('section'))} mm² {ac.get('material') or 'Cu'} {v(ac.get('length_m'), ' m')} / C{v(ac.get('breaker_a') or pa.get('breaker_a'))}",
                     f"{v(dc.get('section') or pd.get('section'))} mm² {v(dc.get('length_m'), ' m')} / {v(dc.get('spd_ucpv') or pd.get('spd_ucpv'), ' V')}",
                     f"{r['battery_kwh']:g} kWh" if r["battery_kwh"] else ("comună" if inv.get("battery_mode") == "shared" else "—")])
    tbl = [Spacer(1, 6), P("Date tehnice pentru verificare", "b"),
           table(rows, [10 * mm, 42 * mm, 26 * mm, 28 * mm, 30 * mm, 28 * mm, 40 * mm, 36 * mm, 26 * mm]),
           Spacer(1, 4),
           P(f"Totaluri: {t['kwp']:g} kWp panouri · {t['inverters_kw']:g} kW invertoare (max {t['inverters_kw_max']:g} kW) · putere evacuată {t['export_kw']:g} kW · "
             f"stocare {t['storage_kwh']:g} kWh · {t['panels']} panouri · temperatură minimă de calcul {res['tmin']:g}°C.")]
    for e in res["errors"]:
        tbl.append(P(f"<font color='#b03a2e'><b>EROARE:</b> {e}</font>"))
    for w in res["warnings"]:
        tbl.append(P(f"<font color='#b9770e'><b>ATENȚIE:</b> {w}</font>"))
    tbl.append(P(res["note"], "small"))
    from docgen import REGLAJ
    rg = rec.get("reglaj") or {}
    tbl.append(P("FUNCȚII DE PROTECȚIE INTERFAȚĂ (ORDIN ANRE 228/2018)", "b"))
    tbl.append(table([["Parametru", "Prag", "t (s)"]] + [[lbl, str((rg.get(k) or {}).get("val") or ""), str((rg.get(k) or {}).get("t") or "")] for k, lbl in REGLAJ],
                     [150 * mm, 70 * mm, 53 * mm]))
    tbl.append(P("CARTUȘ PLANȘĂ", "b"))
    tbl.append(table([["Denumire planșă", "Nr. proiect / planșă", "Prestator", "Beneficiar", "Adresă CEF", "POD"],
                      [f"CEF {t['kwp']:g} kWp — Schemă monofilară", ctx.v("project_no"), ctx.company, ctx.name, ctx.loc, ctx.v("pod")],
                      ["Proiectat", "Desenat", "Verificator", "Data", "Alimentare TEG", ""],
                      [ctx.v("designer", ctx.rep), ctx.v("drawn_by", ctx.rep), ctx.e("verifier"), ctx.date, ctx.v("teg_supply"), ""]],
                     [50 * mm, 40 * mm, 40 * mm, 45 * mm, 60 * mm, 38 * mm]))
    return out, tbl
