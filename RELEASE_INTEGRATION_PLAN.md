# DNS Energy — plan de integrare și lansare

Ultima actualizare: 29.10.2026

## Sursa de adevăr

- Repository: https://github.com/drinkdrinc-spec/Dns-energy.ro
- Ramură: `main`
- Aplicația publicată anterior în Emergent: https://dns-energy.preview.emergentagent.com/
- Domeniu cumpărat și activ: `dns-energy.ro` (Hostinger). Publicarea finală și asocierea domeniului trebuie verificate separat după sincronizarea codului.

Nu se reconstruiește aplicația de la zero. Se sincronizează proiectul Emergent cu ramura GitHub `main`, se păstrează funcționalitățile deja existente și se repară diferențele prin modificări mici, verificabile.

## Funcționalități care trebuie păstrate și verificate

1. Autentificare, utilizatori/tenanți separați, roluri, profil de firmă și atestat ANRE.
2. Abonamente: START 250 lei (un singur invertor/dosar prosumator), PRO 500 lei (prosumator + DI-U), FULL 1.000 lei (platforma completă), fără TVA; TVA configurabil (21% în configurația curentă). Nu se schimbă prețurile fără aprobarea proprietarului.
3. Date client introduse o singură dată și reutilizate în ofertă, contract, dosar prosumator, DI-U, ATR, scheme și documente.
4. Date de facturare separate pentru fiecare utilizator, facturi/proforme, plată online și confirmare prin webhook. Se verifică end-to-end cu setări reale, fără a expune chei secrete.
5. Generator de dosare prosumator, opis, documente de racordare și formulare pe operator, DI-U, ATR, PIF, PV de recepție, PV de teste, buletine PRAM, buletin de reglaj, declarații, împuternicire, serii echipamente, documente de stocare.
6. Modul ANRE pentru dosarele de atestare: opis, cereri, șabloane, personal, echipamente, documente justificative și flux de verificare/semnare/depunere. Șabloanele generate trebuie etichetate corect; nu se pretinde că sunt formulare oficiale fără sursă verificată.
7. Catalog căutabil de invertoare, panouri, baterii și smart meter; extindere controlată către protecții, cabluri, SPD, tablouri și aparate de măsură. Fișe tehnice și declarații UE de conformitate trebuie să provină din documente oficiale, cu sursă și model exact.
8. Configurator CEF și schemă monofilară: parametri derivați din modelul selectat, configurare/salvare/editare, recalcul, previzualizare și PDF; fără valori inventate sau pierderea modificărilor.
9. Buletinul PRAM trebuie să distingă valorile efectiv măsurate de calcule și câmpurile necompletate; nu se inventează rezultate de măsurare.
10. Oferte și contracte: contractul se generează după acceptarea ofertei; condițiile de plată/garanție nu se inventează.
11. Semnături, ștampila și datele firmei se afișează o singură dată în fiecare bloc/document, conform tipului de document.
12. Site public, SEO, versiune în engleză și domeniu: conținutul public nu trebuie confundat cu aplicația internă. Datele de contact convenite: office@dns-energy.ro și 0741540265. Nu se inventează proiecte, acreditări sau certificări.

## Modificări înregistrate în GitHub la 29.10.2026

- `backend/docgen.py`: protecție împotriva blocurilor repetate de semnătură în PV-ul de recepție.
- `backend/cef.py`: coeficienții de temperatură Voc/Vmp lipsă nu mai sunt înlocuiți cu valori implicite inventate; calculele dependente sunt neconfirmate.
- `backend/sizing.py`: raportul de dimensionare explică parametrii lipsă și nu pretinde că valorile dependente sunt calculate.
- `frontend/src/pages/EquipmentCatalog.jsx`: câmpuri de catalog pentru coeficient Vmp, NOCT și coeficient Pmax.
- `backend/tests/test_technical_parameter_safety.py`: teste de regresie pentru parametri tehnici lipsă/disponibili.

## Ordinea obligatorie de verificare înainte de lansare

### A. Sincronizare cod
- Confirmă că Emergent folosește exact repository-ul și ramura `main`.
- Confirmă commitul curent înainte și după sincronizare.
- Nu rescrie fișierele deja existente cu variante mai vechi dintr-un ZIP.
- Nu elimina funcționalități, pagini, teste sau date existente.

### B. Teste locale/CI
- Testele `test_technical_parameter_safety.py`.
- Testele pentru dosare, schema monofilară, semnături, abonamente, billing, ANRE și contracte.
- Build frontend complet.
- Remedierea tuturor erorilor critice; nu marca testele drept trecute dacă nu au rulat.

### C. Teste end-to-end în mediu de test
- Creare cont și blocarea accesului conform stării atestatului ANRE.
- START/PRO/FULL și restricțiile de module/invertoare.
- Facturare, plată, webhook, acces după plată și expirarea abonamentului.
- Client → ofertă → acceptare → contract → documente.
- Catalog → selectare model → configurator → schemă editabilă → salvare → PDF.
- Generarea fiecărui document și verificarea numărului de blocuri de semnătură.
- Upload/descărcare fișe tehnice și documente de conformitate.
- Test pe mobil și desktop.

### D. Lansare
- Verifică variabilele de mediu și secretele în mediul de găzduire; niciun secret în cod.
- Verifică MongoDB, storage, e-mail, Stripe/webhook și serviciul de documente.
- Rulează migrațiile/seed-urile fără a șterge datele existente.
- Publică numai după build și teste; verifică autentificarea și fluxurile principale pe URL-ul live.
- Verifică DNS pentru domeniul public și păstrează înregistrările de e-mail existente.

## Regula pentru lipsuri

Dacă lipsește o cheie, un serviciu, o fișă oficială, un certificat sau un parametru tehnic, raportează exact ce lipsește și oprește doar verificarea dependentă. Nu fabrica date, nu șterge date reale și nu declara lansarea gata fără dovadă verificabilă.
