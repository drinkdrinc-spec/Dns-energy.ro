# DNS Energy — sursa unică de adevăr pentru implementare

Acest document centralizează cerințele existente pentru a evita solicitări repetate și implementări paralele. Se lucrează pe proiectul existent; nu se reconstruiește aplicația de la zero.

## Reguli de lucru

- Repository: `drinkdrinc-spec/Dns-energy.ro`.
- Baza de lucru: codul existent din `deployment-prep`; nu se modifică direct `main`.
- Orice funcție nouă trebuie conectată la fluxul existent și testată. O pagină sau un fișier izolat nu reprezintă o funcție terminată.
- Păstrează datele, autentificarea, permisiunile și configurațiile. Nu migra/șterge date de producție fără plan și backup.
- Nu folosi credite pentru a reimplementa funcții existente. Înainte de schimbare, inspectează codul și testele actuale.
- Nu declara publicarea sau testarea reușită fără rezultat observabil.

## Modelul documentelor — obligatoriu

Folosește documentele de referință încărcate de utilizator ca modele vizuale și structurale, în special dosarul complet de prosumator `DOSAR publiserv_srl_semnat_(1).pdf` și exemplul `Sisterean .pdf` pentru verificarea tipului de document relevant. Păstrează ordinea, organizarea paginilor, rubricile, tabelarea, anteturile/subsolurile și stilul cât mai fidel modelului; înlocuiește numai datele beneficiarului și valorile care depind de configurație. Nu inventa formulare și nu simplifica arbitrar modelul.

`all_Test_Client_SRL.pdf` este un PDF generat de aplicație, nu trebuie tratat automat drept model original al utilizatorului. Compară rezultatul generat cu modelul original și raportează diferențele.

Modelul exact pentru schema monofilară trebuie identificat din materialele de referință disponibile. Nu presupune că o schemă demonstrativă generată este originalul. Schema finală trebuie să fie editabilă, să păstreze valorile salvate și să reflecte configurația reală.

## Obiectivul produsului

DNS Energy este o platformă completă pentru activitatea unei firme fotovoltaice/electrice, nu doar un generator de dosare. Modulele trebuie să împartă aceleași date și să evite introducerea repetată.

### Module care trebuie să funcționeze împreună

1. Clienți și proiecte: date de identificare, adresă, POD/distribuitor, date de facturare și echipamente; o singură sursă de date reutilizată.
2. Configurator fotovoltaic/CEF: panouri, stringuri, unul sau mai multe invertoare, baterii, accesorii, puteri și capacități; validări electrice și avertizări explicite.
3. Catalog tehnic: căutare după producător și cod exact de model; invertoare, panouri, baterii, contoare, CT, MCB, SPD AC/DC, siguranțe gPV, cabluri și aparataj.
4. Dosare prosumator și racordare: opis, formulare și anexe specifice distribuitorului, PDF-uri și schema monofilară separată.
5. DI-U/PIF/PRAM: documente complete și consecvente; valorile de măsurare sunt introduse de persoana competentă și nu se generează fictiv.
6. Personal și setări: autorizații, atestate, semnături grafice, ștampilă și aparate de măsură/metrologie; folosire numai pentru persoanele și rolurile autorizate.
7. Dosare ANRE: documente și opis în funcție de categoria/procedura selectată; verificarea cerințelor din surse oficiale actuale.
8. Oferte și contracte: echipamente/prețuri, ofertă PDF, acceptare și contract cu termene și avans.
9. Utilizatori, abonamente și plăți: 250 lei — dosar prosumator cu un singur invertor; 500 lei — prosumator + dosar de utilizare/DI-U; 1.000 lei — întreaga platformă. Prețurile sunt fără TVA; cota configurată în discuție este 21%. Păstrează aceste planuri separate de pachetele comerciale Start/Pro/Full discutate anterior.
10. Site public și publicare: domeniul `dns-energy.ro`; testarea frontendului și backendului separat înainte de lansare.

## Cerințe pentru datele tehnice

Pentru fiecare model salvează codul exact, producătorul, versiunea fișei, URL-ul sursei, data verificării și starea: verificat / incomplet / neverificat. Atașează numai documente aplicabile modelului exact: fișă tehnică, declarație UE de conformitate, manual și certificate/rapoarte relevante.

- Invertoare: kW nominal AC, kW maxim AC, putere DC maximă, MPPT, domenii de tensiune, curenți, faze, randament, protecții și compatibilitate baterii.
- Panouri: Wp, Voc, Isc, Vmp, Imp, coeficienți termici, dimensiuni și limite electrice.
- Baterii: kWh nominal/utilizabil, Ah, tensiune, curenți/putere de încărcare-descărcare, module min/max, BMS și compatibilitate.
- Aparataj: tensiune, curent, capacitate de rupere, secțiuni și parametri relevanți tipului de produs.

Nu confunda kW cu kWh. Nu deduce coeficienți de temperatură și nu introduce valori implicite care par confirmate. Dacă lipsește un parametru necesar, marchează calculul dependent ca neconfirmat și explică ce document lipsește. Datele din catalog trebuie folosite efectiv în dimensionare, verificarea compatibilității, schema monofilară și PDF-uri.

## Fluxul simplificat pentru utilizator

- Beneficiarul și datele de facturare se introduc o singură dată.
- Utilizatorul selectează modelele exacte; aplicația preia parametrii documentați.
- Introducerea stringurilor trebuie simplificată și să valideze automat limitele electrice.
- Datele selectate se reutilizează în ofertă, contract, schemă, dosar prosumator, DI-U/PIF și documentele aplicabile.
- Înainte de export, se arată lista documentelor lipsă, valorile neverificate și incompatibilitățile.
- Exporturile PDF trebuie comparate vizual cu modelele de referință și verificate pentru câmpuri lipsă, tăieri, pagini goale și neconcordanțe.

## Criterii de acceptare

Nu considera proiectul gata până când se pot demonstra aceste fluxuri cu date de test:

1. Creează client/proiect o singură dată și reutilizează datele în toate documentele.
2. Selectează modele exacte și vede parametrii, sursa și starea de verificare.
3. Verifică compatibilitatea invertor–baterie și limitele stringurilor fără presupuneri.
4. Editează schema, salvează, redeschide și exportă PDF cu aceleași valori.
5. Generează un dosar complet pentru distribuitorul ales și compară-l cu modelul original.
6. Generează DI-U/PIF/PRAM cu aparatul și persoanele selectate; nu fabrică măsurători sau semnături.
7. Generează ofertă și contract; verifică drepturile pe planuri și confirmarea reală a plății.
8. Rulează testele backend/frontend disponibile și notează explicit testele blocate de servicii/secrete.
9. Integrează numai după revizuirea diff-ului; publică pe `dns-energy.ro` numai după verificarea mediului de producție.

## Raport de lucru obligatoriu

La finalul fiecărei etape raportează succint: fișiere schimbate, funcții existente reutilizate, teste trecute/eșuate, funcții conectate end-to-end, blocaje reale și următorul pas. Nu prezenta catalogul ca fiind complet dacă sunt doar câteva exemple sau documente încărcate manual.
