import math

T_MIN_DEFAULT = -10.0
T_CELL_HOT = 70.0
RHO = {"Cu": 0.0225, "Al": 0.036}
SECTIONS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120]
BREAKERS = [6, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250]
# Motor-operated anti-islanding breaker frames; exact device and fault-level checks remain required.
MAIN_BREAKERS = [100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000]
MAIN_PROTECTION = sorted(set(BREAKERS + [315, 400, 500, 630, 800, 1000, 1250, 1600, 2000]))
GPV = [10, 12, 15, 16, 20, 25, 30, 32]
# IEC 60364-5-52, Cu PVC 70°C, 3 conductori încărcați, 30°C (A)
IZ_AC = {
    "A1": [13.5, 18, 24, 31, 42, 56, 73, 89, 108, 136, 164, 188],
    "B1": [15.5, 21, 28, 36, 50, 68, 89, 110, 134, 171, 207, 239],
    "B2": [15, 20, 27, 34, 46, 62, 80, 99, 118, 149, 179, 206],
    "C": [17.5, 24, 32, 41, 57, 76, 96, 119, 144, 184, 223, 259],
    "D": [18, 24, 30, 38, 50, 64, 82, 98, 116, 143, 169, 192],
    "E": [18.5, 25, 34, 43, 60, 80, 101, 126, 153, 196, 238, 276],
}
# cablu solar H1Z2Z2-K, aer liber, 1 conductor
IZ_DC = [30, 41, 55, 70, 98, 132, 176, 218, 276, 347, 416, 488]
INSTALL_LABELS = {"A1": "A1 — în tub, perete izolat", "B1": "B1 — în tub pe perete", "B2": "B2 — multiconductor în tub",
                  "C": "C — aparent pe perete", "D": "D — îngropat în tub", "E": "E — pe pat de cabluri / aer liber"}


def n(v, d=0.0):
    try:
        if v in (None, ""):
            return d
        return float(str(v).replace(",", "."))
    except Exception:
        return d


def up(lst, v):
    return next((x for x in lst if x >= v - 1e-9), None)


def iz(section, material, install, phases_loaded, k, dc=False):
    if section not in SECTIONS:
        return 0
    i = SECTIONS.index(section)
    base = IZ_DC[i] if dc else IZ_AC.get(install or "C", IZ_AC["C"])[i]
    if not dc and phases_loaded == 2:
        base *= 1.15
    if material == "Al":
        base *= 0.78
    return base * (k or 1)


def vdrop_ac(i, length, section, material, tri, cos=0.95):
    if not section or not length:
        return 0
    rho = RHO.get(material, RHO["Cu"])
    u = 400 if tri else 230
    k = math.sqrt(3) if tri else 2
    return k * length * i * cos * rho / section / u * 100


def vdrop_dc(i, length, section, material, v):
    if not section or not length or not v:
        return 0
    return 2 * length * i * RHO.get(material, RHO["Cu"]) / section / v * 100


def string_calc(s, inv, tmin):
    """Calculate string values only from supplied model parameters; never invent temperature coefficients."""
    cnt = int(n(s.get("panels")))
    voc, vmp, isc = n(inv.get("panel_voc")), n(inv.get("panel_vmp")), n(inv.get("panel_isc"))
    cv_raw = inv.get("panel_coef_voc")
    cv = (n(cv_raw) / 100) if cv_raw not in (None, "") else None
    cvmp_raw = inv.get("panel_coef_vmp")
    cvmp = (n(cvmp_raw) / 100) if cvmp_raw not in (None, "") else None
    voc_cold = cnt * voc * (1 + cv * (tmin - 25)) if voc and cv is not None else None
    vmp_hot = cnt * vmp * (1 + cvmp * (T_CELL_HOT - 25)) if vmp and cvmp is not None else None
    return {"panels": cnt, "mppt": int(n(s.get("mppt"), 1)) or 1, "voc_stc": cnt * voc, "voc_cold": voc_cold,
            "vmp_stc": cnt * vmp, "vmp_hot": vmp_hot, "isc": isc, "kwp": cnt * n(inv.get("panel_w")) / 1000}


def check(cef: dict) -> dict:
    cef = cef or {}
    grid = cef.get("grid") or {}
    supply_known = bool(grid.get("supply"))
    tri_grid = "mono" not in str(grid.get("supply") or "").lower() if supply_known else False
    tmin = n(cef.get("tmin"), n(grid.get("tmin"), T_MIN_DEFAULT))
    invs = cef.get("inverters") or []
    shared = {b.get("id"): b for b in (cef.get("shared_batteries") or [])}
    shared_users = {}
    out_inv, errors, warnings = [], [], []
    tot_kwp = tot_kw = tot_kwmax = tot_export = tot_kwh = 0.0

    for idx, inv in enumerate(invs):
        tag = f"Invertor {idx + 1}"
        unit_count = max(1, min(100, int(n(inv.get("count"), 1) or 1)))
        e, w, prop = [], [], {}
        phase_known = bool(inv.get("phases") or grid.get("supply"))
        tri = "mono" not in str(inv.get("phases") or grid.get("supply") or "").lower() if phase_known else False
        p_nom, p_max = n(inv.get("p_nom_kw")), n(inv.get("p_max_kw")) or n(inv.get("p_nom_kw"))
        p_lim = n(inv.get("p_limit_kw")) or p_nom
        vdc_max, mmin, mmax = n(inv.get("vdc_max")), n(inv.get("mppt_min")), n(inv.get("mppt_max"))
        mppt_count, imax = int(n(inv.get("mppt_count"))), n(inv.get("imax_mppt"))
        isc_mppt_limit = n(inv.get("isc_max_mppt"))
        strings = [string_calc(s, inv, tmin) for s in (inv.get("strings") or []) if n(s.get("panels")) > 0]
        kwp = sum(s["kwp"] for s in strings)
        tot_kwp += kwp * unit_count; tot_kw += p_nom * unit_count; tot_kwmax += p_max * unit_count
        tot_export += min(p_lim, p_max or p_lim) * unit_count
        if p_lim > p_nom > 0:
            w.append(f"{tag}: limitarea configurată ({p_lim} kW) depășește puterea nominală ({p_nom} kW).")
        if supply_known and tri and not tri_grid:
            e.append(f"{tag}: invertor trifazat pe branșament monofazat — configurație incompatibilă.")
        if not tri and tri_grid and grid.get("supply") and not inv.get("phase"):
            w.append(f"{tag}: invertor monofazat pe racord trifazat — specifică faza (L1/L2/L3).")
        if not strings:
            if inv.get("kind") != "Invertor de baterie (AC)":
                w.append(f"{tag}: nu are stringuri definite.")
        if strings and not (n(inv.get("panel_voc")) and n(inv.get("panel_vmp"))):
            w.append(f"{tag}: lipsesc Voc/Vmp ale panoului — tensiunile stringurilor nu pot fi verificate.")
        if strings and inv.get("panel_coef_voc") in (None, ""):
            w.append(f"{tag}: lipsește coeficientul de temperatură Voc din fișa panoului — Voc la rece și verificarea Udc max nu se calculează.")
        if strings and inv.get("panel_coef_vmp") in (None, ""):
            w.append(f"{tag}: lipsește coeficientul de temperatură Vmp din fișa panoului — Vmp la cald și verificarea limitei MPPT min nu se calculează.")
        if strings and "Invertor de baterie" in str(inv.get("kind") or inv.get("type") or ""):
            e.append(f"{tag}: invertorul de baterie (AC) nu are intrări PV — eliminați stringurile sau schimbați tipul.")
        if strings and mppt_count and len({s["mppt"] for s in strings}) < min(mppt_count, len(strings)):
            w.append(f"{tag}: stringurile folosesc {len({s['mppt'] for s in strings})} din {mppt_count} MPPT — verificați repartizarea.")
        if strings and not isc_mppt_limit:
            w.append(f"{tag}: lipsește limita Isc max / MPPT din fișa invertorului; curentul de scurtcircuit al stringurilor nu poate fi verificat.")
        per_mppt = {}
        for si, s in enumerate(strings):
            st = f"{tag} / string {si + 1}"
            if vdc_max and s["voc_cold"] is not None and s["voc_cold"] > vdc_max:
                e.append(f"{st}: Voc la {tmin:g}°C = {s['voc_cold']:.0f} V depășește tensiunea maximă DC a invertorului ({vdc_max:g} V).")
            if mmax and s["vmp_stc"] > mmax:
                w.append(f"{st}: Vmp = {s['vmp_stc']:.0f} V peste limita superioară MPPT ({mmax:g} V).")
            if mmin and s["vmp_hot"] and s["vmp_hot"] < mmin:
                w.append(f"{st}: Vmp la cald ≈ {s['vmp_hot']:.0f} V sub limita inferioară MPPT ({mmin:g} V).")
            if mppt_count and s["mppt"] > mppt_count:
                e.append(f"{st}: MPPT {s['mppt']} inexistent (invertorul are {mppt_count} MPPT).")
            per_mppt.setdefault(s["mppt"], []).append(s)
        for m, ss in per_mppt.items():
            i_sum = sum(x["isc"] for x in ss)
            imp_panel = n(inv.get("panel_imp")) or (n(inv.get("panel_w")) / n(inv.get("panel_vmp")) if n(inv.get("panel_vmp")) else 0)
            i_work = imp_panel * len(ss)
            if len({x["panels"] for x in ss}) > 1:
                e.append(f"{tag} / MPPT {m}: stringuri în paralel cu număr diferit de panouri.")
            if imax and i_work and i_work > imax:
                e.append(f"{tag} / MPPT {m}: Imp total {i_work:.1f} A depășește curentul maxim de funcționare al intrării ({imax:g} A).")
            if isc_mppt_limit and i_sum > isc_mppt_limit:
                e.append(f"{tag} / MPPT {m}: Isc total {i_sum:.1f} A depășește limita de scurtcircuit a intrării ({isc_mppt_limit:g} A).")
        ratio = kwp / p_nom if p_nom else 0
        if ratio > 1.5:
            w.append(f"{tag}: raport DC/AC {ratio:.2f} — supradimensionare mare, verifică fișa producătorului.")

        # battery
        bat = inv.get("battery") or {}
        mode = inv.get("battery_mode") or "none"
        b_kwh = 0
        if mode == "own":
            b_kwh = n(bat.get("kwh")) * (int(n(bat.get("modules"), 1)) or 1)
            if not b_kwh and n(bat.get("ah")) and n(bat.get("voltage")):
                b_kwh = n(bat.get("ah")) * n(bat.get("voltage")) / 1000 * (int(n(bat.get("modules"), 1)) or 1)
            tot_kwh += b_kwh * unit_count
            coupling = str(bat.get("coupling") or "").strip().upper()
            if not coupling:
                w.append(f"{tag}: cuplarea bateriei nu este declarată; confirmați AC/DC din fișa tehnică înainte de validarea schemei.")
            if inv.get("type") == "On-grid" and coupling == "DC":
                e.append(f"{tag}: invertor on-grid cu baterie cuplată DC — necesită invertor hibrid sau cuplare AC.")
            bv, vmin_, vmax_ = n(bat.get("voltage")), n(inv.get("bat_v_min")), n(inv.get("bat_v_max"))
            if coupling == "DC":
                if bv and vmin_ and vmax_ and not (vmin_ <= bv <= vmax_):
                    e.append(f"{tag}: tensiunea bateriei ({bv:g} V) este în afara domeniului acceptat de invertor ({vmin_:g}–{vmax_:g} V) — baterie incompatibilă (HV/LV).")
                elif bv and not (vmin_ and vmax_):
                    w.append(f"{tag}: introduceți domeniul de tensiune baterie al invertorului (fișa tehnică) pentru verificarea compatibilității bateriei.")
            bi, ii = n(bat.get("i_max")), n(inv.get("bat_i_max"))
            if bi and ii and bi > ii:
                w.append(f"{tag}: bateria permite {bi:g} A, invertorul max. {ii:g} A — curentul va fi limitat de invertor (verificați dimensionarea protecției).")
            if not (bat.get("model") or b_kwh):
                w.append(f"{tag}: baterie asociată fără model/capacitate.")
        elif mode == "shared":
            sid = inv.get("shared_battery_id")
            if sid not in shared:
                e.append(f"{tag}: bateria comună selectată nu există.")
            else:
                shared_users.setdefault(sid, []).append(idx + 1)

        # AC cable & protection
        u = 400 if tri else 230
        ib = ((p_max * 1000 / (math.sqrt(3) * u * 0.95)) if tri else (p_max * 1000 / (u * 0.95))) if phase_known else 0
        ac = inv.get("ac") or {}
        mat, inst, L, k = ac.get("material") or "Cu", ac.get("install") or "C", n(ac.get("length_m")), n(ac.get("k_correction"), 1)
        loaded = 3 if tri else 2
        cur_in, cur_s = n(ac.get("breaker_a")), n(ac.get("section"))
        p_in = up(BREAKERS, ib) if ib else None
        p_s = None
        for sct in SECTIONS:
            if p_in and iz(sct, mat, inst, loaded, k) >= p_in and (not L or vdrop_ac(ib, L, sct, mat, tri) <= 3):
                p_s = sct; break
        prop["ac"] = {"breaker_a": p_in, "section": p_s, "ib": round(ib, 1) if phase_known else None,
                      "poles": ("4P" if tri else "2P") if phase_known else None, "phase_known": phase_known}
        if cur_in and cur_s and phase_known:
            izv = iz(cur_s, mat, inst, loaded, k)
            if cur_in < ib:
                e.append(f"{tag}: disjunctor AC {cur_in:g} A sub curentul de calcul Ib = {ib:.1f} A.")
            if cur_in > izv:
                e.append(f"{tag}: disjunctor AC {cur_in:g} A > Iz = {izv:.0f} A al cablului {cur_s:g} mm² {mat} ({inst}) — cablul nu este protejat.")
            du = vdrop_ac(ib, L, cur_s, mat, tri)
            if du > 3:
                w.append(f"{tag}: cădere de tensiune AC {du:.2f}% > 3% pe {L:g} m.")
            prop["ac"].update({"iz": round(izv, 1), "du": round(du, 2)})
        elif p_nom:
            if phase_known:
                w.append(f"{tag}: completează disjunctorul și secțiunea cablului AC (propunere: {p_in} A, {p_s} mm² {mat}).")
            else:
                w.append(f"{tag}: fazele racordului/invertorului nu sunt precizate; secțiunea și protecția AC nu se propun până la confirmarea monofazat/trifazat.")

        # DC cable & protections
        dc = inv.get("dc") or {}
        dmat, dL, ds = dc.get("material") or "Cu", n(dc.get("length_m")), n(dc.get("section"))
        isc_max = max([sum(x["isc"] for x in ss) for ss in per_mppt.values()] or [0])
        isc1 = max([x["isc"] for x in strings] or [0])
        i_dc = 1.25 * isc1
        vmp_any = max([x["vmp_stc"] for x in strings] or [0])
        voc_values = [x["voc_cold"] for x in strings if x.get("voc_cold") is not None]
        voc_cold_max = max(voc_values) if voc_values else 0
        p_ds = None
        for sct in SECTIONS[1:]:
            if iz(sct, dmat, None, 1, n(dc.get("k_correction"), 1), dc=True) >= i_dc and (not dL or vdrop_dc(isc1, dL, sct, dmat, vmp_any) <= 1):
                p_ds = sct; break
        par = max([len(ss) for ss in per_mppt.values()] or [0])
        fuse = up(GPV, 1.5 * isc1) if par >= 3 else None
        spd_ucpv = up([600, 800, 1000, 1100, 1200, 1500], voc_cold_max * 1.0) if voc_cold_max else None
        prop["dc"] = {"section": p_ds, "fuse": fuse, "fuse_note": "necesare (≥3 stringuri în paralel)" if fuse else "nu sunt necesare (≤2 stringuri în paralel/MPPT)",
                      "spd_ucpv": spd_ucpv, "i_design": round(i_dc, 1)}
        if ds and strings:
            izd = iz(ds, dmat, None, 1, n(dc.get("k_correction"), 1), dc=True)
            if izd < i_dc:
                e.append(f"{tag}: cablul DC {ds:g} mm² (Iz {izd:.0f} A) sub 1,25·Isc = {i_dc:.1f} A.")
            dud = vdrop_dc(isc1, dL, ds, dmat, vmp_any)
            if dud > 1:
                w.append(f"{tag}: cădere de tensiune DC {dud:.2f}% > 1% recomandat.")
            prop["dc"].update({"iz": round(izd, 1), "du": round(dud, 2)})
        spd = n(dc.get("spd_ucpv"))
        if spd and voc_cold_max and spd < voc_cold_max:
            e.append(f"{tag}: SPD DC Ucpv {spd:g} V sub Voc la rece ({voc_cold_max:.0f} V).")

        out_inv.append({"index": idx + 1, "count": unit_count, "tri": tri if phase_known else None, "phase_known": phase_known, "kwp": round(kwp, 3), "p_nom": p_nom, "p_max": p_max, "p_limit": p_lim,
                        "dc_ac_ratio": round(ratio, 2), "battery_kwh": round(b_kwh, 2), "strings": [{k2: (round(v, 1) if isinstance(v, float) else v) for k2, v in s.items()} for s in strings],
                        "isc_mppt_max": round(isc_max, 1), "voc_cold_max": round(voc_cold_max, 0), "proposals": prop, "errors": e, "warnings": w})
        errors += e; warnings += w

    for sid, users in shared_users.items():
        b = shared[sid]
        kwh = n(b.get("kwh")) * (int(n(b.get("modules"), 1)) or 1)
        if not kwh and n(b.get("ah")) and n(b.get("voltage")):
            kwh = n(b.get("ah")) * n(b.get("voltage")) / 1000 * (int(n(b.get("modules"), 1)) or 1)
        tot_kwh += kwh
        if len(users) > 1 and not b.get("parallel_supported"):
            errors.append(f"Baterie comună „{b.get('model') or sid}” folosită de invertoarele {users}: confirmă că producătorul permite funcționarea în paralel pe aceeași baterie.")
    for sid, b in shared.items():
        if sid not in shared_users:
            warnings.append(f"Bateria comună „{b.get('model') or sid}” nu este asociată niciunui invertor.")

    br_kw = n(grid.get("bransament_kw"))
    if br_kw and tot_export > br_kw:
        errors.append(f"Puterea evacuată totală ({tot_export:g} kW) depășește puterea aprobată a branșamentului ({br_kw:g} kW) — necesar spor de putere / ATR.")
    if supply_known and not tri_grid and tot_export > 3.68 * max(1, len(invs)) and invs:
        warnings.append("Racord monofazat cu putere mare — verifică cerințele OD privind dezechilibrul (uzual trifazat peste ~3,7–5 kW).")
    i_br = ((br_kw * 1000 / (math.sqrt(3) * 400 * 0.95)) if tri_grid else (br_kw * 1000 / (230 * 0.95))) if br_kw and supply_known else 0
    backup_enabled = any(bool((inv.get("backup") or {}).get("enabled")) for inv in invs)
    anti_size_auto = tot_kwp > 27 or tot_kw > 27 or i_br > 63
    anti_auto = anti_size_auto or backup_enabled
    anti = bool(grid.get("anti_required")) or anti_auto
    if backup_enabled:
        warnings.append("Circuitul de backup este selectat: schema propune protecție antiinsularizare pe branșamentul de rețea cu bobină de declanșare; soluția finală și dimensionarea se confirmă cu ATR-ul și schema producătorului.")
    main_proposal = up(MAIN_PROTECTION, i_br) if br_kw and supply_known else None
    anti_breaker_proposal = up(MAIN_BREAKERS, i_br) if anti and i_br else None
    if br_kw and i_br > MAIN_PROTECTION[-1]:
        warnings.append("Curentul de calcul al branșamentului depășește domeniul componentelor din catalogul de propuneri (2.000 A); este necesară proiectarea echipamentului de putere și selectivitatea protecțiilor.")
    column_section = None
    column_du = None
    column_iz = None
    column_length = n(grid.get("column_length"))
    column_material = grid.get("column_material") or "Cu"
    column_install = grid.get("column_install") or "D"
    if main_proposal:
        for sct in SECTIONS:
            ampacity = iz(sct, column_material, column_install, 3 if tri_grid else 2, n(grid.get("column_k_correction"), 1))
            drop = vdrop_ac(i_br, column_length, sct, column_material, tri_grid)
            if ampacity >= main_proposal and (not column_length or drop <= 3):
                column_section, column_du, column_iz = sct, drop, ampacity
                break
        if column_section is None:
            warnings.append("Coloana BMP–TG nu poate fi dimensionată automat în limitele tabelului disponibil (max. 120 mm² / pozare selectată). Pentru curenți mari sunt necesare conductoare în paralel și proiect dedicat; aplicația nu ghicește secțiunea.")
    selected_section = n(grid.get("column_section"))
    selected_breaker = n(grid.get("bmp_a")) or main_proposal or 0
    if selected_section and supply_known:
        selected_iz = iz(selected_section, column_material, column_install, 3 if tri_grid else 2, n(grid.get("column_k_correction"), 1))
        if selected_breaker > selected_iz:
            errors.append(f"Protecția BMP ({selected_breaker:g} A) depășește Iz = {selected_iz:.0f} A a coloanei BMP–TG ({selected_section:g} mm²) — cablul nu este protejat.")
        if column_length:
            selected_du = vdrop_ac(i_br, column_length, selected_section, column_material, tri_grid)
            if selected_du > 3:
                warnings.append(f"Căderea de tensiune pe coloana BMP–TG este {selected_du:.2f}% > 3% recomandat.")
    if selected_section and not supply_known:
        warnings.append("Tipul branșamentului lipsește; secțiunea și protecția coloanei nu pot fi verificate.")
    return {"totals": {"kwp": round(tot_kwp, 3), "inverters_kw": round(tot_kw, 2), "inverters_kw_max": round(tot_kwmax, 2),
                       "export_kw": round(tot_export, 2), "storage_kwh": round(tot_kwh, 2),
                       "panels": sum(s["panels"] * i.get("count", 1) for i in out_inv for s in i["strings"]),
                       "inverters": sum(i.get("count", 1) for i in out_inv)},
            "grid": {"tri": tri_grid if supply_known else None, "bransament_kw": br_kw, "i_br": round(i_br, 1) if br_kw and supply_known else 0,
                     "main_proposal": main_proposal, "main_section_proposal": column_section, "main_section_iz": round(column_iz, 1) if column_iz else None, "main_section_du": round(column_du, 2) if column_du is not None else None, "anti_breaker_proposal": anti_breaker_proposal, "anti_breaker_note": "întreruptor motorizat cu bobină de declanșare; confirmați curba, Icu/Ics și schema din ATR" if anti_breaker_proposal else None, "anti": anti, "anti_auto": anti_auto, "anti_backup": backup_enabled},
            "inverters": out_inv, "errors": errors, "warnings": warnings, "tmin": tmin,
            "note": "Valorile propuse sunt orientative (IEC 60364-5-52 / I7). Se validează de personal autorizat ANRE conform instrucțiunilor producătorului."}


def flatten(rec: dict) -> dict:
    cef = rec.get("cef") or {}
    invs = cef.get("inverters") or []
    if not invs:
        return rec
    r = check(cef)
    t = r["totals"]
    out = dict(rec)
    out["inverter"] = "; ".join(f"{i.get('brand_model') or '—'}" for i in invs)
    out["inverter_kw"] = t["inverters_kw"]
    out["inverter_count"] = sum(max(1, min(100, int(n(i.get("count"), 1) or 1))) for i in invs)
    models = {i.get("panel_model") for i in invs if i.get("panel_model")}
    out["panels"] = "; ".join(models)
    out["panel_count"] = t["panels"] or rec.get("panel_count", 0)
    ws = {n(i.get("panel_w")) for i in invs if n(i.get("panel_w"))}
    out["panel_w"] = next(iter(ws)) if len(ws) == 1 else "/".join(f"{w:g}" for w in ws)
    out["_kwp"] = t["kwp"]
    bats = [i.get("battery", {}).get("model") for i in invs if i.get("battery_mode") == "own"] + \
           [b.get("model") for b in cef.get("shared_batteries") or []]
    out["battery"] = "; ".join(b for b in bats if b) or rec.get("battery")
    out["battery_kwh"] = t["storage_kwh"] or rec.get("battery_kwh")
    out.setdefault("power", t["export_kw"])
    if not rec.get("power"):
        out["power"] = t["export_kw"]
    g = cef.get("grid") or {}
    if g.get("supply"):
        out["supply"] = g["supply"]
    if g.get("bransament_kw"):
        out["bransament_kw"] = g["bransament_kw"]
    return out


def from_legacy(rec: dict) -> dict:
    """Builds cef from classic dossier fields (no invented values) when cef.inverters is empty."""
    cef = dict(rec.get("cef") or {})
    if cef.get("inverters") or not (rec.get("inverter") or rec.get("inverter_kw") or rec.get("panel_count")):
        return rec
    cnt = max(1, int(n(rec.get("inverter_count"), 1) or 1))
    pc = int(n(rec.get("panel_count"), 0) or 0)
    legacy_supply = rec.get("supply") or (cef.get("grid") or {}).get("supply")
    legacy_phase = ("Trifazat" if "mono" not in str(legacy_supply).lower() else "Monofazat") if legacy_supply else None
    bat = None
    if rec.get("battery") or rec.get("battery_kwh"):
        bat = {"model": rec.get("battery"), "kwh": n(rec.get("battery_kwh"), None), "voltage": n(rec.get("battery_v"), None), "ah": n(rec.get("battery_ah"), None), "modules": 1}
    invs = []
    for k in range(cnt):
        share = pc // cnt + (1 if k < pc % cnt else 0)
        invs.append({"brand_model": rec.get("inverter"), **({"phases": legacy_phase} if legacy_phase else {}), "p_nom_kw": n(rec.get("inverter_kw"), None),
                     "type": "hibrid" if bat else "on-grid", "panel_model": rec.get("panels"), "panel_w": n(rec.get("panel_w"), None),
                     "strings": [{"panels": share, "mppt": 1, "aggregate": True}] if share else [],
                     "battery_mode": "own" if bat and k == 0 else "none", "battery": bat if k == 0 else None, "legacy": True})
    grid = dict(cef.get("grid") or {})
    for gk, rk in (("supply", "supply"), ("bransament_kw", "bransament_kw"), ("grounding_ohm", "grounding_ohm")):
        if grid.get(gk) in (None, "") and rec.get(rk) not in (None, ""):
            grid[gk] = n(rec[rk], None) if gk != "supply" else rec[rk]
    cef.update({"inverters": invs, "grid": grid, "from_legacy": True})
    return {**rec, "cef": cef}
