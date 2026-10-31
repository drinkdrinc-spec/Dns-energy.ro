import io
import re
import uuid
import hmac
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import HTTPException, Request, Depends, BackgroundTasks

import server as S
from mailer import send_email

db, api, get_current_user = S.db, S.api_router, S.get_current_user
logger = logging.getLogger("d-energy.forms")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
OK, CHANGED, BROKEN, BLOCKED, NEW, ACCESSIBLE = "valid", "versiune nouă detectată", "link invalid", "neverificabil automat", "neverificat", "link accesibil — neconfirmat"

SEED = [
    ("DEER", "Cerere de racordare prosumator — loc existent / spor de putere (Anexa 1, Ord. ANRE 69/2020)", "prosumator / spor putere",
     "https://www.distributie-energie.ro/wp-content/uploads/2021/01/10-Cerere-loc-consum-existent-Spor-de-putere-Anexa-1.pdf"),
    ("DEER", "Cerere Anexa 1 — loc existent cu spor de putere (sursa curentă, formular DOCX)", "prosumator / spor putere",
     "https://www.distributie-energie.ro/wp-content/uploads/2023/12/4.-Loc-consum-si_sau-producere-existent-Spor-Putere_Anexa-nr-1.docx"),
    ("DEER", "Cerere Anexa 1 — loc nou de consum și producere (formular DOCX)", "prosumator / racordare",
     "https://www.distributie-energie.ro/wp-content/uploads/2023/12/1.-Loc-consum-si-producere-nou-_Anexa-nr-1.docx"),
    ("DEER", "Anexa 2 — notificare loc de consum existent (formular DOCX)", "prosumator / notificare",
     "https://www.distributie-energie.ro/wp-content/uploads/2023/12/2.-Loc-de-consum-existent_Anexa-nr-2.docx"),
    ("DEER", "Anexa 3 — actualizare CRR loc de consum și producere existent (formular DOCX)", "prosumator / notificare",
     "https://www.distributie-energie.ro/wp-content/uploads/2023/12/3.-Loc-de-consum-si-producere-existent-actualizare-CRR_Anexa-nr-3.docx"),
    ("DEER", "Anexa 4 — cerere prosumator cu finanțare (formular DOCX)", "prosumator / finanțare",
     "https://www.distributie-energie.ro/wp-content/uploads/2023/12/5.-Cerere-de-racordare-prosumator-%E2%80%93-prin-programe-de-finantare-Anexa-4.docx"),
    ("DEER", "Anexa 5 — notificare prosumator până la 10,8 kW, conform portalului DEER", "prosumator / notificare",
     "https://www.distributie-energie.ro/wp-content/uploads/2023/12/5.-Loc-consum-si_sau-producere-existent-prevazut_cu_instalatii_de_producere_Anexa-nr-5.docx"),
    ("Delgaz Grid", "Cerere prosumator — Anexa 1 (fișier publicat în portalul Delgaz)", "prosumator / spor putere",
     "https://delgaz.ro/getattachment/91755a0d-890c-4357-917a-ac5128ec735a/Cerere_de_racordare_prosumator-Anexa-1.pdf"),
    ("Rețele Electrice România", "Anexa 1 — cerere prosumator (link publicat pe pagina oficială)", "prosumator / spor putere",
     "https://www.reteleelectrice.ro/wp-content/uploads/rer-anexa-1-cerere-racordare.pdf"),
    ("Distribuție Energie Oltenia", "Anexa 1 rev06 — cerere prosumator, loc nou sau spor de putere", "prosumator / spor putere",
     "https://www.distributieoltenia.ro/resources/ckfinder/core/connector/php/connector.php?command=Proxy&currentFolder=%2FDO%2FINFORMATII+UTILE%2FFormulare+racordare%2F2024%2F26.01.2024%2F&fileName=01-03-01_P03-F16_Cerere+racordare+prosumatori_LC+noi+sau+spor+putere_anexa+1_rev06.pdf&hash=24460cc7b9aefcd5&lang=en&type=Files"),
    ("Distribuție Energie Oltenia", "Anexa 4 rev04 — cerere prosumator cu finanțare AFM", "prosumator / finanțare",
     "https://www.distributieoltenia.ro/resources/ckfinder/core/connector/php/connector.php?command=Proxy&currentFolder=%2FDO%2FINFORMATII+UTILE%2FFormulare+racordare%2F2023%2F&fileName=01-03-01_P03-F15_Cerere+de+racordare+prosumator+pt+LC+existent+care+acceseaza+programul+AFM_anexa+4_rev04.doc.pdf&hash=24460cc7b9aefcd5&lang=en&type=Files"),
    ("DEER", "Cerere tip de racordare loc de producere / consum și producere (autoproducător)", "ATR producere",
     "https://www.distributie-energie.ro/wp-content/uploads/2020/12/4-Producator.pdf"),
    ("DEER", "Documentație prosumatori — listă documente și date tehnice", "prosumator", "https://www.distributie-energie.ro/wp-content/uploads/2020/12/5.pdf"),
    ("DEER", "Anexa tehnică consumator mare noncasnic", "ATR consum", "https://www.distributie-energie.ro/wp-content/uploads/2021/01/3-Consumator-mare-noncasnic.pdf"),
    ("DEER", "Model de împuternicire", "împuternicire", "https://www.distributie-energie.ro/wp-content/uploads/2026/07/Model-de-imputernicire.pdf"),
    ("DEER", "Pagina oficială Racordare la rețea", "pagină", "https://www.distributie-energie.ro/racordare-la-retea-2/"),
    ("Delgaz Grid", "Cerere de racordare prosumator (Anexa 1, Ord. ANRE 69/2020)", "prosumator / spor putere",
     "https://delgaz.ro/getattachment/a49b57e4-6692-4772-87cd-314cd378657a/Cerere_de_racordare_prosumator.pdf"),
    ("Delgaz Grid", "Cerere de racordare prosumatori care accesează programe de finanțare", "prosumator",
     "https://delgaz.ro/getattachment/b70508d0-b697-4015-8281-440e696d57ad/Cerere-de-racordare-pt-prosumatorii-care-acceseaza-programe-de-finantare.pdf"),
    ("Delgaz Grid", "Ghidul prosumatorului", "ghid", "https://delgaz.ro/getattachment/0e35df50-566e-4da7-b2ab-54c4dbd66aac/Ghidul-Prosumatorului.pdf"),
    ("Rețele Electrice România", "Cerere și chestionar ATR — puteri sub 100 kW", "ATR consum", "https://www.reteleelectrice.ro/wp-content/uploads/atr-cerere-sub-100-kw.pdf"),
    ("Rețele Electrice România", "Cerere și chestionar ATR — puteri peste 100 kW", "ATR consum", "https://www.reteleelectrice.ro/wp-content/uploads/rer-cerere-atr-peste-100-kw.pdf"),
    ("Rețele Electrice România", "Cerere racordare prosumator (Anexa 1)", "prosumator / spor putere", "https://www.reteleelectrice.ro/wp-content/uploads/rer-anexa-1-cerere-racordare.pdf"),
    ("Rețele Electrice România", "Cerere racordare prosumator programe de finanțare (Anexa 4)", "prosumator", "https://www.reteleelectrice.ro/wp-content/uploads/rer-anexa-4-cerere-racordare.pdf"),
    ("Rețele Electrice România", "Pagina oficială Cereri și documente", "pagină", "https://www.reteleelectrice.ro/cereri-documente/"),
    ("Distribuție Energie Oltenia", "Racordarea la rețeaua electrică — documente și formulare ATR (pagina oficială)", "pagină",
     "https://www.distributieoltenia.ro/ro/informatii-utile/racordarea-la-reteaua-electrica.html"),
    ("Distribuție Energie Oltenia", "Formularele necesare pentru a deveni prosumator (Anexa 1, Anexa 4, notificări)", "pagină / prosumator",
     "https://www.distributieoltenia.ro/ro/informatii-utile/prosumatori/formularele-necesare-pentru-a-deveni-prosumator.html"),
]
VER_RE = re.compile(r"([A-Z]{2,}(?:-[A-Z0-9.]+){2,}-F\d+|Edi[țt]ia\s*[:\-]?\s*\w+|Rev(?:izia|\.)?\s*[:\-]?\s*\d+|versiunea?\s*[:\-]?\s*[\w.]+)", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def seed():
    for op, title, kind, url in SEED:
        await db.official_forms.update_one({"url": url}, {"$setOnInsert": {"id": str(uuid.uuid4()), "operator": op, "title": title, "kind": kind, "url": url,
                                           "version": "", "notes": "", "status": NEW, "created_at": now(), "history": []}}, upsert=True)


def detect_version(data: bytes, ct: str) -> str:
    try:
        if "pdf" in ct or data[:4] == b"%PDF":
            import pymupdf
            d = pymupdf.open(stream=data, filetype="pdf")
            txt = d[0].get_text()[:5000] if d.page_count else ""
            meta = d.metadata or {}
            m = VER_RE.search(txt)
            return (m.group(1).strip() if m else "") or (meta.get("modDate") or "")[2:10]
        if "wordprocessingml" in ct or data[:2] == b"PK":
            from docx import Document
            document = Document(io.BytesIO(data))
            chunks = [p.text for p in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    chunks.append(" | ".join(cell.text for cell in row.cells))
            txt = "\n".join(chunks)[:12000]
            m = VER_RE.search(txt)
            if m:
                return m.group(1).strip()
            modified = document.core_properties.modified
            return modified.strftime("%Y-%m-%d") if modified else ""
    except Exception as exc:
        logger.debug("Official form version extraction failed: %s", exc)
    return ""


async def check_one(f: dict) -> dict:
    res = {"at": now()}
    try:
        async with httpx.AsyncClient(headers=UA, follow_redirects=True, timeout=40) as h:
            r = await h.get(f["url"])
        ct = r.headers.get("content-type", "")
        res.update({"http": r.status_code, "content_type": ct[:60], "size": len(r.content), "last_modified": r.headers.get("last-modified", "")})
        if r.status_code in (401, 403, 429) or "cf-mitigated" in r.headers:
            res["status"] = BLOCKED
        elif r.status_code >= 400:
            res["status"] = BROKEN
        else:
            body = r.content
            if "html" in ct:
                body = re.sub(rb"<script.*?</script>|<style.*?</style>|nonce=\"[^\"]*\"|\b\d{10,}\b", b"", body, flags=re.S)
                links = sorted(set(re.findall(rb'href="([^"]+\.(?:pdf|docx?))"', body)))
                res["links"] = [x.decode("utf-8", "ignore") for x in links][:80]
                digest = hashlib.sha256(b"\n".join(links) or body).hexdigest()
            else:
                digest = hashlib.sha256(body).hexdigest()
                res["detected_version"] = detect_version(body, ct)
            res["hash"] = digest
            prev = (f.get("last_check") or {}).get("hash")
            res["status"] = CHANGED if prev and prev != digest else (OK if f.get("confirmed_at") and prev == digest else ACCESSIBLE)
    except Exception as e:
        res.update({"status": BROKEN, "error": str(e)[:200]})
    upd = {"last_check": res, "status": res["status"] if res["status"] != CHANGED else CHANGED}
    if res["status"] == BLOCKED and (f.get("last_check") or {}).get("hash"):
        upd["last_check"] = {**f["last_check"], **{k: v for k, v in res.items() if k in ("at", "http", "status")}}
    await db.official_forms.update_one({"id": f["id"]}, {"$set": upd, "$push": {"history": {"$each": [{k: res.get(k) for k in ("at", "status", "http", "hash", "detected_version", "size")}], "$slice": -30}}})
    return {**f, **upd}


async def check_all(notify: bool = False) -> list:
    out = [await check_one(f) for f in await db.official_forms.find({}, {"_id": 0, "history": 0}).to_list(500)]
    bad = [f for f in out if f["status"] in (CHANGED, BROKEN)]
    if notify and bad:
        rows = "".join(f"<li><b>{S.hesc(f['operator'])}</b> — {S.hesc(f['title'])}: <b>{f['status']}</b> (HTTP {f['last_check'].get('http', '—')})<br/>"
                       f"<span style='font-size:12px'>{S.hesc(f['url'])}</span></li>" for f in bad)
        try:
            await send_email(to=os.environ["ADMIN_EMAIL"], subject=f"Registru formulare: {len(bad)} formular(e) de verificat",
                             html=f"<div style='font-family:Arial'><p>Verificarea săptămânală a formularelor oficiale a găsit modificări:</p><ul>{rows}</ul>"
                                  "<p>Deschideți D-ENERGY → Registru formulare oficiale, verificați noua versiune și confirmați-o.</p></div>")
        except Exception as e:
            logger.warning(f"forms mail: {e}")
    return out


def pub(f: dict) -> dict:
    return {k: v for k, v in f.items() if k not in ("_id",)}


@api.get("/forms")
async def forms_list(user: dict = Depends(get_current_user)):
    return [pub(f) for f in await db.official_forms.find({}, {"_id": 0}).sort([("operator", 1), ("title", 1)]).to_list(500)]


def plat(user: dict):
    if user["uid"] != S.PLATFORM["id"]:
        raise HTTPException(status_code=403, detail="Doar administratorul platformei gestionează registrul formularelor")


def clean(b: dict) -> dict:
    d = {k: str(b.get(k) or "").strip()[:500] for k in ("operator", "title", "kind", "url", "version", "notes") if k in b}
    if "url" in d and not d["url"].startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Link invalid (trebuie să înceapă cu https://)")
    return d


@api.post("/forms")
async def forms_create(request: Request, user: dict = Depends(get_current_user)):
    plat(user)
    d = clean(await request.json())
    if not d.get("url") or not d.get("title") or not d.get("operator"):
        raise HTTPException(status_code=400, detail="Completați operatorul, denumirea și linkul")
    if await db.official_forms.find_one({"url": d["url"]}):
        raise HTTPException(status_code=400, detail="Linkul există deja în registru")
    f = {"id": str(uuid.uuid4()), **d, "status": NEW, "created_at": now(), "history": []}
    await db.official_forms.insert_one(dict(f))
    return pub(await check_one(f))


@api.put("/forms/{fid}")
async def forms_update(fid: str, request: Request, user: dict = Depends(get_current_user)):
    plat(user)
    d = clean(await request.json())
    if not await db.official_forms.find_one({"id": fid}):
        raise HTTPException(status_code=404, detail="Formular inexistent")
    await db.official_forms.update_one({"id": fid}, {"$set": {**d, "updated_at": now()}})
    return pub(await db.official_forms.find_one({"id": fid}, {"_id": 0}))


@api.post("/forms/{fid}/confirm")
async def forms_confirm(fid: str, request: Request, user: dict = Depends(get_current_user)):
    plat(user)
    b = await request.json()
    f = await db.official_forms.find_one({"id": fid}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="Formular inexistent")
    v = str(b.get("version") or (f.get("last_check") or {}).get("detected_version") or f.get("version") or "").strip()[:80]
    await db.official_forms.update_one({"id": fid}, {"$set": {"status": OK, "version": v, "confirmed_at": now(), "confirmed_by": user.get("email")}})
    return pub(await db.official_forms.find_one({"id": fid}, {"_id": 0}))


@api.delete("/forms/{fid}")
async def forms_delete(fid: str, user: dict = Depends(get_current_user)):
    plat(user)
    await db.official_forms.delete_one({"id": fid})
    return {"ok": True}


@api.post("/forms/check")
async def forms_check(fid: Optional[str] = None, user: dict = Depends(get_current_user)):
    plat(user)
    if fid:
        f = await db.official_forms.find_one({"id": fid}, {"_id": 0, "history": 0})
        if not f:
            raise HTTPException(status_code=404, detail="Formular inexistent")
        return [pub(await check_one(f))]
    return [pub(f) for f in await check_all()]


@api.post("/cron/forms-check")
async def cron_forms(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or not hmac.compare_digest(h[7:], os.environ.get("WEBHOOK_CRON_SECRET", "")):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("x-webhook-id") or str(uuid.uuid4())
    if await db.cron_runs.find_one({"id": run_id}):
        return {"status": "duplicate"}
    await db.cron_runs.insert_one({"id": run_id, "at": now(), "name": "forms-check"})
    background.add_task(check_all, True)
    return {"status": "accepted"}
