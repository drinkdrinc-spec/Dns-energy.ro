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

export function CatalogPick({ items, category, onPick, onManual, testid, label = "Alege din catalog", selectedId, selectedLabel }) {
  const [query, setQuery] = useState("");
  const list = useMemo(() => items.filter((i) => i.category === category
    && (!query || `${i.brand_model} ${i.type || ""} ${i.phases || ""}`.toLowerCase().includes(query.toLowerCase()))), [items, category, query]);
  const selected = items.find((i) => i.id === selectedId && i.category === category);
  const meta = (i) => category === "Invertor" ? `${i.p_nom_kw ?? "—"} kW · ${i.phases || "faze neprecizate"} · ${i.type || "tip neprecizat"}` : category === "Panou" ? `${i.w ?? "—"} W · Voc ${i.voc ?? "—"} V` : category === "Baterie" ? `${i.kwh ?? "—"} kWh · ${i.voltage ?? "—"} V · ${i.tech || "tensiune neprecizată"}` : `${i.phases || "faze neprecizate"}`;
  return (
    <div className="den-field">
      <label>{label}</label>
      <input className="den-input mb-1" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Caută marcă sau model..." aria-label={`Caută ${category}`} data-testid={`${testid}-search`} />
      {query.trim() && !list.some((item) => item.brand_model?.trim().toLocaleLowerCase() === query.trim().toLocaleLowerCase()) && <button type="button" onClick={() => { onManual ? onManual(query.trim()) : onPick({ id: "", category, brand_model: query.trim(), manual: true }); setQuery(""); }} className="mb-1 rounded-md px-2 py-1 text-left text-[11px] font-bold" style={{ color: "var(--blue)", background: "#edf4ff" }}>Folosește „{query.trim()}” ca model introdus manual</button>}
      <select className="den-input" value={selectedId || ""} data-testid={testid} onChange={(e) => { const it = list.find((x) => x.id === e.target.value) || items.find((x) => x.id === e.target.value); if (it) onPick(it); }}>
        <option value="">— {list.length} modele {category.toLowerCase()} —</option>
        {selected && !list.some((i) => i.id === selected.id) && <option value={selected.id}>{selected.brand_model} · selectat</option>}
        {list.map((i) => <option key={i.id} value={i.id}>{i.brand_model} · {meta(i)}{i.datasheet && i.conformity ? " · documente complete" : " · documente lipsă"}</option>)}
      </select>
      {!selectedId && selectedLabel && <p className="mt-1 text-[10px]" style={{ color: "#8a5a00" }}>Model introdus manual: {selectedLabel}. Verifică fișa oficială și completează datele tehnice.</p>}
      {selected && <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[10px]" style={{ color: "var(--muted)" }}>
        <span>{meta(selected)}</span>
        {selected.spec_source_url && <a className="font-bold" style={{ color: "var(--blue)" }} href={selected.spec_source_url} target="_blank" rel="noreferrer">Sursa specificațiilor</a>}
        {selected.datasheet ? <a className="font-bold" style={{ color: "var(--blue)" }} href={fileUrl(selected.datasheet.storage_path)} target="_blank" rel="noreferrer">Fișă tehnică</a> : <span>Fișă tehnică lipsă</span>}
        {selected.conformity ? <a className="font-bold" style={{ color: "var(--blue)" }} href={fileUrl(selected.conformity.storage_path)} target="_blank" rel="noreferrer">Conformitate</a> : <span>Conformitate lipsă</span>}
      </div>}
    </div>
  );
}

export const INSTALL = [["A1", "A1 — în tub, perete izolat"], ["B1", "B1 — în tub pe perete"], ["B2", "B2 — multiconductor în tub"], ["C", "C — aparent pe perete"], ["D", "D — îngropat"], ["E", "E — pat de cabluri / aer liber"]];
export const SECTIONS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120];
export const uid = () => Math.random().toString(36).slice(2, 9);
