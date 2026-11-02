import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { AtrDeadlines } from "@/components/AtrDeadlines";
import {
  Users, FolderOpen, GitBranch, AlertTriangle, SquareStack, Zap, ExternalLink,
  ShieldAlert, FileText, SunMedium, Cpu, Archive, FileCheck2, Receipt,
  ArrowRight, Upload, ClipboardCheck, PackageCheck, Search,
} from "lucide-react";

const FLOW = [
  {
    number: "01",
    title: "Client și acte",
    desc: "Încarcă CI, factura de energie și cartea funciară. Verifică datele extrase înainte de salvare.",
    to: "/clienti",
    action: "Încarcă documente",
    icon: Upload,
    tone: "amber",
  },
  {
    number: "02",
    title: "Cerere ATR",
    desc: "Alege clientul și pregătește cererea cu datele POD, operatorului și locului de consum.",
    to: "/cerere-atr",
    action: "Pregătește cererea",
    icon: FileText,
    tone: "blue",
  },
  {
    number: "03",
    title: "Spor de putere",
    desc: "Pregătește separat solicitarea și anexele aplicabile pentru majorarea puterii aprobate.",
    to: "/spor-putere",
    action: "Pregătește sporul",
    icon: Zap,
    tone: "blue",
  },
  {
    number: "04",
    title: "Dosar prosumator",
    desc: "Alege invertorul, panourile și bateria. Datele tehnice disponibile se preiau din catalog.",
    to: "/prosumator",
    action: "Configurează instalația",
    icon: Cpu,
    tone: "blue",
  },
  {
    number: "05",
    title: "Dosar DI-U",
    desc: "Pregătește documentele instalației folosind datele deja salvate la client și în dosar.",
    to: "/diu",
    action: "Pregătește DI-U",
    icon: ClipboardCheck,
    tone: "blue",
  },
  {
    number: "06",
    title: "Buletin PRAM",
    desc: "Completează și descarcă separat buletinul folosind numai rezultatele măsurate efectiv.",
    to: "/pram",
    action: "Deschide PRAM",
    icon: FileCheck2,
    tone: "blue",
  },
  {
    number: "07",
    title: "Schema monofilară",
    desc: "Verifică protecțiile și dimensionarea, apoi descarcă schema separat.",
    to: "/mono",
    action: "Deschide schema",
    icon: GitBranch,
    tone: "blue",
  },
  {
    number: "08",
    title: "Verificare ANRE și portal OD",
    desc: "Verifică documentele necesare și deschide canalul oficial al operatorului.",
    to: "/dosare-anre",
    action: "Verifică dosarul",
    icon: PackageCheck,
    tone: "blue",
  },
];

const TILES = [
  { to: "/clienti", icon: Users, title: "Clienți și documente", desc: "Încarcă actele clientului și verifică datele extrase." },
  { to: "/cerere-atr", icon: FileText, title: "Cereri ATR", desc: "Cererile pentru avizul tehnic de racordare." },
  { to: "/spor-putere", icon: Zap, title: "Spor de putere", desc: "Solicitări pentru majorarea puterii aprobate." },
  { to: "/prosumator", icon: SunMedium, title: "Dosare prosumator", desc: "Date client, instalație și documente pentru depunere." },
  { to: "/diu", icon: FolderOpen, title: "Dosare DI-U", desc: "Documentele instalației de utilizare." },
  { to: "/pram", icon: FileCheck2, title: "Buletine PRAM", desc: "Documente PRAM separate de dosar." },
  { to: "/mono", icon: GitBranch, title: "Scheme monofilare", desc: "Scheme și protecțiile instalației." },
  { to: "/dosare-anre", icon: ShieldAlert, title: "Dosare ANRE", desc: "Dosare și documente pentru depunere ANRE." },
  { to: "/catalog-echipamente", icon: Cpu, title: "Catalog echipamente", desc: "Panouri, invertoare, baterii și fișe." },
  { to: "/portaluri-distribuitori", icon: ExternalLink, title: "Portaluri operatori", desc: "Acces rapid la portalurile oficiale de depunere." },
  { to: "/oferte", icon: Receipt, title: "Oferte și contracte", desc: "Documentele comerciale ale firmei." },
  { to: "/dosare-arhivate", icon: Archive, title: "Arhivă", desc: "Dosare și documente generate anterior." },
];

function Stat({ label, value, foot, color, icon: Icon }) {
  return (
    <div className="den-panel mobile-dashboard-stat" data-testid={`stat-${label}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>{label}</div>
        <Icon size={18} style={{ color: "var(--blue)" }} />
      </div>
      <div className="text-4xl font-extrabold mt-3" style={{ color: color || "var(--ink)" }}>{value}</div>
      <div className="text-[11px] mt-1" style={{ color: color || "var(--muted)" }}>{foot}</div>
    </div>
  );
}

export default function Dashboard() {
  const [s, setS] = useState({ clients: 0, diu: 0, mono: 0, pending: 0, recent: [] });
  const [clientQuery, setClientQuery] = useState("");
  const [clientResults, setClientResults] = useState([]);
  const [searchingClients, setSearchingClients] = useState(false);
  const [clientSearchFailed, setClientSearchFailed] = useState(false);
  useEffect(() => { api.get("/stats/dashboard").then((r) => setS(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    const query = clientQuery.trim();
    if (query.length < 2) { setClientResults([]); setSearchingClients(false); setClientSearchFailed(false); return undefined; }
    let cancelled = false;
    setClientResults([]);
    setClientSearchFailed(false);
    setSearchingClients(true);
    const timer = setTimeout(() => api.get("/clients/search", { params: { q: query } })
      .then((r) => { if (!cancelled) { setClientResults((r.data?.results || []).slice(0, 8)); setClientSearchFailed((r.data?.unavailable || []).includes("Client")); } })
      .catch(() => { if (!cancelled) { setClientResults([]); setClientSearchFailed(true); } })
      .finally(() => { if (!cancelled) setSearchingClients(false); }), 250);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [clientQuery]);

  return (
    <div className="dns-dashboard">
      <PageHeader
        eyebrow="DNS ENERGY · SPAȚIU DE LUCRU"
        title="Panou principal"
        sub="Un singur flux pentru dosarul clientului, de la documentele inițiale până la pregătirea depunerii."
        action={<Link to="/prosumator"><Btn data-testid="new-diu-btn"><SunMedium size={15} /> Dosar nou</Btn></Link>}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <Stat label="Clienți înregistrați" value={s.clients} foot="În baza de date" icon={Users} />
        <Stat label="Dosare DI-U" value={s.diu} foot="Dosare de lucru" icon={FolderOpen} />
        <Stat label="Scheme monofilare" value={s.mono} foot="Înregistrări" icon={GitBranch} />
        <Stat label="De verificat" value={s.pending} foot="Documente incomplete" color="var(--amber)" icon={AlertTriangle} />
      </div>

      <AtrDeadlines />

      <section className="den-panel mb-6" aria-labelledby="client-fast-search-title" data-testid="dashboard-client-search">
        <div className="flex items-center gap-2 mb-3">
          <Search size={17} style={{ color: "var(--blue)" }} />
          <h2 id="client-fast-search-title" className="text-base font-bold">Acces rapid la baza de clienți</h2>
        </div>
        <input
          className="den-input w-full"
          value={clientQuery}
          onChange={(event) => setClientQuery(event.target.value)}
          placeholder="Caută nume, POD, telefon, e-mail sau adresă…"
          aria-label="Caută în baza de clienți"
          data-testid="dashboard-client-search-input"
        />
        {clientQuery.trim().length >= 2 && <div className="mt-2 divide-y" style={{ borderColor: "var(--line)" }} aria-live="polite">
          {searchingClients ? <div className="py-3 text-xs" style={{ color: "var(--muted)" }}>Caut în baza de date…</div> : clientResults.length ? clientResults.map((client) => (
            <Link key={client.id} to={client.href} className="flex items-center justify-between gap-3 py-3 hover:bg-slate-50" data-testid={"dashboard-client-result-" + client.id}>
              <span className="min-w-0">
                <b className="block text-sm truncate">{client.title || "Client fără nume"}</b>
                <span className="block text-xs truncate" style={{ color: "var(--muted)" }}>{client.detail || "Deschide fișa clientului"}</span>
              </span>
              <ArrowRight size={16} className="shrink-0" style={{ color: "var(--blue)" }} />
            </Link>
          )) : <div className="py-3 text-xs" style={{ color: "var(--muted)" }}>{clientSearchFailed ? "Căutarea bazei de clienți nu este disponibilă momentan." : "Nu am găsit clienți pentru această căutare."}</div>}
        </div>}
      </section>

      <section className="den-panel mb-6" aria-labelledby="main-flow-title">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--blue)" }}>FLUX DE LUCRU</div>
            <h2 id="main-flow-title" className="text-lg sm:text-xl font-bold">Dosar client, în ordinea completării</h2>
            <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>Datele și echipamentele selectate se folosesc în documentele următoare.</p>
          </div>
          <PackageCheck className="hidden sm:block shrink-0" size={22} style={{ color: "var(--blue)" }} />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
          {FLOW.map((step, index) => (
            <Link
              key={step.number}
              to={step.to}
              data-testid={`workflow-step-${step.number}`}
              className="group relative flex flex-col rounded-xl border p-4 transition hover:shadow-md"
              style={{ borderColor: "var(--line)", background: "var(--surface, white)" }}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-extrabold tracking-wider" style={{ color: step.tone === "amber" ? "#a65b00" : "var(--blue)" }}>PASUL {step.number}</span>
                <step.icon size={18} style={{ color: step.tone === "amber" ? "#e68a00" : "var(--blue)" }} />
              </div>
              <b className="text-[15px] leading-snug">{step.title}</b>
              <p className="text-[12px] leading-relaxed mt-2 flex-1" style={{ color: "var(--muted)" }}>{step.desc}</p>
              <span className="inline-flex items-center gap-1.5 mt-4 text-sm font-bold" style={{ color: "var(--blue)" }}>
                {step.action}<ArrowRight size={15} className="transition group-hover:translate-x-1" />
              </span>
              {index < FLOW.length - 1 && <span className="sr-only">Urmează pasul {FLOW[index + 1].number}</span>}
            </Link>
          ))}
        </div>
      </section>

      <section className="den-panel mb-6 mobile-dashboard-modules">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2"><SquareStack size={18} style={{ color: "var(--blue)" }} /> Acces direct la module</h2>
          <span className="text-[11px] font-bold px-3 py-1 rounded-full" style={{ background: "#fff1d6", color: "#a65b00" }}>DNS Energy</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-2 xl:grid-cols-3 gap-2.5 sm:gap-3">
          {TILES.map((t) => (
            <Link key={t.to} to={t.to} data-testid={`tile-${t.to}`}
              className="mobile-module-card group flex flex-col sm:flex-row items-start sm:items-center gap-2.5 sm:gap-3 rounded-xl border p-3 sm:p-4 min-w-0 transition hover:shadow-md"
              style={{ borderColor: "var(--line)" }}>
              <div className="mobile-module-icon h-10 w-10 shrink-0 rounded-xl grid place-items-center" style={{ background: "#edf4ff" }}>
                <t.icon size={19} style={{ color: "var(--blue)" }} />
              </div>
              <div className="min-w-0 flex-1">
                <b className="block text-[13px] sm:text-[14px] leading-snug">{t.title}</b>
                <p className="hidden sm:block text-[11px] mt-1 leading-relaxed" style={{ color: "var(--muted)" }}>{t.desc}</p>
              </div>
              <span className="mobile-module-chevron text-xl hidden sm:inline self-center" aria-hidden="true">›</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="den-panel mobile-dashboard-recent">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2"><Zap size={18} style={{ color: "var(--blue)" }} /> Dosare recente</h2>
          <Link to="/dosare-arhivate"><Btn variant="secondary">Arhivă</Btn></Link>
        </div>
        {s.recent.length === 0 ? (
          <div className="text-sm py-6 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>
            Nu ai dosare recente afișate. Începe cu încărcarea documentelor clientului din pasul 01.
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: "var(--line)" }}>
            {s.recent.map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <div className="font-semibold text-sm break-words">{r.number || "Fără număr"} · {r.client_name || "—"}</div>
                  <div className="text-[12px]" style={{ color: "var(--muted)" }}>{r.type} · {r.power ? `${r.power} kW` : "—"}</div>
                </div>
                <span className="shrink-0 text-[11px] font-bold px-3 py-1 rounded-full" style={{ background: "#fff1d6", color: "#a65b00" }}>{r.status || "În lucru"}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
