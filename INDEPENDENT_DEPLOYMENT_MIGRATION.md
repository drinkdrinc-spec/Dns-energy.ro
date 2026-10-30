# DNS Energy — plan de migrare independentă de Emergent

Data: 30.10.2026
Ramură de lucru: `dns-energy-independent-deploy`
Sursa de cod: `main` (nemodificată)

## Obiectiv și limite

Publicarea DNS Energy pe infrastructură controlată separat de Emergent, fără pierderea conturilor, dosarelor, documentelor, semnăturilor, ștampilelor, abonamentelor sau istoricului. Migrarea se face etapizat, cu mediu de test și posibilitate de revenire. Această ramură este pregătitoare; nu schimbă domeniul live și nu modifică baza de date de producție.

## Dependențe Emergent identificate în codul din main

1. **Object storage** — `backend/server.py`: `init_storage()`, `put_object(path, data, content_type)`, `get_object(path)` folosesc implicit `https://integrations.emergentagent.com/objstore/api/v1/storage` și `EMERGENT_LLM_KEY`. Aceste funcții sunt folosite de rutele de fișiere și de modulele care păstrează documente. Înlocuirea trebuie să păstreze interfața și cheile/căile logice existente sau să includă o migrare verificată a tuturor obiectelor.
2. **AI / extragere** — `backend/ai_extract.py` și `backend/ai_routes.py` importă `emergentintegrations.llm.chat`, folosesc `LlmChat` și `EMERGENT_LLM_KEY`. Trebuie înlocuite atât extragerea documentelor (inclusiv PDF/imagine), cât și chat-ul/streaming-ul, verificarea dosarelor, redactarea și mesajele de semnare. Contractele JSON, fluxurile SSE și regulile de a nu inventa parametri trebuie păstrate și testate.
3. **E-mail** — `backend/mailer.py` trimite prin endpoint-ul Emergent și citește `EMERGENT_EMAIL_KEY`. Înlocuirea trebuie să păstreze verificările anti-phishing existente, reply-to, HTML și rezultatul/erorile așteptate de apelanți.
4. **Configurație/deployment** — `backend/.env.example` și configurațiile de deployment trebuie curățate de dependențe obligatorii Emergent. Secretele rămân exclusiv în managerul de secrete al furnizorului, niciodată în Git.

## Arhitectură țintă (alegerea furnizorilor se face înainte de activare)

- Frontend React/Vite servit prin CDN/hosting static, cu domeniu și HTTPS.
- Backend FastAPI într-un serviciu persistent, cu health checks, loguri și backup.
- MongoDB existent păstrat ca sursă de adevăr; înainte de mutare se face backup consistent și restaurare de probă. Nu se pornește o bază goală pentru producție.
- Object storage S3-compatible (de exemplu Cloudflare R2 sau AWS S3), cu acces privat, politici minime și verificare SHA-256 la migrare.
- AI prin API direct de la furnizor ales, cu limite de cost, timeout, tratarea erorilor și validarea ieșirilor.
- E-mail prin furnizor SMTP/API separat, cu SPF, DKIM și DMARC configurate pentru domeniu.
- Stripe/webhook și integrarea de plată existente se păstrează și se retestează; nu se schimbă prețuri sau reguli de abonament.

## Ordinea de implementare obligatorie

### Etapa 1 — inventar și contracte
- Inventarierea tuturor apelurilor storage și a formatelor de cale/metadata.
- Inventarierea tuturor funcțiilor AI, prompturilor, formatelor JSON, streaming-ului și tipurilor de fișiere.
- Inventarierea tuturor apelanților e-mail și a șabloanelor.
- Identificarea tuturor variabilelor de mediu și a serviciilor externe.
- Adăugarea de teste pentru contractele existente înainte de înlocuire.

### Etapa 2 — adaptoare compatibile
- Introducerea unui adaptor storage cu aceeași interfață `put_object/get_object`; mod de dezvoltare locală și backend S3-compatible. Nicio ștergere a obiectelor vechi.
- Introducerea unui adaptor AI cu funcții explicite pentru text, fișiere, imagini și streaming; menținerea prompturilor și schemelor de răspuns. Dacă AI nu este configurat, funcțiile AI raportează indisponibilitate controlată; aplicația și documentele non-AI continuă să funcționeze.
- Introducerea unui adaptor e-mail SMTP/API cu validările de siguranță păstrate. Lipsa configurării trebuie să producă eroare controlată, nu blocarea importului întregului backend.
- Păstrarea temporară a integrărilor vechi ca fallback numai în medii de test, nu ca dependență de producție după migrare.

### Etapa 3 — migrarea datelor și fișierelor
- Backup MongoDB și export de inventar al fișierelor (cale, tip MIME, dimensiune, hash).
- Copiere storage în loturi, verificare hash și raport pentru fiecare obiect; reluare sigură a loturilor întrerupte.
- Verificarea unui eșantion și a tuturor fișierelor critice (semnături, ștampile, atestate, fișe tehnice, documente semnate).
- Nu se șterge și nu se dezactivează storage-ul vechi până când verificarea și testele de restaurare nu sunt complete.

### Etapa 4 — mediu staging
- Deploy pe subdomeniu de test, cu bază de date clonată/anonimizată, nu cu baza de producție.
- Teste backend, frontend, autentificare, izolare tenant, roluri, abonamente, facturare/webhook, toate generatoarele PDF/DOCX, upload/download, semnare, AI și e-mail.
- Teste mobile și desktop, monitorizare loguri și verificare performanță.
- CI verde pentru testele relevante; niciun test nu se declară trecut dacă nu a rulat.

### Etapa 5 — lansare și revenire
- Fereastră de migrare anunțată, backup imediat înainte de schimbare și verificare DNS.
- Schimbarea domeniului numai după aprobarea verificărilor; păstrarea configurației DNS pentru e-mail.
- Monitorizare post-lansare și procedură de revenire la hostingul anterior fără a suprascrie datele noi.
- Emergent rămâne disponibil ca fallback până la confirmarea stabilității; apoi se elimină cheile și dependențele după confirmarea că nu mai există apeluri.

## Criterii de acceptare

- Niciun utilizator, tenant, abonament sau document pierdut.
- Hash-urile fișierelor migrate corespund; toate fișierele critice se pot descărca.
- Documentele generate păstrează conținutul, datele și semnăturile fără dubluri.
- Parametrii tehnici lipsă rămân marcați ca lipsă/neconfirmați; nu se introduc valori implicite inventate.
- Fluxurile de plată, webhook, autentificare, roluri și separarea tenant funcționează.
- AI și e-mail funcționează cu chei proprii și limite de cost configurate.
- Nicio cheie secretă, copie de date sau fișier privat nu este comisă în Git.

## Blocaje care necesită acces/decizie înainte de activare

- Acces la contul de hosting/DNS și alegerea serviciilor pentru backend și frontend.
- Acces la MongoDB actual și posibilitatea unui backup/restore.
- Alegerea furnizorului S3-compatible și acces la storage-ul Emergent pentru export.
- Alegerea furnizorului AI și furnizarea cheii API prin secret manager.
- Alegerea furnizorului de e-mail și configurarea DNS SPF/DKIM/DMARC.
- Acces la setările plăților/webhook pentru retestare.

## Reguli de siguranță

Nu se publică automat, nu se schimbă DNS, nu se modifică baza de producție, nu se șterg fișiere și nu se dezactivează Emergent în această etapă. Orice migrare de date este reversibilă și verificată înainte de comutare.
