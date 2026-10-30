# DNS Energy — migrare de la Emergent la infrastructură proprie

## Principii obligatorii
- `main` și instanța publicată nu se modifică în timpul pregătirii.
- Nu se schimbă DNS-ul până când staging-ul trece toate testele.
- Nu se șterg obiecte sau înregistrări din baza de date în timpul migrării.
- Se face backup MongoDB și inventar al fișierelor înainte de copiere.
- Cheile se introduc numai în Environment Variables ale serviciului, niciodată în Git.

## Implementat pe branch-ul de migrare
- Adaptor Cloudflare R2 S3-compatible: `backend/r2_storage.py`.
- Selector de stocare opt-in: `OBJECT_STORAGE_BACKEND=emergent` (implicit) sau `r2`.
- Adaptor direct OpenAI pentru chat/analiza documentelor: `backend/ai_provider.py`.
- Rutele AI și extragerea documentelor folosesc adaptorul OpenAI; PDF-urile sunt randate local ca imagini pentru analiză.
- Serviciul de e-mail poate utiliza SMTP: `EMAIL_PROVIDER=smtp`; Emergent rămâne implicit până la test.
- Dependențele Python private `emergentintegrations` și wheel-ul privat Emergent au fost scoase din requirements.

## Variabile de configurat în Render staging

### Obligatorii pentru aplicație
- `MONGO_URL`: URI către baza MongoDB existentă sau o copie staging izolată.
- `DB_NAME`: numele bazei staging.
- `JWT_SECRET`: secret aleatoriu nou, lung; nu reutiliza o valoare expusă.
- `ADMIN_EMAIL` și `ADMIN_PASSWORD`: contul administratorului inițial (nu reseta contul existent).

### Cloudflare R2
- `OBJECT_STORAGE_BACKEND=r2` numai după copiere și verificarea fișierelor.
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME=dns-energy-files`
- `R2_ENDPOINT_URL` este opțional; implicit se formează din Account ID.

Tokenul R2 trebuie să aibă doar `Object Read & Write` pentru bucketul `dns-energy-files`. Nu este necesar Admin Read & Write. Păstrați secretul tokenului în managerul de secrete; dacă a fost expus într-o captură sau conversație, revocați-l și emiteți altul.

### OpenAI
- `OPENAI_API_KEY`: cheie API OpenAI cu facturare API activă.
- `OPENAI_MODEL`: implicit `gpt-4.1-mini`; modelul și costul trebuie validate înainte de producție.
- API-ul OpenAI se facturează separat de abonamentul ChatGPT.

### E-mail SMTP
- `EMAIL_PROVIDER=smtp`
- `EMAIL_FROM_NAME=DNS Energy`
- `SMTP_HOST`, `SMTP_PORT` (587 STARTTLS sau 465 SSL), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`
- `EMAIL_REPLY_TO` (opțional)

## Ordinea de migrare
1. Creează staging separat; nu conecta domeniul principal.
2. Fă backup consistent al MongoDB și verifică restaurarea într-o bază staging.
3. Obține inventarul cheilor de obiecte stocate în baza de date și exportă lista cu dimensiuni/MIME/hash.
4. Copiază obiectele din stocarea veche în R2 păstrând exact cheile; verifică numărul, dimensiunea și SHA-256 pentru fiecare obiect.
5. Pornește staging cu `OBJECT_STORAGE_BACKEND=r2` și verifică descărcarea documentelor, PDF-urilor, imaginilor, semnăturilor și ștampilelor.
6. Testează OpenAI pe extragere PDF și conversație, cu verificarea costurilor și a răspunsurilor.
7. Testează SMTP: livrare, SPF, DKIM, DMARC, Reply-To, linkurile de semnare.
8. Rulează testele de autentificare, roluri, abonamente, creare/editare dosare, generare PDF/Word, semnare, download, ofertare și ANRE.
9. Doar după acceptanță se planifică fereastra de schimbare DNS și rollback.

## Rollback
- Revino la `OBJECT_STORAGE_BACKEND=emergent` dacă vechiul serviciu este încă activ.
- Revino la furnizorul AI/e-mail vechi prin variabilele de mediu dacă este necesar.
- Nu șterge bucketul R2 și nu șterge datele vechi până la confirmarea completă a migrării.
- Pentru baza de date, restaurează backup-ul numai într-un plan controlat; nu suprascrie baza de producție automat.

## Limitări rămase înainte de publicare
- Nu există încă acces API la contul Render sau MongoDB în această sesiune; variabilele mascate nu pot fi citite sau transferate automat.
- Cheile R2 create în Cloudflare nu sunt vizibile ulterior în dashboard; trebuie copiate în siguranță în variabilele Render.
- Testul de integrare R2 necesită acces de rețea la bucket și credențiale din staging.
- Nu s-a efectuat încă migrarea datelor, deploy-ul sau schimbarea DNS.


## Confirmarea proprietarului — păstrarea datelor (30 octombrie 2026)
Proprietarul a confirmat explicit că trebuie păstrate toate datele existente. Prin urmare:
1. Migrarea rămâne blocată până la obținerea backupului bazei MongoDB reale și a exportului fișierelor din stocarea veche.
2. Clusterul Atlas `dns-energy-test` este doar un cluster de test cunoscut și nu este sursa datelor reale.
3. Nu se face resetare, inițializare cu date goale, suprascriere sau schimbare a conexiunii de producție.
4. Restaurarea se face într-o bază staging separată; se verifică utilizatorii, dosarele, documentele, semnăturile, ștampilele, indexurile și relațiile dintre înregistrări.
5. Pentru fiecare fișier se păstrează cheia originală și se verifică numărul, dimensiunea și SHA-256 înainte și după copierea în R2.
6. Lansarea pe infrastructura nouă este permisă numai după testarea autentificării, accesului la dosare și descărcării tuturor tipurilor de documente.

### Date încă necesare pentru migrare
- Backup MongoDB complet (`mongodump --archive --gzip`) din baza utilizată de aplicația existentă sau acces securizat la URI-ul sursă.
- Exportul fișierelor originale din object storage-ul vechi, cu inventar de chei.
- Confirmarea că backupul provine din instanța activă de producție și data/ora la care a fost realizat.
- Creditele de acces la sursă trebuie transmise numai printr-un manager de secrete sau introduse direct în dashboard-ul de infrastructură; nu în issue-uri, commit-uri sau conversații.
