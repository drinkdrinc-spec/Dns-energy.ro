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
        self.items, self.missing, self.verification_missing, self.errors, self.warnings, self.cables, self.prot = [], [], [], [], [], [], []

    def it(self, group, label, value, src="calculat", formula="", ok=None, note=""):
        self.items.append({"group": group, "label": label, "value": value if has(value) else None, "source": src,
                           "formula": formula, "ok": ok, "note": note})

    def need(self, path, label, val, group=""):
        if not has(val):
            self.missing.append({"path": path, "label": f"{group} — {label}" if group else label})
            return False
        return True

    def confirm(self, path, label, val, group=""):
        if not has(val):
            self.verification_missing.append({"path": path, "label": f"{group} — {label}" if group else label})
            return False
        return True


def src_of(d, key, cat_key):
    return "catalog" if d.get(cat_key) else "introdus"


def compute(rec: dict, client: dict | None = None, settings: dict | None = None) -> dict:
    cef = rec.get("cef") or {}
    client = client or {}
    base = C.check(cef, (settings or {}).get("sizing_rules"))
    grid = cef.get("grid") or {}
    o = Out()
    get = lambda k: client.get(k) if has(client.get(k)) else rec.get(k)
    for k, lbl in REQ_CLIENT:
        # Only the beneficiary is essential for a useful draft preview. The
        # remaining title-block details can be supplied before approval.
        (o.need if k == "name" else o.confirm)(k, lbl, get(k), "Date generale")
    invs = cef.get("inverters") or []
    if not invs:
        o.missing.append({"path": "cef.inverters", "label": "Configurație CEF — niciun invertor definit"})
    tmin = base["tmin"]
    tri_grid = base["grid"]["tri"]
    ik = n(grid.get("ik_ka"))
    G = "Racord / TG / BMP"
    o.need("cef.grid.supply", "Tip branșament", grid.get("supply"), G)
    o.need("cef.grid.bransament_kw", "Putere aprobată (kW)", grid.get("bransament_kw"), G)
    o.confirm("cef.grid.earthing", "Sistem de legare la pământ (TN-C-S / TT)", grid.get("earthing"), G)
    o.confirm("cef.grid.ik_ka", "Curent de scurtcircuit la punctul de racord Ik (kA, din ATR/OD)", grid.get("ik_ka"), G)
    # BMP/TG ratings and SPD poles are derived from the selected branch and
    # the inverter data. Keep them as proposals; ask only for site measurements.
    gro = rec.get("grounding_ohm") or grid.get("grounding_ohm")
    o.confirm("cef.grid.grounding_ohm", "Rezistența prizei de pământ — valoare MĂSURATĂ (Ω)", gro, G)
    inv_in = []
    tot_loss = 0.0
    for i, inv in enumerate(invs):
        r = base["inverters"][i]
        T = f"INV {i + 1}"
        ac, dc, pa, pd = inv.get("ac") or {}, inv.get("dc") or {}, r["proposals"]["ac"], r["proposals"]["dc"]
        si, sp = src_of(inv, "x", "catalog_id"), src_of(inv, "x", "panel_catalog_id")
        inv_type = str(inv.get("type") or inv.get("kind") or "")
        battery_ac = inv.get("battery_charger") or "Invertor de baterie" in inv_type
        has_pv = not inv.get("no_panels") and not battery_ac
        core_specs = [("brand_model", "Marcă și model invertor"), ("p_nom_kw", "Putere nominală AC (kW)")]
        if has_pv:
            core_specs += [("vdc_max", "Udc max (V)"), ("mppt_min", "MPPT min (V)"), ("mppt_max", "MPPT max (V)"),
                           ("mppt_count", "Nr. MPPT"), ("imax_mppt", "Curent max / MPPT (A)")]
        for k, lbl in core_specs:
            present = o.need(f"cef.inverters.{i}.{k}", lbl, inv.get(k), T) if k in ("brand_model", "p_nom_kw") else o.confirm(f"cef.inverters.{i}.{k}", lbl, inv.get(k), T)
            if present:
                o.it(T, lbl, g(inv.get(k)), si)
        strings = r["strings"]
        if has_pv:
            for k, lbl in [("panel_model", "Model panou"), ("panel_w", "Putere panou (W)"), ("panel_voc", "Voc panou (V)"),
                           ("panel_vmp", "Vmp panou (V)"), ("panel_isc", "Isc panou (A)")]:
                present = o.need(f"cef.inverters.{i}.{k}", lbl, inv.get(k), T) if k == "panel_model" else o.confirm(f"cef.inverters.{i}.{k}", lbl, inv.get(k), T)
                if present:
                    o.it(T, lbl, g(inv.get(k)), sp)
            o.confirm(f"cef.inverters.{i}.panel_imp", "Imp panou (A)", inv.get("panel_imp"), T)
            o.confirm(f"cef.inverters.{i}.panel_coef_voc", "Coeficient temperatură Voc", inv.get("panel_coef_voc"), T)
            o.confirm(f"cef.inverters.{i}.panel_coef_vmp", "Coeficient temperatură Vmp", inv.get("panel_coef_vmp"), T)
            o.it(T, "Coeficient Voc (%/°C)", g(inv.get("panel_coef_voc")), sp if has(inv.get("panel_coef_voc")) else "lipsă",
                 note="" if has(inv.get("panel_coef_voc")) else "preluați valoarea din fișa tehnică oficială; nu se folosește o valoare implicită")
            o.it(T, "Coeficient Vmp (%/°C)", g(inv.get("panel_coef_vmp")), sp if has(inv.get("panel_coef_vmp")) else "lipsă",
                 note="" if has(inv.get("panel_coef_vmp")) else "preluați valoarea din fișa tehnică oficială; verificarea Vmp la cald rămâne neconfirmată")
            if not strings:
                o.missing.append({"path": f"cef.inverters.{i}.strings", "label": f"{T} — configurația stringurilor"})
        vdc_max, mmin, mmax, imax = n(inv.get("vdc_max")), n(inv.get("mppt_min")), n(inv.get("mppt_max")), n(inv.get("imax_mppt"))
        for k, s in enumerate(strings):
            o.it(T, f"String {k + 1} (MPPT {s['mppt']}) — {s['panels']} panouri", g(s["kwp"], " kWp"), "calculat", "P = Ns · Pmod")
            o.it(T, f"String {k + 1} — Voc la {tmin:g}°C", g(s["voc_cold"], " V", 0), "calculat" if s["voc_cold"] is not None else "necalculat",
                 "Voc,min = Ns·Voc·[1 + βVoc·(Tmin − 25)]",
                 (s["voc_cold"] <= vdc_max) if (vdc_max and s["voc_cold"] is not None) else None,
                 f"≤ Udc max {vdc_max:g} V" if vdc_max else ("" if s["voc_cold"] is not None else "lipsește coeficientul Voc din fișa panoului"))
            vmp_hot_label = f"{s['vmp_hot']:.0f} / {s['vmp_stc']:.0f} V" if s["vmp_hot"] is not None else f"— / {s['vmp_stc']:.0f} V"
            o.it(T, f"String {k + 1} — Vmp la 70°C / STC", vmp_hot_label, "calculat" if s["vmp_hot"] is not None else "necalculat",
                 "Vmp,70 = Ns·Vmp·[1 + βVmp·(Tcell − 25)]",
                 (mmin <= s["vmp_hot"] and s["vmp_stc"] <= mmax) if (mmin and mmax and s["vmp_hot"] is not None) else None,
                 f"în domeniul MPPT {mmin:g}–{mmax:g} V" if mmax else ("" if s["vmp_hot"] is not None else "lipsește coeficientul Vmp din fișa panoului"))
        per = {}
        for s in strings:
            per.setdefault(s["mppt"], []).append(s)
        for m, ss in per.items():
            isum = sum(x["isc"] for x in ss)
            panel_imp = n(inv.get("panel_imp")) or (n(inv.get("panel_w")) / n(inv.get("panel_vmp")) if n(inv.get("panel_vmp")) else 0)
            imp_sum = len(ss) * panel_imp
            input_limits = inv.get("imax_mppt_values") or []
            input_limit = n(input_limits[m - 1]) if 0 < m <= len(input_limits) else imax
            isc_limits = inv.get("isc_mppt_max_values") or []
            isc_limit = n(isc_limits[m - 1]) if 0 < m <= len(isc_limits) else n(inv.get("isc_mppt_max"))
            o.it(T, f"MPPT {m} — Imp total / curent de lucru max", f"{imp_sum:.1f} / {g(input_limit, ' A') or '—'}", "calculat",
                 "ΣImp pe MPPT; se compară cu Imax de lucru", (imp_sum <= input_limit) if input_limit and imp_sum else None,
                 f"limita MPPT {m}: {input_limit:g} A" if input_limit else "curentul maxim de lucru lipsește din fișa echipamentului")
            o.it(T, f"MPPT {m} — Isc total / scurtcircuit admis", f"{isum:.1f} / {g(isc_limit, ' A') or '—'}", "calculat",
                 "ΣIsc pe MPPT; se compară cu Isc maxim admis", (isum <= isc_limit) if isc_limit else None,
                 f"limita Isc MPPT {m}: {isc_limit:g} A" if isc_limit else "limita Isc maximă nu este disponibilă în datele echipamentului")
        isc1 = max([s["isc"] for s in strings] or [0])
        imp = n(inv.get("panel_imp")) or (n(inv.get("panel_w")) / n(inv.get("panel_vmp")) if n(inv.get("panel_vmp")) else 0)
        voc_max = r["voc_cold_max"]
        if strings:
            # DC cable
            dmat, dL, ds = dc.get("material") or "Cu", n(dc.get("length_m")), n(dc.get("section"))
            o.confirm(f"cef.inverters.{i}.dc.length_m", "Lungime cablu DC (m)", dc.get("length_m"), T)
            o.it(T, "DC — curent de dimensionare", g(1.25 * isc1, " A", 1), "calculat", "Ib,DC = 1,25 · Isc,STC (IEC 62548)")
            o.need(f"cef.inverters.{i}.dc.section", "Secțiune cablu DC (mm²)", dc.get("section") or pd["section"], T)
            o.it(T, "DC — secțiune propusă", g(dc.get("section") or pd["section"], " mm²"), "calculat" if not dc.get("section") else "introdus", "Iz ≥ 1,25·Isc și ΔU ≤ 1%")
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
            o.it(T, "Separator DC", dc.get("switch") or inv.get("dc_switch_integrated") or f"≥ {sw_v} V / {sw_a} A DC-PV2 (propus)",
                 "introdus" if (dc.get("switch") or inv.get("dc_switch_integrated")) else "calculat", note="confirmați modelul din catalogul de aparataj înainte de execuție")
            par = max([len(x) for x in per.values()] or [0])
            if par >= 3:
                fmin, fmax = 1.5 * isc1, 2.4 * isc1
                fa = n(dc.get("fuse_a"))
                o.it(T, "Siguranțe gPV", g(fa, " A") or g(pd["fuse"], " A (propus)"), "introdus" if fa else "calculat", "1,5·Isc ≤ In ≤ 2,4·Isc",
                     (fmin <= fa <= fmax) if fa else None, f"{fmin:.1f}–{fmax:.1f} A")
                o.it(T, "Siguranțe gPV (A)", g(dc.get("fuse_a") or pd["fuse"], " A"),
                     "introdus" if dc.get("fuse_a") else "calculat", note="necesare deoarece sunt cel puțin 3 stringuri în paralel pe MPPT")
            else:
                o.it(T, "Siguranțe gPV", "nu sunt necesare", "calculat", "≤ 2 stringuri în paralel / MPPT (IEC 62548)")
            spd = n(dc.get("spd_ucpv"))
            o.it(T, "SPD DC Ucpv", g(spd or pd["spd_ucpv"], " V"), "introdus" if spd else "calculat", "Ucpv ≥ Voc,min")
            o.it(T, "SPD DC Ucpv", g(spd, " V") or g(pd["spd_ucpv"], " V (propus)"), "introdus" if spd else "calculat", "Ucpv ≥ Voc,min",
                 (spd >= voc_max) if spd else None, f"≥ {voc_max:.0f} V")
        # AC
        tri = r["tri"]
        mat, L, sct, ina = ac.get("material") or "Cu", n(ac.get("length_m")), n(ac.get("section")), n(ac.get("breaker_a"))
        ib = pa["ib"]
        o.confirm(f"cef.inverters.{i}.ac.length_m", "Lungime cablu AC (m)", ac.get("length_m"), T)
        o.need(f"cef.inverters.{i}.ac.section", "Secțiune cablu AC (mm²)", ac.get("section") or pa.get("section"), T)
        o.need(f"cef.inverters.{i}.ac.breaker_a", "Întreruptor AC (A)", ac.get("breaker_a") or pa.get("breaker_a"), T)
        o.it(T, "AC — întreruptor / secțiune propuse",
             f"{g(ac.get('breaker_a') or pa.get('breaker_a'), ' A')} / {g(ac.get('section') or pa.get('section'), ' mm²')}",
             "introdus" if ac.get("breaker_a") and ac.get("section") else "calculat", "Ib ≤ In ≤ Iz; ΔU ≤ 3%")
        o.confirm(f"cef.inverters.{i}.rcd_type", "Tip protecție diferențială (din manualul invertorului)", inv.get("rcd_type"), T)
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
            o.confirm(f"cef.inverters.{i}.battery.model", "Model baterie", bat.get("model"), T)
            o.confirm(f"cef.inverters.{i}.battery.i_max", "Curent max descărcare baterie (A)", bat.get("i_max"), T)
            battery_kwh = n(bat.get("kwh")) * (int(n(bat.get("modules"), 1)) or 1)
            if not battery_kwh and n(bat.get("ah")) and n(bat.get("voltage")):
                battery_kwh = n(bat.get("ah")) * n(bat.get("voltage")) / 1000 * (int(n(bat.get("modules"), 1)) or 1)
            o.confirm(f"cef.inverters.{i}.battery.kwh", "Capacitate / tensiune baterie", battery_kwh, T)
            if str(bat.get("coupling") or "DC").upper() == "DC":
                if not (bat.get("voltage_ranges") or (n(bat.get("voltage_min")) and n(bat.get("voltage_max"))) or n(bat.get("voltage"))):
                    o.confirm(f"cef.inverters.{i}.battery.voltage", "Tensiune baterie (V)", None, T)
                if not (n(inv.get("bat_v_min")) and n(inv.get("bat_v_max"))):
                    o.confirm(f"cef.inverters.{i}.bat_v_min", "Domeniu baterie acceptat de invertor", None, T)
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
    tg_proposal = gr["main_proposal"]
    tg_effective = tg or tg_proposal
    if tg_effective:
        o.it(G, "Întreruptor general TEG", g(tg_effective, " A") + (" (propus)" if not tg else ""),
             "introdus" if tg else "calculat", "dimensionat după puterea aprobată și numărul de faze")
    spd_ac_proposal = grid.get("spd_ac") or f"SPD {'4P' if tri_grid else '2P'} · Tip 2 · Up 1,5 kV (propus)"
    o.it(G, "SPD AC", spd_ac_proposal, "introdus" if grid.get("spd_ac") else "calculat",
         "poli derivați din branșament; selecția finală se verifică după schema de legare la pământ și protecția la trăsnet")
    if inv_in and tg_effective:
        ok = max(inv_in) < tg_effective and (not bmp or tg_effective <= bmp)
        o.it(G, "Selectivitate (cascadă)", f"INV {max(inv_in):g} A < TG {tg_effective:g} A" + (f" ≤ BMP {bmp:g} A" if bmp else ""), "calculat",
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
        lim = n(rec.get("grounding_limit") or grid.get("grounding_limit"), 4)
        o.need("cef.grid.grounding_limit", "Valoare admisă priză de pământ (Ω) — stabilită de proiectant pentru această instalație", lim, G)
        o.it(G, "Priză de pământ — valoare măsurată vs. admisă", f"{R:g} Ω ≤ {lim:g} Ω" if lim else g(R, " Ω"), "introdus", "Buletin de măsurare vs. valoarea admisă",
             (R <= lim) if lim else None, "valoarea admisă se stabilește de proiectant (I7-2011, schema TN/TT, IPT, cerințe OD/producător) — fără prag universal")
    else:
        o.it(G, "Priză de pământ", None, "de confirmat", note="se completează DOAR cu valoarea măsurată (buletin PRAM) — aplicația nu estimează rezultate de măsurare")
    if gr["anti"]:
        o.need("cef.grid.anti_relay", "Releu protecție interfață (antiinsularizare)", grid.get("anti_relay"), G)
    used_shared_ids = {inv.get("shared_battery_id") for inv in invs if inv.get("battery_mode") == "shared"}
    for b in cef.get("shared_batteries") or []:
        if b.get("id") in used_shared_ids:
            capacity = n(b.get("kwh")) * (int(n(b.get("modules"), 1)) or 1)
            if not capacity and n(b.get("ah")) and n(b.get("voltage")):
                capacity = n(b.get("ah")) * n(b.get("voltage")) / 1000 * (int(n(b.get("modules"), 1)) or 1)
            o.confirm("shared.kwh", f"Baterie comună {b.get('model') or ''} — capacitate", capacity, "Baterii")
            o.confirm("shared.i_max", f"Baterie comună {b.get('model') or ''} — curent max (A)", b.get("i_max"), "Baterii")
            if not (b.get("voltage_ranges") or (n(b.get("voltage_min")) and n(b.get("voltage_max"))) or n(b.get("voltage"))):
                o.confirm("shared.voltage", f"Baterie comună {b.get('model') or ''} — domeniu de tensiune", None, "Baterii")
            for idx, inv in enumerate(invs):
                if inv.get("battery_mode") == "shared" and inv.get("shared_battery_id") == b.get("id"):
                    if not (n(inv.get("bat_v_min")) and n(inv.get("bat_v_max"))):
                        o.confirm(f"cef.inverters.{idx}.bat_v_min", f"INV {idx + 1} — domeniu baterie acceptat", None, "Baterii")
    o.it(G, "Pierderi totale estimate în cabluri", g(tot_loss, " W", 1), "calculat", "Σ pierderi DC + AC (la Pmax / STC)")
    for it in o.items:
        if it["ok"] is False:
            msg = f"{it['group']}: {it['label']} = {it['value']} — NECONFORM ({it['formula']}{' · ' + it['note'] if it['note'] else ''})"
            (o.warnings if "recomandat" in (it["note"] or "") or "de confirmat" in (it["note"] or "") else o.errors).append(msg)
    ns = sum(len(i["strings"]) for i in base["inverters"])
    circuit_count = len(grid.get("circuits") or []) or 4
    complex_ = len(invs) > 1 or ns > 2 or circuit_count > 2 or gr["anti"] or bool(cef.get("shared_batteries")) or any(
        i.get("battery_mode") == "own" or (i.get("backup") or {}).get("enabled") for i in invs)
    can_preview = not o.missing
    approval_ready = can_preview and not o.verification_missing and not o.errors
    return {"base": base, "items": o.items, "missing": o.missing, "verification_missing": o.verification_missing,
            "errors": o.errors, "warnings": o.warnings, "cables": o.cables,
            "format": "A3" if complex_ else "A4", "standards": STANDARDS,
            "can_preview": can_preview, "approval_ready": approval_ready, "ready": approval_ready}


def apply(cef: dict, settings: dict | None = None) -> tuple[dict, list]:
    cef = json.loads(json.dumps(cef or {}))
    base = C.check(cef, (settings or {}).get("sizing_rules"))
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
    put(gd, "rcd_ma", 30, "cef.grid.rcd_ma")
    put(gd, "tg_breaker_a", base["grid"]["main_proposal"], "cef.grid.tg_breaker_a")
    tri = base["grid"]["tri"]
    put(gd, "spd_ac", f"SPD {'4P' if tri else '2P'} · Tip 2 · Up 1,5 kV", "cef.grid.spd_ac")
    if n(gd.get("tg_breaker_a")):
        put(gd, "tg_general", f"{g(n(gd.get('tg_breaker_a')))} A {'4P' if tri else '2P'} dif. {g(n(gd.get('rcd_ma')) or 30)} mA", "cef.grid.tg_general")
    cef["auto_filled"] = sorted(set((cef.get("auto_filled") or []) + filled))
    return cef, filled


def fingerprint(rec: dict, client: dict | None, settings: dict | None = None) -> str:
    client = client or {}
    cef = {k: v for k, v in (rec.get("cef") or {}).items() if k != "auto_filled"}
    keys = {k: (client.get(k) or rec.get(k)) for k, _ in REQ_CLIENT}
    sld = rec.get("sld") or {}
    payload = {"cef": cef, "client": keys, "sizing_rules": (settings or {}).get("sizing_rules"), "source": sld.get("source"), "upload": (sld.get("upload") or {}).get("storage_path"),
               "g": rec.get("grounding_ohm")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def state(rec: dict, client: dict | None, s: dict) -> dict:
    sld = rec.get("sld") or {}
    fp = fingerprint(rec, client, s)
    aps = sld.get("approvals") or ({sld["approval"]["role"]: sld["approval"]} if sld.get("approval") else {})
    valid = {r: a for r, a in aps.items() if a.get("hash") == fp}
    ap = max(valid.values(), key=lambda a: a.get("at") or "") if valid else (max(aps.values(), key=lambda a: a.get("at") or "") if aps else None)
    status = "draft" if not aps else ("approved" if valid else "stale")
    return {**(ap or {}), "status": status, "fingerprint": fp, "approvals": {r: {**a, "valid": r in valid} for r, a in aps.items()},
            "designer": f"{s.get('designer_name')} ({s.get('designer_name_auth')})" if s.get("designer_name") else None,
            "verifier": f"{s.get('verifier')} ({s.get('verifier_auth')})" if s.get("verifier") else None}


def approved_file(rec: dict, fp: str):
    for h in reversed((rec.get("sld") or {}).get("history") or []):
        if h.get("hash") == fp and h.get("file"):
            return h["file"]
    return None
