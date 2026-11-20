import { ArrowDown, ArrowRight, ArrowUpRight, BadgeCheck, BookOpenCheck, Building2, ChevronRight, FileCheck2, FolderKanban, Menu, ShieldCheck, Zap, X } from "lucide-react";
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

function Brand({ light = false }) {
  return <span className={`dns-brand${light ? " dns-brand-light" : ""}`}><span className="dns-brand-mark"><Zap size={20} fill="currentColor" strokeWidth={2.4} /></span><span>DNS <b>ENERGY</b></span></span>;
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
            <a href="#platforma" onClick={closeMenu}>Platforma</a>
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
            <div className="dns-eyebrow"><span /> SOLUȚII DIGITALE PENTRU ENERGIE SOLARĂ</div>
            <h1>Documentația energetică,<br /><em>mai ușor de gestionat.</em></h1>
            <p className="dns-hero-lede">DNS Energy aduce dosarele, datele instalației și documentele tehnice într-un singur spațiu de lucru.</p>
            <div className="dns-hero-actions"><Link to="/app" className="dns-button dns-button-primary">Intră în aplicație <ArrowRight size={18} /></Link><a href="#platforma" className="dns-text-link">Descoperă platforma <ArrowDown size={16} /></a></div>
            <div className="dns-hero-note"><ShieldCheck size={16} /> Acces securizat pentru echipa ta</div>
          </div>
          <WorkPreview />
        </div>
        <div className="dns-hero-bottom"><span>PLANIFICĂ</span><i /><span>DOCUMENTEAZĂ</span><i /><span>FINALIZEAZĂ</span></div>
      </section>

      <section className="dns-intro" id="platforma">
        <div className="dns-section-label">PLATFORMĂ DNS ENERGY</div>
        <div className="dns-intro-row"><h2>Tot ce ține de un dosar,<br /><em>într-un flux de lucru clar.</em></h2><p>O platformă pentru echipele care pregătesc documentația instalațiilor fotovoltaice și gestionează dosarele clienților.</p></div>
        <div className="dns-feature-grid">{features.map(({ icon: Icon, title, text }, index) => <article className="dns-feature-card" key={title}><div className="dns-feature-top"><span className="dns-feature-icon"><Icon size={21} /></span><span className="dns-feature-number">0{index + 1}</span></div><h3>{title}</h3><p>{text}</p><a href="#cum-functioneaza" aria-label={`Află despre ${title}`}><ChevronRight size={18} /></a></article>)}</div>
      </section>

      <section className="dns-process" id="cum-functioneaza">
        <div className="dns-process-inner">
          <div className="dns-process-heading"><div className="dns-section-label">UN FLUX, DE LA DATE LA DOCUMENTE</div><h2>Pașii dosarului,<br /><em>la vedere.</em></h2><p>Informațiile sunt organizate pe etape, ca echipa să poată continua dosarul fără să piardă contextul.</p><Link to="/app" className="dns-button dns-button-outline">Deschide aplicația <ArrowRight size={17} /></Link></div>
          <div className="dns-steps">{steps.map(([number, title, text]) => <div className="dns-step" key={number}><span className="dns-step-number">{number}</span><div><h3>{title}</h3><p>{text}</p></div><ArrowUpRight size={18} className="dns-step-arrow" /></div>)}</div>
        </div>
      </section>

      <section className="dns-contact" id="contact">
        <div className="dns-contact-card"><div className="dns-contact-copy"><div className="dns-section-label">DNS ENERGY</div><h2>Hai să discutăm<br /><em>despre proiectul tău.</em></h2><p>Contactează echipa DNS HOSTESS pentru informații despre platformă și serviciile oferite.</p><a className="dns-button dns-button-primary" href="mailto:dnshostess@outlook.com">Scrie-ne <ArrowRight size={17} /></a></div><div className="dns-contact-details"><div className="dns-contact-detail"><span>EMAIL</span><a href="mailto:dnshostess@outlook.com">dnshostess@outlook.com</a></div><div className="dns-contact-detail"><span>TELEFON</span><a href="tel:+40741540265">+40 741 540 265</a></div><div className="dns-contact-detail"><span>SEDIU</span><p>Str. 1 nr. 85, Cheriu, Bihor, 417362</p></div><div className="dns-contact-company"><Building2 size={17} /> DNS HOSTESS SRL</div></div></div>
      </section>

      <footer className="dns-footer"><Link to="/" className="dns-brand-link"><Brand /></Link><span>© {new Date().getFullYear()} DNS HOSTESS SRL</span><Link to="/app" className="dns-footer-app">Acces aplicație <ArrowRight size={15} /></Link></footer>
    </main>
  );
}

