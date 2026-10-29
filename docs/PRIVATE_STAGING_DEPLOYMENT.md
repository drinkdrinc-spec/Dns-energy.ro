# DNS Energy — găzduire privată de test

## Regula de siguranță
Nu conecta acest mediu la domeniul principal `dns-energy.ro` și nu modifica deployment-ul Emergent existent. Folosește doar un subdomeniu separat de test, de exemplu `test.dns-energy.ro`, după ce este configurat în furnizorul DNS.

## Arhitectură propusă
- Frontend static și API FastAPI din blueprint-ul Render sunt servicii separate de producție.
- Protecția la nivel de edge trebuie activată înainte de a comunica linkul: Cloudflare Zero Trust Access (sau protecție echivalentă a furnizorului), cu allow policy doar pentru adresa de e-mail a administratorului.
- Backend-ul rulează cu `DNS_ENERGY_PRIVATE_MODE=true` și `ADMIN_EMAIL` setat la adresa administratorului. În acest mod, login-ul și fiecare cerere API autentificată sunt limitate la acel cont admin.
- `MONGO_URL`, `JWT_SECRET`, `ADMIN_EMAIL` și orice chei de integrare se configurează ca environment secrets în hosting, niciodată în Git.
- Folosește o bază de date separată pentru test; nu conecta testul la baza de date de producție și nu copia date reale ale clienților în test.
- Dezactivează endpoint-ul de documentație publică API pentru deployment-ul expus sau pune-l în spatele aceleiași protecții edge.

## Checklist înainte de a trimite linkul administratorului
1. Creează serviciile staging din `render.yaml`; verifică explicit că nu se schimbă serviciile live.
2. Setează toate variabilele secrete și o bază de date separată.
3. Configurează un subdomeniu de test și TLS/HTTPS.
4. Creează o politică Access de tip allowlist pentru un singur e-mail de administrator; politica trebuie să fie implicit deny pentru toți ceilalți.
5. Într-o sesiune privată/incognito, confirmă că vizitatorul fără Access nu vede aplicația/API-ul.
6. Confirmă că login-ul cu orice adresă diferită de `ADMIN_EMAIL` este refuzat, inclusiv direct la API; confirmă că tokenurile unui cont diferit nu pot apela endpoint-uri protejate.
7. Confirmă că administratorul poate intra, iar logout-ul șterge sesiunea din browser.
8. Testează generarea PDF și datele doar cu un client de probă, fără date personale reale.
9. Nu considera staging-ul privat până când pașii 4–6 au fost verificați efectiv.

## Limitări
Commiturile din GitHub și fișierul `render.yaml` nu configurează automat DNS, Cloudflare Access, variabile secrete sau servicii de hosting. Aceste acțiuni cer acces autorizat la conturile furnizorilor și trebuie făcute fără a modifica deployment-ul live.
