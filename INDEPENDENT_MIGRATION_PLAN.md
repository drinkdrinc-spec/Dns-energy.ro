# DNS Energy — plan de migrare independentă de Emergent

Status: pregătire tehnică, fără modificări asupra producției.

## Obiectiv și reguli de siguranță

Publicarea DNS Energy pe infrastructură controlată separat de Emergent, păstrând aplicația existentă, utilizatorii, dosarele, fișierele și domeniul actual până la validarea completă.

- Ramura de lucru: `migration/independent-hosting-prep`
- Sursa de referință inspectată: `main`
- Nu se schimbă DNS-ul domeniului și nu se înlocuiește instanța publicată în etapa de pregătire.
- Nu se migrează, șterge sau resetează baza de date fără backup verificat și test de restaurare.
- Se păstrează compatibilitatea cu obiectele deja salvate în stocarea Emergent până la migrarea și verificarea lor.
- Secretele se configurează exclusiv în managerul de variabile de mediu al serviciului, niciodată în Git.

## Infrastructură observată

- MongoDB Atlas: clusterul fotografiat este `dns-energy-test`, regiune AWS Frankfurt. Fotografiile arată un cluster cu 3 noduri și 0 B la momentul capturii. Acesta nu este confirmat ca baza de date de producție și nu trebuie conectat la utilizatorii reali până când proprietarul confirmă conținutul și backupul.
- Cloudflare R2: bucket `dns-energy-files` creat, privat (Public Access Disabled), regiune automată în Europa de Est, storage class Standard.
- Cloudflare R2 API token: `DNS-Energy-R2-Production`, limitat la bucketul `dns-energy-files`, permisiune Object Read & Write. Tokenul a fost generat și salvat de proprietar; valoarea secretă nu este inclusă în repository.
- Render: servicii `dns-energy-web` și `dns-energy-api`. Frontendul apare deployed; backendul are un deploy eșuat.
- Render logul backendului arată: `No matching distribution found for emergentintegrations==0.2.2`.

## Blocaje tehnice confirmate în codul de pe main

1. `backend/requirements.txt` conține `emergentintegrations==0.2.2` și un pachet `litellm` instalat dintr-un URL privat `customer-assets.emergentagent.com`. Aceste dependențe nu sunt potrivite pentru un build independent și trebuie eliminate numai după înlocuirea tuturor importurilor/funcțiilor care le folosesc.
2. `backend/server.py` implementează `put_object` și `get_object` prin proxy-ul Emergent (`integrations.emergentagent.com/objstore`) și cheia `EMERGENT_LLM_KEY`.
3. `backend/ai_extract.py` și `backend/ai_routes.py` importă `emergentintegrations.llm.chat`. Funcțiile AI trebuie portate la un SDK/API standard, păstrând contractele de intrare/ieșire, streaming-ul, validarea JSON și comportamentul de eroare.
4. `backend/mailer.py` trimite email prin endpointul Emergent și cere `EMERGENT_EMAIL_KEY`. Trebuie înlocuit cu un furnizor SMTP/API independent și testat fluxul de semnare și notificare.
5. `render.yaml` de pe ramura `deployment-prep` este doar staging, nu configurație de producție. Nu se aplică automat pe `main`.

## Plan de execuție în etape

### Etapa 0 — verificări și protecție (înainte de cod)
- Confirmă care cluster MongoDB conține datele reale și care este doar test.
- Creează backup MongoDB și verifică restaurarea într-o bază separată.
- Identifică toate colecțiile, volumele și referințele către fișiere.
- Inventariază toate apelurile Emergent, nu doar cele din fișierele deja inspectate.
- Păstrează aplicația curentă funcțională pe toată durata migrării.

### Etapa 1 — stocare R2 compatibilă
- Introdu un adaptor S3 compatibil folosind boto3 și endpointul S3 R2.
- Variabile necesare (numele exacte se confirmă la implementare): `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`.
- Bucketul rămâne privat; fișierele se livrează prin backend autentificat sau URL-uri presemnate cu expirare scurtă.
- Nu se activează acces public și nu se expun secrete în frontend.
- Păstrează citirea obiectelor vechi printr-un mecanism de compatibilitate până la migrarea completă.
- Migrarea fișierelor se face cu inventar, număr de obiecte, verificare dimensiune/hash și test de descărcare.

### Etapa 2 — eliminarea dependențelor Emergent
- Înlocuiește serviciile AI cu un client standard configurabil (OpenAI/Gemini), cu chei proprii și modele disponibile public.
- Înlocuiește emailul cu un provider independent; verifică DNS SPF, DKIM și DMARC pentru domeniul expeditor.
- Elimină pachetele private din requirements numai după ce nu mai există importuri sau utilizări.
- Adaugă teste pentru AI, email și storage și verifică pornirea aplicației fără variabile Emergent.

### Etapa 3 — deploy de test
- Deploy backend și frontend pe Render sau alt host ales, pe subdomeniu de test.
- Folosește o bază de date de test restaurată din backup/anonymizată, nu baza live.
- Configurează health check real, logs, HTTPS, CORS restrâns, rate limits și secrete.
- Testează autentificare, roluri, planuri, dosare, generare PDF/DOCX, upload/download, semnare, e-mail, AI și toate fluxurile critice.

### Etapa 4 — migrare controlată
- Planifică fereastră de mentenanță.
- Realizează backup final și migrare incrementală a fișierelor/datei.
- Compară numărul de utilizatori, dosare, documente și fișiere.
- Schimbă DNS-ul numai după acceptarea testelor.
- Păstrează instanța veche disponibilă pentru rollback până la confirmarea stabilității.
- Nu șterge resursele Emergent până când perioada de rollback s-a încheiat și integritatea datelor este confirmată.

## Criterii obligatorii de acceptare

- Build și teste backend/frontend reușite.
- Niciun import sau URL privat Emergent rămas în fluxurile de producție.
- Backup MongoDB restaurat cu succes.
- Fișiere vechi și noi accesibile corect, fără pierderi.
- Niciun secret în Git, loguri, browser sau răspunsuri API.
- Toate fluxurile critice verificate pe subdomeniu.
- Plan de rollback documentat și testat.

## Ce NU s-a făcut

Nu s-a modificat `main`, nu s-a modificat baza de date, nu s-a încărcat niciun fișier în R2, nu s-a făcut deploy și nu s-a schimbat DNS-ul. Acest document este doar planul de migrare în ramura separată.
