# DNS Energy — specificație de implementare și verificare

Document de lucru pentru ramura `deployment-prep`. Nu reprezintă confirmarea că funcționalitățile de mai jos sunt deja implementate. Fiecare cerință trebuie construită în aplicație, testată și marcată ca finalizată numai după verificare.

## 1. Ordinea meniului principal

Ordine obligatorie în fluxul de lucru:
1. Clienți
2. Cerere ATR
3. Spor de putere — modul separat, înainte de dosarul de prosumator
4. Dosare de prosumator
5. Dosar DIU
6. Buletine PRAM
7. Schema monofilară

Restul modulelor existente rămân disponibile: panou principal, asistent AI, oferte, contracte, gestionarea lucrărilor, tablouri electrice, antiinsularizare, echipamente, semnare la distanță, cataloage, formulare oficiale, portaluri distribuitori și administrare.

## 2. Pagina Dosare — acțiuni distincte

Afișează controale separate și ușor de găsit:
- Previzualizare dosar.
- Schema monofilară — generare PDF separat.
- Dosar de prosumator — generare PDF.
- Buletin PRAM — generare PDF separat.
- Dosar de utilizare (DIU) — deschide fluxul de modificare/generare.

DIU trebuie să reutilizeze datele existente ale clientului și instalației. La cerere de spor de putere, inițiază/actualizează automat documentația DIU din aceleași date, fără reintroducerea lor. Schimbările datelor comune trebuie reflectate în documentele regenerate. PDF-ul DIU include opis și documentele aplicabile.

Generarea PDF trebuie să reutilizeze logica existentă, să raporteze clar erorile și să nu afișeze succes dacă fișierul nu a fost produs.

## 3. Catalog tehnic comun

Catalog selectabil și căutabil pentru:
- Invertoare, baterii de stocare și panouri fotovoltaice.
- Întrerupătoare, protecții, relee, CT-uri, separatoare, contactoare, bare, cleme, conductori și tablouri.
- Producător, model/cod, valori nominale, fișă tehnică și certificat/document de conformitate UE, atunci când este disponibil oficial.

Prioritate surselor oficiale ale producătorilor. Salvează sursa și versiunea/data documentului. Nu inventa fișe, coduri, certificări sau parametri. Dacă datele exacte nu sunt găsite, cere selecție manuală ori afișează avertizare și nu pretinde că dimensionarea este validată.

## 4. Tablouri electrice interioare/casnice și industriale

Configurator după puterea solicitată, tipul de racord și circuitele aproximative/necesare. Tablouri de la 8 la 200 de module; dimensiunea și ocuparea reală trebuie verificate după aparatajul selectat și spațiile de rezervă.

Circuite configurabile:
- Prize generale.
- Iluminat interior.
- Cameră tehnică.
- Bucătărie și consumatori dedicați.
- Centrală electrică/pompă de căldură.
- Garaj.
- Prize exterioare.
- Iluminat exterior.

Aparataj selectabil în calibre și dimensiuni reale, după compatibilitate:
- MCB/întreruptoare automate.
- AFDD.
- RCD/RCCB.
- RCBO.
- Descărcătoare de supratensiune.
- Separator și separator fuzibil.
- Contactoare și relee de monitorizare.
- Protecții la incendiu/arc unde sunt cerute de soluția tehnică și reglementări.

Alte elemente:
- Tablou media separat, pentru date/comunicații.
- Cleme de șir și cleme de derivație.
- Distribuitoare de fază și nul.
- Bare N și PE tratate separat.
- Cablu BMP–tablou dimensionat după curent, lungime, material, metoda de pozare, temperatură, cădere de tensiune, protecție și condițiile de scurtcircuit.
- Plan de amplasare a aparatajului în tablou, repartizare pe șine/module și schemă monofilară.
- Listă de materiale cu cantități, producători/coduri și fișe disponibile.
- Export PDF pentru ofertare și execuție, cu avertizări și datele de calcul.

AFDD, RCD/RCCB, RCBO și funcțiile antiincendiu nu sunt interschimbabile; alegerea trebuie justificată circuit cu circuit.

## 5. Tablou de antiinsularizare — 27 kW până la 5.000 kW

Configuratorul trebuie să primească puterea, tensiunea și tipul rețelei, numărul și modelele exacte ale invertoarelor, puterea/curentul fiecăruia, lungimile și condițiile de pozare pentru cabluri, precum și datele de racordare disponibile.

Echipamente cerute:
- UPS de 2.000 VA.
- Releu de monitorizare Schrack, model identificat din documentație.
- Întrerupător principal motorizat.
- Separatoare de măsură dispuse etajat conform schemei aprobate.
- CT-uri pentru măsură indirectă, alese după curent, raport, clasă și sarcină secundară.
- 2–5 prize de serviciu selectabile, cu circuite și protecții adecvate.
- Protecții separate pentru releu, prize și circuite de măsură, potrivit schemei.
- Bare de cupru R/S/T, N și PE, dimensionate și organizate corect; N și PE rămân distincte.
- Cleme, distribuitoare, conductoare și accesorii compatibile.

Calcul și selecție:
1. Citește fișa tehnică exactă a fiecărui invertor și păstrează sursa.
2. Calculează curentul nominal/maxim al fiecărei plecări pe baza datelor reale AC și a tensiunii/fazelor.
3. Cumulează curenții pentru alimentarea comună folosind ipotezele de simultaneitate și proiectare explicite; nu folosi doar suma kW ca unic criteriu.
4. Selectează întreruptoarele, aparatajul motorizat, CT-urile și separatoarele după curent, tensiune, capacitate de rupere, curent de scurtcircuit, coordonare și compatibilitatea circuitelor de comandă.
5. Propune secțiunile cablurilor pentru fiecare invertor și pentru plecarea principală, pe baza curentului, lungimii, materialului, metodei de instalare, temperaturii, grupării și căderii de tensiune.
6. Verifică UPS-ul de 2.000 VA în raport cu puterea reală a sarcinilor de comandă și autonomia cerută.
7. Generează schema monofilară și planul fizic de amplasare a aparatelor, în funcție de amperaj și dimensiunile reale.
8. La puteri mari, permite propunerea de dulapuri/compartimente multiple și arhitecturi diferite în funcție de tensiunea și soluția de racordare.

Nu presupune că o singură arhitectură este potrivită pentru întregul interval 27–5.000 kW. Dacă lipsesc datele de scurtcircuit, cablare sau schema de racordare, marchează rezultatul ca preliminar și cere verificare de proiectant autorizat.

Rezultate: schema monofilară PDF, dispunerea aparatajului, lista completă de materiale, calculele curenților, cablurilor și protecțiilor, sursele fișelor și lista de avertizări.

## 6. Documente, conformitate și flux

- Dosarele folosesc formularele oficiale aplicabile operatorului de distribuție și tipului de solicitare.
- Pentru spor de putere, tratează separat fluxul și formularul oficial corect; nu genera un formular oficial fictiv dacă nu este disponibil.
- Include opisul și anexele aplicabile și arată ce documente lipsesc.
- Nu pretinde că platforma depune automat dosarul la operator fără o integrare autorizată și confirmare tehnică.
- Nu afirma acceptarea garantată de către distribuitor.
- Păstrează semnăturile, documentele și datele clientului în fluxurile existente cu controlul accesului potrivit.

## 7. Portaluri de distribuție după POD

- Recunoașterea operatorului după POD doar când prefixul este validat; altfel utilizatorul confirmă operatorul de pe factură.
- Linkuri către portalurile oficiale.
- Nu solicita și nu stoca parola operatorului în DNS Energy fără o integrare oficială, sigură și autorizată.
- Nu declara depunerea efectuată fără confirmare reală din portal/API.

## 8. Verificare înainte de publicare

- Verifică buildul frontend și testele disponibile.
- Testează navigarea și permisiunile pentru fiecare plan/rol.
- Testează generarea separată a fiecărui PDF și scenariile cu date lipsă.
- Testează circuite monofazate/trifazate, puteri diferite, număr de invertoare și lipsa fișelor tehnice.
- Verifică schema generată, ocuparea modulelor, secțiunile de cablu, protecțiile și avertizările cu scenarii de test documentate.
- Remediază erorile înainte de publicare.
- Lucrul se face pe `deployment-prep`; nu modifica `main` și nu publica live fără acord explicit.
