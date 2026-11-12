import { useMemo, useState } from "react";
import { fileUrl } from "@/lib/api";

export function F({ label, value, onChange, type = "text", options, testid, className = "" }) {
  const common = { className: "den-input", value: value ?? "", "data-testid": testid, onChange: (e) => onChange(type === "number" && e.target.value !== "" ? Number(e.target.value) : e.target.value) };
  return (
    <div className={`den-field ${className}`}>
      <label>{label}</label>
      {options ? (
        <select {...common}><option value="">Alege...</option>{options.map((o) => Array.isArray(o) ? <option key={o[0]} value={o[0]}>{o[1]}</option> : <option key={o} value={o}>{o}</option>)}</select>
      ) : <input {...common} type={type} step={type === "number" ? "any" : undefined} />}
    </div>
  );
}

export function Check({ label, value, onChange, testid }) {
  return (
    <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
      <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} data-testid={testid} /> {label}
    </label>
  );
}

export function CatalogPick({ items, category, onPick, testid, label = "Alege din catalog", selectedId }) {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState("");
  const [system, setSystem] = useState("");
  const [docs, setDocs] = useState("all");
  const list = useMemo(() => items.filter((i) => i.category === category
    && (!query || `${i.brand_model} ${i.type || ""} ${i.phases || ""}`.toLowerCase().includes(query.toLowerCase()))
    && (!phase || i.phases === phase) && (!system || i.type === system)
    && (docs === "all" || (docs === "complete" ? !!i.datasheet && !!i.conformity : !i.datasheet || !i.conformity))), [items, category, query, phase, system, docs]);
  const selected = items.find((i) => i.id === selectedId && i.category === category);
  const meta = (i) => category === "Invertor" ? `${i.p_nom_kw ?? "—"} kW · ${i.phases || "faze neprecizate"} · ${i.type || "tip neprecizat"}` : category === "Panou" ? `${i.w ?? "—"} W · Voc ${i.voc ?? "—"} V` : category === "Baterie" ? `${i.kwh ?? "—"} kWh · ${i.voltage ?? "—"} V · ${i.tech || "tensiune neprecizată"}` : `${i.phases || "faze neprecizate"}`;
  return (
    <div className="den-field">
      <label>{label}</label>
      <input className="den-input mb-1" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Caută marcă sau model..." aria-label={`Caută ${category}`} data-testid={`${testid}-search`} />
      <div className="mb-1 grid grid-cols-2 gap-1">
        {(category === "Invertor" || category === "Smart meter") && <select className="den-input !py-1.5 !text-[10px]" value={phase} onChange={(e) => setPhase(e.target.value)} aria-label={`Faze ${category}`}><option value="">Mono + trifazat</option><option value="Monofazat">Monofazat</option><option value="Trifazat">Trifazat</option></select>}
        {category === "Invertor" && <select className="den-input !py-1.5 !text-[10px]" value={system} onChange={(e) => setSystem(e.target.value)} aria-label="Tip invertor"><option value="">Hibrid + on-grid</option><option value="Hibrid">Hibrid</option><option value="On-grid">On-grid</option></select>}
        <select className="den-input !py-1.5 !text-[10px]" value={docs} onChange={(e) => setDocs(e.target.value)} aria-label={`Documente ${category}`}><option value="all">Toate documentele</option><option value="complete">Documente complete</option><option value="missing">Documente lipsă</option></select>
      </div>
      <select className="den-input" value={selectedId || ""} data-testid={testid} onChange={(e) => { const it = list.find((x) => x.id === e.target.value) || items.find((x) => x.id === e.target.value); if (it) onPick(it); }}>
        <option value="">— {list.length} modele {category.toLowerCase()} —</option>
        {selected && !list.some((i) => i.id === selected.id) && <option value={selected.id}>{selected.brand_model} · selectat</option>}
        {list.map((i) => <option key={i.id} value={i.id}>{i.brand_model} · {meta(i)}{i.datasheet && i.conformity ? " · documente complete" : " · documente lipsă"}</option>)}
      </select>
      {selected && <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[10px]" style={{ color: "var(--muted)" }}>
        <span>{meta(selected)}</span>
        {selected.datasheet ? <a className="font-bold" style={{ color: "var(--blue)" }} href={fileUrl(selected.datasheet.storage_path)} target="_blank" rel="noreferrer">Fișă tehnică</a> : <span>Fișă tehnică lipsă</span>}
        {selected.conformity ? <a className="font-bold" style={{ color: "var(--blue)" }} href={fileUrl(selected.conformity.storage_path)} target="_blank" rel="noreferrer">Conformitate</a> : <span>Conformitate lipsă</span>}
      </div>}
    </div>
  );
}

export const INSTALL = [["A1", "A1 — în tub, perete izolat"], ["B1", "B1 — în tub pe perete"], ["B2", "B2 — multiconductor în tub"], ["C", "C — aparent pe perete"], ["D", "D — îngropat"], ["E", "E — pat de cabluri / aer liber"]];
export const SECTIONS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120];
export const uid = () => Math.random().toString(36).slice(2, 9);
