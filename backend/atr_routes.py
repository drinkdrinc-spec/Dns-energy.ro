import os
import re
import hmac
import uuid
import secrets
import logging
import io
import zipfile
import httpx
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta, date
from html import escape as hesc
from typing import Optional

from fastapi import HTTPException, Request, Depends, BackgroundTasks, Response
from pypdf import PdfReader, PdfWriter

import server as S
import atr_doc as ATR
from mailer import send_email

db, api, get_current_user = S.db, S.api_router, S.get_current_user
logger = logging.getLogger("d-energy.atr")
OP_DOMAINS = {"deer": ("distributie-energie.ro",), "delgaz": ("delgaz-grid.ro", "delgaz.ro"), "rer": ("reteleelectrice.ro",),
              "oltenia": ("distributieoltenia.ro", "evryo.ro")}
DEFAULT_TERMS = {"check_days": 10, "issue_days": 30, "remind_days": 3}
LINK_DAYS = 30
DEER_GDPR_URL = "https://www.distributie-energie.ro/wp-content/uploads/2026/04/Informare-generala-site-v-feb-2026.pdf"
DEER_FORMS_URL = "https://www.distributie-energie.ro/racordare-la-retea-2/"

# Current official Retele Electrice (RER) forms. The operator page is the
# source of truth; direct PDF URLs are used only when the registry is empty.
RER_FORMS_URL = "https://www.reteleelectrice.ro/cereri-documente/"
RER_STORAGE_FORM_URL = "https://www.reteleelectrice.ro/wp-content/uploads/Anexa-aferenta-instalatiilor-de-stocare.pdf"

DELGaz_FORMS_URL = "https://delgaz.ro/energie-electrica/prosumatori"
DELGaz_GDPR_URLS = {
    "Nota de informare privind prelucrarea datelor personale": "https://delgaz.ro/getattachment/d30fba83-32ae-405a-b5fe-c36bfe4ad767/Nota-de-informare-cu-privire-la-prelucrarea-datelor-cu-caracter-personal.pdf",
    "Nota de informare DEGR supliment": "https://delgaz.ro/getattachment/9928a34a-405a-4061-9ffd-7204ed908dd3/Nota-de-infromare-DEGR-supliment.pdf",
}
DELGaz_FORM_PDFS = {
    1: "https://delgaz.ro/getattachment/91755a0d-890c-4357-917a-ac5128ec735a/Cerere_de_racordare_prosumator-Anexa-1.pdf",
    2: "https://delgaz.ro/getattachment/90cf84fa-708e-46a7-b60b-266364c50098/Notificare_racordare_prosumator-Anexa-2.pdf",
    3: "https://delgaz.ro/getattachment/e2021264-a5fa-43f4-95d6-3975d8960202/Notificare_certificare_calitate_prosumator-Anexa-3.pdf",
    4: "https://delgaz.ro/getattachment/d1de9dd7-849d-458f-aed2-3f3fc1694eaf/Cerere_de_racordare_prosumator_programe-Anexa-4.pdf",
    5: "https://delgaz.ro/getattachment/f0d42548-d9fe-4275-b694-6bfc075842f3/Notificare_racordare_10-8kW-Anexa-5.pdf",
}

OLTENIA_FORMS_URL = "https://www.distributieoltenia.ro/ro/informatii-utile/prosumatori/formularele-necesare-pentru-a-deveni-prosumator.html"
OLTENIA_FORM_PDFS = {
    1: "https://www.distributieoltenia.ro/resources/ckfinder/core/connector/php/connector.php?command=Proxy&currentFolder=%2FDO%2FINFORMATII+UTILE%2FFormulare+racordare%2F2024%2F26.01.2024%2F&fileName=01-03-01_P03-F16_Cerere+racordare+prosumatori_LC+noi+sau+spor+putere_anexa+1_rev06.pdf&hash=24460cc7b9aefcd5&lang=en&type=Files",
    2: "https://www.distributieoltenia.ro/resources/ckfinder/core/connector/php/connector.php?command=Proxy&lang=en&type=Files&currentFolder=%2FDO%2FINFORMATII%20UTILE%2FProsumatori%2Finformatii%20prosumatori%20racordati%2F&hash=24460cc7b9aefcd5&fileName=01-03-01_P03-F18_Notificare%20racordare%20prosumator%20LC%20existent%20_anexa%202_rev06.pdf",
    3: "https://www.distributieoltenia.ro/resources/ckfinder/core/connector/php/connector.php?command=Proxy&lang=en&type=Files&currentFolder=%2FDO%2FINFORMATII%20UTILE%2FFormulare%20racordare%2F2023%2F&hash=24460cc7b9aefcd5&fileName=01-03-01_P03-F17_Notificare%20certificarea%20calitatii%20de%20prosumator%20LC%20producator%20existent_anexa%203_rev05.doc.pdf",
    4: "https://www.distributieoltenia.ro/resources/ckfinder/core/connector/php/connector.php?command=Proxy&lang=en&type=Files&currentFolder=%2FDO%2FINFORMATII%20UTILE%2FProsumatori%2F2023%2F11.09.2023%2F&hash=24460cc7b9aefcd5&fileName=01-03-01_P03-F15_CerereDeRacordProsuMPtLcExistCareAccesProgDeFinan%C8%9BPrivInstlDeCE-PtProdDeEnElDin%20SursRegen_Anexa%204_rev05.pdf",
    5: "https://www.distributieoltenia.ro/resources/ckfinder/core/connector/php/connector.php?command=Proxy&lang=en&type=Files&currentFolder=%2FDO%2FINFORMATII%20UTILE%2FProsumatori%2F2023%2F08.06.2023%2F&hash=24460cc7b9aefcd5&fileName=01-03-01_P03-F28_NotifRacordLC_LC%26proddin%20surse%20renerabileProsumPutereSub%2010%2C8kw_rev_01.pdf",
}

RER_FORM_PDFS = {
    1: "https://www.reteleelectrice.ro/wp-content/uploads/rer-anexa-1-cerere-racordare.pdf",
    2: "https://www.reteleelectrice.ro/wp-content/uploads/rer-anexa-2-cerere-racordare.pdf",
    3: "https://www.reteleelectrice.ro/wp-content/uploads/rer-anexa-3-cerere-racordare.pdf",
    4: "https://www.reteleelectrice.ro/wp-content/uploads/rer-anexa-4-cerere-racordare.pdf",
    5: "https://www.reteleelectrice.ro/wp-content/uploads/rer-anexa-5-cerere-racordare.pdf",
}



def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def orthodox_easter(y: int) -> date:
    a, b, c = y % 4, y % 7, y % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    m, day = divmod(d + e + 114, 31)
    return date(y, m, day + 1) + timedelta(days=13)


def ro_holidays(y: int) -> dict:
    e = orthodox_easter(y)
    h = {}
    for d, lbl in ((date(y, 1, 1), "Anul Nou"), (date(y, 1, 2), "Anul Nou"), (date(y, 1, 6), "Boboteaza"), (date(y, 1, 7), "Sf. Ioan Botezătorul"),
                   (date(y, 1, 24), "Unirea Principatelor Române"), (e - timedelta(days=2), "Vinerea Mare"), (e, "Paștele ortodox"),
                   (e + timedelta(days=1), "A doua zi de Paște"), (date(y, 5, 1), "Ziua Muncii"), (date(y, 6, 1), "Ziua Copilului"),
                   (e + timedelta(days=49), "Rusaliile"), (e + timedelta(days=50), "A doua zi de Rusalii"), (date(y, 8, 15), "Adormirea Maicii Domnului"),
                   (date(y, 11, 30), "Sf. Andrei"), (date(y, 12, 1), "Ziua Națională"), (date(y, 12, 25), "Crăciunul"), (date(y, 12, 26), "A doua zi de Crăciun")):
        k = d.isoformat()
        h[k] = f"{h[k]} / {lbl}" if k in h and lbl not in h[k] else lbl
    return h


async def extra_days() -> dict:
    c = await db.calendar_config.find_one({"id": "main"}, {"_id": 0}) or {}
    return {x["date"]: x.get("label") or "zi liberă" for x in c.get("extra") or []}


def add_workdays(d: date, n: int, extra: Optional[dict] = None) -> date:
    extra = extra or {}
    cache = {}
    while n > 0:
        d += timedelta(days=1)
        hol = cache.setdefault(d.year, ro_holidays(d.year))
        if d.weekday() < 5 and d.isoformat() not in hol and d.isoformat() not in extra:
            n -= 1
    return d


@api.get("/calendar/holidays")
async def holidays(year: int, user: dict = Depends(get_current_user)):
    ex = await extra_days()
    return {"legal": [{"date": k, "label": v} for k, v in sorted(ro_holidays(year).items())],
            "extra": [{"date": k, "label": v} for k, v in sorted(ex.items())]}


@api.put("/calendar/extra")
async def holidays_extra(request: Request, user: dict = Depends(get_current_user)):
    if user["uid"] != S.PLATFORM["id"]:
        raise HTTPException(status_code=403, detail="Doar administratorul platformei setează zilele libere suplimentare")
    rows = (await request.json()).get("extra") or []
    clean = []
    for r in rows[:100]:
        clean.append({"date": pdate(r.get("date"), "Zi liberă").isoformat(), "label": str(r.get("label") or "zi liberă")[:80]})
    await db.calendar_config.update_one({"id": "main"}, {"$set": {"id": "main", "extra": clean}}, upsert=True)
    return {"extra": clean}


ACTIVE = ["trimis", "înregistrat", "completări solicitate", "dosar complet"]


@api.get("/atr/deadlines")
async def atr_deadlines(user: dict = Depends(get_current_user)):
    if not S.has_feature(user, "atr"):
        return []
    q = {**S.scope_q(user, "atr"), "atr_track.status": {"$in": ACTIVE}}
    today_ = datetime.now(timezone.utc).date()
    out = []
    for r in await db.atr.find(q, {"_id": 0, "id": 1, "client_name": 1, "operator": 1, "atr_track": 1, "is_test": 1}).to_list(500):
        t = r["atr_track"]
        due, kind = (t.get("check_due"), "verificare documentație") if t.get("check_due") else (t.get("issue_due"), "emitere aviz")
        left = (date.fromisoformat(due) - today_).days if due else None
        out.append({"id": r["id"], "client_name": r.get("client_name"), "operator": r.get("operator"), "status": t["status"], "reg_no": t.get("reg_no"),
                    "due": due, "due_kind": kind if due else None, "days_left": left, "remind_days": (t.get("terms") or {}).get("remind_days", 3),
                    "sent_at": t.get("sent_at"), "is_test": bool(r.get("is_test"))})
    return sorted(out, key=lambda x: (x["days_left"] is None, x["days_left"] if x["days_left"] is not None else 0))


@api.post("/atr/{item_id}/aviz")
async def atr_aviz(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    rec = await get_rec(user, item_id)
    b = await request.json()
    f = b.get("file") or {}
    if not f.get("storage_path") or not str(f["storage_path"]).startswith(f"{S.APP_NAME}/uploads/{user['id']}/"):
        raise HTTPException(status_code=400, detail="Încărcați întâi fișierul avizului")
    atr_no = (b.get("atr_no") or "").strip()[:60]
    if not atr_no:
        raise HTTPException(status_code=400, detail="Introduceți numărul avizului tehnic de racordare")
    d = pdate(b.get("date"), "Data avizului")
    t = track(rec)
    t.update({"status": "aviz emis", "atr_no": atr_no, "atr_date": d.isoformat(), "issue_due": None, "check_due": None})
    f = {k: f.get(k) for k in ("storage_path", "original_filename", "content_type", "size")}
    await db.atr.update_one({"id": item_id}, {"$set": {"aviz_file": f, "atr_ref": f"{atr_no} / {d.isoformat()}"}})
    return {"aviz_file": f, **pub(await save_track(item_id, t, f"Aviz tehnic de racordare primit și încărcat: {atr_no} / {d.isoformat()} ({f.get('original_filename')})", user.get("email")))}


def pdate(v: str, label: str) -> date:
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label}: dată invalidă")


def valid_operator_email(op: str, email: str) -> bool:
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", email):
        return False
    dom = email.split("@")[1]
    return any(dom == d or dom.endswith("." + d) for d in OP_DOMAINS.get(op, ()))


async def get_rec(user: dict, item_id: str, write: bool = True) -> dict:
    if write:
        S.guard("atr", user, write=True)
    return await S.check_access(user, "atr", item_id)


def track(rec: dict) -> dict:
    t = rec.get("atr_track") or {}
    t.setdefault("status", "ciornă")
    t.setdefault("events", [])
    t.setdefault("terms", dict(DEFAULT_TERMS))
    return t


async def save_track(item_id: str, t: dict, ev: str, by: str):
    t["events"] = (t.get("events") or [])[-40:] + [{"at": now(), "by": by, "text": ev}]
    await db.atr.update_one({"id": item_id}, {"$set": {"atr_track": t}})
    return t


# ---------------- operator contacts (platform) ----------------
@api.get("/operator-contacts")
async def contacts(user: dict = Depends(get_current_user)):
    rows = {c["op"]: c for c in await db.operator_contacts.find({}, {"_id": 0}).to_list(20)}
    return [{"op": k, "name": ATR.OP_NAMES[k], "domains": list(v), "email": (rows.get(k) or {}).get("email", "")} for k, v in OP_DOMAINS.items()]


@api.put("/operator-contacts/{op}")
async def contacts_set(op: str, request: Request, user: dict = Depends(get_current_user)):
    if user["uid"] != S.PLATFORM["id"]:
        raise HTTPException(status_code=403, detail="Doar administratorul platformei setează adresele operatorilor")
    email = ((await request.json()).get("email") or "").strip().lower()
    if op not in OP_DOMAINS or (email and not valid_operator_email(op, email)):
        raise HTTPException(status_code=400, detail=f"Adresa trebuie să fie pe domeniul oficial al operatorului ({', '.join(OP_DOMAINS.get(op, ()))})")
    await db.operator_contacts.update_one({"op": op}, {"$set": {"op": op, "email": email, "updated_at": now()}}, upsert=True)
    return {"ok": True}


# ---------------- form alerts ----------------
@api.get("/forms/alerts")
async def form_alerts(operator: str = "", scope: str = "atr", user: dict = Depends(get_current_user)):
    op = ATR.op_key(operator)
    if not op:
        return []
    want = ("atr",) if scope == "atr" else ("spor", "prosumator")
    out = []
    for f in await db.official_forms.find({"status": {"$in": ["versiune nouă detectată", "link invalid"]}}, {"_id": 0, "history": 0}).to_list(200):
        if ATR.op_key(f.get("operator")) == op and any(w in (f.get("kind") or "").lower() for w in want):
            out.append({k: f.get(k) for k in ("id", "operator", "title", "url", "status", "version")} | {"checked": (f.get("last_check") or {}).get("at")})
    return out


# ---------------- official operator forms ----------------
@api.get("/forms/operator-links")
async def operator_form_links(operator: str = "", scope: str = "atr", user: dict = Depends(get_current_user)):
    """Return registered official-form links for the selected distributor, not only changed/broken forms."""
    if not operator.strip():
        return []
    op = ATR.op_key(operator)
    want = ("atr",) if scope == "atr" else ("spor", "prosumator")
    rows = await db.official_forms.find({}, {"_id": 0, "history": 0}).to_list(500)
    out = []
    for f in rows:
        kind = str(f.get("kind") or "").lower()
        url = str(f.get("url") or "").strip()
        if ATR.op_key(f.get("operator")) != op or not any(w in kind for w in want) or not url.startswith("https://"):
            continue
        out.append({k: f.get(k) for k in ("id", "operator", "title", "url", "status", "version")} |
                   {"checked": (f.get("last_check") or {}).get("at")})
    if op == "rer" and scope == "atr":
        existing_titles = {str(row.get("title") or "").casefold() for row in out}
        for annex_no, url in RER_FORM_PDFS.items():
            title = f"Retele Electrice — Anexa {annex_no} prosumatori"
            if title.casefold() not in existing_titles:
                out.append({"id": f"builtin-rer-annex-{annex_no}", "operator": "Retele Electrice",
                            "title": title, "url": url, "status": "sursă oficială", "version": "formular curent",
                            "source_url": RER_FORMS_URL})
    if op == "delgaz" and scope == "atr":
        existing_titles = {str(row.get("title") or "").casefold() for row in out}
        for annex_no, url in DELGaz_FORM_PDFS.items():
            title = f"Delgaz Grid — Anexa {annex_no} prosumatori"
            if title.casefold() not in existing_titles:
                out.append({"id": f"builtin-delgaz-annex-{annex_no}", "operator": "Delgaz Grid",
                            "title": title, "url": url, "status": "sursă oficială", "version": "formular curent",
                            "source_url": DELGaz_FORMS_URL})
    if op == "oltenia" and scope == "atr":
        existing_titles = {str(row.get("title") or "").casefold() for row in out}
        for annex_no, url in OLTENIA_FORM_PDFS.items():
            title = {1: "Distribuție Oltenia — Anexa 1 prosumatori rev. 06", 2: "Distribuție Oltenia — Anexa 2 prosumatori rev. 06", 3: "Distribuție Oltenia — Anexa 3 prosumatori rev. 05", 4: "Distribuție Oltenia — Anexa 4 prosumatori rev. 05", 5: "Distribuție Oltenia — Anexa 5 prosumatori rev. 01"}[annex_no]
            if title.casefold() not in existing_titles:
                out.append({"id": f"builtin-oltenia-annex-{annex_no}", "operator": "Distribuție Oltenia",
                            "title": title, "url": url, "status": "sursă oficială", "version": "formular curent",
                            "source_url": OLTENIA_FORMS_URL})
    return sorted(out, key=lambda f: (f.get("status") in ("link invalid", "versiune nouă detectată"), str(f.get("title") or "")))



# ---------------- official operator form retrieval ----------------
async def _registry_annex1(operator_key: str) -> dict | None:
    """Select an official prosumer Annex 1 from the operator registry, never an arbitrary user URL."""
    if operator_key not in OP_DOMAINS:
        return None
    rows = await db.official_forms.find({}, {"_id": 0}).to_list(500)
    matches = []
    for form in rows:
        kind = str(form.get("kind") or "").casefold()
        title = str(form.get("title") or "").casefold()
        if ATR.op_key(form.get("operator")) != operator_key:
            continue
        if "prosumator" not in kind or "anexa 1" not in title:
            continue
        if form.get("status") == "link invalid":
            continue
        parsed = urlparse(str(form.get("url") or ""))
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not any(host == domain or host.endswith("." + domain) for domain in OP_DOMAINS[operator_key]):
            continue
        matches.append(form)
    if not matches:
        return None
    # Prefer a version confirmed in the official forms register.
    return max(matches, key=lambda row: (bool(row.get("confirmed_at")), row.get("status") == "valid", str(row.get("title") or "")))


async def _fetch_registry_annex(form: dict, operator_key: str) -> tuple[bytes, str]:
    """Fetch a bounded public form only from the configured operator's official domains."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "DNS-Energy/1.0 (official form package)"},
        follow_redirects=True,
        timeout=httpx.Timeout(25.0, connect=7.0),
    ) as client:
        async with client.stream("GET", form["url"]) as response:
            host = (urlparse(str(response.url)).hostname or "").lower().rstrip(".")
            if not any(host == domain or host.endswith("." + domain) for domain in OP_DOMAINS[operator_key]):
                raise ValueError("Redirecționarea formularului a părăsit domeniul oficial al operatorului.")
            if response.status_code != 200:
                raise ValueError(f"Formularul oficial a răspuns cu HTTP {response.status_code}.")
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise ValueError("Formularul oficial depășește limita de 20 MB.")
                chunks.append(chunk)
            data = b"".join(chunks)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(form.get("title") or "Anexa_1")).strip("_")[:100] or "Anexa_1"
    if data.startswith(b"%PDF"):
        return data, f"{safe}.pdf"
    if data.startswith(b"PK"):
        return data, f"{safe}.docx"
    raise ValueError("Linkul din registru nu a returnat un PDF sau un DOCX.")

async def _registry_forms_for_request(operator_key: str, rec: dict, pros: dict | None = None) -> tuple[int | None, list[dict]]:
    """Choose only official forms whose annex matches the selected ATR case."""
    if operator_key not in OP_DOMAINS:
        return None, []
    case = " ".join(str(rec.get(k) or "") for k in ("deer_case", "request_type")).casefold().replace("ț", "t").replace("ș", "s")
    request_type = ATR.rtype(rec)
    if request_type in ("nou", "temp", "spor", "mod_dep"):
        # All three operators use Annex 1 for new places and technical changes
        # that exceed the previously approved power.
        annex_no = 1
    elif request_type == "admin":
        annex_no = 3
    elif "finant" in case:
        # RER separates AFM/own-funds cases (Annex 2) from other funding
        # programmes (Annex 4); Delgaz and Oltenia use Annex 4 for AFM cases.
        if operator_key == "rer" and any(mark in case for mark in ("afm", "casa verde", "fonduri proprii", "surse proprii")):
            annex_no = 2
        else:
            annex_no = 4
    elif any(mark in case for mark in ("≤10,8", "<=10,8", "<=10.8", "≤ 10,8")):
        annex_no = 5
    elif request_type == "mod_fara":
        pros = pros or {}
        cef = pros.get("cef") or {}
        panel_kwp = sum(
            sum(float(str(string.get("panels") or 0).replace(",", ".")) for string in (inv.get("strings") or []))
            * float(str(inv.get("panel_w") or 0).replace(",", ".")) / 1000
            * max(1, int(float(str(inv.get("count") or 1).replace(",", "."))))
            for inv in (cef.get("inverters") or [])
        )
        raw_kwp = panel_kwp or pros.get("_kwp") or pros.get("panel_kwp") or cef.get("total_kwp")
        try:
            kwp = float(str(raw_kwp).replace(",", ".")) if raw_kwp not in (None, "") else None
        except (TypeError, ValueError):
            kwp = None
        supply = str(rec.get("supply") or pros.get("supply") or (cef.get("grid") or {}).get("supply") or "").casefold()
        single_phase = bool(supply) and not any(mark in supply for mark in ("trifaz", "400", "three-phase", "3 phase"))
        annex_no = 5 if kwp is not None and kwp <= 10.8 and single_phase else 2
    else:
        annex_no = None
    if annex_no is None:
        return None, []
    # Prefer the curated direct operator PDFs; the optional registry can contain
    # stale versions even when a newer official form is published.
    if operator_key == "rer" and annex_no in RER_FORM_PDFS:
        return annex_no, [{
            "operator": "Retele Electrice",
            "kind": "prosumator atr",
            "title": f"Anexa {annex_no} — formular prosumator Retele Electrice",
            "url": RER_FORM_PDFS[annex_no],
            "source_url": RER_FORMS_URL,
            "status": "sursă oficială",
            "version": "formular curent",
        }]
    if operator_key == "delgaz" and annex_no in DELGaz_FORM_PDFS:
        return annex_no, [{
            "operator": "Delgaz Grid",
            "kind": "prosumator atr",
            "title": f"Anexa {annex_no} — formular prosumator Delgaz Grid",
            "url": DELGaz_FORM_PDFS[annex_no],
            "source_url": DELGaz_FORMS_URL,
            "status": "sursă oficială",
            "version": "formular curent",
        }]
    if operator_key == "oltenia" and annex_no in OLTENIA_FORM_PDFS:
        return annex_no, [{
            "operator": "Distribuție Oltenia",
            "kind": "prosumator atr",
            "title": {1: "Anexa 1 prosumator Distribuție Oltenia rev. 06", 2: "Anexa 2 prosumator Distribuție Oltenia rev. 06", 3: "Anexa 3 prosumator Distribuție Oltenia rev. 05", 4: "Anexa 4 prosumator Distribuție Oltenia rev. 05", 5: "Anexa 5 prosumator Distribuție Oltenia rev. 01"}[annex_no],
            "url": OLTENIA_FORM_PDFS[annex_no],
            "source_url": OLTENIA_FORMS_URL,
            "status": "sursă oficială",
            "version": "formular curent",
        }]
    rows = await db.official_forms.find({}, {"_id": 0}).to_list(500)
    matches = []
    annex_pattern = re.compile(rf"anexa\s*(?:nr\.?\s*)?{annex_no}\b", re.I)
    for form in rows:
        kind = str(form.get("kind") or "").casefold()
        title = str(form.get("title") or "").casefold()
        if ATR.op_key(form.get("operator")) != operator_key:
            continue
        if "prosumator" not in kind and "prosumator" not in title:
            continue
        if not annex_pattern.search(title) and not annex_pattern.search(kind):
            continue
        if form.get("status") == "link invalid":
            continue
        parsed = urlparse(str(form.get("url") or ""))
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not any(host == domain or host.endswith("." + domain) for domain in OP_DOMAINS[operator_key]):
            continue
        matches.append(form)
    # A request maps to one annex. Including multiple versions of that same official
    # form makes the package ambiguous; keep only the highest-priority registered source.
    matches.sort(key=lambda row: (bool(row.get("confirmed_at")), row.get("status") == "valid", str(row.get("title") or "")), reverse=True)
    if matches:
        return annex_no, matches[:1]
    return annex_no, []


def _prefill_official_pdf(pdf_bytes: bytes, rec: dict, client: dict, pros: dict) -> tuple[bytes, int]:
    """Fill only semantically named text fields in official PDF forms; never infer values."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        fields = reader.get_fields() or {}
    except Exception:
        return pdf_bytes, 0
    if not fields:
        return pdf_bytes, 0

    def norm(value):
        import unicodedata
        return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower())

    c, r, p = client or {}, rec or {}, pros or {}
    cef = p.get("cef") or {}
    inverters = cef.get("inverters") or []
    batteries = ATR.storage_details(p, r)
    panel_models = ", ".join(dict.fromkeys(str(x.get("panel_model")) for x in inverters if x.get("panel_model")))
    inverter_models = ", ".join(dict.fromkeys(str(x.get("brand_model")) for x in inverters if x.get("brand_model")))
    battery_models = ", ".join(dict.fromkeys(str(x.get("model")) for x in batteries if x.get("model")))

    def number(value):
        try:
            return float(str(value or 0).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    panel_count = sum(
        sum(int(number(st.get("panels"))) for st in (inv.get("strings") or []))
        * max(1, int(number(inv.get("count")) or 1))
        for inv in inverters
    )
    battery_kwh = sum(number(b.get("kwh")) for b in batteries)
    battery_ah = ", ".join(str(b.get("ah")) for b in batteries if b.get("ah") not in (None, ""))
    battery_voltage = ", ".join(str(b.get("voltage")) for b in batteries if b.get("voltage") not in (None, ""))
    battery_modules = sum(int(number(b.get("modules")) or 0) for b in batteries)
    battery_coupling = ", ".join(dict.fromkeys(str(b.get("coupling")) for b in batteries if b.get("coupling")))
    values = [
        (("numecomplet", "utilizator", "beneficiar", "solicitant", "denumireclient"), c.get("name")),
        (("prenume",), c.get("first_name")),
        (("cnp",), c.get("idcode") if str(r.get("applicant_type") or "").lower() not in ("pj", "persoana juridica") else None),
        (("cui", "codfiscal", "codinregistrarefiscala"), c.get("cui") or (c.get("idcode") if str(r.get("applicant_type") or "").lower() in ("pj", "persoana juridica") else None)),
        (("email",), c.get("email")),
        (("telefon", "telefonmobil", "phone"), c.get("phone")),
        (("judet", "county"), r.get("county") or c.get("county")),
        (("localitate", "locality", "oras", "municipiu"), r.get("locality") or c.get("locality")),
        (("pod", "codpunctconsum"), r.get("pod") or c.get("pod")),
        (("numarcf", "nrcf", "cartefunciara"), r.get("cf_nr") or c.get("cf_nr")),
        (("numarcadastral", "cadastral"), r.get("cadastral_nr") or c.get("cadastral_nr")),
        (("adresalocconsum", "adresapunctconsum", "locconsum", "stradalocconsum"), r.get("address")),
        (("adresadomiciliu", "adresasolicitant", "domiciliu", "clientaddress", "applicantaddress", "strada"), c.get("address")),
        (("pabsorbita", "putereabsorbita", "pabs", "pmaxabsorbita"), r.get("p_abs_kw")),
        (("putereevacuatakva", "pevackva", "pmaxevacuatakva"), r.get("p_evac_kva")),
        (("putereevacuatakw", "pevackw", "pmaxevacuatakw", "putereevacuata", "pevacuare", "pmaxevacuata"), r.get("p_evac_kw") or p.get("power")),
        (("modelpanou", "tipmodelpanou", "modelpanoufotovoltaic"), panel_models or None),
        (("numarpanouri", "nrpanouri"), panel_count or None),
        (("modelinvertor", "tipmodelinvertor", "marcainvertor"), inverter_models or None),
        (("modelbaterie", "tipmodelbaterie", "marcabaterie"), battery_models or None),
        (("capacitatebateriekwh", "capacitatekwh", "energieutilizabilakwh"), battery_kwh or None),
        (("numarmodulebaterie", "modulebaterie", "numarbaterii"), battery_modules or None),
        (("amperoribaterie", "baterieah", "capacitateah"), battery_ah or None),
        (("tensiunebateriev", "bateriev", "tensiunesistemstocare"), battery_voltage or None),
        (("cuplarebaterie", "modcuplare", "acdcoupling"), battery_coupling or None),
    ]
    def value_for(field_name):
        key = norm(field_name)
        if not key:
            return None
        for aliases, value in values:
            if value in (None, ""):
                continue
            if any(norm(alias) in key for alias in aliases):
                return str(value)
        return None

    page_updates = []
    filled = 0
    for page_index, page in enumerate(reader.pages):
        update = {}
        for field_name, field in fields.items():
            if field.get("/FT") != "/Tx":
                continue
            value = value_for(field_name)
            if value is not None:
                update[field_name] = value
        if update:
            page_updates.append((page_index, update))
            filled += len(update)
    if not filled:
        return pdf_bytes, 0
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    for page_index, update in page_updates:
        try:
            writer.update_page_form_field_values(writer.pages[page_index], update, auto_regenerate=False)
        except Exception:
            return pdf_bytes, 0
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue(), filled


# ---------------- complete downloadable package ----------------
@api.get("/atr/{item_id}/package.zip")
async def atr_package(item_id: str, user: dict = Depends(get_current_user)):
    """Bundle the ATR PDF and the official operator form; DEER templates are prefilled when available."""
    rec = await get_rec(user, item_id, write=False)
    client = await S.get_client(user["id"], rec) or {}
    settings = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    pros = {}
    if rec.get("pros_id") and await db.prosumator.find_one({**S.scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"id": 1}):
        pros, pros_client, settings, _ = await S.dossier_ctx(user, rec["pros_id"])
        client = {**(pros_client or {}), **(client or {})}

    pdf, pdf_name = await S.atr_pack(user, rec, 1)
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(pdf_name, pdf)
        op_key = ATR.op_key(rec.get("operator"), (pros or {}).get("operator"), client.get("operator"))
        if op_key == "deer":
            annex_info = ATR.deer_annex_info(rec)
            try:
                annex = ATR.render_deer_official_docx(rec, client, settings, pros or {})
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            label = re.sub(r"[^A-Za-z0-9_-]+", "_", (annex_info or ("Anexa_DEER",))[0]).strip("_")
            archive.writestr(f"Anexe oficiale/{label}_completata.docx", annex)

            # Include the operator's blank source form beside the prefilled working copy.
            # The source file is retrieved only from the allow-listed DEER host and checked
            # for a PDF/DOCX signature and a 20 MB size limit by _fetch_registry_annex.
            deer_notes = [
                "Pachet DEER — formularul completat este o copie de lucru precompletată din datele salvate.",
                "Verificați versiunea curentă, completați câmpurile rămase goale și semnați înainte de depunere.",
                f"Sursa oficială cu formularele aplicabile: {DEER_FORMS_URL}",
            ]
            if annex_info and annex_info[2]:
                try:
                    source, source_name = await _fetch_registry_annex(
                        {"title": annex_info[1], "url": annex_info[2]}, "deer")
                    archive.writestr(f"Anexe oficiale/Formular oficial necompletat/{source_name}", source)
                    deer_notes.append(f"Formularul oficial {annex_info[0]} a fost inclus ca fișier original necompletat.")
                except (httpx.HTTPError, ValueError) as exc:
                    deer_notes.append(f"Formularul oficial nu a putut fi preluat acum: {exc}")
            else:
                deer_notes.append("Nu a fost identificată anexa oficială pentru selecția curentă; verificați pagina DEER.")

            try:
                gdpr, gdpr_name = await _fetch_registry_annex(
                    {"title": "Nota DEER de informare GDPR v1/2026", "url": DEER_GDPR_URL}, "deer")
                archive.writestr(f"Anexe oficiale/{gdpr_name}", gdpr)
                deer_notes.append("Nota oficială DEER privind prelucrarea datelor personale (v1/2026) a fost inclusă.")
            except (httpx.HTTPError, ValueError) as exc:
                deer_notes.append(f"Nota GDPR oficială nu a putut fi preluată acum; descărcați-o de aici: {DEER_GDPR_URL} ({exc})")
            archive.writestr("Anexe oficiale/INFO_DEER.txt", "\n".join(deer_notes))
        else:
            annex_no, forms = await _registry_forms_for_request(op_key, rec, pros)
            if annex_no:
                worksheet = ATR.render_operator_annex_prep(rec, client, pros, op_key, annex_no, forms[0].get("title", "") if forms else "")
                archive.writestr(f"Anexe oficiale/Fisa_precompletare_Anexa_{annex_no}.pdf", worksheet)
            note = [
                "Pachet ATR — formular oficial pentru operator",
                f"Operator selectat: {rec.get('operator') or (pros or {}).get('operator') or client.get('operator') or 'neselectat'}",
                f"Tip solicitare: {ATR.rtype(rec) or 'neselectat'}",
                f"Anexă oficială selectată pentru tipul cererii: {annex_no or 'nedeterminată'}",
                "",
                "Fișa de precompletare din arhivă este inclusă și în PDF-ul principal; ambele sunt generate din aceleași date salvate.",
                "Formularele oficiale atașate rămân originale și necompletate. Verificați versiunea, eligibilitatea și semnați formularul oficial înainte de depunere.",
                "Verificați versiunea și eligibilitatea în portalul operatorului înainte de depunere. Valorile lipsă nu sunt inventate.",
            ]
            if forms:
                for form in forms:
                    note.extend(["", f"Sursă oficială: {form.get('source_url') or form.get('url')}", f"Formular: {form.get('title')}", f"Stare link: {form.get('status') or 'neverificat'}"])
                    try:
                        annex, official_name = await _fetch_registry_annex(form, op_key)
                        archive.writestr(f"Anexe oficiale/Formulare originale/{official_name}", annex)
                        completed, filled_fields = _prefill_official_pdf(annex, rec, client, pros)
                        if filled_fields:
                            stem = re.sub(r"[^A-Za-z0-9_-]+", "_", official_name.rsplit(".", 1)[0]).strip("_")
                            archive.writestr(f"Anexe oficiale/{stem}_completata.pdf", completed)
                            note.append(f"Formular PDF oficial completat automat în {filled_fields} câmpuri etichetate; copia originală a fost păstrată.")
                        else:
                            note.append("Formular oficial descărcat; nu are câmpuri text etichetate compatibile pentru completare automată. Rămâne disponibil originalul și fișa de precompletare.")
                    except (httpx.HTTPError, ValueError) as exc:
                        note.append(f"Formularul nu a putut fi atașat la generare: {exc}")
                if op_key == "rer" and ATR.storage_details(pros, rec):
                    storage_form = {"title": "Anexa Retele Electrice aferentă instalațiilor de stocare",
                                    "url": RER_STORAGE_FORM_URL}
                    try:
                        storage_pdf, storage_name = await _fetch_registry_annex(storage_form, op_key)
                        archive.writestr(f"Anexe oficiale/Formulare originale/{storage_name}", storage_pdf)
                        storage_completed, storage_fields = _prefill_official_pdf(storage_pdf, rec, client, pros)
                        if storage_fields:
                            storage_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", storage_name.rsplit(".", 1)[0]).strip("_")
                            archive.writestr(f"Anexe oficiale/{storage_stem}_completata.pdf", storage_completed)
                            note.append(f"Anexa oficială pentru stocare a fost completată în {storage_fields} câmpuri etichetate; originalul a fost păstrat.")
                        else:
                            note.append("Anexa oficială pentru stocare a fost inclusă în original; câmpurile ei nu sunt etichetate pentru precompletare automată.")
                    except (httpx.HTTPError, ValueError) as exc:
                        note.append(f"Anexa oficială pentru instalația de stocare nu a putut fi atașată: {exc}")
                        note.append(f"Descărcați formularul de aici: {RER_STORAGE_FORM_URL}")
            elif annex_no:
                note.append(f"Nu există în registru un formular oficial Anexa {annex_no} verificabil pentru operatorul și tipul cererii selectate.")
                official_pages = {
                    "delgaz": DELGaz_FORMS_URL,
                    "oltenia": OLTENIA_FORMS_URL,
                    "rer": RER_FORMS_URL,
                }
                if op_key in official_pages:
                    note.append(f"Pagina oficială cu formulare și reguli: {official_pages[op_key]}")
            else:
                note.append("Tipul cererii curente nu are încă o mapare automată la o anexă oficială în registrul aplicației.")
            if op_key == "delgaz":
                for title, url in DELGaz_GDPR_URLS.items():
                    try:
                        privacy_doc, privacy_name = await _fetch_registry_annex({"title": title, "url": url}, op_key)
                        archive.writestr(f"Anexe oficiale/{privacy_name}", privacy_doc)
                        note.append(f"Document oficial atașat: {title}.")
                    except (httpx.HTTPError, ValueError) as exc:
                        note.append(f"{title} nu a putut fi atașat la generare: {exc}")
            archive.writestr("Anexe oficiale/INFO_completare.txt", "\n".join(note))
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", pdf_name.rsplit(".", 1)[0]) + "_pachet.zip"
    return Response(content=bundle.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": S.disp("attachment", name), "Cache-Control": "no-store"})


# ---------------- submission ----------------
@api.post("/atr/{item_id}/submit")
async def atr_submit(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    rec = await get_rec(user, item_id)
    b = await request.json()
    op = ATR.op_key(rec.get("operator"))
    if not op:
        raise HTTPException(status_code=400, detail="Selectați operatorul de distribuție înainte de trimiterea cererii ATR.")
    to = (b.get("to") or "").strip().lower()
    if not valid_operator_email(op, to):
        raise HTTPException(status_code=400, detail=f"Destinatarul trebuie să fie o adresă oficială {ATR.OP_NAMES.get(op, 'operatorului selectat')} ({', '.join(OP_DOMAINS.get(op, ()))})")
    att = rec.get("attachments") or {}
    pdf, name = await S.atr_pack(user, rec, 1)
    if "_INCOMPLET" in name:
        raise HTTPException(status_code=400, detail="Dosarul ATR este incomplet sau conține fișiere indisponibile. Verifică pagina «Listă de verificare» din PDF, completează lipsurile și încearcă din nou.")
    origin = (request.headers.get("origin") or "").rstrip("/")
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    if not origin.startswith("https://") or (host and origin[8:] != host):
        raise HTTPException(status_code=400, detail="Deschideți trimiterea din aplicație")
    token = secrets.token_urlsafe(24)
    exp = (datetime.now(timezone.utc) + timedelta(days=LINK_DAYS)).isoformat()
    client = await S.get_client(user["id"], rec)
    st = await db.settings.find_one({"owner": user["id"]}, {"_id": 0, "company": 1, "phone": 1, "email": 1}) or {}
    link = f"{origin}/api/public/atr/{token}"
    cname, comp = hesc(str(client.get("name") or rec.get("client_name") or "")), hesc(str(st.get("company") or ""))
    html = (f"<p>Bună ziua,</p><p>Vă transmitem cererea de racordare (aviz tehnic de racordare) pentru <b>{cname}</b>, "
            f"obiectiv: {hesc(str(rec.get('object_name') or rec.get('address') or client.get('address') or ''))}, "
            f"tip: {hesc(str(rec.get('kind') or 'Loc de consum'))}.</p>"
            f"<p>Dosarul complet (cerere, chestionar și documentele anexate, PDF {round(len(pdf) / 1048576, 1)} MB) poate fi descărcat aici, timp de {LINK_DAYS} de zile:<br/>"
            f'<a href="{link}">Descarcă dosarul ATR (PDF)</a></p>'
            f"<p>Vă rugăm să ne comunicați numărul și data de înregistrare a cererii.</p>"
            f"<p>Cu stimă,<br/>{comp}<br/>{hesc(str(st.get('phone') or ''))} · {hesc(str(st.get('email') or user.get('email') or ''))}</p>"
            f"<p style='font-size:11px;color:#777'>Transmis prin D-ENERGY în numele {comp}.</p>")
    subj = f"Cerere de racordare (ATR) — {client.get('name') or rec.get('client_name') or ''}"
    sent_to = await S.deliver(user["id"], bool(rec.get("is_test")), to, subj, html)
    copy = await S.deliver(user["id"], bool(rec.get("is_test")), user.get("email"), "Copie: " + subj, "<p><b>Copie a e-mailului trimis la " + hesc(to) + "</b></p>" + html) if user.get("email") else ""
    t = track(rec)
    t.update({"status": "trimis", "sent_at": now(), "sent_to": to, "token": token, "token_exp": exp, "real_sent": bool(sent_to)})
    await save_track(item_id, t, f"Dosar trimis la {to}" + ("" if sent_to else " (dosar TEST — e-mail real neexpediat)") + (f"; copie la {copy}" if copy else ""), user.get("email"))
    return {"ok": True, "sent_to": sent_to, "copy": copy, "track": pub(t)}


@api.get("/public/atr/{token}")
async def atr_public(token: str):
    rec = await db.atr.find_one({"atr_track.token": token}, {"_id": 0})
    if not rec or (rec["atr_track"].get("token_exp") or "") < now():
        raise HTTPException(status_code=404, detail="Link expirat sau invalid")
    owner = rec["owner"]
    u = {"id": owner, "uid": owner, "role": "admin", "plan": {"exempt": True}}
    pdf, name = await S.atr_pack(u, rec, 1)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": S.disp("inline", name)})


def pub(t: dict) -> dict:
    return {k: v for k, v in t.items() if k != "token"}


@api.get("/atr/{item_id}/track")
async def atr_track(item_id: str, user: dict = Depends(get_current_user)):
    rec = await get_rec(user, item_id, write=False)
    return {**pub(track(rec)), "aviz_file": rec.get("aviz_file")}


@api.post("/atr/{item_id}/track")
async def atr_track_update(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    rec = await get_rec(user, item_id)
    b = await request.json()
    t = track(rec)
    act = b.get("action")
    terms = {**DEFAULT_TERMS, **(t.get("terms") or {})}
    for k in ("check_days", "issue_days", "remind_days"):
        if b.get(k) not in (None, ""):
            v = int(b[k])
            if not 0 < v <= 365:
                raise HTTPException(status_code=400, detail="Termen invalid")
            terms[k] = v
    t["terms"] = terms
    if act == "register":
        reg_no = (b.get("reg_no") or "").strip()[:60]
        if not reg_no:
            raise HTTPException(status_code=400, detail="Introduceți numărul de înregistrare primit de la distribuitor")
        d = pdate(b.get("reg_date"), "Data înregistrării")
        t.update({"status": "înregistrat", "reg_no": reg_no, "reg_date": d.isoformat(), "check_due": add_workdays(d, terms["check_days"], await extra_days()).isoformat()})
        ev = f"Înregistrat la distribuitor: nr. {reg_no} / {d.isoformat()}; verificare documente până la {t['check_due']}"
    elif act == "incomplete":
        t.update({"status": "completări solicitate", "incomplete_note": (b.get("note") or "")[:300], "check_due": None})
        ev = f"Distribuitorul a solicitat completări: {t['incomplete_note']}"
    elif act == "complete":
        d = pdate(b.get("date"), "Data dosarului complet")
        t.update({"status": "dosar complet", "complete_date": d.isoformat(), "issue_due": (d + timedelta(days=terms["issue_days"])).isoformat(), "check_due": None})
        ev = f"Dosar declarat complet la {d.isoformat()}; termen emitere aviz {t['issue_due']}"
    elif act == "issued":
        d = pdate(b.get("date"), "Data avizului")
        t.update({"status": "aviz emis", "atr_no": (b.get("atr_no") or "").strip()[:60], "atr_date": d.isoformat(), "issue_due": None, "check_due": None})
        await db.atr.update_one({"id": item_id}, {"$set": {"atr_ref": f"{t['atr_no']} / {d.isoformat()}"}})
        ev = f"Aviz tehnic de racordare emis: {t['atr_no']} / {d.isoformat()}"
    elif act == "dates":
        for k, lbl in (("check_due", "Termen verificare"), ("issue_due", "Termen aviz")):
            if b.get(k):
                t[k] = pdate(b[k], lbl).isoformat()
        ev = f"Termene modificate manual: verificare {t.get('check_due') or '—'}, aviz {t.get('issue_due') or '—'}"
    elif act == "terms":
        ev = f"Termene standard: verificare {terms['check_days']} zile lucrătoare, aviz {terms['issue_days']} zile, reamintire cu {terms['remind_days']} zile înainte"
    else:
        raise HTTPException(status_code=400, detail="Acțiune necunoscută")
    return pub(await save_track(item_id, t, ev, user.get("email")))


# ---------------- deadline reminders (cron) ----------------
async def run_deadlines(run_id: str):
    today = datetime.now(timezone.utc).date()
    async for rec in db.atr.find({"atr_track.status": {"$in": ["înregistrat", "dosar complet"]}}, {"_id": 0}):
        t = rec["atr_track"]
        rd = int((t.get("terms") or {}).get("remind_days") or 3)
        for key, label in (("check_due", "verificarea documentației de către distribuitor"), ("issue_due", "emiterea avizului tehnic de racordare")):
            if not t.get(key):
                continue
            due = date.fromisoformat(t[key])
            phase = "depășit" if today > due else "aproape" if (due - today).days <= rd else None
            if not phase:
                continue
            rid = f"atr:{rec['id']}:{key}:{t[key]}:{phase}"
            if await db.reminders.find_one({"id": rid}):
                continue
            await db.reminders.insert_one({"id": rid, "at": now(), "run_id": run_id})
            u = await db.users.find_one({"id": rec.get("created_by") or rec["owner"]}, {"_id": 0, "email": 1}) or \
                await db.users.find_one({"id": rec["owner"]}, {"_id": 0, "email": 1}) or {}
            msg = (f"Termenul pentru {label} a fost depășit ({due.strftime('%d.%m.%Y')})." if phase == "depășit"
                   else f"Termenul pentru {label} expiră pe {due.strftime('%d.%m.%Y')}.")
            html = (f"<p>Bună ziua,</p><p>Cererea ATR pentru <b>{hesc(str(rec.get('client_name') or ''))}</b> "
                    f"(nr. înregistrare {hesc(str(t.get('reg_no') or '—'))}): {msg}</p>"
                    "<p>Verificați stadiul la distribuitor și actualizați cererea în D-ENERGY → Cerere ATR.</p>")
            try:
                await S.deliver(rec["owner"], bool(rec.get("is_test")), u.get("email") or "", f"Termen ATR {phase}: {rec.get('client_name') or ''}", html)
            except Exception as e:
                logger.warning(f"atr reminder: {e}")
            t["events"] = (t.get("events") or [])[-40:] + [{"at": now(), "by": "cron", "text": f"Reamintire trimisă: {msg}"}]
            await db.atr.update_one({"id": rec["id"]}, {"$set": {"atr_track.events": t["events"]}})


@api.post("/cron/atr-deadlines")
async def cron_atr(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or not hmac.compare_digest(h[7:], os.environ.get("WEBHOOK_CRON_SECRET", "")):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("x-webhook-id") or str(uuid.uuid4())
    if await db.cron_runs.find_one({"id": run_id}):
        return {"status": "duplicate"}
    await db.cron_runs.insert_one({"id": run_id, "at": now(), "name": "atr-deadlines"})
    background.add_task(run_deadlines, run_id)
    return {"status": "accepted"}
