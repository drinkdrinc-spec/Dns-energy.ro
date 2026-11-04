import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { MapPin, ExternalLink, FolderOpen, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Layout";

function locationOf(item) {
  return [item.locality, item.county].filter((part) => String(part || "").trim()).join(", ");
}

export default function WorkMap() {
  const [rows, setRows] = useState([]);
  const [missingLocationCount, setMissingLocationCount] = useState(0);
  const [stage, setStage] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("/work-map", { params: { include_archived: includeArchived } });
      const allRows = (Array.isArray(response.data) ? response.data : []).map((item) => ({
        ...item,
        moduleLabel: item.module_label,
        href: ({ prosumator: "/prosumator", atr: "/cerere-atr", power: "/spor-putere", diu: "/diu" })[item.module],
      }));
      setMissingLocationCount(allRows.filter((row) => !row.locality && !row.county).length);
      setRows(allRows.filter((row) => row.locality || row.county));
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || "Nu am putut încărca lucrările. Încearcă din nou.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [includeArchived]);

  const stages = useMemo(() => [...new Set(rows.map((row) => row.stage).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ro-RO")), [rows]);
  const visible = useMemo(() => rows.filter((row) => !stage || row.stage === stage), [rows, stage]);
  const groups = useMemo(() => {
    const grouped = new Map();
    visible.forEach((row) => {
      const place = locationOf(row) || "Locație necompletată";
      const key = place.toLocaleLowerCase("ro-RO");
      const group = grouped.get(key) || { place, items: [] };
      group.items.push(row);
      grouped.set(key, group);
    });
    return [...grouped.values()].sort((a, b) => b.items.length - a.items.length || a.place.localeCompare(b.place, "ro-RO"));
  }, [visible]);

  return <>
    <PageHeader eyebrow="Lucrări" title="Harta lucrărilor" sub="Lucrări grupate după localitate și județ, cu filtrare pe stadiu. Harta externă primește doar localitatea și județul, fără adresă, POD sau datele clientului." action={<button type="button" onClick={load} disabled={loading} className="den-btn-secondary inline-flex min-h-10 items-center gap-2 px-3 text-sm"><RefreshCw size={15} className={loading ? "animate-spin" : ""} /> Reîncarcă</button>} />

    <section className="mb-5 grid gap-3 sm:grid-cols-3" aria-label="Rezumat hartă">
      <div className="den-panel"><div className="text-xs" style={{ color: "var(--muted)" }}>Lucrări cu localitate</div><div className="mt-1 text-3xl font-extrabold">{loading ? "…" : visible.length}</div></div>
      <div className="den-panel"><div className="text-xs" style={{ color: "var(--muted)" }}>Localități</div><div className="mt-1 text-3xl font-extrabold">{loading ? "…" : groups.length}</div></div>
      <div className="den-panel"><div className="text-xs" style={{ color: "var(--muted)" }}>Fără locație completată</div><div className="mt-1 text-3xl font-extrabold">{loading ? "…" : missingLocationCount}</div><div className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Completează județul și localitatea în dosar pentru a-l include.</div></div>
    </section>

    <div className="den-panel mb-5 flex flex-wrap items-center gap-3">
      <label className="den-field min-w-[220px] flex-1"><span>Filtrează după etapă</span><select className="den-input" value={stage} onChange={(event) => setStage(event.target.value)}><option value="">Toate etapele</option>{stages.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label className="inline-flex min-h-10 items-center gap-2 pt-4 text-sm"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /> Include dosarele arhivate</label>
    </div>

    {error && <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    {loading ? <div className="den-panel text-sm" role="status">Se încarcă lucrările…</div> : groups.length === 0 ? <div className="den-panel text-sm" data-testid="work-map-empty">Nu există lucrări cu județ și localitate completate pentru filtrul ales.</div> :
      <div className="grid gap-3 lg:grid-cols-2" data-testid="work-map-groups">
        {groups.map((group) => {
          const mapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(group.place)}`;
          return <section key={group.place} className="den-panel" data-testid="work-map-place">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 text-base font-bold"><MapPin size={17} style={{ color: "var(--blue)" }} />{group.place}</h2>
              <a href={mapUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-9 items-center gap-1 rounded-lg border px-2.5 text-xs font-semibold" style={{ borderColor: "var(--line)" }} aria-label={`Deschide harta pentru ${group.place}`}>Deschide harta <ExternalLink size={13} /></a>
            </div>
            <div className="mb-3 flex flex-wrap gap-1.5">{[...new Set(group.items.map((item) => item.stage))].map((item) => <span key={item} className="rounded-full px-2.5 py-1 text-[11px] font-semibold" style={{ background: "#edf3ff", color: "#315b9a" }}>{item} · {group.items.filter((row) => row.stage === item).length}</span>)}</div>
            <ul className="divide-y" style={{ borderColor: "var(--line)" }}>{group.items.map((item) => <li key={`${item.module}-${item.id}`} className="flex flex-wrap items-center justify-between gap-2 py-2.5 first:pt-0 last:pb-0">
              <div className="min-w-0"><div className="truncate text-sm font-semibold">{item.number || item.moduleLabel}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{item.moduleLabel}{item.operator ? ` · ${item.operator}` : ""}{item.archived ? " · Arhivat" : ""}</div></div>
              <Link to={`${item.href}?edit=${encodeURIComponent(item.id)}`} className="inline-flex min-h-9 items-center gap-1 rounded-lg border px-2.5 text-xs font-semibold" style={{ borderColor: "var(--line)" }}><FolderOpen size={13} /> Deschide dosarul</Link>
            </li>)}</ul>
          </section>;
        })}
      </div>}
  </>;
}

