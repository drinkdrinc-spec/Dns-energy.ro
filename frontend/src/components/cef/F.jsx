import { useState } from "react";
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

export function CatalogPick({ items, category, onPick, onQueryChange, testid, label = "Caută model în catalog" }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const list = items.filter((i) => i.category === category);
  const fold = (value) => String(value || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase("ro-RO");
  const hasValue = (value) => value !== undefined && value !== null && value !== "" && Number.isFinite(Number(value));
  const positive = (value) => hasValue(value) && Number(value) > 0;
  const missing = (item) => {
    if (category === "Invertor") return [
      [positive(item.p_nom_kw), "puterea nominală"],
      [!!item.phases, "numărul de faze"],
      [!!item.type, "tipul invertorului"],
    ].filter(([ok]) => !ok).map(([, name]) => name);
    if (category === "Panou") return [
      [positive(item.w), "puterea panoului"],
      [positive(item.voc), "Voc"],
      [positive(item.vmp), "Vmp"],
      [positive(item.isc), "Isc"],
      [hasValue(item.coef_voc), "coeficientul Voc"],
    ].filter(([ok]) => !ok).map(([, name]) => name);
    if (category === "Baterie") return [
      [positive(item.kwh) || positive(item.ah), "capacitatea (kWh sau Ah)"],
      [positive(item.voltage), "tensiunea"],
      [positive(item.i_max), "curentul maxim"],
      [!!item.coupling, "tipul de cuplare AC/DC"],
    ].filter(([ok]) => !ok).map(([, name]) => name);
    return [];
  };
  const filtered = list.filter((item) => fold(item.brand_model).includes(fold(query)));
  const pick = (item) => {
    if (missing(item).length) return;
    onPick(item);
    setQuery(item.brand_model);
    setOpen(false);
  };
  return (
    <div className="den-field relative">
      <label htmlFor={testid}>{label}</label>
      <input
        id={testid}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={`${testid}-options`}
        className="den-input"
        value={query}
        placeholder={`Caută în ${list.length} modele...`}
        autoComplete="off"
        data-testid={testid}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => { const value = event.target.value; setQuery(value); setOpen(true); onQueryChange?.(value); }}
        onKeyDown={(event) => { if (event.key === "Escape") setOpen(false); }}
      />
      {open && (
        <div id={`${testid}-options`} role="listbox" className="absolute left-0 right-0 top-full z-50 mt-1 max-h-56 overflow-y-auto rounded-lg border bg-white p-1 shadow-xl" style={{ borderColor: "var(--line)" }}>
          {filtered.slice(0, 60).map((item) => (
            <button
              key={item.id}
              type="button"
              role="option"
              aria-selected={false}
              aria-disabled={missing(item).length > 0}
              disabled={missing(item).length > 0}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => pick(item)}
              className={`block w-full rounded-md px-3 py-2 text-left text-xs ${missing(item).length ? "cursor-not-allowed opacity-60" : "hover:bg-[#eef4ff]"}`}
            >
              <span className="block font-semibold">{item.brand_model}</span>
              <span className="block" style={{ color: "var(--muted)" }}>
                {category === "Invertor" ? [item.p_nom_kw && `${item.p_nom_kw} kW`, item.phases, item.type].filter(Boolean).join(" · ")
                  : category === "Panou" ? [item.w && `${item.w} W`, item.voc && `Voc ${item.voc} V`].filter(Boolean).join(" · ")
                  : category === "Baterie" ? [item.kwh && `${item.kwh} kWh`, item.ah && `${item.ah} Ah`, item.voltage && `${item.voltage} V`].filter(Boolean).join(" · ")
                  : [item.phases].filter(Boolean).join(" · ")}
              </span>
              {missing(item).length > 0 && <span className="mt-1 block text-[11px] font-medium text-amber-700">Indisponibil pentru proiectare · lipsesc: {missing(item).join(", ")}</span>}
            </button>
          ))}
          {!filtered.length && <p className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>Modelul nu este în catalog. Îl poți scrie în câmpul de model de mai jos.</p>}
          {filtered.length > 60 && <p className="px-3 py-2 text-[11px]" style={{ color: "var(--muted)" }}>Afișez primele 60 de rezultate; rafinează căutarea.</p>}
        </div>
      )}
    </div>
  );
}

export const INSTALL = [["A1", "A1 — în tub, perete izolat"], ["B1", "B1 — în tub pe perete"], ["B2", "B2 — multiconductor în tub"], ["C", "C — aparent pe perete"], ["D", "D — îngropat"], ["E", "E — pat de cabluri / aer liber"]];
export const SECTIONS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120];
export const uid = () => Math.random().toString(36).slice(2, 9);
