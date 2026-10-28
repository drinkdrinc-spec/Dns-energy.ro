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

export function CatalogPick({ items, category, onPick, testid, label = "Alege din catalog" }) {
  const list = items.filter((i) => i.category === category);
  return (
    <div className="den-field">
      <label>{label}</label>
      <select className="den-input" value="" data-testid={testid} onChange={(e) => { const it = list.find((x) => x.id === e.target.value); if (it) onPick(it); }}>
        <option value="">— {list.length} modele {category.toLowerCase()} —</option>
        {list.map((i) => <option key={i.id} value={i.id}>{i.brand_model}</option>)}
      </select>
    </div>
  );
}

export const INSTALL = [["A1", "A1 — în tub, perete izolat"], ["B1", "B1 — în tub pe perete"], ["B2", "B2 — multiconductor în tub"], ["C", "C — aparent pe perete"], ["D", "D — îngropat"], ["E", "E — pat de cabluri / aer liber"]];
export const SECTIONS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120];
export const uid = () => Math.random().toString(36).slice(2, 9);
