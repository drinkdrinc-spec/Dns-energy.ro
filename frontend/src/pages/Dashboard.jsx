import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { AtrDeadlines } from "@/components/AtrDeadlines";
import {
  Users, FolderOpen, GitBranch, AlertTriangle, SquareStack, Zap, ExternalLink,
  ShieldAlert, FileText, SunMedium, Cpu, Archive, FileCheck2, Receipt,
  ArrowRight, Upload, ClipboardCheck, PackageCheck, Search, List as ListIcon, LayoutGrid,
} from "lucide-react";

const FLOW = [
  {
    number: "01",
    title: "Client și loc de consum",
    desc: "Încarcă CI, factura și cartea funciară. Verifică datele citite și POD-ul înainte de salvare.",
    to: "/prosumator?start=documents",
    action: "Începe din documente",
    icon: Upload,
    tone: "amber",
  },
  {
    number: "02",
    title: "Echipamente și schemă",
    desc: "Selectează modelele din catalog. Confirmă configurarea, cablurile și protecțiile propuse.",
    to: "/prosumator",
    action: "Configurează instalația",
    icon: Cpu,
    tone: "blue",
  },
  {
    number: "03",
    title: "Documente și depunere",
    desc: "Verifică dosarul, generează PDF-urile, trimite documentele la semnat și urmărește etapele.",
    to: "/prosumator",
    action: "Deschide dosarul",
    icon: FileCheck2,
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
  const [inboxView, setInboxView] = useState("list");
  const [inboxQuery, setInboxQuery] = useState("");
  const [inboxModule, setInboxModule] = useState("all");
  const [inboxStatus, setInboxStatus] = useState("all");
  const [inboxOperator, setInboxOperator] = useState("all");
  const [workflowStatusBusy, setWorkflowStatusBusy] = useState("");
  const [workflowStatusError, setWorkflowStatusError] = useState("");
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

  const inboxItems = s.inbox || [];
  const moduleLabels = { prosumator: "Prosumator", atr: "Cerere ATR", power: "Spor de putere", diu: "DI-U", mono: "Schemă monofilară", anre_dossiers: "Dosar ANRE" };
  const inboxStatuses = [...new Set(inboxItems.map((item) => item.workflow_status || item.status || "În lucru"))];
  const inboxOperators = [...new Set(inboxItems.map((item) => item.operator || item.distributor).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "ro-RO"));
  const normalizedInboxQuery = inboxQuery.trim().toLocaleLowerCase("ro-RO");
  const visibleInboxItems = inboxItems.filter((item) => {
    const searchText = [item.client_name, item.number, item.label, item.pod, item.operator, item.distributor]
      .filter(Boolean).join(" ").toLocaleLowerCase("ro-RO");
    return (!normalizedInboxQuery || searchText.includes(normalizedInboxQuery))
      && (inboxModule === "all" || item.module === inboxModule)
      && (inboxStatus === "all" || (item.workflow_status || item.status || "În lucru") === inboxStatus)
      && (inboxOperator === "all" || (item.operator || item.distributor) === inboxOperator);
  });
  const renderInboxItem = (item) => {
    const paths = { prosumator: "/prosumator", atr: "/cerere-atr", power: "/spor-putere", diu: "/diu", mono: "/mono", anre_dossiers: "/dosare-anre" };
    const path = paths[item.module] || "/prosumator";
    const openParam = item.module === "anre_dossiers" ? "open" : "edit";
    const itemKey = item.module + "-" + item.id;
    const currentStatus = item.workflow_status || item.status || "În lucru";
    const dueDate = item.next_action_due ? new Date(`${item.next_action_due}T00:00:00`) : null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const hasValidDueDate = dueDate && !Number.isNaN(dueDate.getTime());
    const overdue = hasValidDueDate && dueDate < today;
    const stages = ["În lucru", "Documente de completat", "În verificare", "Pregătit pentru depunere", "Depus la operator", "În așteptare la operator", "Avizat", "Respins", "Finalizat"];
    return (
      <article key={itemKey}
        data-testid={"inbox-item-" + item.module + "-" + item.id}
        className={`flex items-center justify-between gap-3 rounded-xl border p-3 transition hover:shadow-sm ${inboxView === "kanban" ? "mb-2" : ""}`}
        style={{ borderColor: "var(--line)", background: "var(--surface, white)" }}>
        <Link to={path + "?" + openParam + "=" + encodeURIComponent(item.id)} className="min-w-0 flex-1">
          <b className="block text-sm truncate">{item.client_name || item.number || item.label}</b>
          <span className="block text-xs truncate" style={{ color: "var(--muted)" }}>{item.label}{item.number ? " · " + item.number : ""}{item.pod ? " · POD " + item.pod : ""}{item.operator ? " · " + item.operator : ""}</span>
          {item.next_action && <span className="mt-1 block truncate text-xs font-semibold" style={{ color: overdue ? "#b43b2f" : "var(--blue)" }} data-testid={`inbox-action-${itemKey}`}>Următorul pas: {item.next_action}{hasValidDueDate ? ` · ${dueDate.toLocaleDateString("ro-RO")}` : ""}{overdue ? " · depășit" : ""}</span>}
          <span className="block text-[10px] mt-1" style={{ color: "var(--muted)" }}>{item.updated_at ? new Date(item.updated_at).toLocaleDateString("ro-RO") : "—"}</span>
        </Link>
        {item.module === "anre_dossiers" ? <span className="shrink-0 rounded-full px-2 py-1 text-[11px] font-bold" style={{ background: "#eef4ff", color: "var(--blue)" }}>{currentStatus}</span> : <select
          className="den-input shrink-0 !w-auto max-w-[48%] !py-1 !px-2 !text-[11px] font-bold"
          aria-label={`Stadiul dosarului ${item.client_name || item.number || item.label}`}
          data-testid={"inbox-status-" + itemKey}
          value={currentStatus}
          disabled={workflowStatusBusy === itemKey}
          onChange={async (event) => {
            const nextStatus = event.target.value;
            setWorkflowStatusBusy(itemKey);
            setWorkflowStatusError("");
            try {
              await api.patch(`/data/${encodeURIComponent(item.module)}/${encodeURIComponent(item.id)}/status`, { status: nextStatus });
              const refreshed = await api.get("/stats/dashboard");
              setS(refreshed.data);
            } catch (error) {
              setWorkflowStatusError(error.response?.data?.detail || "Nu am putut salva stadiul dosarului.");
            } finally {
              setWorkflowStatusBusy("");
            }
          }}>
          {!stages.includes(currentStatus) && <option value={currentStatus}>{currentStatus}</option>}
          {stages.map((status) => <option key={status} value={status}>{status}</option>)}
        </select>}
      </article>
    );
  };

  return (
    <div className="dns-dashboard">
      <PageHeader
        eyebrow="DNS ENERGY · SPAȚIU DE LUCRU"
        title="Panou principal"
        sub="Un singur flux pentru dosarul clientului, de la documentele inițiale până la pregătirea depunerii."
        action={<Link to="/prosumator"><Btn data-testid="new-diu-btn"><SunMedium size={15} /> Dosar nou</Btn></Link>}
      />

      <details className="den-panel mb-4 group" data-testid="dashboard-quick-guide">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
          <span className="min-w-0">
            <span className="block text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)" }}>REPERE RAPIDE</span>
            <span className="mt-1 block text-sm font-bold">Găsește imediat următorul pas</span>
          </span>
          <span className="shrink-0 rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }}>Deschide ghidul</span>
        </summary>
        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Link to="/prosumator?start=documents" className="rounded-xl border p-3 transition hover:shadow-sm" style={{ borderColor: "var(--line)" }}>
            <b className="block text-sm">Începe cu actele clientului</b>
            <span className="mt-1 block text-xs leading-relaxed" style={{ color: "var(--muted)" }}>Încarcă documentele și verifică datele extrase înainte să le folosești în dosar.</span>
            <span className="mt-2 inline-flex items-center gap-1 text-xs font-bold" style={{ color: "var(--blue)" }}>Deschide fluxul <ArrowRight size={13} /></span>
          </Link>
          <Link to="/catalog-echipamente" className="rounded-xl border p-3 transition hover:shadow-sm" style={{ borderColor: "var(--line)" }}>
            <b className="block text-sm">Alege echipamentele din catalog</b>
            <span className="mt-1 block text-xs leading-relaxed" style={{ color: "var(--muted)" }}>Caută modele și verifică fișele tehnice și documentele de conformitate disponibile.</span>
            <span className="mt-2 inline-flex items-center gap-1 text-xs font-bold" style={{ color: "var(--blue)" }}>Deschide catalogul <ArrowRight size={13} /></span>
          </Link>
          <Link to="/mono" className="rounded-xl border p-3 transition hover:shadow-sm" style={{ borderColor: "var(--line)" }}>
            <b className="block text-sm">Pregătește schema și documentele</b>
            <span className="mt-1 block text-xs leading-relaxed" style={{ color: "var(--muted)" }}>Revizuiește schema monofilară și descarcă separat documentele tehnice disponibile.</span>
            <span className="mt-2 inline-flex items-center gap-1 text-xs font-bold" style={{ color: "var(--blue)" }}>Deschide schemele <ArrowRight size={13} /></span>
          </Link>
        </div>
      </details>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <Stat label="Clienți înregistrați" value={s.clients} foot="În baza de date" icon={Users} />
        <Stat label="Dosare active" value={s.total_dossiers ?? (s.diu + s.mono)} foot="Prosumator, ATR, spor, DI-U, scheme și ANRE" icon={FolderOpen} />
        <Stat label="Scheme monofilare" value={s.mono} foot="Înregistrări" icon={GitBranch} />
        <Stat label="Necesită atenție" value={s.pending} foot="Dosare în lucru sau de verificat" color="var(--amber)" icon={AlertTriangle} />
      </div>

      <section className="den-panel mb-6" aria-labelledby="dashboard-workload-title" data-testid="dashboard-workload">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--blue)" }}>VIZIBILITATE OPERAȚIONALĂ</div>
            <h2 id="dashboard-workload-title" className="text-lg font-bold">Dosare pe stadiu și operator</h2>
            <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>Numără toate dosarele din cont; în lista de mai jos apar cele actualizate cel mai recent.</p>
          </div>
          <span className="shrink-0 text-xs font-semibold" style={{ color: "var(--muted)" }}>{s.total_dossiers ?? 0} total</span>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide mb-3" style={{ color: "var(--muted)" }}>Stadiu dosar</h3>
            {Object.entries(s.stage_counts || {}).length ? <div className="space-y-3">
              {Object.entries(s.stage_counts || {}).map(([label, count]) => {
                const max = Math.max(...Object.values(s.stage_counts || {}).map(Number), 1);
                return <div key={label}>
                  <div className="flex justify-between gap-3 text-xs mb-1"><span className="truncate">{label}</span><b>{count}</b></div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--bg)" }}><div className="h-full rounded-full" style={{ width: `${Math.max(4, Number(count) / max * 100)}%`, background: "var(--blue)" }} /></div>
                </div>;
              })}
            </div> : <p className="text-sm" style={{ color: "var(--muted)" }}>Nu există încă dosare în lucru.</p>}
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide mb-3" style={{ color: "var(--muted)" }}>Operator de distribuție</h3>
            {Object.entries(s.operator_counts || {}).length ? <div className="divide-y" style={{ borderColor: "var(--line)" }}>
              {Object.entries(s.operator_counts || {}).map(([label, count]) => <div key={label} className="flex items-center justify-between gap-3 py-2 text-sm"><span className="truncate">{label}</span><b className="shrink-0">{count}</b></div>)}
            </div> : <p className="text-sm" style={{ color: "var(--muted)" }}>Operatorii apar aici după adăugarea dosarelor.</p>}
          </div>
        </div>
      </section>

      <AtrDeadlines />

      <section className="den-panel mb-6" aria-labelledby="dashboard-inbox-title" data-testid="dashboard-inbox">
        {workflowStatusError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{workflowStatusError}</p>}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--blue)" }}>ACTIVITATE RECENTĂ</div>
            <h2 id="dashboard-inbox-title" className="text-lg sm:text-xl font-bold">Dosare de urmărit</h2>
            <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>Acțiunile și termenele introduse în dosare apar primele; celelalte sunt ordonate după ultima actualizare.</p>
          </div>
          <div className="flex items-center gap-1 shrink-0 rounded-lg border p-1" style={{ borderColor: "var(--line)" }} aria-label="Mod vizualizare dosare">
            <button type="button" onClick={() => setInboxView("list")} aria-pressed={inboxView === "list"} aria-label="Vizualizare listă" title="Listă" className="grid h-8 w-8 place-items-center rounded-md" style={{ background: inboxView === "list" ? "#edf4ff" : "transparent", color: "var(--blue)" }}><ListIcon size={17} /></button>
            <button type="button" onClick={() => setInboxView("kanban")} aria-pressed={inboxView === "kanban"} aria-label="Vizualizare Kanban" title="Kanban" className="grid h-8 w-8 place-items-center rounded-md" style={{ background: inboxView === "kanban" ? "#edf4ff" : "transparent", color: "var(--blue)" }}><LayoutGrid size={17} /></button>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2 mb-3" data-testid="dashboard-inbox-filters">
          <input className="den-input w-full" value={inboxQuery} onChange={(event) => setInboxQuery(event.target.value)}
            placeholder="Caută client, număr dosar, POD sau operator…" aria-label="Caută dosare după client, număr, POD sau operator" />
          <select className="den-input w-full" value={inboxModule} onChange={(event) => setInboxModule(event.target.value)} aria-label="Filtrează după tipul dosarului">
            <option value="all">Toate tipurile de dosar</option>
            {Object.entries(moduleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <select className="den-input w-full" value={inboxStatus} onChange={(event) => setInboxStatus(event.target.value)} aria-label="Filtrează după starea dosarului">
            <option value="all">Toate stările</option>
            {inboxStatuses.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
          <select className="den-input w-full" value={inboxOperator} onChange={(event) => setInboxOperator(event.target.value)} aria-label="Filtrează după operatorul de distribuție">
            <option value="all">Toți operatorii</option>
            {inboxOperators.map((operator) => <option key={operator} value={operator}>{operator}</option>)}
          </select>
        </div>
        {visibleInboxItems.length === 0 ? (
          <div className="text-sm py-5 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>
            {inboxItems.length === 0 ? "Nu există încă dosare în lucru. Începe prin încărcarea documentelor clientului." : "Nu am găsit dosare care să corespundă filtrelor."}
          </div>
        ) : (
          inboxView === "list" ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">{visibleInboxItems.map(renderInboxItem)}</div>
          ) : (
            <div className="flex gap-3 overflow-x-auto pb-2" data-testid="dashboard-inbox-kanban">
              {inboxStatuses.filter((status) => inboxStatus === "all" || status === inboxStatus).map((status) => (
                <div key={status} className="min-w-[260px] flex-1 rounded-xl border p-3" style={{ borderColor: "var(--line)", background: "var(--bg)" }}>
                  <h3 className="text-xs font-extrabold uppercase tracking-wide mb-3">{status}<span className="ml-2 font-normal" style={{ color: "var(--muted)" }}>{visibleInboxItems.filter((item) => (item.workflow_status || item.status || "În lucru") === status).length}</span></h3>
                  {visibleInboxItems.filter((item) => (item.workflow_status || item.status || "În lucru") === status).map(renderInboxItem)}
                </div>
              ))}
            </div>
          )
        )}
      </section>

      <section className="den-panel mb-6" aria-labelledby="client-fast-search-title" data-testid="dashboard-client-search">
        <div className="flex items-center gap-2 mb-3">
          <Search size={17} style={{ color: "var(--blue)" }} />
          <h2 id="client-fast-search-title" className="text-base font-bold">Acces rapid la baza de clienți</h2>
        </div>
        <input
          className="den-input w-full"
          value={clientQuery}
          onChange={(event) => setClientQuery(event.target.value)}
          placeholder="Caută nume, CI/CUI, POD, telefon, e-mail sau adresă…"
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
            <h2 id="main-flow-title" className="text-lg sm:text-xl font-bold">Dosarul de prosumator în trei pași</h2>
            <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>Datele clientului se reutilizează în echipamente, schemă și documentele de depunere.</p>
          </div>
          <PackageCheck className="hidden sm:block shrink-0" size={22} style={{ color: "var(--blue)" }} />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
          <h2 className="text-lg font-bold flex items-center gap-2"><SquareStack size={18} style={{ color: "var(--blue)" }} /> Alte module DNS Energy</h2>
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
          <h2 className="text-lg font-bold flex items-center gap-2"><Zap size={18} style={{ color: "var(--blue)" }} /> Dosare DI-U recente</h2>
          <Link to="/dosare-arhivate"><Btn variant="secondary">Arhivă</Btn></Link>
        </div>
        {s.recent.length === 0 ? (
          <div className="text-sm py-6 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>
            Nu ai dosare DI-U recente afișate. Începe cu încărcarea documentelor clientului din pasul 01.
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: "var(--line)" }}>
            {s.recent.map((r) => (
              <Link key={r.id} to={`/diu?edit=${encodeURIComponent(r.id)}`} aria-label={`Deschide dosarul DI-U ${r.number || ""} pentru ${r.client_name || "client"}`} data-testid={`recent-dossier-${r.id}`}
                className="flex items-center justify-between gap-3 py-3 rounded-lg px-2 -mx-2 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <div className="min-w-0">
                  <div className="font-semibold text-sm break-words">{r.number || "Fără număr"} · {r.client_name || "—"}</div>
                  <div className="text-[12px]" style={{ color: "var(--muted)" }}>{r.type} · {r.power ? `${r.power} kW` : "—"}</div>
                </div>
                <span className="shrink-0 text-[11px] font-bold px-3 py-1 rounded-full" style={{ background: "#fff1d6", color: "#a65b00" }}>{r.status || "În lucru"}</span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}


