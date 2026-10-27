import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { Users, FolderOpen, GitBranch, AlertTriangle, SquareStack, Zap, ShieldAlert } from "lucide-react";

const TILES = [
  { to: "/diu", icon: FolderOpen, title: "Dosar de utilizare (DI-U)", desc: "Date beneficiar, instalație, checklist documente și predare finală." },
  { to: "/mono", icon: GitBranch, title: "Scheme monofilare", desc: "Fișe de schemă și elemente de protecție asociate." },
  { to: "/antiinsularizare", icon: ShieldAlert, title: "Tablou antiinsularizare", desc: "Evidență releu, declanșare și documente conform ATR / soluției de racordare." },
];

function Stat({ label, value, foot, color, icon: Icon }) {
  return (
    <div className="den-panel" data-testid={`stat-${label}`}>
      <div className="flex items-center justify-between">
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
    <div>
      <PageHeader
        eyebrow="Bine ai revenit" title="Panou principal"
        sub="Spațiul tău de lucru pentru documentația instalațiilor electrice și fotovoltaice."
        action={<Link to="/diu"><Btn data-testid="new-diu-btn"><FolderOpen size={15} /> Dosar DI-U nou</Btn></Link>}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-7">
        <Stat label="Clienți înregistrați" value={s.clients} foot="În baza de date" icon={Users} />
        <Stat label="Dosare DI-U" value={s.diu} foot="Dosare de lucru" icon={FolderOpen} />
        <Stat label="Scheme monofilare" value={s.mono} foot="Înregistrări" icon={GitBranch} />
        <Stat label="Documente de verificat" value={s.pending} foot="De completat" color="var(--amber)" icon={AlertTriangle} />
      </div>

      <div className="den-panel mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold flex items-center gap-2"><SquareStack size={18} style={{ color: "var(--blue)" }} /> Începe de aici</h2>
          <span className="text-[11px] font-bold px-3 py-1 rounded-full" style={{ background: "#eef4ff", color: "var(--blue)" }}>Module de lucru</span>
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          {TILES.map((t) => (
            <Link key={t.to} to={t.to} data-testid={`tile-${t.to}`}
              className="group rounded-xl border p-5 transition hover:shadow-md hover:-translate-y-0.5" style={{ borderColor: "var(--line)" }}>
              <div className="h-10 w-10 rounded-lg grid place-items-center mb-3" style={{ background: "#eef4ff" }}>
                <t.icon size={20} style={{ color: "var(--blue)" }} />
              </div>
              <b className="block text-[15px]">{t.title}</b>
              <p className="text-[12.5px] mt-1" style={{ color: "var(--muted)" }}>{t.desc}</p>
            </Link>
          ))}
        </div>
      </div>

      <div className="den-panel">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2"><Zap size={18} style={{ color: "var(--blue)" }} /> Dosare recente</h2>
          <Link to="/diu"><Btn variant="secondary">Vezi dosarele</Btn></Link>
        </div>
        {s.recent.length === 0 ? (
          <div className="text-sm py-6 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>
            Nu ai creat încă dosare. Apasă „Dosar DI-U nou" pentru a începe.
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: "var(--line)" }}>
            {s.recent.map((r) => (
              <div key={r.id} className="flex items-center justify-between py-3">
                <div>
                  <div className="font-semibold text-sm">{r.number || "Fără număr"} · {r.client_name || "—"}</div>
                  <div className="text-[12px]" style={{ color: "var(--muted)" }}>{r.type} · {r.power ? `${r.power} kW` : "—"}</div>
                </div>
                <span className="text-[11px] font-bold px-3 py-1 rounded-full" style={{ background: "#eef4ff", color: "var(--blue)" }}>{r.status || "În lucru"}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
