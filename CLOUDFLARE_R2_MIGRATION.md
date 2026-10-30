# DNS Energy — migrare stocare Cloudflare R2

## Stare
- Ramură izolată: `migration/cloudflare-r2-storage`.
- Bucket pregătit în Cloudflare: `dns-energy-files`.
- Integrarea R2 este opțională prin variabile de mediu.
- Fără variabile R2, aplicația păstrează stocarea Emergent existentă.
- Cu R2 activ, uploadurile noi merg în R2; la citire, dacă obiectul nu există în R2, se încearcă stocarea Emergent. Astfel, referințele deja salvate în MongoDB rămân utilizabile în timpul migrării.

## Variabile Render
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME=dns-energy-files`
- `R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com` (opțional; se deduce din Account ID dacă lipsește)
- `R2_REGION=auto`

Secretele se introduc exclusiv în Environment din Render, nu în GitHub, fișiere .env comise sau conversații.

## Atenție înainte de activare
1. Nu activați încă R2 pe serviciul de producție.
2. Nu ștergeți și nu dezactivați stocarea Emergent.
3. Testați întâi pe un serviciu Render de staging și pe baza de date de test.
4. Verificați upload, download, PDF-uri, semnături, ștampile și documente atașate.
5. Inventariați obiectele existente și migrați-le în R2 cu verificare de număr, dimensiune și hash. Fallback-ul de citire este o măsură temporară de compatibilitate, nu înlocuiește migrarea și verificarea.
6. Numai după verificarea migrării și a restaurării, schimbați mediul de producție.

## Limitare independentă
Acest pas înlocuiește numai componenta de object storage. Backend-ul încă are dependențe Emergent pentru AI și e-mail, iar `requirements.txt` conține pachete private Emergent care au provocat deja eșecul buildului Render. Independența completă necesită înlocuirea acelor integrări și a dependențelor private înainte de lansare.
