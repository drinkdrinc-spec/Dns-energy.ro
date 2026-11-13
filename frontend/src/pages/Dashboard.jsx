import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Btn, PageHeader } from "@/components/Layout";
import { AtrDeadlines } from "@/components/AtrDeadlines";
import {
  Users, FolderOpen, GitBranch, AlertTriangle, Zap,
  ArrowUpRight, Plus, Clock3, ChevronRight, MapPin,
} from "lucide-react";

const SHORTCUTS = [
  { to: "/prosumator", icon: Zap, title: "Dosar prosumator", text: "Pregătește documentația de racordare." },
  { to: "/diu", icon: FolderOpen, title: "Dosar DI-U", text: "Deschide un dosar de utilizare nou." },
  { to: "/clienti", icon: Users, title: "Adaugă client", text: "Gestionează datele beneficiarilor." },
  { to: "/mono", icon: GitBranch, title: "Schemă monofilară", text: "Continuă documentația tehnică." },
];

function Stat({ label, value, note, icon: Icon, tone = "blue", to }) {
  const tones = {
    blue: { color: "#2878f0", bg: "#edf4ff" },
    green: { color: "#168468", bg: "#eaf8f2" },
    amber: { color: "#b77918", bg: "#fff6e8" },
    violet: { color: "#7558c9", bg: "#f2efff" },
  };
  const c = tones[tone];
  const content = <>
    <div className="flex items-start justify-between gap-2">
      <div className="text-[12px] font-semibold" style={{ color: "var(--muted)" }}>{label}</div>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl" style={{ color: c.color, background: c.bg }}><Icon size={18} /></span>
    </div>
    <div className="mt-4 text-[32px] font-extrabold leading-none" style={{ color: "var(--ink)" }}>{value}</div>
    <div className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>{note}</div>
  </>;
  return to ? <Link to={to} className="den-panel block !p-5 transition hover:-translate-y-0.5 hover:shadow-md" data-testid={`stat-${label}`}>{content}</Link>
    : <div className="den-panel !p-5" data-testid={`stat-${label}`}>{content}</div>;
}

function formatDate(value) {
  if (!value) return "Dată neprecizată";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "Dată neprecizată" : d.toLocaleDateString("ro-RO", { day: "numeric", month: "short", year: "numeric" });
}

export default function Dashboard() {
  const [s, setS] = useState({ clients: 0, prosum_recent: [], prosum_total: 0, prosum_submitted_month: 0, prosum_activated_month: 0, prosum_overdue: 0, prosum_by_status: [], prosum_by_operator: [], prosum_follow_up: [] });
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    api.get("/stats/dashboard").then((r) => setS({ ...r.data, prosum_recent: r.data.prosum_recent || [], prosum_by_status: r.data.prosum_by_status || [], prosum_by_operator: r.data.prosum_by_operator || [], prosum_follow_up: r.data.prosum_follow_up || [] })).catch(() => {})
      .finally(() => setLoaded(true));
  }, []);
  const today = new Date().toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "long" });

  return <div data-testid="dashboard-page">
    <PageHeader eyebrow={`D-ENERGY · ${today}`} title="Tablou de bord"
      sub="Activitatea și documentația instalațiilor tale, într-un singur loc."
      action={<div className="mt-1 flex flex-wrap items-center gap-2"><Link to="/prosumator?new=1" className="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2.5 text-xs font-bold text-white shadow-sm transition hover:brightness-95" style={{ background: "var(--blue)" }} data-testid="new-dossier-btn"><Plus size={14} /> Dosar nou</Link><Link to="/prosumator" className="inline-flex items-center gap-1 rounded-lg border bg-white px-3.5 py-2.5 text-xs font-bold transition hover:bg-slate-50" style={{ borderColor: "var(--line)", color: "var(--ink)" }} data-testid="all-dossiers-btn">Toate dosarele <ArrowUpRight size={14} /></Link></div>} />

    <section className="grid grid-cols-2 xl:grid-cols-4 gap-3 sm:gap-4 mb-6" aria-label="Rezumat">
      <Stat label="Dosare active" value={s.prosum_total} note="Dosare de prosumator" icon={FolderOpen} tone="blue" to="/prosumator" />
      <Stat label="Depuse luna asta" value={s.prosum_submitted_month} note="Dosare trimise operatorului" icon={Clock3} tone="violet" to="/prosumator" />
      <Stat label="Activate luna asta" value={s.prosum_activated_month} note="Punere în funcțiune finalizată" icon={Zap} tone="green" to="/prosumator" />
      <Stat label="Termene OD depășite" value={s.prosum_overdue} note="Peste 30 de zile de la depunere" icon={AlertTriangle} tone="amber" to="/prosumator" />
    </section>

    <section className="grid lg:grid-cols-2 gap-4 mb-6" aria-label="Distribuția dosarelor">
      <div className="den-panel !p-5 sm:!p-6" data-testid="dossier-stage-chart">
        <div className="mb-4"><h2 className="text-[15px] font-bold uppercase tracking-wide">Distribuție pe stadiu</h2><p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Dosarele de prosumator din firma ta</p></div>
        {s.prosum_by_status.length ? <div className="space-y-3">{s.prosum_by_status.map((row) => <div key={row.name} className="grid grid-cols-[minmax(90px,1fr)_2fr_28px] items-center gap-3"><span className="truncate text-[11px]">{row.name}</span><div className="h-2 overflow-hidden rounded-full" style={{ background: "#edf0e9" }}><div className="h-full rounded-full" style={{ width: `${Math.max(8, (row.value / Math.max(1, s.prosum_total)) * 100)}%`, background: "var(--green)" }} /></div><b className="text-right text-[11px]">{row.value}</b></div>)}</div> : <div className="rounded-lg py-6 text-center text-xs" style={{ color: "var(--muted)", background: "var(--bg)" }}>Stadiile vor apărea după crearea dosarelor.</div>}
      </div>
      <div className="den-panel !p-5 sm:!p-6" data-testid="dossier-operator-chart">
        <div className="mb-4"><h2 className="text-[15px] font-bold uppercase tracking-wide">Pe operator</h2><p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Dosare grupate după distribuitor</p></div>
        {s.prosum_by_operator.length ? <div className="space-y-3">{s.prosum_by_operator.map((row) => <div key={row.name} className="grid grid-cols-[minmax(90px,1fr)_2fr_28px] items-center gap-3"><span className="truncate text-[11px]"><MapPin size={12} className="mr-1 inline" />{row.name}</span><div className="h-2 overflow-hidden rounded-full" style={{ background: "#edf0e9" }}><div className="h-full rounded-full" style={{ width: `${Math.max(8, (row.value / Math.max(1, s.prosum_total)) * 100)}%`, background: "#78b48b" }} /></div><b className="text-right text-[11px]">{row.value}</b></div>)}</div> : <div className="rounded-lg py-6 text-center text-xs" style={{ color: "var(--muted)", background: "var(--bg)" }}>Distribuția va apărea după completarea operatorului pe dosare.</div>}
      </div>
    </section>

    <section className="den-panel !p-5 sm:!p-6 mb-6" data-testid="daily-dossier-inbox">
      <div className="mb-4 flex items-center justify-between gap-3"><div><div className="flex items-center gap-2"><h2 className="text-[15px] font-bold">Inbox de azi</h2><span className="rounded-full px-2 py-0.5 text-[10px] font-extrabold" style={{ background: "#edf7f0", color: "var(--green)" }}>{s.prosum_follow_up.length}</span></div><p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Termene OD, dosare nedepuse și programări de punere în funcțiune</p></div><Link to="/prosumator" className="text-xs font-bold" style={{ color: "var(--green)" }}>Vezi toate dosarele →</Link></div>
      {s.prosum_follow_up.length ? <div className="divide-y" style={{ borderColor: "var(--line)" }}>{s.prosum_follow_up.map((d) => <Link key={d.id} to={`/prosumator?edit=${d.id}`} className="flex items-center gap-3 py-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-full" style={{ background: d.inbox_priority === 0 ? "#fff0ed" : "#edf7f0", color: d.inbox_priority === 0 ? "#b53c2e" : "var(--green)" }}><Clock3 size={16} /></span><span className="min-w-0 flex-1"><b className="block truncate text-[12px]">{d.number || "Dosar fără număr"} · {d.client_name || "Beneficiar neprecizat"}</b><span className="text-[10px]" style={{ color: d.inbox_priority === 0 ? "#b53c2e" : "var(--muted)" }}>{d.inbox_reason} · {[d.locality, d.county, d.operator].filter(Boolean).join(" · ")}</span></span><span className="rounded-full px-2.5 py-1 text-[10px] font-bold" style={{ background: "#f1f3ed", color: "#596358" }}>{d.status}</span><ChevronRight size={15} style={{ color: "var(--muted)" }} /></Link>)}</div> : <div className="rounded-xl py-6 text-center text-xs" style={{ color: "var(--muted)", background: "var(--bg)" }}>Nu ai dosare cu acțiuni urgente astăzi.</div>}
    </section>

    <AtrDeadlines />

    <section className="den-panel !p-5 sm:!p-6 mb-6" data-testid="quick-actions">
      <div className="flex items-center justify-between gap-3 mb-4"><div><h2 className="text-[17px] font-bold">Acces rapid</h2><p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Continuă activitatea în modulele folosite frecvent.</p></div></div>
      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {SHORTCUTS.map(({ to, icon: Icon, title, text }) => <Link key={to} to={to} className="group flex gap-3 rounded-xl border p-4 transition hover:-translate-y-0.5 hover:shadow-sm" data-testid={`shortcut-${to}`}>
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: "#edf4ff", color: "var(--blue)" }}><Icon size={19} /></span><span className="min-w-0 flex-1"><b className="block text-[13px]">{title}</b><span className="mt-1 block text-[11px] leading-relaxed" style={{ color: "var(--muted)" }}>{text}</span></span><ArrowUpRight size={14} className="mt-1 opacity-40 group-hover:opacity-100" />
        </Link>)}
      </div>
    </section>

    <section className="den-panel !p-5 sm:!p-6" data-testid="recent-dossiers">
      <div className="flex items-center justify-between gap-3 mb-4"><div><h2 className="text-[17px] font-bold">Dosare actualizate recent</h2><p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Revino rapid la documentația prosumatorului.</p></div><Link to="/prosumator" className="inline-flex items-center gap-1 text-xs font-bold" style={{ color: "var(--blue)" }}>Vezi dosarele <ArrowUpRight size={14} /></Link></div>
      {s.prosum_recent.length === 0 ? <div className="rounded-xl py-8 text-center" style={{ color: "var(--muted)", background: "var(--bg)" }}>
        <FolderOpen size={24} className="mx-auto mb-2 opacity-50" /><div className="text-sm font-semibold">{loaded ? "Nu există încă dosare recente" : "Se încarcă activitatea…"}</div><p className="text-xs mt-1">Creează primul dosar pentru a începe documentația.</p><Link to="/prosumator" className="mt-3 inline-flex"><Btn variant="secondary"><Plus size={14} /> Dosar prosumator nou</Btn></Link>
      </div> : <div className="divide-y" style={{ borderColor: "var(--line)" }}>{s.prosum_recent.map((r) => <Link key={r.id} to={`/prosumator?edit=${r.id}`} className="flex items-center gap-3 py-3.5">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl" style={{ background: "#edf7f0", color: "var(--green)" }}><FolderOpen size={17} /></span><span className="min-w-0 flex-1"><b className="block truncate text-[13px]">{r.number || "Fără număr"} · {r.client_name || "Beneficiar neprecizat"}</b><span className="text-[11px]" style={{ color: "var(--muted)" }}>{[r.locality, r.county, r.operator].filter(Boolean).join(" · ") || "Datele locului de consum se completează în dosar"} · {formatDate(r.updated_at || r.created_at)}</span></span><span className="rounded-full px-2.5 py-1 text-[10px] font-bold" style={{ background: "#edf7f0", color: "var(--green)" }}>{r.status || "CER"}</span><ChevronRight size={15} style={{ color: "var(--muted)" }} />
      </Link>)}</div>}
    </section>
  </div>;
}

