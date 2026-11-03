import math
import re
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Depends, Header, Query, Response

import server as S
import cef as CEF

db, api, get_current_user = S.db, S.api_router, S.get_current_user

INV_FIELDS = [("brand_model", "Invertor — marcă/model", "text"), ("ac.breaker_a", "Întreruptor AC (A)", "num"), ("ac.curve", "Curbă întreruptor AC", "text"),
              ("ac.section", "Cablu AC — secțiune (mm²)", "num"), ("ac.length_m", "Cablu AC — lungime (m)", "num"), ("ac.cable_type", "Cablu AC — tip", "text"),
              ("rcd_type", "DDR — tip (A/B/F)", "text"), ("rcd_ma", "DDR — IΔn (mA)", "num"), ("dc.section", "Cablu DC — secțiune (mm²)", "num"),
              ("dc.length_m", "Cablu DC — lungime (m)", "num"), ("dc.switch", "Separator DC", "text"), ("dc.spd_ucpv", "SPD DC Ucpv (V)", "num"),
              ("dc.fuse_a", "Siguranțe gPV (A)", "num"), ("battery.model", "Baterie — model", "text"), ("battery.fuse_a", "Baterie — protecție DC (A)", "num")]
GRID_FIELDS = [("bmp_a", "BMP — întreruptor (A)", "num"), ("tg_breaker_a", "TG — întreruptor general (A)", "num"), ("spd_ac", "SPD AC (tip)", "text"),
               ("earthing", "Sistem legare la pământ", "text"), ("column_section", "Coloană BMP→TG — secțiune (mm²)", "num"),
               ("column_length", "Coloană BMP→TG — lungime (m)", "num"), ("anti_relay", "Releu protecție interfață", "text")]
PATH_RE = re.compile(r"^cef\.(grid\.[a-z_]+|inverters\.\d+\.[a-z_]+(\.[a-z_]+)?)$")


def get_path(d, parts):
    for p in parts:
        d = (d[int(p)] if p.isdigit() and isinstance(d, list) and int(p) < len(d) else None) if isinstance(d, list) else (d or {}).get(p)
    return d


@api.get("/sld/{item_id}/values")
async def sld_values(item_id: str, user: dict = Depends(get_current_user)):
    rec = CEF.from_legacy(await S.check_access(user, "prosumator", item_id))
    cef = rec.get("cef") or {}
    man = set(cef.get("manual") or [])
    auto = set(cef.get("auto_filled") or [])
    row = lambda path, lbl, t: {"path": path, "label": lbl, "type": t, "value": get_path(rec, path.split(".")), "manual": path in man, "auto": path in auto}
    groups = [{"title": "Racord / BMP / TG", "rows": [row(f"cef.grid.{k}", l, t) for k, l, t in GRID_FIELDS]}]
    for i, inv in enumerate(cef.get("inverters") or []):
        rows = [row(f"cef.inverters.{i}.{k}", l, t) for k, l, t in INV_FIELDS if not (k.startswith("battery") and inv.get("battery_mode") != "own")]
        groups.append({"title": f"INV {i + 1} — {inv.get('brand_model') or 'invertor'}", "rows": rows})
    return {"groups": groups, "from_legacy": bool(cef.get("from_legacy"))}


@api.put("/sld/{item_id}/values")
async def sld_values_save(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    S.guard("prosumator", user, write=True)
    rec = await S.check_access(user, "prosumator", item_id)
    cef = rec.get("cef") or {}
    if not cef.get("inverters"):
        raise HTTPException(status_code=400, detail="Preluați întâi datele în configuratorul CEF (butonul din schemă)")
    vals = (await request.json()).get("values") or {}
    if not isinstance(vals, dict):
        raise HTTPException(status_code=400, detail="Format invalid")
    allowed = {f"cef.grid.{k}": t for k, _, t in GRID_FIELDS} | {f"cef.inverters.{i}.{k}": t for i in range(len(cef["inverters"])) for k, _, t in INV_FIELDS}
    man = set(cef.get("manual") or [])
    for path, v in list(vals.items())[:200]:
        if path not in allowed or not PATH_RE.match(path):
            raise HTTPException(status_code=400, detail=f"Câmp nepermis: {path}")
        if allowed[path] == "num" and v not in (None, ""):
            try:
                v = float(str(v).replace(",", "."))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Valoare numerică invalidă: {path}")
            if not math.isfinite(v) or v < 0:
                raise HTTPException(status_code=400, detail=f"Valoare numerică invalidă: {path}")
        elif v not in (None, ""):
            v = str(v)[:120]
        parts = path.split(".")[1:]
        d = cef
        for p in parts[:-1]:
            d = d[int(p)] if p.isdigit() else d.setdefault(p, {})
        d[parts[-1]] = v if v not in ("",) else None
        man.add(path)
    cef["manual"] = sorted(man)
    cef["auto_filled"] = [p for p in cef.get("auto_filled") or [] if p not in vals]
    await db.prosumator.update_one({"id": item_id}, {"$set": {"cef": cef, "updated_at": datetime.now(timezone.utc).isoformat()}})
    await S.audit(user, "update", "prosumator", item_id, [f"schemă: {p}" for p in vals])
    return {"ok": True, "changed": len(vals), "cef": cef}


# ---------------- Proces-verbal PIF (teste și verificări la punerea în funcțiune) ----------------
from pif_doc import CHECKS, RES, pif_rows  # noqa: E402
import pif_doc as PIFDOC  # noqa: E402


@api.get("/dossier/{item_id}/pif")
async def pif_get(item_id: str, user: dict = Depends(get_current_user)):
    rec = CEF.from_legacy(await S.check_access(user, "prosumator", item_id))
    cef = rec.get("cef") or {}
    inverter_units = []
    for i, inverter in enumerate(cef.get("inverters") or []):
        count = max(1, min(100, int(CEF.n(inverter.get("count") or inverter.get("quantity"), 1) or 1)))
        for unit in range(count):
            inverter_units.append({"key": f"{i}.{unit}", "label": f"Invertor {i + 1}" + (f" — unitatea {unit + 1}" if count > 1 else ""),
                                   "model": inverter.get("brand_model") or ""})
    battery_units = []
    for i, inverter in enumerate(cef.get("inverters") or []):
        battery = inverter.get("battery") or {}
        if inverter.get("battery_mode") != "own" or not battery.get("model"):
            continue
        count = max(1, min(100, int(CEF.n(battery.get("modules") or battery.get("count"), 1) or 1)))
        for unit in range(count):
            battery_units.append({"key": f"inv-{i}-{unit}", "label": f"Baterie invertor {i + 1}" + (f" — modulul {unit + 1}" if count > 1 else ""),
                                  "model": battery.get("model") or ""})
    for i, battery in enumerate(cef.get("shared_batteries") or []):
        count = max(1, min(100, int(CEF.n(battery.get("modules") or battery.get("count"), 1) or 1)))
        for unit in range(count):
            battery_units.append({"key": f"shared-{i}-{unit}", "label": f"Baterie {i + 1}" + (f" — modulul {unit + 1}" if count > 1 else ""),
                                  "model": battery.get("model") or ""})
    panel_count = max(0, min(1000, int(CEF.check(cef).get("totals", {}).get("panels") or rec.get("panel_count") or 0)))
    return {"pif": rec.get("pif") or {}, "strings": pif_rows(rec), "checks": CHECKS, "results": RES,
            "inverters": [{"n": i + 1, "model": v.get("brand_model")} for i, v in enumerate(cef.get("inverters") or [])],
            "inverter_units": inverter_units, "battery_units": battery_units, "panel_count": panel_count,
            "grounding_ohm": cef.get("grid", {}).get("grounding_ohm") or rec.get("grounding_ohm")}


@api.put("/dossier/{item_id}/pif")
async def pif_save(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    S.guard("prosumator", user, write=True)
    await S.check_access(user, "prosumator", item_id)
    b = await request.json()
    if not isinstance(b, dict) or any(not isinstance(b.get(k) or {}, dict) for k in ("strings", "inv", "checks", "serials")):
        raise HTTPException(status_code=400, detail="Format invalid")
    clean = lambda v: str(v)[:120] if v not in (None,) else ""
    serials = b.get("serials") or {}
    if any(not isinstance(serials.get(k) or {}, dict) for k in ("inverters", "batteries")):
        raise HTTPException(status_code=400, detail="Format seriale invalid")
    serial_lists = serials.get("panels") or []
    if isinstance(serial_lists, str):
        serial_lists = serial_lists.splitlines()
    if not isinstance(serial_lists, list):
        raise HTTPException(status_code=400, detail="Format serii panouri invalid")
    serial_data = {
        "inverters": {str(k)[:30]: clean(v) for k, v in (serials.get("inverters") or {}).items() if clean(v)},
        "panels": [clean(v) for v in serial_lists[:1000]],
        "batteries": {str(k)[:30]: clean(v) for k, v in (serials.get("batteries") or {}).items() if clean(v)},
    }
    pif = {"date": clean(b.get("date")), "operator": clean(b.get("operator")), "instruments": clean(b.get("instruments")), "notes": str(b.get("notes") or "")[:1000],
           "strings": {k: {f: clean(v.get(f)) for f in ("voc", "isc", "riso_p", "riso_n", "polarity")} for k, v in (b.get("strings") or {}).items() if isinstance(v, dict)},
           "inv": {k: {f: clean(v.get(f)) for f in ("u_ac", "f_hz", "p_kw", "anti_s", "rcd_ms", "rcd_ma")} for k, v in (b.get("inv") or {}).items() if isinstance(v, dict)},
           "checks": {str(k): v for k, v in (b.get("checks") or {}).items() if v in RES}, "grounding_measured": clean(b.get("grounding_measured")),
           "serials": serial_data,
           "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("email")}
    await db.prosumator.update_one({"id": item_id}, {"$set": {"pif": pif}})
    await S.audit(user, "update", "prosumator", item_id, ["proces-verbal PIF"])
    return {"pif": pif}


@api.get("/dossier/{item_id}/pif/pdf")
async def pif_pdf(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    rec, client, s, _ = await S.dossier_ctx(user, item_id)
    pdf = PIFDOC.render(rec, client, s)
    if rec.get("is_test"):
        import opis as OPIS
        pdf = OPIS.mark_test(pdf)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": S.disp("inline", f"PV_PIF_{(client.get('name') or 'dosar').replace(' ', '_')}.pdf")})
