# DNS Energy — migrare independentă de Emergent

## Scop și reguli de siguranță

Pregătirea unei implementări DNS Energy care poate fi găzduită independent de Emergent. Această ramură pornește din `main`; nu modifică `main`, serviciile publicate sau baza de date existentă.

**Nu se face deploy în producție și nu se schimbă DNS-ul domeniului dns-energy.ro în cadrul acestei etape.** Orice schimbare se verifică prin PR și printr-un mediu separat de test.

## Constatări confirmate

- Render a eșuat la instalarea dependențelor deoarece `backend/requirements.txt` cere `emergentintegrations==0.2.2`, care nu este disponibilă în indexul de pachete folosit de build.
- `backend/ai_routes.py` și `backend/ai_extract.py` importă `emergentintegrations.llm.chat` și folosesc `EMERGENT_LLM_KEY`.
- `backend/server.py` folosește proxy-ul Emergent Object Storage pentru fișiere, PDF-uri, semnături și documente.
- `backend/mailer.py` folosește endpointul de e-mail Emergent și variabila `EMERGENT_EMAIL_KEY`.
- `backend/requirements.txt` conține și o dependență `litellm` instalată dintr-un URL privat Emergent; aceasta trebuie eliminată sau înlocuită după verificarea utilizării efective.
- MongoDB Atlas a fost creat cu clusterul de test `dns-energy-test`; acesta trebuie să rămână separat de orice bază de date care conține date reale.

## Etape de implementare

### 1. Decuplarea serviciilor externe
- Introducerea unei interfețe de stocare cu implementări S3-compatible (de exemplu Cloudflare R2) și un mod local pentru teste.
- Păstrarea contractului funcțiilor `put_object` / `get_object` și a cheilor de obiect existente, astfel încât să nu fie necesare modificări în toate modulele care generează sau descarcă documente.
- Introducerea unui client AI standardizat pe SDK public, cu suport pentru răspunsuri text/streaming și analiză documente/imagine. Modelul și furnizorul se configurează din variabile de mediu; nu se presupune că identificatorul de model Emergent este disponibil în API-ul public.
- Înlocuirea trimiterii e-mailurilor cu un adaptor SMTP sau furnizor public, păstrând validările de securitate din `mailer.py`.

### 2. Configurare și secrete
- Actualizarea `.env.example` și documentației pentru MongoDB Atlas, JWT, storage, AI și e-mail.
- Nicio parolă, cheie API, URI cu credențiale sau fișier `.env` nu se salvează în GitHub.
- Folosirea utilizatorului MongoDB cu rol limitat la baza de test, nu a unui utilizator Atlas Admin.
- Restricționarea accesului de rețea MongoDB la IP-urile serviciului de test când acestea sunt cunoscute; evitarea deschiderii permanente către orice IP.

### 3. Migrare și protejarea datelor
- Nu se conectează aplicația la baza de test goală pentru a înlocui o bază cu date reale.
- Înainte de migrare: identificarea bazei actuale, backup verificat și inventarierea obiectelor din storage.
- Migrarea fișierelor se face cu verificare de număr, dimensiune și checksum; referințele din MongoDB se păstrează sau se actualizează printr-un script idempotent.
- Migrarea datelor se testează întâi pe o copie izolată.

### 4. Validare
- Instalare curată a dependențelor pe Python-ul declarat pentru Render.
- Teste unitare pentru storage, e-mail, AI și compatibilitatea răspunsurilor API.
- Teste pentru autentificare, dosare, upload/download, PDF-uri, semnături, ofertare și contracte.
- Build frontend și teste end-to-end pe staging.
- Se consemnează explicit orice funcție care necesită o cheie de furnizor și nu se declară gata fără test real.

### 5. Lansare controlată
- Publicare pe URL de staging separat.
- Verificare funcțională și acceptare înainte de conectarea domeniului principal.
- Plan de revenire la versiunea curentă și păstrarea configurației DNS/e-mail existente.

## Următorul pas tehnic

Înainte de a schimba dependențele, trebuie inspectate toate punctele de integrare și testele existente. Nu este sigur să ștergem doar `emergentintegrations` din requirements: importurile din AI ar opri pornirea aplicației, iar stocarea și e-mailul ar rămâne dependente de Emergent.
