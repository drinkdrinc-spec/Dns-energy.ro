# Instrucțiune unică pentru Emergent — sincronizare și lansare DNS Energy

**Proiectul existent trebuie continuat, nu reconstruit.** Sursa de cod actualizată este repository-ul GitHub `drinkdrinc-spec/Dns-energy.ro`, ramura `main`. Sincronizează proiectul Emergent cu această sursă și păstrează toate datele, paginile, modulele, componentele și funcțiile deja existente. Nu importa peste codul actual un ZIP mai vechi și nu rescrie aplicația din zero.

## 1. Înainte de orice modificare

1. Confirmă dacă proiectul Emergent este conectat la repository-ul de mai sus și la ramura `main`. Dacă nu este conectat, nu simula sincronizarea și nu reconstrui manual proiectul: raportează exact pașii necesari pentru conectare/import.
2. Înregistrează commitul GitHub folosit și inventariază diferențele dintre codul din Emergent și `main`.
3. Păstrează funcționalitățile existente și datele din baza de date. Nu șterge date, colecții, utilizatori, documente, setări sau fișiere încărcate.
4. Nu consuma credite prin redesign-uri sau implementări duplicate. Lucrează pe diferențe concrete, în pași mici, și rulează verificările după fiecare etapă.
5. Nu expune chei, tokenuri, parole sau variabile secrete în cod, loguri, capturi sau răspunsuri.

## 2. Funcționalități obligatorii de păstrat și finalizat

### Conturi, atestare și acces
- Conturi separate pentru fiecare firmă/utilizator, date de firmă și facturare distincte, CUI, profil, personal și roluri.
- Încărcare și verificare manuală a atestatului ANRE și a documentelor cerute înainte de acordarea accesului, conform regulilor existente.
- Accesul la module trebuie controlat server-side, nu doar ascuns în interfață.

### Abonamente și plăți
- START — 250 lei + TVA: dosare de prosumator cu maximum un invertor.
- PRO — 500 lei + TVA: dosare prosumator și DI-U.
- FULL — 1.000 lei + TVA: toate modulele platformei.
- TVA configurabil; configurația curentă este 21%. Nu modifica prețurile fără aprobarea proprietarului.
- Date de facturare pe utilizator, proforme/facturi, link automat de plată, confirmare prin webhook, activare acces după plata confirmată, expirare și restricții de abonament.
- Verifică integrarea reală cu furnizorul de plăți și serviciul de facturare existente. Dacă lipsesc credențiale sau configurări, raportează exact ce variabile trebuie completate; nu pretinde că plata funcționează end-to-end fără test.

### Date client și documente
- Datele clientului se introduc o singură dată și se reutilizează în ofertă, contract, dosar prosumator, DI-U, ATR, scheme și toate documentele.
- Păstrează generatorul de opis și documentele aferente operatorului de distribuție, cererii de racordare, notificării, împuternicirii, declarațiilor, PV de recepție, PV PIF, teste și verificări, buletin de reglaj, buletin PRAM, serii echipamente și instalația de stocare.
- Documentele generate trebuie să aibă câmpuri editabile unde este necesar, date corecte și un singur bloc de semnături pentru fiecare parte în fiecare document. Anexele pot avea propriile semnături doar dacă documentul respectiv le cere.
- Păstrează încărcarea semnăturii, ștampilei, atestatului ANRE, autorizațiilor personalului și documentelor metrologice. Nu duplica semnătura sau ștampila când acestea sunt inserate în PDF.

### Schema monofilară și dimensionare
- Configuratorul CEF trebuie să preia parametrii tehnici din catalog și să îi folosească în calcule.
- Schema monofilară trebuie să permită editarea parametrilor, salvare, redeschidere, recalculare, previzualizare și export PDF; valorile trebuie să corespundă configurației reale și să nu apară arbitrar.
- Configurarea stringurilor trebuie să fie clară: număr stringuri, panouri/serie, MPPT, compatibilitate cu limitele invertorului și verificări DC/AC.
- Folosește Imp, Voc, Vmp, Isc, coeficienții de temperatură și ceilalți parametri disponibili în fișa exactă. Nu deduce coeficientul Vmp din coeficientul Voc și nu folosi valori implicite inventate. Dacă lipsește un parametru, afișează „neconfirmat/necalculat” și explică ce fișă este necesară.
- Nu prezenta propunerile de dimensionare drept proiect verificat sau aprobat.

### Catalog tehnic
- Catalog căutabil și selectabil după marcă/model pentru invertoare, panouri, baterii și smart meter, cu toate capacitățile și parametrii relevanți.
- Extinde catalogul către protecții, cabluri, SPD, tablouri, separatoare, aparate de măsură și alte componente necesare.
- Fiecare echipament trebuie să poată avea fișă tehnică oficială, declarație UE de conformitate și alte documente aplicabile. Înregistrează producătorul, modelul exact, sursa/URL-ul documentului, data verificării și starea „verificat/neconfirmat”.
- Nu inventa certificate, conformități, parametri sau linkuri. Nu marca datele orientative ca oficial verificate. Modelele se pot căuta după nume și filtra după categorie/parametri.

### PRAM și documentație tehnică
- Formularul PRAM trebuie să distingă valoarea măsurată efectiv, coeficientul aplicat, valoarea calculată, limita admisă, aparatul de măsură și valabilitatea metrologică.
- Nu fabrica rezultate de măsurare, serii de aparate, semnături sau date de autorizare. Câmpurile lipsă rămân necompletate/neconfirmate.
- Verifică dacă experiența DI-U permite completarea completă a documentației, inclusiv PRAM, continuitate, izolație și DDR, fără să fragmenteze inutil un formular pe care utilizatorul îl completează ca un singur flux.

### ANRE
- Finalizează modulul pentru pregătirea dosarelor de atestare ANRE ale firmei, cu opis, cereri, formulare, documente ONRC recente, organigramă, personal/electricieni, autorizații, dovezi de angajare sau servicii, echipamente/scule, declarații, dovada taxei și pașii de semnare/depunere.
- Verifică cerințele curente pentru tipurile de atestat solicitate (inclusiv C1A/C2A unde se aplică) din surse oficiale. Păstrează statutul documentelor: lipsă, încărcat, verificat, expirat sau necesită verificare manuală.
- Nu prezenta șabloanele interne drept formulare oficiale fără confirmarea sursei oficiale.

### Oferte și contracte
- Păstrează ofertarea, selectarea echipamentelor din catalog, exportul PDF și generarea automată a contractului după acceptarea ofertei.
- Nu introduce automat termene de plată, garanții, penalități sau alte obligații contractuale care nu au fost aprobate de utilizator.
- Ofertele și contractele trebuie să preia datele corecte ale clientului și firmei.

## 3. Verificări tehnice înainte de publicare

Rulează și raportează rezultatul real, fără să marchezi verificările ca reușite dacă nu au rulat:

1. Build complet al frontendului.
2. Testele backend, inclusiv testele de siguranță pentru coeficienții PV, dosare, schemă, semnături, abonamente, billing, contracte și ANRE.
3. Teste end-to-end pentru înregistrare/autentificare, verificarea atestatului, permisiunile START/PRO/FULL, plată/webhook, generare factură/proformă, client → ofertă → acceptare → contract, catalog → configurator → schemă → salvare → PDF și toate documentele.
4. Teste de mobil și desktop; verifică erorile din consolă, răspunsurile API, upload/download și persistența datelor după reîncărcare.
5. Remediază erorile critice și de blocare înainte de lansare. Pentru orice test blocat, raportează motivul exact.

## 4. Configurare și lansare

- Verifică MongoDB, storage, e-mail, plată/webhook și variabilele de mediu folosind configurațiile existente. Nu afișa valorile secrete.
- Nu șterge baza de date și nu reseta utilizatorii existenți pentru a face testele.
- Publică numai după confirmarea buildului și a fluxurilor esențiale.
- Domeniul de prezentare este `dns-energy.ro`; aplicația a fost publicată anterior la `https://dns-energy.preview.emergentagent.com/`. Confirmă arhitectura și domeniul final înainte de a modifica DNS-ul. Păstrează înregistrările de e-mail și nu schimba DNS-ul fără să arăți valorile curente și efectul.
- Site-ul public trebuie să aibă pagini SEO separate pentru servicii electrice, JT/MT, fotovoltaice, parcuri și mentenanță, plus versiune în engleză. Date de contact: `office@dns-energy.ro`, `0741540265`. Nu inventa clienți, proiecte, certificări sau acreditări.

## 5. Rezultatul obligatoriu al acestei sarcini

La final, prezintă un raport scurt cu:
- commitul sincronizat și fișierele efectiv modificate;
- funcțiile implementate versus cele care existau deja;
- rezultatul fiecărui build/test;
- configurările/cheile care lipsesc, fără să le expui;
- erorile rămase și blocajele exacte;
- URL-ul public verificat și ce fluxuri au fost testate efectiv.

Nu răspunde doar cu „am implementat”. Arată dovezi verificabile. Nu considera aplicația lansată până când URL-ul live și fluxurile critice au fost testate.
