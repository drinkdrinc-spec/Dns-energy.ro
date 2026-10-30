import json
import re
import os
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from ai_provider import LlmChat, UserMessage, TextDelta, StreamDone

import server as S
import cef as CEF

db, api, get_current_user, logger = S.db, S.api_router, S.get_current_user, S.logger
MODEL = ("openai", "gpt-4.1-mini")
FEAT = "ai_gpt"
RULES = ("Răspunzi exclusiv în limba română, clar și profesionist, text simplu (liste cu „- ”, fără tabele markdown). "
         "Nu inventa niciodată măsurători, numere de aviz/ATR, serii, semnături, ștampile sau autorizații: dacă o informație lipsește, scrie [de completat]. "
         "Responsabilitatea tehnică finală aparține electricianului autorizat ANRE / proiectantului.")
SYS_CHAT = ("Ești asistentul tehnic D-ENERGY (DNS HOSTESS S.R.L.) pentru instalații electrice și sisteme fotovoltaice din România: "
            "normativ I7/2011, Ord. ANRE 19/2022, 59/2013, 69/2020, SR EN IEC 62446-1, HD 60364, PRAM, dosare de prosumator, ATR, DI-U, operatori de distribuție. " + RULES)
now = lambda: datetime.now(timezone.utc).isoformat()


def new_chat(system: str, history: list = None) -> LlmChat:
    init = [{"role": "system", "content": system}] + (history or [])
    return LlmChat(api_key=os.environ["OPENAI_API_KEY"], session_id=str(uuid.uuid4()), system_message=system,
                   initial_messages=init).with_model(*MODEL)


def sse(chat: LlmChat, text: str, on_done=None):
    async def gen():
        out = ""
        try:
            async for ev in chat.stream_message(UserMessage(text=text)):
                if isinstance(ev, TextDelta):
                    out += ev.content
                    yield f"data: {json.dumps({'t': ev.content}, ensure_ascii=False)}\n\n"
                elif isinstance(ev, StreamDone):
                    break
            if on_done:
                await on_done(out)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"AI stream failed: {e}")
            yield f"data: {json.dumps({'error': 'Asistentul AI nu a putut răspunde acum. Încearcă din nou.'}, ensure_ascii=False)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def ai_need(user: dict):
    S.need(user, FEAT, True)


async def own_session(user: dict, sid: str) -> dict:
    s = await db.ai_sessions.find_one({"id": sid, "owner": user["id"], "uid": user["uid"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Conversație inexistentă")
    return s


# ---------------- Asistent tehnic (chat) ----------------
@api.get("/ai/sessions")
async def ai_sessions(user: dict = Depends(get_current_user)):
    ai_need(user)
    return await db.ai_sessions.find({"owner": user["id"], "uid": user["uid"]}, {"_id": 0}).sort("updated_at", -1).to_list(200)


@api.post("/ai/sessions")
async def ai_session_new(user: dict = Depends(get_current_user)):
    ai_need(user)
    s = {"id": str(uuid.uuid4()), "owner": user["id"], "uid": user["uid"], "title": "Conversație nouă", "created_at": now(), "updated_at": now()}
    await db.ai_sessions.insert_one(dict(s))
    return s


@api.delete("/ai/sessions/{sid}")
async def ai_session_del(sid: str, user: dict = Depends(get_current_user)):
    ai_need(user)
    await own_session(user, sid)
    await db.ai_sessions.delete_one({"id": sid})
    await db.ai_messages.delete_many({"session_id": sid})
    return {"ok": True}


@api.get("/ai/sessions/{sid}/messages")
async def ai_messages(sid: str, user: dict = Depends(get_current_user)):
    ai_need(user)
    await own_session(user, sid)
    return await db.ai_messages.find({"session_id": sid}, {"_id": 0}).sort("at", 1).to_list(1000)


@api.post("/ai/sessions/{sid}/message")
async def ai_message(sid: str, request: Request, user: dict = Depends(get_current_user)):
    ai_need(user)
    s = await own_session(user, sid)
    text = str((await request.json()).get("text") or "").strip()[:6000]
    if not text:
        raise HTTPException(status_code=400, detail="Scrie o întrebare")
    past = await db.ai_messages.find({"session_id": sid}, {"_id": 0, "role": 1, "content": 1}).sort("at", -1).to_list(30)
    await db.ai_messages.insert_one({"session_id": sid, "role": "user", "content": text, "at": now()})
    upd = {"updated_at": now()}
    if s["title"] == "Conversație nouă":
        upd["title"] = text[:60]
    await db.ai_sessions.update_one({"id": sid}, {"$set": upd})

    async def done(out):
        await db.ai_messages.insert_one({"session_id": sid, "role": "assistant", "content": out, "at": now()})
    return sse(new_chat(SYS_CHAT, list(reversed(past))), text, done)


# ---------------- Verificare dosar înainte de trimitere ----------------
KEYS = ("client_name", "address", "county", "pod", "operator", "power", "apparent_kva", "supply", "system_type", "inverter", "inverter_kw", "inverter_count",
        "panels", "panel_count", "panel_w", "battery", "grounding_ohm", "grounding_limit", "atr", "afm", "pif_date", "receptie_date", "doc_date", "status")


async def dossier_summary(user: dict, item_id: str) -> dict:
    rec, client, settings, info = await S.dossier_ctx(user, item_id)
    chk = CEF.check(rec.get("cef") or {})
    return {"date_dosar": {k: rec.get(k) for k in KEYS if rec.get(k) not in (None, "")},
            "client": {k: client.get(k) for k in ("name", "kind", "address", "county", "phone", "email") if client.get(k)},
            "executant": {k: settings.get(k) for k in ("company", "cui", "anre_attest", "anre_valid", "rep") if settings.get(k)},
            "configurare_cef": {"totaluri": chk.get("totals"), "erori": chk.get("errors"), "avertizari": chk.get("warnings"),
                                "invertoare": [{"model": i.get("brand_model"), "kw": i.get("ac_kw") or i.get("kw"), "stringuri": len(i.get("strings") or [])}
                                               for i in (rec.get("cef") or {}).get("inverters") or []]},
            "pif_masuratori_completat": bool((rec.get("pif") or {}).get("date")),
            "opis": [{"nr": p["nr"], "document": p["title"], "status": p["status"], "lipsa": p["missing"]} for p in info["positions"]],
            "date_comune_lipsa": info["common_missing"]}


@api.post("/ai/dossier/{item_id}/check")
async def ai_dossier_check(item_id: str, user: dict = Depends(get_current_user)):
    ai_need(user)
    S.guard("prosumator", user)
    ctx = await dossier_summary(user, item_id)
    prompt = ("Verifică dosarul de prosumator de mai jos înainte de trimiterea către operatorul de distribuție. Structurează răspunsul în: "
              "1) Verdict scurt (Gata de trimis / Necesită completări / Probleme tehnice); 2) Date și documente lipsă (concret, pe poziții din opis); "
              "3) Neconcordanțe tehnice (puteri invertor vs. putere evacuată vs. kVA, monofazat/trifazat, priză de pământ vs. valoare admisă, compatibilități CEF); "
              "4) Pașii recomandați, în ordine. Nu repeta datele corecte.\n\nDOSAR (JSON):\n" + json.dumps(ctx, ensure_ascii=False, default=str)[:14000])
    await S.audit(user, "verificare AI", "prosumator", item_id, ["ChatGPT"])
    return sse(new_chat("Ești verificator de dosare de prosumator pentru D-ENERGY. " + RULES), prompt)


# ---------------- Redactare texte ----------------
@api.post("/ai/draft")
async def ai_draft(request: Request, user: dict = Depends(get_current_user)):
    ai_need(user)
    b = await request.json()
    module = b.get("module") or "prosumator"
    if module not in S.MODULES:
        raise HTTPException(status_code=400, detail="Modul invalid")
    S.guard(module, user)
    label = str(b.get("label") or "").strip()[:120]
    if not label:
        raise HTTPException(status_code=400, detail="Câmp necunoscut")
    form = {k: v for k, v in (b.get("form") or {}).items() if isinstance(v, (str, int, float)) and str(v).strip() and k not in ("id", "owner")}
    prompt = (f"Redactează textul pentru câmpul „{label}” al unui document tehnic ({module}). Stil formal, tehnic, concis, potrivit unui proces-verbal / dosar românesc. "
              f"Răspunde DOAR cu textul final, fără introducere. Folosește doar datele de mai jos; pentru ce lipsește pune [de completat].\n"
              f"Instrucțiuni utilizator: {str(b.get('instructions') or '—')[:800]}\nText existent: {str(b.get('current') or '—')[:2000]}\n"
              f"Date din formular (JSON): {json.dumps(form, ensure_ascii=False)[:8000]}")
    return sse(new_chat("Ești redactor tehnic pentru D-ENERGY. " + RULES), prompt)


# ---------------- Verificare automată la finalizare (listă de bifat) ----------------
SEV = ("critic", "important", "minor")


async def collect(chat: LlmChat, text: str) -> str:
    out = ""
    async for ev in chat.stream_message(UserMessage(text=text)):
        if isinstance(ev, TextDelta):
            out += ev.content
        elif isinstance(ev, StreamDone):
            break
    return out


async def run_precheck(summary: dict, what: str) -> list:
    prompt = (f"Verifică {what}. Răspunde DOAR cu JSON valid: "
              '{"items":[{"text":"acțiune concretă de verificat sau completat","severity":"critic|important|minor"}]}. '
              "Maximum 15 puncte, fiecare scurt (max 160 caractere), fără puncte pentru date corecte. Dacă dosarul e complet și coerent, items = [].\n\nDOSAR (JSON):\n"
              + json.dumps(summary, ensure_ascii=False, default=str)[:14000])
    try:
        out = await collect(new_chat("Ești verificator de dosare electrice pentru D-ENERGY. " + RULES), prompt)
        m = re.search(r"\{.*\}", out, re.S)
        raw = (json.loads(m.group(0)) if m else {}).get("items") or []
    except Exception as e:
        logger.error(f"AI precheck failed: {e}")
        raise HTTPException(status_code=502, detail="Verificarea AI nu a putut fi efectuată acum. Poți continua și fără ea.")
    return [{"text": str(i.get("text"))[:300], "severity": i.get("severity") if i.get("severity") in SEV else "important"}
            for i in raw if isinstance(i, dict) and i.get("text")][:15]


async def save_ack(user, module, item_id, request):
    ai_need(user)
    S.guard(module, user, write=True)
    rec = await S.check_access(user, module, item_id)
    n = len((rec.get("ai_precheck") or {}).get("items") or [])
    checked = sorted({int(i) for i in (await request.json()).get("checked") or [] if str(i).isdigit() and int(i) < n})
    await db[module].update_one({"id": item_id}, {"$set": {"ai_precheck.checked": checked, "ai_precheck.ack_at": now()}})
    await S.audit(user, "verificare AI", module, item_id, [f"{len(checked)}/{n} puncte bifate"])
    return {"checked": checked, "unchecked": n - len(checked)}


@api.post("/ai/dossier/{item_id}/precheck")
async def ai_precheck(item_id: str, user: dict = Depends(get_current_user)):
    ai_need(user)
    S.guard("prosumator", user, write=True)
    items = await run_precheck(await dossier_summary(user, item_id), "dosarul de prosumator înainte de FINALIZARE")
    pc = {"at": now(), "by": user.get("email"), "items": items, "checked": []}
    await db.prosumator.update_one({"id": item_id, "owner": user["id"]}, {"$set": {"ai_precheck": pc}})
    return pc


@api.post("/ai/dossier/{item_id}/precheck/ack")
async def ai_precheck_ack(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    return await save_ack(user, "prosumator", item_id, request)


DIU_KEYS = ("number", "client_name", "type", "power", "address", "operator", "atr", "date", "status", "supply", "earthing", "bmp_a", "tg_breaker_a",
            "column_cable", "memoriu_desc", "receptie_date", "receptie_decision", "receptie_findings", "pif_date", "pif_decision", "warranty_months", "warranty_start")


@api.post("/ai/diu/{item_id}/precheck")
async def ai_diu_precheck(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    import diu_routes as DR
    import diu_doc as DD
    ai_need(user)
    S.guard("diu", user, write=True)
    rec, r, client, s = await DR.diu_ctx(user, item_id)
    try:
        form = (await request.json()).get("form") or {}
    except Exception:
        form = {}
    if isinstance(form, dict):
        r = {**r, **{k: v for k, v in form.items() if k in DIU_KEYS + ("circuits", "pram_m") and v not in (None, "")}}
    summary = {"date_diu": {k: r.get(k) for k in DIU_KEYS if r.get(k) not in (None, "")}, "circuite_si_masuratori": r.get("circuits") or [],
               "pram_general": r.get("pram_m") or {}, "client": {k: client.get(k) for k in ("name", "address", "phone", "email") if client.get(k)},
               "executant": {k: s.get(k) for k in ("company", "anre_attest", "anre_valid", "rep") if s.get(k)},
               "documente": [{"nr": p["nr"], "document": p["title"], "status": p["status"], "lipsa": p["missing"]} for p in DD.positions(r, s)]}
    items = await run_precheck(summary, "dosarul instalației de utilizare (DI-U) înainte de PREDAREA către beneficiar: completitudine documente, "
                                        "coerență circuite/protecții/secțiuni, rezultate PRAM (izolație ≥1 MΩ, DDR ≤300 ms, priză ≤ valoarea admisă), date recepție/PIF/garanție")
    pc = {"at": now(), "by": user.get("email"), "items": items, "checked": []}
    await db.diu.update_one({"id": item_id, "owner": user["id"]}, {"$set": {"ai_precheck": pc}})
    return pc


@api.post("/ai/diu/{item_id}/precheck/ack")
async def ai_diu_precheck_ack(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    return await save_ack(user, "diu", item_id, request)


# ---------------- Mesaj AI către client (linkuri de semnare) ----------------
CHANNELS = {"whatsapp": "WhatsApp (scurt, prietenos, fără subiect)", "sms": "SMS (foarte scurt)", "email": "e-mail (prima linie „Subiect: ...”, apoi mesajul)"}


@api.post("/ai/sign-message")
async def ai_sign_message(request: Request, user: dict = Depends(get_current_user)):
    ai_need(user)
    b = await request.json()
    S.guard("diu" if b.get("module") == "diu" else "prosumator", user, write=True)
    links = [x for x in b.get("links") or [] if isinstance(x, dict) and str(x.get("url") or "").startswith("http")][:20]
    if not links or not b.get("dossier_id"):
        raise HTTPException(status_code=400, detail="Nu există linkuri active de trimis")
    ch = b.get("channel") if b.get("channel") in CHANNELS else "whatsapp"
    if b.get("module") == "diu":
        import diu_routes as DR
        rec, _, client, s = await DR.diu_ctx(user, b["dossier_id"])
    else:
        rec, client, s, _ = await S.dossier_ctx(user, b["dossier_id"])
    lst = "\n".join(f"- {str(x.get('title'))[:120]}: {x['url']}" for x in links)
    prompt = (f"Scrie UN SINGUR mesaj pentru canalul {CHANNELS[ch]} către clientul {client.get('name') or rec.get('client_name') or ''}, "
              f"din partea firmei {s.get('company') or 'DNS HOSTESS SRL'} (contact: {s.get('phone') or ''} {s.get('email') or ''}). "
              "Mesajul cere semnarea electronică a documentelor dosarului (prosumator sau DI-U, după titluri). Include TOATE linkurile de mai jos, fiecare pe rândul lui, copiate EXACT, caracter cu caracter. "
              "Explică pe scurt pașii: deschide linkul, citește documentul, cere codul primit pe e-mail, semnează pe ecran. Menționează că fiecare link este valabil 7 zile "
              "și că este o semnătură electronică simplă. Răspunde doar cu textul mesajului.\n\nDocumente și linkuri:\n" + lst)
    return sse(new_chat("Ești asistentul de comunicare cu clienții al firmei. " + RULES), prompt)
