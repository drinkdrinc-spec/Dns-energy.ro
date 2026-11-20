import { ArrowDown, ArrowRight, ArrowUpRight, BadgeCheck, BookOpenCheck, Building2, Cable, ChevronRight, DraftingCompass, FileCheck2, FolderKanban, Menu, PlugZap, ShieldCheck, Sun, Zap, X } from "lucide-react";
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

const steps = [
  ["01", "Client și loc de consum", "Datele beneficiarului și ale racordului, grupate într-un singur dosar."],
  ["02", "Instalație și echipamente", "Configurația sistemului fotovoltaic și echipamentele folosite."],
  ["03", "Documente și punere în funcțiune", "Acte, verificări și informații pentru pașii de finalizare."],
];

const services = [
  {
    icon: Sun,
    title: "Instalații fotovoltaice",
    text: "Proiectăm și realizăm sisteme on-grid, hibride și off-grid pentru locuințe, spații comerciale și obiective industriale, cu sau fără baterii și soluții de backup.",
  },
  {
    icon: Cable,
    title: "Instalații electrice și industriale",
    text: "Executăm instalații electrice pentru clădiri noi și existente, hale și spații de producție, inclusiv tablouri, circuite, protecții și modernizări.",
  },
  {
    icon: ShieldCheck,
    title: "Tablouri de antiinsularizare",
    text: "Configurăm și realizăm tablouri de antiinsularizare pentru instalații fotovoltaice de toate capacitățile, dimensionate la proiect și echipamente.",
  },
  {
    icon: PlugZap,
    title: "Stații de încărcare",
    text: "Proiectăm și instalăm stații de încărcare casnice și industriale, potrivite infrastructurii electrice și modului de utilizare.",
  },
  {
    icon: DraftingCompass,
    title: "Proiectare electrică",
    text: "Elaborăm proiecte pentru instalații electrice și fotovoltaice și dimensionăm soluții tehnice potrivite specificului fiecărei lucrări.",
  },
  {
    icon: Zap,
    title: "Lucrări și soluții electrice",
    text: "Realizăm extinderi, modificări și integrarea echipamentelor, urmărind o soluție coerentă și potrivită cerințelor proiectului.",
  },
];

function Brand({ light = false }) {
  return <span className={`dns-brand${light ? " dns-brand-light" : ""}`}><span className="dns-brand-mark"><img src="/dns-energy-official.png" alt="" /></span><span>DNS <b>ENERGY</b></span></span>;
}

function WorkPreview() {
  return (
    <div className="dns-preview-wrap" aria-label="Previzualizare ilustrativă a aplicației DNS Energy">
      <div className="dns-preview-orbit dns-preview-orbit-one" />
      <div className="dns-preview-orbit dns-preview-orbit-two" />
      <div className="dns-preview-window">
        <div className="dns-preview-top"><span className="dns-preview-dots"><i /><i /><i /></span><span>dns-energy.ro/app</span><span className="dns-preview-live"><i /> activ</span></div>
        <div className="dns-preview-body">
          <div className="dns-preview-sidebar"><Brand light /><span className="dns-preview-nav active" /><span className="dns-preview-nav" /><span className="dns-preview-nav" /><span className="dns-preview-nav short" /></div>
          <div className="dns-preview-content">
            <div className="dns-preview-heading"><div><small>DOSARE</small><strong>Dosar prosumator</strong></div><span className="dns-preview-tag">În lucru</span></div>
            <div className="dns-preview-progress"><span /><span /><span /><span /></div>
            <div className="dns-preview-caption">Progresul dosarului</div>
            <div className="dns-preview-grid"><div className="dns-mini-card"><Building2 size={17} /><small>Client și loc de consum</small><b>Informații salvate</b></div><div className="dns-mini-card"><Zap size={17} /><small>Instalație fotovoltaică</small><b>Echipamente configurate</b></div></div>
            <div className="dns-preview-document"><span className="dns-document-icon"><FileCheck2 size={18} /></span><span><b>Schemă monofilară</b><small>Document tehnic · PDF</small></span><BadgeCheck className="dns-document-check" size={18} /></div>
          </div>
        </div>
      </div>
      <div className="dns-float-note"><span className="dns-float-icon"><ShieldCheck size={18} /></span><span><b>Date centralizate</b><small>Dosar și documente într-un loc</small></span></div>
    </div>
  );
}

export default function PublicHome() {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  return (
    <main className="dns-public">
      <header className="dns-site-header">
        <div className="dns-site-header-inner">
          <Link to="/" className="dns-brand-link" aria-label="DNS Energy, pagina principală"><Brand /></Link>
          <button className="dns-mobile-menu" type="button" onClick={() => setMenuOpen(!menuOpen)} aria-label={menuOpen ? "Închide meniul" : "Deschide meniul"} aria-expanded={menuOpen}>{menuOpen ? <X size={21} /> : <Menu size={21} />}</button>
          <nav className={`dns-site-nav${menuOpen ? " is-open" : ""}`} aria-label="Navigare principală">
            <a href="#despre-noi" onClick={closeMenu}>Despre noi</a>
            <a href="#servicii" onClick={closeMenu}>Servicii</a>
            <a href="#platforma" onClick={closeMenu}>Aplicația</a>
            <a href="#cum-functioneaza" onClick={closeMenu}>Cum funcționează</a>
            <a href="#contact" onClick={closeMenu}>Contact</a>
            <Link className="dns-nav-app" to="/app" onClick={closeMenu}>Intră în aplicație <ArrowUpRight size={16} /></Link>
          </nav>
        </div>
      </header>

      <section className="dns-hero">
        <div className="dns-hero-glow" />
        <div className="dns-hero-inner">
          <div className="dns-hero-copy">
            <div className="dns-eyebrow"><span /> INSTALAȚII ȘI PROIECTARE ELECTRICĂ</div>
            <h1>Soluții energetice,<br /><em>bine gândite și realizate.</em></h1>
            <p className="dns-hero-lede">Oferim servicii de proiectare și execuție pentru instalații fotovoltaice de toate tipurile și instalații electrice, adaptate fiecărui proiect.</p>
            <div className="dns-hero-actions"><a href="#servicii" className="dns-button dns-button-primary">Vezi serviciile <ArrowRight size={18} /></a><Link to="/app" className="dns-text-link">Intră în aplicație <ArrowUpRight size={16} /></Link></div>
            <div className="dns-hero-note"><ShieldCheck size={16} /> Servicii complete, de la proiectare la execuție</div>
          </div>
          <WorkPreview />
        </div>
        <div className="dns-hero-bottom"><span>PLANIFICĂ</span><i /><span>DOCUMENTEAZĂ</span><i /><span>FINALIZEAZĂ</span></div>
      </section>

      <section className="dns-services" id="servicii">
        <div className="dns-section-label">CE FACEM</div>
        <div className="dns-services-heading"><h2>Servicii pentru proiecte<br /><em>energetice și electrice.</em></h2><p>De la planificare la execuție, abordăm fiecare lucrare cu atenție la cerințele tehnice și la specificul obiectivului.</p></div>
        <div className="dns-services-grid">{services.map(({ icon: Icon, title, text }, index) => <article className="dns-service-card" key={title}><span className="dns-service-icon"><Icon size={22} /></span><span className="dns-service-number">0{index + 1}</span><h3>{title}</h3><p>{text}</p></article>)}</div>
        <a href="#contact" className="dns-services-link">Solicitați o discuție despre proiectul dumneavoastră <ArrowRight size={16} /></a>
      </section>

      <section className="dns-equipment" id="echipamente">
        <div className="dns-equipment-inner"><div className="dns-section-label">ECHIPAMENTE PENTRU FIECARE PROIECT</div><div className="dns-equipment-heading"><h2>Lucrăm cu mărci<br /><em>recunoscute în domeniu.</em></h2><p>Selectăm echipamentele în funcție de configurație, cerințele obiectivului și compatibilitatea sistemului. Portofoliul include și alte modele potrivite proiectului.</p></div>
          <div className="dns-equipment-grid">
            <article className="dns-equipment-card"><span>INVERTOARE</span><p>DEYE · SOLIS · HUAWEI · SIGENERGY · FRONIUS</p><small>și alte modele compatibile</small></article>
            <article className="dns-equipment-card"><span>BATERII</span><p>DYNESS · DEYE · UHOME · JA SOLAR</p><small>și alte soluții de stocare</small></article>
            <article className="dns-equipment-card"><span>PANOURI FOTOVOLTAICE</span><p>JINKO · AIKO · TRINA · CANADIAN SOLAR</p><small>și alte mărci disponibile</small></article>
          </div>
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
        <div className="dns-intro-row"><h2>Mai puțină muncă repetitivă.<br /><em>Mai multă claritate.</em></h2><p>Aplicația DNS Energy ajută echipa să organizeze dosarele și să urmărească informațiile tehnice, în timp ce verificarea finală rămâne în grija specialiștilor.</p></div>
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
        <div className="dns-contact-card"><div className="dns-contact-copy"><div className="dns-section-label">DNS ENERGY</div><h2>Suntem aici pentru<br /><em>proiectul dumneavoastră.</em></h2><p>Pentru prezentarea serviciilor și detalii de ofertare, vă invităm să contactați echipa DNS HOSTESS.</p><a className="dns-button dns-button-primary" href="mailto:office@dns-hostess.ro?subject=Prezentare%20servicii%20%C8%99i%20solicitare%20ofert%C4%83">Solicitați o ofertă <ArrowRight size={17} /></a></div><div className="dns-contact-details"><div className="dns-contact-detail"><span>PREZENTARE ȘI OFERTARE</span><a href="mailto:office@dns-hostess.ro">office@dns-hostess.ro</a></div><div className="dns-contact-detail"><span>TELEFON</span><a href="tel:+40741540265">0741 540 265</a></div><div className="dns-contact-detail"><span>SEDIU</span><p>Str. 1 nr. 85, Cheriu, Bihor, 417362</p></div><div className="dns-contact-company"><Building2 size={17} /> DNS HOSTESS SRL</div></div></div>
      </section>

      <footer className="dns-footer"><Link to="/" className="dns-brand-link"><Brand /></Link><span>© {new Date().getFullYear()} DNS HOSTESS SRL</span><Link to="/app" className="dns-footer-app">Acces aplicație <ArrowRight size={15} /></Link></footer>
    </main>
  );
}

