import math, hashlib, json
import cef as C
from cef import n, up, iz, vdrop_ac, vdrop_dc, SECTIONS, BREAKERS, GPV, RHO

UCPV = [600, 800, 1000, 1100, 1200, 1500]
SWITCH_A = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125]
BAT_FUSE = [32, 40, 50, 63, 80, 100, 125, 160, 200, 250]
STANDARDS = [
    ("SR EN 60617 (IEC 60617)", "Simboluri grafice pentru scheme electrice"),
    ("SR EN 61082-1 (IEC 61082-1)", "Întocmirea documentației electrotehnice"),
    ("SR EN 81346-2 (IEC 81346-2)", "Coduri de identificare a echipamentelor (-Q, -F, -P, -T, -U, -G)"),
    ("HD 60364-7-712 / IEC 60364-7-712", "Cerințe pentru instalații de alimentare fotovoltaice"),
    ("IEC 62548", "Cerințe de proiectare pentru generatoare fotovoltaice (1,25·Isc, siguranțe gPV)"),
    ("HD 60364-5-52 / IEC 60364-5-52", "Curenți admisibili Iz, metode de pozare, cădere de tensiune"),
    ("HD 60364-5-54 / IEC 60364-5-54", "Prize de pământ și conductoare de protecție (tabel 54.2)"),
    ("HD 60364-4-43 / IEC 60364-4-43", "Protecția la supracurenți: Ib ≤ In ≤ Iz, I2 ≤ 1,45·Iz"),
    ("SR EN 60898-1 / SR EN 60947-2", "Întreruptoare automate (curbă, Icu/Icn)"),
    ("SR EN 60947-3", "Separatoare de sarcină DC (DC-PV2)"),
    ("SR EN 60269-6", "Siguranțe gPV"),
    ("SR EN 61643-11 / -31", "Descărcătoare de supratensiune AC / DC"),
    ("SR EN 61008 / 61009 / 62423", "Dispozitive de curent diferențial rezidual (tip A, F, B)"),
    ("Normativ I7-2011", "Proiectarea, execuția și exploatarea instalațiilor electrice aferente clădirilor"),
    ("Ordin ANRE 228/2018", "Norma tehnică — racordarea locurilor de producere (protecție interfață)"),
]
REQ_CLIENT = [("name", "Beneficiar"), ("address", "Adresă loc de consum"), ("locality", "Localitate"), ("county", "Județ"),
              ("operator", "Operator de distribuție"), ("project_no", "Număr proiect / planșă")]


def has(x):
    return x not in (None, "", [], {}) and not (isinstance(x, (int, float)) and x == 0)


def g(x, unit="", nd=2):
    if not has(x):
        return None
    if isinstance(x, float):
        x = round(x, nd)
    return f"{x:g}{unit}" if isinstance(x, (int, float)) else f"{x}{unit}"


def pe_for(s):
    if not s:
        return None
    if s <= 16:
        return s
    if s <= 35:
        return 16
    return up(SECTIONS, s / 2)


class Out:
    def __init__(self):
        self.items, self.missing, self.errors, self.warnings, self.cables, self.prot = [], [], [], [], [], []

    def it(self, group, label, value, src="calculat", formula="", ok=None, note=""):
        self.items.append({"group": group, "label": label, "value": value if has(value) else None, "source": src,
                           "formula": formula, "ok": ok, "note": note})

    def need(self, path, label, val, group=""):
        if not has(val):
            self.missing.append({"path": path, "label": f"{group} — {label}" if group else label})
            return False
        return True


def src_of(d, key, cat_key):
    return "catalog" if d.get(cat_key) else "introdus"


def compute(rec: dict, client: dict | None = None) -> dict:
    cef = rec.get("cef") or {}
    client = client or {}
    base = C.check(cef)
    grid = cef.get("grid") or {}
    o = Out()
    get = lambda k: client.get(k) if has(client.get(k)) else rec.get(k)
    for k, lbl in REQ_CLIENT:
        o.need(k, lbl, get(k), "Date generale")
    invs = cef.get("inverters") or []
    if not invs:
        o.missing.append({"path": "cef.inverters", "label": "Configurație CEF — niciun invertor definit"})
    tmin = base["tmin"]
    tri_grid = base["grid"]["tri"]
    ik = n(grid.get("ik_ka"))
    G = "Racord / TG / BMP"
    o.need("cef.grid.supply", "Tip branșament", grid.get("supply"), G)
    o.need("cef.grid.bransament_kw", "Putere aprobată (kW)", grid.get("bransament_kw"), G)
    o.need("cef.grid.earthing", "Sistem de legare la pământ (TN-C-S / TT)", grid.get("earthing"), G)
    o.need("cef.grid.ik_ka", "Curent de scurtcircuit la punctul de racord Ik (kA, din ATR/OD)", grid.get("ik_ka"), G)
    o.need("cef.grid.bmp_a", "Întreruptor BMP (A)", grid.get("bmp_a"), G)
    o.need("cef.grid.tg_breaker_a", "Întreruptor general TG (A)", grid.get("tg_breaker_a"), G)
    o.need("cef.grid.spd_ac", "SPD AC (tip)", grid.get("spd_ac"), G)
    gro = grid.get("grounding_ohm") or rec.get("grounding_ohm")
    o.need("cef.grid.grounding_ohm", "Rezistența prizei de pământ — valoare MĂSURATĂ (Ω)", gro, G)
    inv_in = []
    tot_loss = 0.0
    for i, inv in enumerate(invs):
        r = base["inverters"][i]
        T = f"INV {i + 1}"
        ac, dc, pa, pd = inv.get("ac") or {}, inv.get("dc") or {}, r["proposals"]["ac"], r["proposals"]["dc"]
        si, sp = src_of(inv, "x", "catalog_id"), src_of(inv, "x", "panel_catalog_id")
        for k, lbl in [("brand_model", "Marcă și model invertor"), ("p_nom_kw", "Putere nominală AC (kW)"), ("p_max_kw", "Putere maximă AC (kW)"),
                       ("vdc_max", "Udc max (V)"), ("mppt_min", "MPPT min (V)"), ("mppt_max", "MPPT max (V)"), ("mppt_count", "Nr. MPPT"),
                       ("imax_mppt", "Curent max / MPPT (A)")]:
            if o.need(f"cef.inverters.{i}.{k}", lbl, inv.get(k), T):
                o.it(T, lbl, g(inv.get(k)), si)
        strings = r["strings"]
        if inv.get("kind") != "Invertor de baterie (AC)":
            for k, lbl in [("panel_model", "Model panou"), ("panel_w", "Putere panou (W)"), ("panel_voc", "Voc panou (V)"),
                           ("panel_vmp", "Vmp panou (V)"), ("panel_isc", "Isc panou (A)")]:
                if o.need(f"cef.inverters.{i}.{k}", lbl, inv.get(k), T):
                    o.it(T, lbl, g(inv.get(k)), sp)
            o.it(T, "Coeficient Voc (%/°C)", g(n(inv.get("panel_coef_voc"), -0.27)), sp if has(inv.get("panel_coef_voc")) else "de confirmat",
                 note="" if has(inv.get("panel_coef_voc")) else "valoare implicită -0,27 %/°C — confirmați din fișa panoului")
            if not strings:
                o.missing.append({"path": f"cef.inverters.{i}.strings", "label": f"{T} — configurația stringurilor"})
        vdc_max, mmin, mmax, imax = n(inv.get("vdc_max")), n(inv.get("mppt_min")), n(inv.get("mppt_max")), n(inv.get("imax_mppt"))
        for k, s in enumerate(strings):
            o.it(T, f"String {k + 1} (MPPT {s['mppt']}) — {s['panels']} panouri", g(s["kwp"], " kWp"), "calculat", "P = Ns · Pmod")
            o.it(T, f"String {k + 1} — Voc la {tmin:g}°C", g(s["voc_cold"], " V", 0), "calculat", "Voc,min = Ns·Voc·[1 + βVoc·(Tmin − 25)]",
                 (s["voc_cold"] <= vdc_max) if vdc_max else None, f"≤ Udc max {vdc_max:g} V" if vdc_max else "")
            o.it(T, f"String {k + 1} — Vmp la 70°C / STC", f"{s['vmp_hot']:.0f} / {s['vmp_stc']:.0f} V", "calculat", "Vmp,70 = Ns·Vmp·[1 + (βVoc−0,08%)·45]",
                 (mmin <= s["vmp_hot"] and s["vmp_stc"] <= mmax) if (mmin and mmax) else None, f"în domeniul MPPT {mmin:g}–{mmax:g} V" if mmax else "")
        per = {}
        for s in strings:
            per.setdefault(s["mppt"], []).append(s)
        for m, ss in per.items():
            isum = sum(x["isc"] for x in ss)
            o.it(T, f"MPPT {m} — Isc total ({len(ss)} string)", g(isum, " A", 1), "calculat", "ΣIsc pe MPPT", (isum <= imax) if imax else None,
                 f"≤ Imax MPPT {imax:g} A" if imax else "")
        isc1 = max([s["isc"] for s in strings] or [0])
        imp = n(inv.get("panel_w")) / n(inv.get("panel_vmp")) if n(inv.get("panel_vmp")) else 0
        voc_max = r["voc_cold_max"]
        if strings:
            # DC cable
            dmat, dL, ds = dc.get("material") or "Cu", n(dc.get("length_m")), n(dc.get("section"))
            o.need(f"cef.inverters.{i}.dc.length_m", "Lungime cablu DC (m)", dc.get("length_m"), T)
            o.need(f"cef.inverters.{i}.dc.section", "Secțiune cablu DC (mm²)", dc.get("section"), T)
            o.it(T, "DC — curent de dimensionare", g(1.25 * isc1, " A", 1), "calculat", "Ib,DC = 1,25 · Isc,STC (IEC 62548)")
            o.it(T, "DC — secțiune propusă", g(pd["section"], " mm²"), "calculat", "Iz ≥ 1,25·Isc și ΔU ≤ 1%")
            vmp = max(s["vmp_stc"] for s in strings)
            if ds:
                izd = iz(ds, dmat, None, 1, n(dc.get("k_correction"), 1), dc=True)
                du = vdrop_dc(imp, dL, ds, dmat, vmp)
                loss = len(strings) * 2 * dL * imp ** 2 * RHO.get(dmat, RHO["Cu"]) / ds
                tot_loss += loss
                o.it(T, "DC — Iz cablu ales", g(izd, " A", 0), "calculat", "Iz = Iz,tabel · k", izd >= 1.25 * isc1, f"≥ {1.25 * isc1:.1f} A")
                o.it(T, "DC — cădere de tensiune", g(du, " %") or "0 %", "calculat", "ΔU = 2·L·Imp·ρ/(S·Ump)·100", du <= 1, "≤ 1 % (recomandat)")
                o.it(T, "DC — pierderi estimate (STC)", g(loss, " W", 1), "calculat", "P = Nstr·2·L·Imp²·ρ/S")
                o.cables.append({"id": f"W{i + 1}.DC", "from": f"-PV{i + 1} (stringuri)", "to": f"-U{i + 1}", "type": dc.get("cable_type") or None,
                                 "cores": "1×(+), 1×(−) / string", "section": ds, "material": dmat, "length": dL or None, "ib": round(imp, 1),
                                 "iz": round(izd), "du": round(du, 2), "loss": round(loss, 1)})
            # DC switch / fuses / SPD
            isc_m = r["isc_mppt_max"]
            sw_v, sw_a = up(UCPV, voc_max), up(SWITCH_A, 1.25 * isc_m)
            o.it(T, "Separator DC — Ue / Ie necesar", f"≥ {voc_max:.0f} V / ≥ {1.25 * isc_m:.1f} A", "calculat", "Ue ≥ Voc,min ; Ie ≥ 1,25·ΣIsc,MPPT",
                 note=f"propus {sw_v} V / {sw_a} A, categorie DC-PV2 (SR EN 60947-3)")
            o.need(f"cef.inverters.{i}.dc.switch", "Separator DC (Ue/Ie, model)", dc.get("switch") or inv.get("dc_switch_integrated"), T)
            par = max([len(x) for x in per.values()] or [0])
            if par >= 3:
                fmin, fmax = 1.5 * isc1, 2.4 * isc1
                fa = n(dc.get("fuse_a"))
                o.it(T, "Siguranțe gPV", g(fa, " A") or g(pd["fuse"], " A (propus)"), "introdus" if fa else "calculat", "1,5·Isc ≤ In ≤ 2,4·Isc",
                     (fmin <= fa <= fmax) if fa else None, f"{fmin:.1f}–{fmax:.1f} A")
                o.need(f"cef.inverters.{i}.dc.fuse_a", "Siguranțe gPV (A)", dc.get("fuse_a"), T)
            else:
                o.it(T, "Siguranțe gPV", "nu sunt necesare", "calculat", "≤ 2 stringuri în paralel / MPPT (IEC 62548)")
            spd = n(dc.get("spd_ucpv"))
            o.need(f"cef.inverters.{i}.dc.spd_ucpv", "SPD DC Ucpv (V)", dc.get("spd_ucpv"), T)
            o.it(T, "SPD DC Ucpv", g(spd, " V") or g(pd["spd_ucpv"], " V (propus)"), "introdus" if spd else "calculat", "Ucpv ≥ Voc,min",
                 (spd >= voc_max) if spd else None, f"≥ {voc_max:.0f} V")
        # AC
        tri = r["tri"]
        mat, L, sct, ina = ac.get("material") or "Cu", n(ac.get("length_m")), n(ac.get("section")), n(ac.get("breaker_a"))
        ib = pa["ib"]
        o.need(f"cef.inverters.{i}.ac.length_m", "Lungime cablu AC (m)", ac.get("length_m"), T)
        o.need(f"cef.inverters.{i}.ac.section", "Secțiune cablu AC (mm²)", ac.get("section"), T)
        o.need(f"cef.inverters.{i}.ac.breaker_a", "Întreruptor AC (A)", ac.get("breaker_a"), T)
        o.need(f"cef.inverters.{i}.rcd_type", "Tip protecție diferențială (din manualul invertorului)", inv.get("rcd_type"), T)
        if ib:
            o.it(T, "AC — curent de calcul Ib", g(ib, " A", 1), "calculat", "Ib = Pmax/(√3·400·0,95)" if tri else "Ib = Pmax/(230·0,95)")
            o.it(T, "AC — întreruptor propus", g(pa["breaker_a"], f" A {pa['poles']}"), "calculat", "In ≥ Ib (valoare standard)")
            o.it(T, "AC — secțiune propusă", g(pa["section"], " mm²"), "calculat", "Iz ≥ In și ΔU ≤ 3% (HD 60364-5-52)")
        if ina:
            inv_in.append(ina)
        if sct:
            izv = iz(sct, mat, ac.get("install") or "C", 3 if tri else 2, n(ac.get("k_correction"), 1))
            du = vdrop_ac(ib, L, sct, mat, tri)
            loss = (3 if tri else 2) * L * ib ** 2 * RHO.get(mat, RHO["Cu"]) / sct
            tot_loss += loss
            o.it(T, "AC — coordonare Ib ≤ In ≤ Iz", f"{ib:.1f} ≤ {ina:g} ≤ {izv:.0f} A" if ina else None, "calculat", "HD 60364-4-43 (I2 = 1,45·In ≤ 1,45·Iz)",
                 (ib <= ina <= izv) if ina else None)
            o.it(T, "AC — cădere de tensiune", g(du, " %") or "0 %", "calculat", "ΔU = k·L·Ib·cosφ·ρ/(S·U)·100", du <= 3, "≤ 3 % (I7)")
            o.it(T, "AC — pierderi estimate", g(loss, " W", 1), "calculat", "P = k·L·Ib²·ρ/S")
            pe_req = pe_for(sct)
            pe = n(ac.get("pe_section")) or pe_req
            o.it(T, "AC — secțiune PE", g(pe, " mm²"), "introdus" if n(ac.get("pe_section")) else "calculat", "HD 60364-5-54 tab. 54.2", pe >= pe_req, f"≥ {pe_req:g} mm²")
            o.cables.append({"id": f"W{i + 1}.AC", "from": f"-U{i + 1}", "to": "-TFV", "type": ac.get("cable_type") or None,
                             "cores": "3L+N+PE" if tri else "L+N+PE", "section": sct, "material": mat, "length": L or None, "ib": ib,
                             "iz": round(izv), "du": round(du, 2), "loss": round(loss, 1), "pe": pe})
        icu = n(ac.get("icu_ka"))
        if ina:
            o.it(T, "AC — capacitate de rupere Icu ≥ Ik", f"{icu:g} kA ≥ {ik:g} kA" if (icu and ik) else None, "calculat" if icu and ik else "de confirmat",
                 "Icu (SR EN 60898/60947-2) ≥ Ik la punctul de montaj", (icu >= ik) if (icu and ik) else None,
                 "" if (icu and ik) else "completați Icu al aparatului și Ik comunicat de OD")
        rt = inv.get("rcd_type")
        o.it(T, "Protecție diferențială", f"{rt} {g(inv.get('rcd_ma'), ' mA') or ''}".strip() if rt else None, "introdus" if rt else "de confirmat",
             "HD 60364-7-712.531.3.101", None, "Tip B dacă invertorul NU garantează absența curenților de defect DC; altfel tip A/F conform manualului")
        # battery
        bat = inv.get("battery") or {}
        if inv.get("battery_mode") == "own":
            o.need(f"cef.inverters.{i}.battery.model", "Model baterie", bat.get("model"), T)
            o.need(f"cef.inverters.{i}.battery.i_max", "Curent max descărcare baterie (A)", bat.get("i_max"), T)
            ibat = n(bat.get("i_max"))
            if ibat:
                fb = up(BAT_FUSE, 1.25 * ibat)
                o.it(T, "Baterie — protecție DC propusă", g(fb, " A"), "calculat", "In ≥ 1,25·Imax,desc. (conform manual)")
                bs = n(bat.get("cable_section"))
                if bs:
                    izb = iz(bs, "Cu", None, 1, 1, dc=True)
                    fa = n(bat.get("fuse_a")) or fb
                    o.it(T, "Baterie — Iz cablu ≥ In protecție", f"{izb:.0f} ≥ {fa:g} A", "calculat", "Iz ≥ In", izb >= fa)
                    o.cables.append({"id": f"W{i + 1}.BAT", "from": f"-G{i + 1}", "to": f"-U{i + 1}", "type": bat.get("cable_type") or None, "cores": "1×(+), 1×(−)",
                                     "section": bs, "material": "Cu", "length": n(bat.get("cable_length")) or None, "ib": ibat, "iz": round(izb), "du": None, "loss": None})
        o.errors += r["errors"]; o.warnings += r["warnings"]
    o.errors += [e for e in base["errors"] if e not in o.errors]
    o.warnings += [w for w in base["warnings"] if w not in o.warnings]
    # grid
    gr = base["grid"]
    bmp, tg = n(grid.get("bmp_a")), n(grid.get("tg_breaker_a"))
    if gr["i_br"]:
        o.it(G, "Curent branșament (putere aprobată)", g(gr["i_br"], " A", 1), "calculat", "I = P/(√3·400·0,95)" if tri_grid else "I = P/(230·0,95)")
        o.it(G, "Întreruptor BMP", g(bmp, " A") or g(gr["main_proposal"], " A (propus)"), "introdus" if bmp else "calculat", "In ≥ Ibr", (bmp >= gr["i_br"]) if bmp else None,
             "valoarea finală conform ATR / avizului OD")
    if inv_in and tg:
        ok = max(inv_in) < tg and (not bmp or tg <= bmp)
        o.it(G, "Selectivitate (cascadă)", f"INV {max(inv_in):g} A < TG {tg:g} A" + (f" ≤ BMP {bmp:g} A" if bmp else ""), "calculat",
             "In aval < In amonte (raport ≥ 1,6 recomandat pentru selectivitate amperometrică)", ok,
             "selectivitatea totală se confirmă din tabelele producătorului aparatelor")
    cs, cl = n(grid.get("column_section")), n(grid.get("column_length"))
    if cs and gr["i_br"]:
        cm = grid.get("column_material") or "Cu"
        izc = iz(cs, cm, grid.get("column_install") or "D", 3 if tri_grid else 2, 1)
        duc = vdrop_ac(gr["i_br"], cl, cs, cm, tri_grid)
        o.it(G, "Coloană BMP→TG: Iz ≥ In BMP", f"{izc:.0f} A ≥ {bmp or gr['main_proposal']:g} A", "calculat", "HD 60364-5-52", izc >= (bmp or gr["main_proposal"] or 0))
        o.it(G, "Coloană BMP→TG: cădere de tensiune", g(duc, " %") or "0 %", "calculat", "ΔU la Ibr", duc <= 3 if cl else None)
        o.cables.append({"id": "W0", "from": "-BMP", "to": "-TG", "type": grid.get("column_cable") or None, "cores": "3L+N+PE" if tri_grid else "L+N+PE",
                         "section": cs, "material": cm, "length": cl or None, "ib": gr["i_br"], "iz": round(izc), "du": round(duc, 2), "loss": None, "pe": pe_for(cs)})
    o.it(G, "Sistem de legare la pământ", grid.get("earthing"), "introdus" if grid.get("earthing") else "de confirmat")
    o.it(G, "Ik la punctul de racord", g(ik, " kA"), "introdus" if ik else "de confirmat", note="se preia din ATR / comunicat OD — nu se estimează")
    o.it(G, "Conductor echipotențial rame PV", g(n(grid.get("bond_section")), " mm²") or "≥ 6 mm² Cu (propus)", "introdus" if grid.get("bond_section") else "calculat",
         "HD 60364-7-712 / IEC 62548", note="16 mm² Cu dacă există instalație de protecție la trăsnet")
    if gro:
        R = n(gro)
        idn = n(grid.get("rcd_ma")) / 1000
        if "TT" in str(grid.get("earthing") or "") and idn:
            o.it(G, "Priză de pământ — condiție TT", f"{R:g} Ω ≤ {50 / idn:.0f} Ω", "calculat", "RA · IΔn ≤ 50 V (HD 60364-4-41)", R * idn <= 50)
        o.it(G, "Priză de pământ — valoare măsurată", g(R, " Ω"), "introdus", "Buletin de măsurare", R <= 4, "≤ 4 Ω (de confirmat de proiectant)")
    else:
        o.it(G, "Priză de pământ", None, "de confirmat", note="se completează DOAR cu valoarea măsurată (buletin PRAM) — aplicația nu estimează rezultate de măsurare")
    if gr["anti"]:
        o.need("cef.grid.anti_relay", "Releu protecție interfață (antiinsularizare)", grid.get("anti_relay"), G)
    for b in cef.get("shared_batteries") or []:
        o.need("shared.i_max", f"Baterie comună {b.get('model') or ''} — curent max (A)", b.get("i_max"), "Baterii")
    o.it(G, "Pierderi totale estimate în cabluri", g(tot_loss, " W", 1), "calculat", "Σ pierderi DC + AC (la Pmax / STC)")
    ns = sum(len(i["strings"]) for i in base["inverters"])
    complex_ = len(invs) > 1 or ns > 2 or gr["anti"] or bool(cef.get("shared_batteries")) or any(
        i.get("battery_mode") == "own" or (i.get("backup") or {}).get("enabled") for i in invs)
    return {"base": base, "items": o.items, "missing": o.missing, "errors": o.errors, "warnings": o.warnings,
            "cables": o.cables, "format": "A3" if complex_ else "A4", "standards": STANDARDS,
            "ready": not o.missing and not o.errors}


def apply(cef: dict) -> tuple[dict, list]:
    cef = json.loads(json.dumps(cef or {}))
    base = C.check(cef)
    filled = []
    def put(d, k, v, path):
        if not has(d.get(k)) and has(v):
            d[k] = v; filled.append(path)
    for i, inv in enumerate(cef.get("inverters") or []):
        r = base["inverters"][i]
        pa, pd = r["proposals"]["ac"], r["proposals"]["dc"]
        ac, dc = inv.setdefault("ac", {}), inv.setdefault("dc", {})
        put(ac, "breaker_a", pa["breaker_a"], f"cef.inverters.{i}.ac.breaker_a")
        put(ac, "section", pa["section"], f"cef.inverters.{i}.ac.section")
        put(ac, "pe_section", pe_for(n(ac.get("section"))), f"cef.inverters.{i}.ac.pe_section")
        if r["strings"]:
            put(dc, "section", pd["section"], f"cef.inverters.{i}.dc.section")
            put(dc, "spd_ucpv", pd["spd_ucpv"], f"cef.inverters.{i}.dc.spd_ucpv")
            put(dc, "fuse_a", pd["fuse"], f"cef.inverters.{i}.dc.fuse_a")
            vm, im = r["voc_cold_max"], r["isc_mppt_max"]
            put(dc, "switch", f"{up(UCPV, vm)} V / {up(SWITCH_A, 1.25 * im)} A DC-PV2", f"cef.inverters.{i}.dc.switch")
        bat = inv.get("battery") or {}
        if inv.get("battery_mode") == "own" and n(bat.get("i_max")):
            put(bat, "fuse_a", up(BAT_FUSE, 1.25 * n(bat.get("i_max"))), f"cef.inverters.{i}.battery.fuse_a")
    gd = cef.setdefault("grid", {})
    put(gd, "bmp_a", base["grid"]["main_proposal"], "cef.grid.bmp_a")
    cef["auto_filled"] = sorted(set((cef.get("auto_filled") or []) + filled))
    return cef, filled


def fingerprint(rec: dict, client: dict | None) -> str:
    client = client or {}
    cef = {k: v for k, v in (rec.get("cef") or {}).items() if k != "auto_filled"}
    keys = {k: (client.get(k) or rec.get(k)) for k, _ in REQ_CLIENT}
    sld = rec.get("sld") or {}
    payload = {"cef": cef, "client": keys, "source": sld.get("source"), "upload": (sld.get("upload") or {}).get("storage_path"),
               "g": rec.get("grounding_ohm")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
