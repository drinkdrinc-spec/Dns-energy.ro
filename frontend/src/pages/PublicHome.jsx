import { ArrowDown, ArrowRight, ArrowUpRight, BookOpenCheck, Building2, Cable, ChevronRight, DraftingCompass, FileCheck2, FolderKanban, Menu, MessageCircle, PlugZap, ShieldCheck, Sun, Zap, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import "./PublicHome.css";

const features = [
  {
    icon: FolderKanban,
    title: "Dosare organizate clar",
    text: "Urmărește informațiile clientului, locul de consum, instalația și documentele din același dosar.",
  },
  {
    icon: BookOpenCheck,
    title: "Date tehnice la îndemână",
    text: "Păstrează în catalog modelele de panouri, invertoare și baterii, împreună cu documentele lor.",
  },
  {
    icon: FileCheck2,
    title: "Documente și verificări",
    text: "Pregătește scheme și documente de lucru, apoi urmărește verificările și pașii dosarului.",
  },
];

const services = [
  {
    menuTitle: "Atestare ANRE",
    icon: ShieldCheck,
    title: "Firmă atestată ANRE",
    text: "DNS HOSTESS este atestată ANRE pentru activitățile din domeniul său de autorizare. Abordăm fiecare lucrare în limitele atestatului și ale cerințelor tehnice aplicabile.",
  },
  {
    menuTitle: "Fotovoltaice",
    icon: Sun,
    title: "Instalații fotovoltaice",
    text: "Proiectăm și realizăm sisteme on-grid, hibride și off-grid pentru locuințe, spații comerciale și obiective industriale, cu sau fără baterii și soluții de backup.",
  },
  {
    menuTitle: "Instalații electrice",
    icon: Cable,
    title: "Instalații electrice și industriale",
    text: "Executăm instalații electrice pentru clădiri noi și existente, hale și spații de producție, inclusiv tablouri, circuite, protecții și modernizări.",
  },
  {
    menuTitle: "Tablouri antiinsularizare",
    icon: ShieldCheck,
    title: "Tablouri de antiinsularizare",
    text: "Configurăm și realizăm tablouri de antiinsularizare pentru instalații fotovoltaice de toate capacitățile, dimensionate la proiect și echipamente.",
  },
  {
    menuTitle: "Stații de încărcare",
    icon: PlugZap,
    title: "Stații de încărcare",
    text: "Proiectăm și instalăm stații de încărcare casnice și industriale, potrivite infrastructurii electrice și modului de utilizare.",
  },
  {
    menuTitle: "Echipamente",
    icon: Sun,
    title: "Echipamente fotovoltaice",
    text: "Furnizăm panouri, invertoare, baterii și componente pentru sisteme rezidențiale și industriale, în funcție de proiect.",
  },
  {
    menuTitle: "Structuri de montaj",
    icon: Cable,
    title: "Structuri de montaj",
    text: "Configurăm structuri pentru montajul panourilor pe acoperiș sau la sol, adaptate amplasamentului și tipului de învelitoare.",
  },
  {
    menuTitle: "Proiectare branșamente",
    icon: DraftingCompass,
    title: "Proiectare branșamente și rețele electrice",
    text: "Proiectăm branșamente, linii electrice și instalații pentru obiective rezidențiale, comerciale și industriale, în funcție de cerințele proiectului.",
  },
  {
    menuTitle: "Lucrări electrice",
    icon: Zap,
    title: "Lucrări și soluții electrice",
    text: "Realizăm extinderi, modificări și integrarea echipamentelor, urmărind o soluție coerentă și potrivită cerințelor proiectului.",
  },
  {
    menuTitle: "Dosare prosumator / ANRE",
    icon: FolderKanban,
    title: "Dosare de prosumator și documentație ANRE",
    text: "Prin aplicația DNS Energy, instalatorii pregătesc dosare de prosumator și dosare pentru atestarea operatorilor economici, cu datele firmei și documentele organizate într-un singur loc.",
  },
  {
    menuTitle: "Programe și achiziții",
    icon: FileCheck2,
    title: "Proiecte cu finanțare și achiziții publice",
    text: "Lucrăm la proiecte fotovoltaice și electrice derulate prin programe precum PNRR, AFIR și AFM, precum și la achiziții prin SEAP/SICAP. Oferim sprijin tehnic de la definirea soluției și documentația lucrării până la execuție și punere în funcțiune, în funcție de cerințele fiecărui apel sau proceduri.",
  },
];

const equipmentCategories = [
  { id: "inverters", label: "Invertoare", brands: "DEYE · SOLIS · HUAWEI · SIGENERGY · FRONIUS", text: "Soluții monofazate și trifazate, hibride sau on-grid, alese în funcție de puterea instalației și de modul de utilizare." },
  { id: "batteries", label: "Baterii", brands: "DYNESS · DEYE · UHOME · JA SOLAR", text: "Sisteme de stocare pentru autoconsum, backup și integrare cu invertoare compatibile." },
  { id: "chargers", label: "Stații de încărcare", brands: "CASNICE · COMERCIALE · INDUSTRIALE", text: "Stații de încărcare dimensionate pentru locuințe, parcări, sedii și obiective industriale." },
  { id: "panels", label: "Panouri fotovoltaice", brands: "JINKO · AIKO · TRINA · CANADIAN SOLAR", text: "Module fotovoltaice selectate după suprafață, orientare, puterea urmărită și compatibilitatea cu invertorul." },
  { id: "boards", label: "Tablouri electrice", brands: "TABLOURI ELECTRICE · ANTIINSULARIZARE", text: "Tablouri și protecții configurate pentru instalații fotovoltaice și electrice, conform proiectului și echipamentelor instalate." },
  { id: "roof", label: "Sisteme de prindere acoperiș", brands: "ȚIGLĂ · TABLĂ · TERASĂ", text: "Sisteme de montaj configurate în funcție de tipul acoperișului, structură și amplasarea panourilor." },
  { id: "ground", label: "Structuri la sol", brands: "STRUCTURI FIXE · PROIECTE REZIDENȚIALE ȘI INDUSTRIALE", text: "Structuri de montaj la sol adaptate terenului și configurației sistemului fotovoltaic." },
  { id: "heat-pumps", label: "Pompe de căldură", brands: "SOLUȚII PENTRU LOCUINȚE ȘI SPAȚII COMERCIALE", text: "Soluții de încălzire și preparare a apei calde, evaluate în raport cu clădirea și instalația existentă." },
  { id: "air-conditioning", label: "Aer condiționat", brands: "SISTEME PENTRU LOCUINȚE ȘI SPAȚII DE LUCRU", text: "Echipamente și soluții de climatizare alese în funcție de spațiu, utilizare și cerințele proiectului." },
  { id: "cables", label: "Cabluri fotovoltaice", brands: "CABLURI SOLARE ȘI ACCESORII DE CONEXIUNE", text: "Cabluri și componente de conexiune selectate pentru traseu, condițiile de montaj și parametrii instalației." },
];

function Brand({ light = false }) {
  return <span className={`dns-brand${light ? " dns-brand-light" : ""}`}><span className="dns-brand-mark"><img src="/dns-energy-official.png" alt="" /></span><span>DNS <b>ENERGY</b></span></span>;
}

function EquipmentPreview() {
  return (
    <div className="dns-hero-showcase">
      <img src="/dns-equipment-showcase.jpg" alt="Panouri, invertor, baterii și stații de încărcare, imagini ilustrative" fetchPriority="high" />
      <div className="dns-hero-showcase-label"><Sun size={16} /> SOLUȚII PENTRU LOCUINȚE ȘI INDUSTRIE</div>
    </div>
  );
}

export default function PublicHome() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [servicesMenuOpen, setServicesMenuOpen] = useState(false);
  const [activeEquipment, setActiveEquipment] = useState(equipmentCategories[0].id);
  const [activeService, setActiveService] = useState(0);
  const closeMenu = () => setMenuOpen(false);
  const closeServicesMenu = () => setServicesMenuOpen(false);
  const selectedEquipment = equipmentCategories.find((item) => item.id === activeEquipment) ?? equipmentCategories[0];
  const selectedService = services[activeService] ?? services[0];

  return (
    <main className="dns-public">
      <a className="dns-whatsapp-float" href="https://wa.me/40741540265" target="_blank" rel="noreferrer" aria-label="Contactați DNS Energy pe WhatsApp"><MessageCircle size={22} /><span>WhatsApp</span></a>
      <button className={`dns-services-tab${servicesMenuOpen ? " is-open" : ""}`} type="button" onClick={() => setServicesMenuOpen(!servicesMenuOpen)} aria-expanded={servicesMenuOpen} aria-controls="dns-services-drawer"><Menu size={17} /><span>Ce facem</span></button>
      <div className={`dns-services-scrim${servicesMenuOpen ? " is-open" : ""}`} onClick={closeServicesMenu} aria-hidden="true" />
      <aside className={`dns-services-drawer${servicesMenuOpen ? " is-open" : ""}`} id="dns-services-drawer" aria-label="Meniu Ce facem" aria-hidden={!servicesMenuOpen}>
        <div className="dns-services-drawer-head"><div><span>DNS ENERGY</span><strong>Ce facem</strong></div><button type="button" onClick={closeServicesMenu} aria-label="Închide meniul"><X size={19} /></button></div>
        <nav aria-label="Serviciile DNS Energy">{services.map((item, index) => <button key={item.title} type="button" className={`dns-services-category${activeService === index ? " is-active" : ""}`} onClick={() => { setActiveService(index); closeServicesMenu(); document.getElementById("servicii")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}><span>{item.menuTitle}</span><ChevronRight size={16} /></button>)}</nav>
        <a href="#contact" onClick={closeServicesMenu}>Solicitați o ofertă <ArrowRight size={15} /></a>
      </aside>
      <header className="dns-site-header">
        <div className="dns-site-header-inner">
          <Link to="/" className="dns-brand-link" aria-label="DNS Energy, pagina principală"><Brand /></Link>
          <button className="dns-mobile-menu" type="button" onClick={() => setMenuOpen(!menuOpen)} aria-label={menuOpen ? "Închide meniul" : "Deschide meniul"} aria-expanded={menuOpen}>{menuOpen ? <X size={21} /> : <Menu size={21} />}</button>
          <nav className={`dns-site-nav${menuOpen ? " is-open" : ""}`} aria-label="Navigare principală">
            <a href="#echipamente" onClick={closeMenu}>Echipamente</a>
            <a href="#despre-noi" onClick={closeMenu}>Despre noi</a>
            <a href="#contact" onClick={closeMenu}>Contact</a>
            <Link className="dns-nav-app" to="/app" onClick={closeMenu}>Acces aplicație <ArrowUpRight size={16} /></Link>
            <Link className="dns-nav-app" to="/login?mode=register" onClick={closeMenu}>Cont nou instalator / partener</Link>
          </nav>
        </div>
      </header>

      <section className="dns-hero">
        <div className="dns-hero-glow" />
        <div className="dns-hero-inner">
          <div className="dns-hero-copy">
            <div className="dns-eyebrow"><span /> PANOURI FOTOVOLTAICE · INSTALAȚII REZIDENȚIALE ȘI INDUSTRIALE</div>
            <h1>Instalații fotovoltaice și electrice<br /><em>pentru locuințe, afaceri și industrie.</em></h1>
            <p className="dns-hero-lede">Proiectăm, furnizăm și instalăm sisteme fotovoltaice pentru locuințe, afaceri și obiective industriale — de la alegerea echipamentelor și structurilor până la montaj și integrare electrică.</p>
            <div className="dns-hero-actions"><a href="#contact" className="dns-button dns-button-primary">Solicitați o ofertă <ArrowRight size={18} /></a><a href="#echipamente" className="dns-text-link">Vezi echipamentele <ArrowDown size={16} /></a></div>
            <div className="dns-hero-note"><ShieldCheck size={16} /> Firmă atestată ANRE · structuri la sol și pe acoperiș · soluții casnice și industriale</div>
          </div>
          <EquipmentPreview />
        </div>
        <div className="dns-hero-bottom"><span>PLANIFICĂ</span><i /><span>DOCUMENTEAZĂ</span><i /><span>FINALIZEAZĂ</span></div>
      </section>

      <section className="dns-services" id="servicii">
        <div className="dns-section-label">CE FACEM</div>
        <div className="dns-services-heading"><h2>Servicii pentru proiecte<br /><em>energetice și electrice.</em></h2><p>Suntem o firmă atestată ANRE. De la proiectare și documentație până la execuție, abordăm fiecare lucrare cu atenție la cerințele tehnice și la specificul obiectivului.</p></div>
        <div className="dns-services-browser">
          <article className="dns-service-detail" aria-live="polite">
            <span className="dns-service-icon"><selectedService.icon size={22} /></span>
            <span className="dns-service-detail-kicker">SERVICII DNS ENERGY</span>
            <h3>{selectedService.title}</h3>
            <p>{selectedService.text}</p>
            <a href="#contact" className="dns-service-detail-link">Solicitați detalii <ArrowRight size={16} /></a>
          </article>
        </div>
        <a href="#contact" className="dns-services-link">Solicitați o discuție despre proiectul dumneavoastră <ArrowRight size={16} /></a>
      </section>

      <section className="dns-equipment" id="echipamente">
        <div className="dns-equipment-inner"><div className="dns-section-label">ECHIPAMENTE ȘI FURNIZARE</div><div className="dns-equipment-heading"><h2>Tot sistemul,<br /><em>configurat pentru proiect.</em></h2><p>Furnizăm echipamente și structuri de montaj pentru sisteme fotovoltaice. Selectăm variantele în funcție de configurație, amplasament și compatibilitatea componentelor.</p></div>
          <div className="dns-equipment-browser">
            <nav className="dns-equipment-sidebar" aria-label="Categorii de echipamente">
              <span className="dns-equipment-sidebar-title">CATEGORII</span>
              {equipmentCategories.map((item) => <button key={item.id} type="button" className={`dns-equipment-category${activeEquipment === item.id ? " is-active" : ""}`} onClick={() => setActiveEquipment(item.id)} aria-current={activeEquipment === item.id ? "true" : undefined}><span>{item.label}</span><ChevronRight size={16} /></button>)}
            </nav>
            <article className="dns-equipment-detail" aria-live="polite">
              <div className="dns-equipment-detail-icon"><Zap size={22} /></div>
              <span className="dns-equipment-detail-kicker">ECHIPAMENTE DNS ENERGY</span>
              <h3>{selectedEquipment.label}</h3>
              <p>{selectedEquipment.text}</p>
              <strong>{selectedEquipment.brands}</strong>
              <small>Disponibilitatea, configurația și oferta se confirmă în funcție de proiect.</small>
              <a href="#contact" className="dns-equipment-quote">Solicitați detalii și ofertă <ArrowRight size={16} /></a>
            </article>
          </div>
          <div className="dns-equipment-partner"><p>Prețurile și catalogul extins sunt disponibile doar instalatorilor și partenerilor autorizați.</p><Link to="/app/catalog-echipamente" className="dns-equipment-partner-link">Acces instalatori și parteneri <ArrowUpRight size={15} /></Link></div>
          <figure className="dns-equipment-gallery"><img src="/dns-equipment-showcase.jpg" alt="Exemple ilustrative de invertor solar, baterii, panouri fotovoltaice, stații de încărcare și tablou electric" loading="lazy" /><figcaption>Imagini ilustrative. Mărcile și configurația echipamentelor se stabilesc în funcție de proiect.</figcaption></figure>
        </div>
      </section>

      <section className="dns-story" id="despre-noi">
        <div className="dns-story-inner">
          <div className="dns-story-copy"><div className="dns-section-label">DESPRE DNS ENERGY</div><h2>Fiecare proiect începe<br /><em>cu o înțelegere clară.</em></h2><p>O instalație bună pornește de la felul în care este folosit spațiul: energia necesară, echipamentele existente și planurile pentru viitor. De aceea, punem întrebările potrivite înainte de a propune soluția.</p><p>Combinăm proiectarea cu lucrările fotovoltaice și electrice, astfel încât componentele să funcționeze împreună. Pentru locuințe, afaceri și obiective industriale, soluția se adaptează clădirii și cerințelor proiectului.</p><a href="#contact" className="dns-services-link">Să discutăm despre proiect <ArrowRight size={16} /></a></div>
          <div className="dns-story-note"><span className="dns-story-mark"><Zap size={21} /></span><div className="dns-story-label">ABORDAREA NOASTRĂ</div><strong>Gândit cu atenție.<br />Realizat cu grijă.</strong><p>Proiectare, instalații și integrare electrică — coordonate într-un parcurs clar, de la primele detalii până la punerea în funcțiune.</p><div className="dns-story-line"><span /><span /><span /><span /></div><div className="dns-story-stages"><span>Consultare</span><span>Proiectare</span><span>Execuție</span><span>Predare</span></div></div>
        </div>
      </section>

      <section className="dns-intro" id="platforma">
        <div className="dns-section-label">TEHNOLOGIE CARE SIMPLIFICĂ LUCRUL</div>
        <div className="dns-intro-row"><h2>Dosare de prosumator<br /><em>și atestare ANRE.</em></h2><div><p>Aplicația DNS Energy este destinată instalatorilor și partenerilor. Ajută la organizarea dosarelor de prosumator și a dosarelor pentru atestarea operatorilor economici ANRE, împreună cu informațiile tehnice și documentele aferente. Accesul la aplicație este separat de pagina de prezentare.</p><Link to="/login?mode=register" className="dns-services-link">Creează cont de instalator / partener <ArrowRight size={16} /></Link></div></div>
        <div className="dns-feature-grid">{features.map(({ icon: Icon, title, text }, index) => <article className="dns-feature-card" key={title}><div className="dns-feature-top"><span className="dns-feature-icon"><Icon size={21} /></span><span className="dns-feature-number">0{index + 1}</span></div><h3>{title}</h3><p>{text}</p><a href="#cum-functioneaza" aria-label={`Află despre ${title}`}><ChevronRight size={18} /></a></article>)}</div>
      </section>

      <section className="dns-process" id="cum-functioneaza">
        <div className="dns-process-inner">
          <div className="dns-process-heading"><div className="dns-section-label">UN FLUX DE LUCRU MAI CLAR</div><h2>Automatizăm pașii<br /><em>care consumă timp.</em></h2><p>Aplicația preia activitățile repetitive de organizare, ca echipa să poată urmări mai ușor fiecare dosar și etapă a lucrării.</p><Link to="/app" className="dns-button dns-button-outline">Deschide aplicația <ArrowRight size={17} /></Link></div>
          <div className="dns-steps">{[
            ["01", "Date centralizate", "Informațiile clientului, ale locului de consum și ale instalației sunt grupate în dosar."],
            ["02", "Echipamente ușor de regăsit", "Catalogul păstrează modelele și fișele tehnice pentru echipamentele folosite."],
            ["03", "Documente pregătite mai simplu", "Aplicația reutilizează datele introduse pentru documentele și schemele disponibile."],
            ["04", "Verificare și urmărire", "Echipa verifică rezultatele și vede ce informații sau pași mai sunt necesari."],
          ].map(([number, title, text]) => <div className="dns-step" key={number}><span className="dns-step-number">{number}</span><div><h3>{title}</h3><p>{text}</p></div><ArrowUpRight size={18} className="dns-step-arrow" /></div>)}</div>
        </div>
      </section>

      <section className="dns-contact" id="contact">
        <div className="dns-contact-card"><div className="dns-contact-copy"><div className="dns-section-label">DNS ENERGY</div><h2>Suntem aici pentru<br /><em>proiectul dumneavoastră.</em></h2><p>Pentru prezentarea serviciilor și detalii de ofertare, vă invităm să contactați echipa DNS HOSTESS.</p><a className="dns-button dns-button-primary" href="mailto:office@dns-energy.ro?subject=Prezentare%20servicii%20%C8%99i%20solicitare%20ofert%C4%83">Solicitați o ofertă <ArrowRight size={17} /></a></div><div className="dns-contact-details"><div className="dns-contact-detail"><span>PREZENTARE ȘI OFERTARE</span><a href="mailto:office@dns-energy.ro">office@dns-energy.ro</a></div><div className="dns-contact-detail"><span>TELEFON</span><a href="tel:+40741540265">0741 540 265</a></div><a className="dns-contact-whatsapp" href="https://wa.me/40741540265" target="_blank" rel="noreferrer"><MessageCircle size={17} /> Scrieți-ne pe WhatsApp</a><div className="dns-contact-detail"><span>SEDIU</span><p>Str. 1 nr. 85, Cheriu, Bihor, 417362</p></div><div className="dns-contact-company"><Building2 size={17} /> DNS HOSTESS SRL</div></div></div>
      </section>

      <footer className="dns-footer"><Link to="/" className="dns-brand-link"><Brand /></Link><span>© {new Date().getFullYear()} DNS HOSTESS SRL</span><Link to="/app" className="dns-footer-app">Acces aplicație <ArrowRight size={15} /></Link></footer>
    </main>
  );
}



