import io
from html import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import docgen as D
import cef as CEF

M = D.M
DOCS = [("a", "copia actului de identitate / certificatului de înregistrare la registrul comerțului / alte autorizații legale de funcționare"),
        ("b", "certificatul constatator (doar prosumator persoană juridică)"),
        ("c", "certificatul de urbanism (doar loc de consum și de producere nou)"),
        ("d", "planul de situație la scară (doar loc nou)"),
        ("e", "PUZ / PUD aprobat, dacă a fost solicitat prin certificatul de urbanism (doar loc nou)"),
        ("f", "actul de proprietate / dreptul de folosință asupra terenului, incintei sau clădirii (doar loc nou)"),
        ("g", "autorizația de construire, pentru organizare de șantier (doar loc nou)"),
        ("h", "procesul-verbal de recepție la terminarea lucrărilor instalației de producere"),
        ("i", "buletinul de încercare a prizei de pământ"),
        ("j", "certificatele de conformitate și fișele tehnice ale invertoarelor și unităților generatoare"),
        ("k", "schema electrică monofilară a instalației de producere și modul de racordare, cu protecțiile și reglajele")]
EXISTING_ONLY, NEW_ONLY = set("hijk"), set("cdefg")


def _battery_items(pros: dict, rec: dict, flat: dict) -> list:
    cef = (pros or {}).get("cef") or {}
    items = []
    for inv in cef.get("inverters") or []:
        if inv.get("battery_mode") == "own" and isinstance(inv.get("battery"), dict):
            battery = dict(inv["battery"])
            inverter_count = max(1, int(D.num(inv.get("count") or inv.get("quantity")) or 1))
            module_count = max(1, int(D.num(battery.get("modules")) or 1))
            battery["modules"] = module_count * inverter_count
            items.append(battery)
    items.extend(b for b in cef.get("shared_batteries") or [] if isinstance(b, dict))
    if not items and (flat.get("battery") or rec.get("battery") or rec.get("storage")):
        model = flat.get("battery") or rec.get("battery") or rec.get("storage")
        items.append({
            "model": model if isinstance(model, str) else model.get("model"),
            "modules": (model.get("modules") if isinstance(model, dict) else None) or rec.get("battery_count"),
            "kwh": (model.get("kwh") if isinstance(model, dict) else None) or flat.get("battery_kwh") or rec.get("battery_kwh"),
            "ah": (model.get("ah") if isinstance(model, dict) else None) or rec.get("battery_ah"),
            "voltage": (model.get("voltage") if isinstance(model, dict) else None) or rec.get("battery_v"),
            "coupling": (model.get("coupling") if isinstance(model, dict) else None) or rec.get("battery_coupling"),
        })
    return items


def _battery_table(items: list) -> list:
    rows = [["Model baterie", "Buc.", "Capacitate totală", "Ah / unitate", "Tensiune", "Imax / unitate", "Cuplare"]]
    for b in items:
        modules, kwh = b.get("modules"), b.get("kwh")
        total = M
        try:
            if modules not in (None, "") and kwh not in (None, ""):
                total = f"{D.fmt(float(str(modules).replace(',', '.')) * float(str(kwh).replace(',', '.')), 2)} kWh ({modules} × {kwh} kWh)"
            elif kwh not in (None, ""):
                total = f"{kwh} kWh / unitate"
        except (TypeError, ValueError):
            total = f"{kwh} kWh / unitate" if kwh not in (None, "") else M
        rows.append([escape(str(b.get("model") or M)), escape(str(modules or M)), escape(total),
                     escape(str(b.get("ah") or M)), escape(str(b.get("voltage") or M)),
                     escape(str(b.get("i_max") or M)), escape(str(b.get("coupling") or M)).upper()])
    return rows


def box(v):
    return "<b>[X]</b>" if v else "[  ]"


def render_anexa1(rec: dict, client: dict, s: dict, pros: dict, attached: set, op: str = "") -> bytes:
    from atr_doc import OP_NAMES
    st = D.S
    c = client or {}
    p = CEF.flatten(pros) if pros else {}
    g = lambda d, k: escape(str(d.get(k))) if d.get(k) not in (None, "") else M
    P = lambda t, k="p": Paragraph(t, st[k])
    new = rec.get("request_kind") == "nou"
    mods = "—" if new else (f"alimentare existentă {g(rec, 'current_supply')}, putere aprobată {g(rec, 'approved')} kW; se solicită {g(rec, 'requested')} kW, "
                            f"alimentare {g(rec, 'new_supply')}; BMP: {g(rec, 'bmp')}. " + escape(rec.get("changes") or rec.get("purpose") or ""))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm, title="Anexa 1 — Cerere de racordare")
    T = lambda rows, w: D.pdf_table(rows, w, True, 7.6, 178)
    story = [P(f"Anexa 1 la Procedura aprobată prin Ordinul ANRE nr. 69/2020 — formular pentru <b>{escape(OP_NAMES.get(op, 'operator de distribuție neselectat'))}</b>" + (" (model Delgaz Grid — cerere de racordare prosumator)" if op == "delgaz" else ""), "small"), P("Nr. înregistrare ____________ / Data ____________", "small"),
             P("CERERE DE RACORDARE", "h"),
             P("pentru un loc de consum şi de producere care deţine instalaţii de producere a energiei electrice din surse regenerabile cu puteri electrice instalate de cel mult 27 kW pe loc de consum", "sub"),
             P(f"{box(new)} Loc de consum şi de producere nou<br/>{box(not new)} Loc de consum existent cu modificarea unor elemente de natură tehnică cu depăşirea puterii absorbite aprobate anterior"),
             P(f"Utilizatorul <b>{g(c, 'name')}</b>, cu domiciliul/sediul în judeţul {g(c, 'county')}, localitatea {g(c, 'locality')}, adresa {g(c, 'address')}, "
               f"codul poştal {g(c, 'postal_code')}, telefon {g(c, 'phone')}, cod fiscal/CNP {g(c, 'idcode')}, nr. registrul comerţului {g(c, 'regcom') if c.get('regcom') else '—'}, "
               f"reprezentat prin {g(c, 'rep_name') if c.get('rep_name') else '—'}, în calitate de {g(c, 'rep_role') if c.get('rep_role') else '—'}, contul {g(c, 'iban')} deschis la banca {g(c, 'bank')}, "
               f"reprezentat prin împuternicit / reprezentant al operatorului economic atestat <b>{g(s, 'company')}</b>, cu sediul în {g(s, 'address')}, telefon {g(s, 'phone')}, "
               f"e-mail {g(s, 'email')}, nr./data act autorizare {g(s, 'anre_attest')}{(' / ' + escape(str(s.get('anre_issued')))) if s.get('anre_issued') else ''}, emis de {g(s, 'anre_issuer') if s.get('anre_issuer') else 'ANRE'}"),
             P("solicit prin prezenta:"),
             P(f"{box(rec.get('ask_atr', True))} obţinerea avizului tehnic de racordare pentru obiectivul situat în judeţul {g(c, 'county')}, localitatea {g(c, 'locality')}, "
               f"adresa {g(rec, 'address') if rec.get('address') else g(c, 'address')}, nr. CF {g(c, 'cf_nr')}, nr. cadastral {g(c, 'cadastral_nr')}, şi certificarea calităţii de prosumator;<br/>"
               f"{box(rec.get('ask_meter'))} înlocuirea contorului existent la locul de consum existent cu un contor de măsurare a energiei electrice în ambele sensuri;<br/>"
               f"{box(rec.get('ask_probe'))} punerea sub tensiune pentru perioada de probe a instalaţiei de producere a energiei electrice racordate la locul de consum existent."),
             P(f"Data estimată solicitată pentru punerea sub tensiune finală a instalaţiei de utilizare*): {g(rec, 'energize_date') if new else '—'}"),
             P(f"Modul de alimentare actual al obiectivului şi descrierea modificărilor de natură tehnică faţă de situaţia anterioară**): {mods}"),
             P("*) Se completează numai în cazul locului de consum şi de producere nou. **) Se completează numai în cazul locului de consum existent cu depăşirea puterii absorbite aprobate anterior.", "small"),
             P("1. Date tehnice şi energetice pentru locul de consum:", "b"),
             P(f"1.1. Puterea aprobată — Puterea maximă simultan absorbită din reţea: <b>{g(rec, 'requested')}</b> kW / <b>{g(rec, 'requested_kva')}</b> kVA"),
             P(f"1.2. Tipul de racord solicitat: {box(rec.get('new_supply') == 'Monofazat')} monofazat {box(rec.get('new_supply') == 'Trifazat')} trifazat"),
             P("1.3. Lista receptoarelor cu precizarea puterii şi a tensiunii nominale:")]
    recs = rec.get("receptors") or []
    story.append(T([["Nr. crt.", "Denumire receptoare", "Puterea instalată Pi (kW)", "Observaţii (caracteristici, regim de funcţionare)"]] +
                   [[str(i + 1), escape(r.get("name") or ""), escape(str(r.get("kw") or "")), escape(r.get("notes") or "")] for i, r in enumerate(recs)] +
                   ([["", "", "", ""]] * (0 if recs else 3)) + [["", "Total Pi (kW)", D.fmt(sum(D.num(r.get("kw")) for r in recs)) if recs else M, ""]], [8, 40, 18, 34]))
    story += [Spacer(1, 4), P("2. Date tehnice şi energetice pentru locul de producere:", "b"),
              P(f"2.1. Puterea aprobată — Puterea maximă simultan evacuată în reţea: <b>{g(p, 'power')}</b> kW / <b>{g(p, 'apparent_kva')}</b> kVA"),
              P("2.2. Generatoare fotovoltaice:")]
    invs = (pros.get("cef") or {}).get("inverters") or [] if pros else []
    rows = [["Nr. crt.", "Nr. panouri", "Tip", "Pi panou (c.c.) (kW)", "Pi total panouri (c.c.) (kW)", "Pmax debitat (c.c.) (kW)", "Pi total panouri pe 1 invertor (kW)", "Obs."]]
    irows = [["Nr. crt.", "Nr. invertoare", "Tipul invertoarelor", "Un invertor (c.a.) (V)", "Pi invertor (c.a.) (kW)", "Pmax evacuată în reţea (kW)", "Obs."]]
    export_limit_notes = []
    for i, inv in enumerate(invs):
        unit_count = max(1, int(D.num(inv.get("count") or inv.get("quantity")) or 1))
        panels_per_inverter = sum(int(D.num(x.get("panels"))) for x in inv.get("strings") or [])
        total_panels = panels_per_inverter * unit_count
        w = D.num(inv.get("panel_w")) / 1000
        total_kwp = D.fmt(total_panels * w, 3) if total_panels and w else ""
        per_inverter_kwp = D.fmt(panels_per_inverter * w, 3) if panels_per_inverter and w else ""
        rows.append([str(i + 1), str(total_panels or ""), escape(inv.get("panel_model") or ""), D.fmt(w, 3) if w else "",
                     total_kwp, total_kwp, per_inverter_kwp, ""])
        rated_kw = D.num(inv.get("p_nom_kw"))
        max_kw = D.num(inv.get("p_max_kw")) or rated_kw
        configured_limit = D.num(inv.get("p_limit_kw"))
        export_per_inverter = min(configured_limit, max_kw) if configured_limit and configured_limit > 0 and max_kw > 0 else (
            configured_limit if configured_limit and configured_limit > 0 else max_kw)
        export_total = D.fmt(export_per_inverter * unit_count, 3) if export_per_inverter and export_per_inverter > 0 else ""
        limit_note = (f"{inv.get('brand_model') or 'Invertor'}: {configured_limit:g} kW/invertor × {unit_count} buc. = {configured_limit * unit_count:g} kW total"
                      if configured_limit and configured_limit > 0 else
                      f"{inv.get('brand_model') or 'Invertor'}: limită de injecție nedeclarată")
        export_limit_notes.append(limit_note)
        irows.append([str(i + 1), str(unit_count), escape(inv.get("brand_model") or ""),
                      "400" if "tri" in str(inv.get("phases") or "").lower() else "230" if inv.get("phases") else "",
                      escape(str(rated_kw if rated_kw > 0 else "")), export_total,
                      "Limită setată" if configured_limit and configured_limit > 0 else "Nedeclarată"])
    if not invs:
        rows.append([""] * 8); irows.append([""] * 7)
    story += [T(rows, [7, 9, 22, 11, 13, 12, 14, 8]), Spacer(1, 3), P("Invertoare:"), T(irows, [7, 10, 30, 12, 12, 16, 9]),
              P("Limită de injecție declarată: " + escape("; ".join(export_limit_notes) or "nedeclarată în configurarea invertorului."), "small"), Spacer(1, 3),
              P(f"2.3. Serviciile interne ale instalaţiei de producere: Pi servicii interne {g(p, 'internal_pi')} kW; Puterea maximă simultan absorbită servicii interne {g(p, 'internal_pmax')} kW"),
              P("Anexez prezentei următoarele documente:", "b")]
    for k, t in DOCS:
        na = (k in NEW_ONLY and not new) or (k in EXISTING_ONLY and new) or (k == "b" and "jurid" not in str(c.get("kind") or "").lower())
        story.append(P(f"{box(k in attached)} {k}) {t}{' — nu este cazul' if na and k not in attached else ''}", "li"))
    batteries = _battery_items(pros or {}, rec, p)
    bat = bool(batteries)
    story += [P("În sprijinul solicitării mele transmit următoarele informaţii privind:"),
              P(f"a) deţinerea de sisteme de stocare a energiei electrice: {box(not bat)} NU {box(bat)} DA."
                + (f" Detalii scheme de alimentare: {', '.join(str(b.get('coupling') or 'nespecificată').upper() for b in batteries)}." if bat else "")),
              *([T(_battery_table(batteries), [40, 10, 38, 18, 18, 22, 32])] if bat else []),
              P(f"b) echipamente de măsurare montate în instalaţiile de utilizare, altele decât ale operatorului: {box(not p.get('smart_meter_type'))} NU {box(p.get('smart_meter_type'))} DA"),
              T([["Nr. crt.", "Serie contor", "Tip contor", "Date tehnice"], ["1", g(p, "smart_meter_serial") if p.get("smart_meter_type") else "", g(p, "smart_meter_type") if p.get("smart_meter_type") else "",
                 g(p, "smart_meter_data") if p.get("smart_meter_type") else ""]], [8, 30, 30, 32]),
              Spacer(1, 6), P("Declar pe propria răspundere că datele şi informaţiile cuprinse în prezenta cerere sunt autentice şi că documentele anexate, în copie, sunt conforme cu originalul."),
              D.pdf_sign([f"Data: {escape(D.ro_date(rec.get('date')) or M)}"], ["Solicitant / Împuternicit,", f"<b>{g(c, 'name')}</b> / <b>{g(s, 'company')}</b>", s.get("rep") and escape(s["rep"]) or M,
                                                                                    "(numele, prenumele şi semnătura)", "(ștampilă)"], s)]
    doc.build(story)
    return buf.getvalue()
