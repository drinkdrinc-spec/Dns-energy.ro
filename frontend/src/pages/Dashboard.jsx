import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { AtrDeadlines } from "@/components/AtrDeadlines";
import {
  Users, FolderOpen, GitBranch, AlertTriangle, SquareStack, Zap,
  ShieldAlert, FileText, SunMedium, Cpu, Archive, FileCheck2, Receipt,
} from "lucide-react";

const TILES = [
  { to: "/prosumator", icon: SunMedium, title: "Dosar de prosumator", desc: "Creează dosarul, completează datele tehnice și pregătește documentele pentru depunere.", tone: "amber" },
  { to: "/cerere-atr", icon: FileText, title: "Cerere ATR", desc: "Pregătește cererea și datele necesare pentru avizul tehnic de racordare.", tone: "blue" },
  { to: "/diu", icon: FolderOpen, title: "Dosar de utilizare (DI-U)", desc: "Date beneficiar, instalație, checklist documente și predare finală.", tone: "blue" },
  { to: "/mono", icon: GitBranch, title: "Schema monofilară", desc: "Configurează schema și elementele de protecție asociate instalației.", tone: "blue" },
  { to: "/pram", icon: FileCheck2, title: "Buletin de verificare PRAM", desc: "Completează datele măsurătorilor și pregătește documentul de verificare.", tone: "blue" },
  { to: "/catalog-echipamente", icon: Cpu, title: "Catalog echipamente", desc: "Caută panouri, invertoare, baterii și documentele tehnice aferente.", tone: "blue" },
  { to: "/dosare-arhivate", icon: Archive, title: "Dosare arhivate", desc: "Accesează dosarele salvate și documentele generate anterior.", tone: "blue" },
  { to: "/oferte", icon: Receipt, title: "Oferte și contracte", desc: "Gestionează ofertele și continuă fluxul de documente comerciale.", tone: "blue" },
  { to: "/antiinsularizare", icon: ShieldAlert, title: "Antiinsularizare", desc: "Evidență releu, declanșare și documente conform soluției de racordare.", tone: "blue" },
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
  useEffect(() => { api.get("/stats/dashboard").then((r) => setS(r.data)).catch(() => {}); }, []);

  return (
    <div className="dns-dashboard">
      <PageHeader
        eyebrow="DNS ENERGY · SPAȚIU DE LUCRU" title="Panou principal"
        sub="Acces rapid la dosarele și documentațiile instalațiilor electrice și fotovoltaice."
        action={<Link to="/prosumator"><Btn data-testid="new-diu-btn"><SunMedium size={15} /> Dosar prosumator nou</Btn></Link>}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <Stat label="Clienți înregistrați" value={s.clients} foot="În baza de date" icon={Users} />
        <Stat label="Dosare DI-U" value={s.diu} foot="Dosare de lucru" icon={FolderOpen} />
        <Stat label="Scheme monofilare" value={s.mono} foot="Înregistrări" icon={GitBranch} />
        <Stat label="De verificat" value={s.pending} foot="Documente incomplete" color="var(--amber)" icon={AlertTriangle} />
      </div>

      <AtrDeadlines />

      <section className="den-panel mb-6 mobile-dashboard-modules">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2"><SquareStack size={18} style={{ color: "var(--blue)" }} /> Module de lucru</h2>
          <span className="text-[11px] font-bold px-3 py-1 rounded-full" style={{ background: "#fff1d6", color: "#a65b00" }}>DNS Energy</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-2 xl:grid-cols-3 gap-2.5 sm:gap-3">
          {TILES.map((t) => (
            <Link key={t.to} to={t.to} data-testid={`tile-${t.to}`}
              className="mobile-module-card group flex flex-col sm:flex-row items-start sm:items-center gap-2.5 sm:gap-3 rounded-xl border p-3 sm:p-5 min-w-0 transition hover:shadow-md hover:-translate-y-0.5"
              style={{ borderColor: "var(--line)" }}>
              <div className="mobile-module-icon h-10 w-10 sm:h-12 sm:w-12 shrink-0 rounded-xl grid place-items-center" style={{ background: "#fff1d6" }}>
                <t.icon size={20} style={{ color: "#e68a00" }} />
              </div>
              <div className="min-w-0 flex-1">
                <b className="block text-[14px] sm:text-[15px] leading-snug">{t.title}</b>
                <p className="hidden sm:block text-[12px] mt-1 leading-relaxed" style={{ color: "var(--muted)" }}>{t.desc}</p>
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
            Nu ai dosare recente afișate. Alege un modul de mai sus pentru a începe.
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
