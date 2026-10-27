import uuid
from datetime import datetime, timezone, timedelta
from html import escape

from fastapi import HTTPException, Request, Depends, Header, Query, Response
from pymongo import ReturnDocument

import server as S
import offer_doc as OD

db, api, get_current_user = S.db, S.api_router, S.get_current_user
FEAT = "oferte"
START = {"offer": 249, "contract": 93}
OFFER_ST = ["Ciornă", "Trimisă", "Acceptată", "Respinsă", "Expirată"]
CONTRACT_ST = ["Generat", "Trimis la semnare", "Semnat", "În execuție", "Finalizat", "Reziliat"]
now = lambda: datetime.now(timezone.utc).isoformat()
P = lambda *a: "\n".join(a)

DEFAULT_ARTICLES = [
    {"title": "I. PĂRȚILE CONTRACTANTE", "text": P("Încheiat azi, {data}, între părțile:", "{prestator}, denumită în continuare PRESTATOR,", "şi",
                                                    "{beneficiar}", "Încheie acest contract având in vedere următoarele condiții contractuale:")},
    {"title": "II. OBIECTUL CONTRACTULUI", "text": P(
        "Obiectul prezentului contract îl constituie:",
        "1. Furnizarea echipamentelor fotovoltaice de către Furnizor așa cum acestea sunt descrise în cuprinsul Anexei nr. 1 parte integrantă a prezentului contract;",
        "2. Furnizarea materialelor necesare instalării de către Furnizor așa cum acestea sunt descrise in cuprinsul Anexei nr. 1 parte integrantă a prezentului contract;",
        "3. Executarea lucrării de montaj a sistemului de panouri solare fotovoltaice de către Furnizor așa cum este descris în Anexa nr.1 parte integrantă a prezentului contract;",
        "4. Întocmirea dosarului de prosumator după predarea-primirea serviciilor de instalare, punerea în funcțiune a sistemului fotovoltaic și achitării integrale a prețului contractual;")},
    {"title": "III. PREŢUL CONTRACTULUI", "text": P(
        "a. Prețul contractului este {pret_net} + TVA ({tva}; total {pret_total} cu TVA), cel reflectat în conținutul anexei nr. 1 parte integrantă a prezentului contract.",
        "b. {plata}", "c. Efectuarea acestei plăți reprezintă acceptarea ofertei cu toate condițiile menționate și lansarea comenzii.",
        "d. Documentația pentru dosarul de prosumator nu se va întocmi și depune decât după plata integrală a prezentului contract.")},
    {"title": "IV. DURATA CONTRACTULUI", "text": P(
        "Prezentul contract intră în vigoare de la data semnării lui și este valabil până la stingerea tuturor obligațiilor asumate de părți prin prezentul contract.",
        "Termenul de livrare a produselor și executarea lucrărilor este de {termen_executie} de la data plății facturii, emise de către Prestator.")},
    {"title": "V. DREPTURILE ŞI OBLIGAŢIILE BENEFICIARULUI", "text": P(
        "Beneficiarul are următoarele drepturi:", "1. De a primi bunurile oferate și contractate;",
        "2. De a beneficia de montaj și instalare în condițiile prezentului contract și a Anexei nr.1;",
        "3. De a beneficia de service pentru lucrările ce fac obiectul prezentului contract în termenul și cu respectarea condițiilor de garanție specificate în cuprinsul Anexei nr.2 parte integrantă a prezentului contract. Se poate asigura și un service post garanție pentru produsele livrate, inclusiv piesele de schimb, fie pe baza unui contract de service/mentenanță, ce urmează sa fie încheiat cu beneficiarul, caz în care, se efectuează revizii periodice (fapt ce poate preîntâmpina defecțiuni mai costisitoare), fie, fără un asemenea contract, caz în care, intervenția se va efectua doar la solicitarea clientului.",
        "Beneficiarul are următoarele obligații:",
        "a.) {obligatie_plata} În funcție de întârzierea beneficiarului la plata, furnizorul își rezerva dreptul de a decala termenul de livrare cu o perioadă corespunzătoare, fără a fi răspunzător în vreun fel.",
        "b.) Să achite, integral, contravaloarea contractului conform condițiilor și etapelor de plată specificate în prezentul contract și a Anexei nr. 1",
        "c.) Să primească echipamentele și componentele sistemului de panouri fotovoltaice contractate și furnizate de Furnizor în condițiile prezentului contract;",
        "d.) Să participe la recepția sistemului de panouri fotovoltaice consemnând eventualele obiecțiuni în cadrul procesului verbal întocmit de furnizor;",
        "e.) Să recepționeze întreaga lucrare in maxim 3 zile de la finalizarea acesteia; în cazul în care, beneficiarul nu trece la recepționarea lucrării în termenul mai sus indicat, lucrarea se consideră ca fiind acceptată, preluată (fără obiecțiuni), iar recepția ca fiind efectuată, obiecțiuni ulterioare nefiind acceptate.",
        "f.) Să asigure accesul la locul de lucru pentru montaj și instalare împreuna cu utilitățile necesare (parcare, acces, acces scară acoperiș, priză alimentare cu energie electrică 230VAC etc.); în cazul în care beneficiarul nu îndeplinește aceasta obligație, furnizorul își rezerva dreptul de a decala termenul de montaj pana la asigurarea utilităților necesare fără a fi răspunzător în vreun fel.",
        "g.) Să încheie o convenție privind respectarea cerințelor minime de securitate și sănătate în muncă, situații de urgență și protecția mediului pentru activitatea de prestări servicii execuție sistem de panouri fotovoltaice;",
        "h.) Să pună la dispoziția Furnizorului toate documentele necesare pentru întocmirea documentației de prosumator, acestea fiind: CI/CUI SCANAT; Extras de Carte Funciară pentru imobil actualizat, nu mai vechi de 30 zile; Factura de energie electrică; Și orice alte documente solicitate de către Furnizor;",
        "i.) Beneficiarul se obligă să pună la dispoziția Prestatorului documentele, informațiile (cu titlu de exemplu informații cu privire la structura de rezistență a imobilului, studiu tehnic, etc) solicitate și, totodată, răspunde de realitatea și veridicitatea informațiilor și datelor din documentele prezentate. Beneficiarul garantează faptul că locația, inclusiv acoperișul, structurile de suport și cablarea electrică sunt sigure și potrivite pentru instalarea sistemului.")},
    {"title": "VI. DREPTURILE ŞI OBLIGAŢIILE FURNIZORULUI", "text": P(
        "Prestatorul are următoarele drepturi:",
        "1. De a primi, cu titlu de despăgubire , contravaloarea a 70% din pretul achitat, în cazul în care prezentul contract este reziliat unilateral și nemotivat de către Beneficiar. Astfel:",
        "- Cumpărătorul este de acord și accepta în mod expres ca, 70 % din suma de bani plătită pentru acest contract nu va fi restituită de către vânzător/furnizor (aceasta reprezentând despăgubirea furnizorului pentru prejudiciul creat) în cazul renunțării, anularii sau modificării (exceptând modificarea acceptata de către Furnizor si situația creșterii comenzii) de către cumpărător a comenzii efectuate, fără a mai avea dreptul de a ridica vreo pretenție asupra mărfurilor din comanda la care a renunțat, a anulat-o sau modificat-o.",
        "- Diferența de 30% din contravaloarea achitata se va restitui Beneficiarului în termen de 30 zile calendaristice.",
        "2. De a încasa contravaloarea bunurilor livrate și a serviciilor furnizate la termenele stabilite;",
        "3. De a folosi energia electrică și a altor utilități de la locul de montaj necesare pentru executarea lucrărilor în bune condiții;",
        "4. Bunurile rămân proprietatea furnizorului până la plata integrală a prețului acestora conform prevederilor contractuale, cumpărătorul exprimându-și acordul cu privire la accesul vânzătorului în incinta locului unde se află produsele, în cazul neachitării integrale a prețului contractual, în vederea ridicării acestora de către vânzător.",
        "5. De a nu depune documentația pentru dosarul de prosumator până la plata integrală a prezentului contract.",
        "Prestatorul are următoarele obligații:",
        "1. Să livreze bunurile și să presteze serviciile de montaj ale sistemului de panouri fotovoltaice în termenele și la calitatea stabilită; cheltuielile cu transportul și punerea în funcțiune a tuturor componentelor sistemului de panouri fotovoltaice vor fi suportate de către furnizor;",
        "2. Să furnizeze beneficiarului certificatele de garanție, declarațiile de conformitate, manualele de utilizare și întreținere pentru produsele fotovoltaice;",
        "3. Să asigure service pentru lucrările ce fac obiectul prezentului contract în limitele legii și în conformitate cu art. VIII din prezentul contract;",
        "4. Să efectueze punerea în funcțiune a sistemului de panouri fotovoltaice și să întocmească procesul verbal de recepție;",
        "5. Să încheie o convenție privind respectarea cerințelor minime de securitate și sănătate în muncă, situații de urgență și protecția mediului pentru activitatea de prestări servicii execuție sistem de panouri fotovoltaice;",
        "6. Să restituie tranșa încasată în cazul în care furnizorul anulează contractul.")},
    {"title": "VII. FORŢA MAJORĂ/CAZ FORTUIT", "text": P(
        "- Forța Majoră suspendă drepturile și obligațiile prezentului contract până la dispariția acesteia.",
        "- Forța Majoră nu poate fi invocată după predarea-primirea bunurilor și lucrărilor.",
        "- Forța majoră, cazul forțuit exonerează de răspundere părțile, în cazul neexecutării parțiale sau totale a obligațiilor asumate prin prezentul contract.",
        "Prin forța majoră se înțelege un eveniment independent de voința părților, imprevizibil sau insurmontabil, apărut după încheierea contractului și, care împiedică părțile să execute total sau parțial obligațiile asumate. Partea care invocă forța majoră are obligația să o aducă la cunoștința celeilalte părți în scris, în maxim 10 zile de la apariție, iar dovadă forței majore se va comunica în maximum 15 zile de la apariție. În acest caz, nici una dintre părți nu are dreptul de a cere despăgubiri la cealaltă parte, dar ele au îndatorirea de a-și onora toate obligațiile până la această dată.",
        "Art.1364 – (1) Dacă legea nu prevede altfel sau părțile nu convin contrariul, răspunderea este înlăturată atunci când prejudiciul este cauzat de forță majoră, de caz forțuit, de fapta victimei înseși sau de fapta unui terț pentru care cel căruia i se solicită repararea prejudiciului nu este ținut să răspundă.",
        "(2) Forța majoră este orice eveniment extern, absolut imprevizibil și absolut invincibil.",
        "(3) Cazul forțuit este un eveniment care nu poate fi prevăzut și nici împiedicat de către cel care ar fi fost chemat să răspundă dacă evenimentul nu s-ar fi produs.",
        "(4) Fapta victimei înseși și fapta terțului înlătură răspunderea chiar dacă nu au trăsături similare forței majore, însă numai în cazurile în care, potrivit legii sau convenției părților, cazul forțuit este exonerator de răspundere.",
        "(5) Dacă, potrivit legii, debitorul este exonerat de răspundere contractuală pentru un caz forțuit, el este, de asemenea, exonerat și în caz de forță majoră.")},
    {"title": "VIII. LITIGII", "text": P(
        "- Orice neînțelegeri sau dezacorduri cu privire la executarea prezentului contract vor fi soluționate pe cale amiabilă.",
        "- În cazul în care nu este posibilă concilierea diferențelor pe cale amiabilă acestea vor fi soluționate de către instanța judecătorească competentă de la sediul Furnizorului.")},
    {"title": "IX. RECEPȚIA ȘI PERIOADA DE GARANŢIE ACORDATĂ PRODUSELOR", "text": P(
        "1. La finalizarea lucrărilor, ulterior punerii în funcțiune a sistemului de panouri fotovoltaice, furnizorul va înștiința beneficiarul (prin e-mail/notificare scrisă) cu privire la data efectuarii recepției sistemului de panouri fotovoltaice. Furnizorul va întocmi procesul verbal de recepție în cadrul căruia se vor menționa eventualele obiecțiuni sau lipsa lor.",
        "2. Prestatorul are obligaţia de a garanta (pe baza garanției primite la achiziționarea acestora de la producator) ca echipamentele furnizate prin contract sunt noi, nefolosite, de ultimă generaţie şi incorporează toate îmbunătăţirile recente în proiectare şi structura materialelor. De asemenea, furnizorul are obligaţia de a garanta că echipamentele/oricare componentă a acestora, furnizate prin contract nu vor avea nici un defect ca urmare a montării acestora sau ca și consecință a unei acţiuni sau omisiuni a Prestator şi că acestea vor funcţiona în condiţii normale de funcţionare.",
        "3. Perioada de garanţie acordată sistemului de panouri fotovoltaice cuprinde:",
        "a) Garanția echipamentelor/oricăror componente ale sistemului fiind cea prevazută în certificatele de garanție – emise de catre producator - care însoțesc echipamentele cumpărate de furnizor (la data achiziției produsele venind însoțite de aceste certificate), conform anexei prevazute mai jos de la recepția echipamentelor sistemului de panouri fotovoltaice.",
        "b) Garanția pentru manopera și montajul tuturor echipamentelor și componentelor sistemului de panouri fotovoltaice este de {garantie_lucrari} luni de la semnarea Procesului verbal de terminare a lucrărilor.",
        "4. Perioada de garanţie, atât a echipamentelor sistemului fotovoltaic cât și pentru pentru manoperă și montajul acestora, începe să curgă de la data recepţiei echipamentelor sistemului fotovoltaic, respectiv dupa punerea în funcțiune a sistemului de panouri fotovoltaice.",
        "5. Beneficiarul are dreptul de a notifica imediat furnizorului, în scris (prin e-mail/notificare scrisă), orice reclamaţie ce apare în conformitate cu această garanţie. La primirea unei astfel de notificări, furnizorul, pe baza constatarilor facute, are obligaţia de a remedia defecţiunea sau de a înlocui echipamentul/oricare componentă a acestuia într-un termen de maxim 90 zile calendaristice (în situații de excepție, părțile vor putea negocia un alt termen), cu excepția cazurilor în care, deteriorările sunt rezultatul unor utilizări defectuoase, intervenții neautorizate, calamități naturale, caz în care, toate cheltuielile legate de reparație și piese de schimb, se vor suporta de către beneficiar. Echipamentele/componentele care, în timpul perioadei de garanţie, le înlocuiesc pe cele defecte, beneficiază de o nouă perioadă de garanţie care curge de la data înlocuirii produsului.",
        "6. Orice defect vizual al echipamentelor din sistemul fotovoltaic trebuie notificat Furnizorului la data recepției acestora.",
        "7. În perioada de garanție a centralei fotovoltaice, orice modificări sau intervenții în instalația electrică făcute de persoane, altele decât personalul Prestatorului, vor duce la anularea garanției oferite de Prestator.",
        "8. Orice modificări ale parametrilor de funcționare a invertoarelor fotovoltaice sau a centralei electrice fotovoltaice se vor face doar de Prestator sau de personal autorizat Huawei,Solis,Deye, etc, cu acordul explicit al Prestatorului.",
        "9. Orice modificări ale parametrilor de funcționare ai invertoarelor fotovoltaice sau ai centralei electrice fotovoltaice făcute de alt personal și în alte condiții decât este stipulate la art. VIII vor duce la anularea garanției oferite de prestator.")},
    {"title": "X. REZILIEREA CONTRACTULUI", "text": P(
        "1. Nerespectarea obligaţiilor asumate prin prezentul contract de către una dintre părţi dă dreptul părţii lezate de a cere rezilierea contractului şi de a pretinde plata de daune-interese.",
        "2. Beneficiarul poate cere rezilierea contractului dacă:",
        "a) Frunizorul intră în re-organizare, fuzionare sau dizolvare, se deschide procedura insolvenței împotriva sa ori are o ipotecă pe capital;",
        "b) Furnizorul neglijează în mod flagrant și repetat să-și îndeplinească obligaţiile contractuale mai mult de 30 zile calendaristice, deşi a fost notificat de Beneficiar.",
        "3. Furnizorul poate cere rezilierea contractului coroborat cu solicitarea de penalități de întârziere dacă:",
        "a) Beneficiarul nu onorează o plată scadentă mai mult de 15 zile calendaristice.",
        "4. Notificarea de reziliere a contractului, se va comunica în scris părții contractante.",
        "5. În cazul rezilierii pentru motivele menționate la pct.2 lit. a - b Furnizorul va restitui Beneficiarului tranșa plătită. În acesta situație contractul înceteaza de plin drept la data comunicării notificării de reziliere, fără a mai fi necesară vreo notificare suplimentară sau intervenţia instanţei judecătoreşti.",
        "6. Rezilierea contractului nu va avea nici un efect în ceea ce privește obligațiile scadente până la acea dată, și neachitate, ale părților. Cumpărătorul este de acord și acceptă în mod expres ca, 50 % din suma de bani plătită ca avans pentru acest contract nu va fi restituită de către vânzător/furnizor (aceasta reprezentând despăgubirea furnizorului pentru prejudiciul creat) în cazul renunțării, anulării sau modificării (exceptând modificarea acceptată de către Furnizor și situația creșterii comenzii) de către cumpărător a comenzii efectuate, fără a mai avea dreptul de a ridica vreo pretenție asupra mărfurilor din comanda la care a renunțat, a anulat-o sau modificat-o.",
        "7. Denunțarea unilaterală a contractului de către beneficiar este interzisă.")},
    {"title": "XI. DISPOZIŢII FINALE", "text": P(
        "1. În accepțiunea părților contractante, orice comunicare adresată de către una dintre acestea celeilalte, este valabil îndeplinită dacă va fi transmisă la adresa menționată în prezentul contract, prin poștă/curier sau predare directă însoțită de semnătura de primire ori prin poșta electronică la adresa de e-mail pusă la dispoziția fiecărei părți cu ocazia încheierii acestui contract. În cazul în care comunicarea se realizează prin intermediul poștei electronice, aceasta se consideră primită la momentul confirmării de transmitere.",
        "2. E-Mail/Telefon contact furnizor: {email_furnizor} / {tel_furnizor}", "3. E-Mail contact beneficiar: {email_beneficiar} / {tel_beneficiar}",
        "4. Orice modificare a prezentului contract se va face în scris cu acordul ambelor părți contractante.",
        "5. Prezentul contract împreună cu anexele, parte integrantă a acestuia, este încheiat în 2 (două) exemplare originale, câte unul pentru fiecare parte și intră în vigoare din momentul semnării lui de către cele două părți contractante.")},
    {"title": "XII. PROTECȚIA ȘI PRELUCRAREA DATELOR", "text": P(
        "Prin semnarea prezentului contract, părțile înțeleg că își dau acordul pentru prelucrarea datelor mele cu caracter personal de către societatea {firma} și de către terții stabiliți de aceasta, în scopul realizării demersurilor necesare ofertării și încheierii prezentului contract. Datele cu caracter personal colectate / comunicate de către Părți în vederea executării prezentului contract (nume, prenume, telefon, email, funcție, semnătură), vor fi utilizate strict pentru realizarea obiectului contractului, iar la încetarea acestuia vor fi returnate / șterse după caz, cu excepția celor care, trebuie păstrate o anumita perioadă de timp, potrivit prevederilor legislative aplicabile. Părțile sunt direct responsabile pentru îndeplinirea condițiilor de păstrare / stocare a datelor cu caracter personal astfel cum sunt detaliate în Regulamentul GDPR nr. 679/2016.",
        "Prezentul contract a fost încheiat astăzi {data}, în loc. {localitate}, în 2 exemplare originale, câte unul pentru fiecare Parte contractantă și produce efecte de la data semnării lui de către ambele Părți contractante.")},
]


def admin_only(user):
    if not S.is_admin(user):
        raise HTTPException(status_code=403, detail="Doar administratorul firmei poate modifica numerotarea și șablonul de contract")


def need(user, write=False):
    S.need(user, FEAT, write)


def clean(d):
    return {k: v for k, v in (d or {}).items() if k != "_id"}


async def settings(user):
    return await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}


async def next_number(owner: str, kind: str) -> int:
    coll = db.offers if kind == "offer" else db.contracts
    top = await coll.find({"owner": owner}, {"number": 1}).sort("number", -1).limit(1).to_list(1)
    floor = max(START[kind], (top[0]["number"] + 1) if top else 0)
    key = f"{kind}:{owner}"
    await db.counters.update_one({"id": key}, {"$max": {"next": floor}}, upsert=True)
    while True:
        n = (await db.counters.find_one_and_update({"id": key}, {"$inc": {"next": 1}}, return_document=ReturnDocument.BEFORE))["next"]
        if not await coll.find_one({"owner": owner, "number": n}, {"_id": 1}):
            return n


async def own(coll, user, item_id):
    d = await db[coll].find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Înregistrare inexistentă")
    return d


EDIT = ("title", "date", "validity_days", "beneficiary", "system", "items", "discount", "vat_rate", "prices_include_vat", "currency", "exchange_rate",
        "includes", "warranties", "commercial_notes", "maintenance", "show_line_prices", "client_id", "notes")


def pick(b):
    o = {k: b.get(k) for k in EDIT if k in b}
    if "items" in o:
        o["items"] = [{k: it.get(k) for k in ("category", "kind", "name", "description", "manufacturer", "model", "power", "capacity", "warranty", "qty", "unit", "unit_price")}
                      for it in o["items"] or [] if isinstance(it, dict)][:200]
    if o.get("currency") not in (None, "RON", "EUR"):
        raise HTTPException(status_code=400, detail="Moneda trebuie să fie RON sau EUR")
    return o


def summary(o):
    t = OD.calc(o)
    b = o.get("beneficiary") or {}
    return {**{k: o.get(k) for k in ("id", "number", "date", "status", "title", "version", "contract_id", "contract_version", "updated_at")},
            "beneficiary": b.get("name"), "net": t["net"], "gross": t["gross"], "currency": t["currency"],
            "contract_outdated": bool(o.get("contract_id")) and o.get("contract_version") != o.get("version")}


# ---------------- Oferte ----------------
@api.get("/offers")
async def offers_list(user: dict = Depends(get_current_user)):
    need(user)
    return [summary(o) for o in await db.offers.find({"owner": user["id"]}, {"_id": 0}).sort("number", -1).to_list(2000)]


@api.get("/offers/numbering")
async def numbering_get(user: dict = Depends(get_current_user)):
    need(user)
    return {"offer_next": await peek(user["id"], "offer"), "contract_next": await peek(user["id"], "contract")}


async def peek(owner, kind):
    coll = db.offers if kind == "offer" else db.contracts
    top = await coll.find({"owner": owner}, {"number": 1}).sort("number", -1).limit(1).to_list(1)
    c = await db.counters.find_one({"id": f"{kind}:{owner}"}) or {}
    n = max(START[kind], (top[0]["number"] + 1) if top else 0, c.get("next", 0))
    while await coll.find_one({"owner": owner, "number": n}, {"_id": 1}):
        n += 1
    return n


@api.put("/offers/numbering")
async def numbering_set(request: Request, user: dict = Depends(get_current_user)):
    need(user, True)
    admin_only(user)
    b = await request.json()
    for kind, key in (("offer", "offer_next"), ("contract", "contract_next")):
        if b.get(key) in (None, ""):
            continue
        n = int(b[key])
        coll = db.offers if kind == "offer" else db.contracts
        if n < 1 or await coll.find_one({"owner": user["id"], "number": {"$gte": n}}, {"_id": 1}):
            raise HTTPException(status_code=400, detail=f"Numărul {n} este deja folosit sau mai mic decât ultimul număr emis")
        await db.counters.update_one({"id": f"{kind}:{user['id']}"}, {"$set": {"next": n}}, upsert=True)
    return await numbering_get(user)


@api.post("/offers")
async def offer_create(request: Request, user: dict = Depends(get_current_user)):
    need(user, True)
    b = pick(await request.json())
    o = {"id": str(uuid.uuid4()), "owner": user["id"], "number": await next_number(user["id"], "offer"), "status": "Ciornă", "version": 1,
         "created_at": now(), "updated_at": now(), "created_by": user.get("email"), "date": b.get("date") or datetime.now(timezone.utc).date().isoformat(),
         "vat_rate": 21, "currency": "RON", "validity_days": 30, "show_line_prices": True, **{k: v for k, v in b.items() if k != "date"}}
    await db.offers.insert_one(dict(o))
    await S.audit(user, "creare ofertă", "offers", o["id"], [f"nr. {o['number']}"])
    return clean(o)


@api.get("/offers/{oid}")
async def offer_get(oid: str, user: dict = Depends(get_current_user)):
    need(user)
    o = await own("offers", user, oid)
    return {**o, "totals": OD.calc(o), "contract_outdated": bool(o.get("contract_id")) and o.get("contract_version") != o.get("version")}


@api.put("/offers/{oid}")
async def offer_update(oid: str, request: Request, user: dict = Depends(get_current_user)):
    need(user, True)
    o = await own("offers", user, oid)
    body = await request.json()
    b = pick(body)
    changed = {k: v for k, v in b.items() if o.get(k) != v}
    if not changed:
        return {**o, "totals": OD.calc(o)}
    if o.get("contract_id") and not body.get("confirm_contract_change"):
        raise HTTPException(status_code=409, detail="Oferta are deja un contract generat. Confirmă modificarea: contractul existent NU se modifică automat.")
    versioned = o.get("status") != "Ciornă" or o.get("contract_id")
    if versioned:
        await db.offer_versions.insert_one({"offer_id": oid, "owner": user["id"], "version": o["version"], "snapshot": o, "at": now(), "by": user.get("email")})
    upd = {**changed, "version": o["version"] + (1 if versioned else 0), "updated_at": now()}
    await db.offers.update_one({"id": oid}, {"$set": upd})
    await S.audit(user, "modificare ofertă", "offers", oid, list(changed.keys()))
    return await offer_get(oid, user)


@api.delete("/offers/{oid}")
async def offer_delete(oid: str, user: dict = Depends(get_current_user)):
    need(user, True)
    o = await own("offers", user, oid)
    if o.get("contract_id") or o.get("status") != "Ciornă":
        raise HTTPException(status_code=400, detail="Se pot șterge doar ofertele în stadiul Ciornă, fără contract (numărul rămâne rezervat)")
    await db.offers.delete_one({"id": oid})
    await S.audit(user, "ștergere ofertă", "offers", oid, [f"nr. {o['number']}"])
    return {"ok": True}


@api.post("/offers/{oid}/duplicate")
async def offer_dup(oid: str, user: dict = Depends(get_current_user)):
    need(user, True)
    o = await own("offers", user, oid)
    n = {**{k: o.get(k) for k in EDIT if k in o}, "id": str(uuid.uuid4()), "owner": user["id"], "number": await next_number(user["id"], "offer"), "status": "Ciornă",
         "version": 1, "created_at": now(), "updated_at": now(), "created_by": user.get("email"), "date": datetime.now(timezone.utc).date().isoformat(), "duplicated_from": o["number"]}
    await db.offers.insert_one(dict(n))
    return clean(n)


@api.post("/offers/{oid}/status")
async def offer_status(oid: str, request: Request, user: dict = Depends(get_current_user)):
    need(user, True)
    o = await own("offers", user, oid)
    st = (await request.json()).get("status")
    if st not in OFFER_ST:
        raise HTTPException(status_code=400, detail="Status invalid")
    if o.get("contract_id") and st != "Acceptată":
        raise HTTPException(status_code=400, detail="Oferta are contract generat; statusul rămâne Acceptată")
    await db.offers.update_one({"id": oid}, {"$set": {"status": st, "updated_at": now()}, "$push": {"history": {"at": now(), "by": user.get("email"), "status": st}}})
    await S.audit(user, "status ofertă", "offers", oid, [st])
    return {"status": st}


@api.get("/offers/{oid}/versions")
async def offer_versions(oid: str, user: dict = Depends(get_current_user)):
    need(user)
    await own("offers", user, oid)
    return [{"version": v["version"], "at": v["at"], "by": v.get("by"), "net": OD.calc(v["snapshot"])["net"]}
            for v in await db.offer_versions.find({"offer_id": oid, "owner": user["id"]}, {"_id": 0}).sort("version", -1).to_list(200)]


@api.get("/offers/{oid}/pdf")
async def offer_pdf(oid: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    need(user)
    o = await own("offers", user, oid)
    pdf = OD.offer_pdf(o, await settings(user))
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": S.disp("inline", f"Oferta_de_pret_{o['number']}.pdf")})


# ---------------- Șablon contract (clauze cu aprobare) ----------------
async def template(owner):
    t = await db.contract_templates.find_one({"owner": owner, "status": "aprobat"}, {"_id": 0}, sort=[("version", -1)])
    return t or {"version": 0, "status": "aprobat", "articles": DEFAULT_ARTICLES, "source": "model Contract nr. 817 (implicit)"}


@api.get("/contract-template")
async def tpl_get(user: dict = Depends(get_current_user)):
    need(user)
    pend = await db.contract_templates.find_one({"owner": user["id"], "status": "în așteptare"}, {"_id": 0}, sort=[("version", -1)])
    return {"active": await template(user["id"]), "pending": pend,
            "placeholders": ["data", "prestator", "beneficiar", "pret_net", "tva", "pret_total", "plata", "obligatie_plata", "termen_executie", "garantie_lucrari",
                             "email_furnizor", "tel_furnizor", "email_beneficiar", "tel_beneficiar", "firma", "localitate"]}


@api.put("/contract-template")
async def tpl_save(request: Request, user: dict = Depends(get_current_user)):
    need(user, True)
    admin_only(user)
    arts = (await request.json()).get("articles") or []
    arts = [{"title": str(a.get("title") or "").strip(), "text": str(a.get("text") or "")} for a in arts if isinstance(a, dict) and str(a.get("title") or "").strip()]
    if not arts:
        raise HTTPException(status_code=400, detail="Șablonul trebuie să conțină cel puțin un articol")
    last = await db.contract_templates.find_one({"owner": user["id"]}, sort=[("version", -1)])
    v = (last or {}).get("version", 0) + 1
    await db.contract_templates.delete_many({"owner": user["id"], "status": "în așteptare"})
    await db.contract_templates.insert_one({"owner": user["id"], "version": v, "status": "în așteptare", "articles": arts, "created_at": now(), "created_by": user.get("email")})
    await S.audit(user, "propunere șablon contract", "contracts", f"tpl-{v}", [f"{len(arts)} articole"])
    return {"version": v, "status": "în așteptare"}


@api.post("/contract-template/approve")
async def tpl_approve(request: Request, user: dict = Depends(get_current_user)):
    need(user, True)
    admin_only(user)
    b = await request.json()
    p = await db.contract_templates.find_one({"owner": user["id"], "status": "în așteptare"}, sort=[("version", -1)])
    if not p:
        raise HTTPException(status_code=404, detail="Nu există modificări în așteptare")
    st = "aprobat" if b.get("approve", True) else "respins"
    await db.contract_templates.update_one({"_id": p["_id"]}, {"$set": {"status": st, "decided_at": now(), "decided_by": user.get("email")}})
    await S.audit(user, f"șablon contract {st}", "contracts", f"tpl-{p['version']}", [])
    return {"version": p["version"], "status": st}


# ---------------- Contracte ----------------
def pay_calc(pay: dict, t: dict) -> dict:
    r, net, cur = t["vat_rate"] / 100, t["net"], t["currency"]
    m = lambda v: OD.money(v, cur)
    g = lambda v: round(v * (1 + r), 2)
    if pay.get("mode") == "avans":
        tr = [x for x in pay.get("tranches") or [] if isinstance(x, dict) and OD.num(x.get("value")) > 0]
        if tr:
            rows, left = [], net
            for i, x in enumerate(tr):
                a = round(net * OD.num(x["value"]) / 100, 2) if x.get("type") == "percent" else round(OD.num(x["value"]), 2)
                left = round(left - a, 2)
                rows.append({"label": x.get("label") or f"Tranșa {i + 1}", "net": a, "gross": g(a), "due": x.get("due") or ""})
            if left < -0.01:
                raise HTTPException(status_code=400, detail="Suma tranșelor depășește valoarea contractului")
            if left > 0.01:
                rows.append({"label": "Diferența rămasă", "net": left, "gross": g(left), "due": pay.get("balance_rule") or ""})
            txt = "Beneficiarul va plăti prețul contractului în tranșe, astfel: " + "; ".join(
                f"{x['label']}: {m(x['net'])} fără TVA ({m(x['gross'])} cu TVA){', ' + x['due'] if x['due'] else ''}" for x in rows) + "."
            return {"mode": "avans", "tranches": rows, "text": txt, "obligation": f"Să plătească tranșele de plată la termenele stabilite la art. III lit. b;"}
        v = OD.num(pay.get("advance_value"))
        adv = round(net * v / 100, 2) if pay.get("advance_type") == "percent" else round(v, 2)
        if adv <= 0 or adv > net:
            raise HTTPException(status_code=400, detail="Avansul trebuie să fie mai mare ca 0 și cel mult egal cu valoarea contractului")
        rest = round(net - adv, 2)
        days = int(OD.num(pay.get("advance_days"), 5))
        txt = (f"Beneficiarul va plăti, în termen de {days} zile calendaristice de la data semnării contractului, suma de {m(adv)} fără TVA ({m(g(adv))} cu TVA), "
               f"această sumă reprezentând avans" + (f", iar diferența de {m(rest)} fără TVA ({m(g(rest))} cu TVA) {pay.get('balance_rule') or '[termen de completat]'}" if rest > 0 else "") + ".")
        return {"mode": "avans", "advance_net": adv, "advance_gross": g(adv), "rest_net": rest, "rest_gross": g(rest), "advance_days": days, "text": txt,
                "obligation": f"Să plătească avansul în termen de {days} zile calendaristice de la semnarea contractului și emiterea facturii, pentru bunurile și lucrările prestate de către Furnizor;"}
    days = int(OD.num(pay.get("due_days"), 0))
    when = f"până la data de {D_ro(pay['due_date'])}" if pay.get("due_date") else (f"în termen de {days} zile calendaristice de la data semnării contractului și emiterea facturii" if days else (pay.get("due_rule") or "[termen de completat]"))
    return {"mode": "integral", "due_days": days, "due_date": pay.get("due_date"), "text": f"Beneficiarul va plăti integral prețul contractului, în sumă de {m(net)} fără TVA ({m(t['gross'])} cu TVA), {when}.",
            "obligation": f"Să plătească integral prețul contractului {when};"}


def D_ro(v):
    return OD.D.ro_date(v) or v


def render_articles(arts, vals):
    out = []
    for a in arts:
        txt = escape(a["text"])
        for k, v in vals.items():
            txt = txt.replace("{" + k + "}", v)
        out.append({"title": a["title"], "text": txt})
    return out


def values(o, t, s, pay, c):
    b = o.get("beneficiary") or {}
    m = lambda v: OD.money(v, t["currency"])
    e = lambda v: f"<b>{escape(str(v))}</b>" if v not in (None, "") else OD.M
    prest = (f"<b>S.C. {escape(s.get('company') or '')}</b>, cu sediul în {e(s.get('address'))}, având cod fiscal {e(s.get('cui'))}, "
             f"înregistrată la Registrul Comerțului sub Nr. {e(s.get('regcom'))}, reprezentat prin {e(s.get('rep'))}")
    return {"data": D_ro(c["date"]), "prestator": prest, "beneficiar": OD.party_line(b), "pret_net": f"<b>{m(t['net'])}</b>", "tva": f"TVA {t['vat_rate']:g}% = {m(t['vat'])}",
            "pret_total": f"<b>{m(t['gross'])}</b>", "plata": escape(pay["text"]), "obligatie_plata": escape(pay["obligation"]),
            "termen_executie": e(c.get("execution_term")), "garantie_lucrari": e(c.get("works_warranty_months")), "email_furnizor": e(s.get("email")),
            "tel_furnizor": e(s.get("phone")), "email_beneficiar": e(b.get("email")), "tel_beneficiar": e(b.get("phone")), "firma": e(s.get("company")),
            "localitate": e(c.get("place"))}


CFIELDS = ("payment", "execution_term", "works_warranty_months", "place", "date")


@api.post("/offers/{oid}/contract")
async def contract_create(oid: str, request: Request, user: dict = Depends(get_current_user)):
    need(user, True)
    o = await own("offers", user, oid)
    if o.get("status") != "Acceptată":
        raise HTTPException(status_code=400, detail="Contractul se generează doar dintr-o ofertă acceptată")
    b = await request.json()
    old = await db.contracts.find_one({"id": o.get("contract_id"), "owner": user["id"]}, {"_id": 0}) if o.get("contract_id") else None
    if old and not b.get("regenerate"):
        raise HTTPException(status_code=409, detail="Contractul există deja. Confirmă regenerarea din versiunea curentă a ofertei (versiunea anterioară se păstrează în istoric).")
    s = await settings(user)
    t = OD.calc(o)
    if t["net"] <= 0:
        raise HTTPException(status_code=400, detail="Oferta nu are valoare — adaugă pozițiile și prețurile")
    c = {**{k: b.get(k) for k in CFIELDS}, "date": b.get("date") or datetime.now(timezone.utc).date().isoformat()}
    if not isinstance(c["payment"], dict) or c["payment"].get("mode") not in ("integral", "avans"):
        raise HTTPException(status_code=400, detail="Alege modalitatea de plată (integrală sau cu avans)")
    pay = pay_calc(c["payment"], t)
    tpl = await template(user["id"])
    offer_snap = {k: o.get(k) for k in EDIT + ("number", "version")}
    doc = {**c, "payment_calc": pay, "offer": offer_snap, "totals": t, "template_version": tpl["version"],
           "articles": render_articles(tpl["articles"], values(o, t, s, pay, c)), "offer_id": oid, "offer_number": o["number"], "offer_version": o["version"]}
    if old:
        await db.contracts.update_one({"id": old["id"]}, {"$set": {**doc, "updated_at": now()}, "$push": {"revisions": {k: old.get(k) for k in ("date", "offer_version", "totals", "payment_calc", "articles", "template_version")} | {"archived_at": now()},
                                                                                                      "history": {"at": now(), "by": user.get("email"), "event": f"regenerat din oferta v{o['version']}"}}})
        cid = old["id"]
    else:
        cid = str(uuid.uuid4())
        await db.contracts.insert_one({**doc, "id": cid, "owner": user["id"], "number": await next_number(user["id"], "contract"), "status": "Generat", "created_at": now(),
                                       "updated_at": now(), "history": [{"at": now(), "by": user.get("email"), "event": f"generat din oferta nr. {o['number']} v{o['version']}"}], "revisions": []})
    await db.offers.update_one({"id": oid}, {"$set": {"contract_id": cid, "contract_version": o["version"]}})
    await S.audit(user, "generare contract", "contracts", cid, [f"oferta {o['number']}"])
    return clean(await db.contracts.find_one({"id": cid}, {"_id": 0}))


@api.post("/offers/{oid}/contract/preview")
async def contract_preview(oid: str, request: Request, user: dict = Depends(get_current_user)):
    need(user)
    o = await own("offers", user, oid)
    b = await request.json()
    return pay_calc(b.get("payment") or {}, OD.calc(o))


@api.get("/contracts")
async def contracts_list(user: dict = Depends(get_current_user)):
    need(user)
    out = []
    for c in await db.contracts.find({"owner": user["id"]}, {"_id": 0, "articles": 0, "revisions": 0}).sort("number", -1).to_list(2000):
        o = await db.offers.find_one({"id": c["offer_id"]}, {"version": 1})
        out.append({**{k: c.get(k) for k in ("id", "number", "date", "status", "offer_id", "offer_number", "offer_version")}, "beneficiary": (c["offer"].get("beneficiary") or {}).get("name"),
                    "net": c["totals"]["net"], "gross": c["totals"]["gross"], "currency": c["totals"]["currency"], "payment_mode": c["payment_calc"]["mode"],
                    "offer_changed": bool(o) and o.get("version") != c.get("offer_version")})
    return out


@api.get("/contracts/{cid}")
async def contract_get(cid: str, user: dict = Depends(get_current_user)):
    need(user)
    return await own("contracts", user, cid)


@api.post("/contracts/{cid}/status")
async def contract_status(cid: str, request: Request, user: dict = Depends(get_current_user)):
    need(user, True)
    await own("contracts", user, cid)
    st = (await request.json()).get("status")
    if st not in CONTRACT_ST:
        raise HTTPException(status_code=400, detail="Status invalid")
    await db.contracts.update_one({"id": cid}, {"$set": {"status": st, "updated_at": now()}, "$push": {"history": {"at": now(), "by": user.get("email"), "event": f"status: {st}"}}})
    await S.audit(user, "status contract", "contracts", cid, [st])
    return {"status": st}


@api.get("/contracts/{cid}/pdf")
async def contract_pdf(cid: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    need(user)
    c = await own("contracts", user, cid)
    pdf = OD.contract_pdf(c, await settings(user))
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": S.disp("inline", f"Contract_nr_{c['number']}.pdf")})


@S.app.on_event("startup")
async def _idx():
    await db.offers.create_index([("owner", 1), ("number", 1)], unique=True)
    await db.contracts.create_index([("owner", 1), ("number", 1)], unique=True)


_ = (timedelta, ReturnDocument)
