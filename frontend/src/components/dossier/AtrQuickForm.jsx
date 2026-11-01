import { useEffect, useState } from "react";

const BASIC = new Set(["client_name", "pod", "operator", "kind", "request_type", "deer_case", "applicant_type", "submission_mode", "address", "supply", "p_abs_kw"]);
const label = (f) => (f.label || "").replace(/\s*\*$/, "");

function panelCapacityKwp(pros) {
  const inverters = pros?.cef?.inverters || [];
  const derived = inverters.reduce((total, inv) => {
    const watts = Number(inv.panel_w) || 0;
    const count = (inv.strings || []).reduce((sum, string) => sum + (Number(string.panels) || 0), 0);
    return total + watts * count * Math.max(1, Number(inv.count) || 1) / 1000;
  }, 0);
  return derived || (Number(pros?.panel_count) > 0 && Number(pros?.panel_w) > 0 ? Number(pros.panel_count) * Number(pros.panel_w) / 1000 : Number(pros?._kwp || pros?.panel_kwp) || 0);
}

function equipmentSummary(pros) {
  const cef = pros?.cef || {};
  const inverters = cef.inverters || [];
  const panelCounts = new Map();
  for (const inverter of inverters) {
    const model = String(inverter.panel_model || "").trim();
    if (!model) continue;
    const inverterCount = Math.max(1, Number(inverter.count) || 1);
    const stringPanelCount = (inverter.strings || []).reduce((sum, string) => sum + (Number(string.panels) || 0), 0);
    if (stringPanelCount > 0) panelCounts.set(model, (panelCounts.get(model) || 0) + stringPanelCount * inverterCount);
  }
  const batteries = [
    ...inverters.filter((x) => x.battery_mode === "own" && x.battery?.model).map((x) => ({ ...x.battery, modules: (Number(x.battery.modules) || 1) * (Number(x.count) || 1) })),
    ...(cef.shared_batteries || []),
  ];
  const strings = inverters.flatMap((x) => x.strings || []);
  const declaredPanelCount = Math.max(0, Number(pros?.panel_count) || 0);
  if (panelCounts.size === 1 && ![...panelCounts.values()][0] && declaredPanelCount) {
    const model = panelCounts.keys().next().value;
    panelCounts.set(model, declaredPanelCount);
  }
  return {
    inverters: inverters.length ? inverters.map((x) => [x.brand_model, x.count > 1 ? `× ${x.count}` : "", x.p_nom_kw ? `${x.p_nom_kw} kW` : ""].filter(Boolean).join(" · ")).filter(Boolean) : [pros?.inverter, pros?.inverter_kw ? `${pros.inverter_kw} kW` : ""].filter(Boolean),
    panels: [...panelCounts.entries()].map(([model, count]) => `${model}${count ? ` · ${count} buc.` : ""}`).concat(!panelCounts.size && pros?.panels ? [`${pros.panels}${declaredPanelCount ? ` · ${declaredPanelCount} buc.` : ""}`] : []),
    batteries: batteries.map((x) => [x.model, x.modules ? `× ${x.modules}` : "", x.kwh ? `${Number(x.kwh) * (Number(x.modules) || 1)} kWh` : "", x.ah ? `${x.ah} Ah` : "", x.voltage ? `${x.voltage} V` : "", x.coupling ? `cuplare ${x.coupling}` : ""].filter(Boolean).join(" · ")).concat(!batteries.length && pros?.battery ? [`${pros.battery}${pros.battery_kwh ? ` · ${pros.battery_kwh} kWh` : ""}`] : []),
    power: pros?.power || pros?.p_evac_kw || pros?.inverter_kw || "",
    panelPower: panelCapacityKwp(pros),
    strings: strings.map((x, i) => `${i + 1}(${x.panels || "?"})`).join(", "),
  };
}

export function AtrQuickForm({ cfg, form, setVal, refOptions }) {
  const fields = cfg.fields || [];
  const isDeer = /deer|distribuție energie electrică|distributie energie electrica/i.test(String(form.operator || ""));
  const basic = fields.filter((f) => BASIC.has(f.name) && (f.name !== "deer_case" || isDeer));
  const advanced = fields.filter((f) => !BASIC.has(f.name));
  const clients = refOptions.clients || [];
  const pros = refOptions.prosumator || [];
  const norm = (v) => String(v || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO");
  const linkedPros = pros.filter((p) => {
    if (form.pros_id) return p.id === form.pros_id && (!form.client_id || !p.client_id || p.client_id === form.client_id);
    if (form.client_id && p.client_id) return p.client_id === form.client_id;
    return Boolean(form.client_name && norm(p.client_name) === norm(form.client_name));
  });
  const linkedProsKey = linkedPros.map((item) => item.id).join("|");
  const [selectedProsId, setSelectedProsId] = useState(form.pros_id || (linkedPros.length === 1 ? linkedPros[0].id : ""));
  useEffect(() => {
    if (form.pros_id && linkedPros.some((item) => item.id === form.pros_id)) setSelectedProsId(form.pros_id);
    else if (linkedPros.length === 1) setSelectedProsId(linkedPros[0].id);
    else if (!linkedPros.some((item) => item.id === selectedProsId)) setSelectedProsId("");
  }, [form.pros_id, form.client_id, linkedProsKey]);
  const selectedPros = linkedPros.find((p) => p.id === selectedProsId) || (linkedPros.length === 1 ? linkedPros[0] : null);
  const equipment = equipmentSummary(selectedPros);
  const choosePros = (id) => {
    const record = linkedPros.find((p) => p.id === id);
    setSelectedProsId(id);
    setVal("pros_id", id);
    if (!record) return;
    const invs = record.cef?.inverters || [];
    const panelKwp = panelCapacityKwp(record);
    setVal("kind", "Loc de consum și de producere (prosumator)");
    setVal("supply", record.supply || record.cef?.grid?.supply || form.supply || "");
    setVal("pv_kw", panelKwp ? Number(panelKwp.toFixed(3)) : record._kwp || "");
    setVal("p_evac_kw", record.power || record.p_evac_kw || record.inverter_kw || "");
    setVal("p_abs_kw", record.bransament_kw || form.p_abs_kw || "");
    setVal("current_supply_desc", [record.request_type, ...equipmentSummary(record).inverters.map((value) => `Invertor: ${value}`), ...equipmentSummary(record).panels.map((value) => `Panouri: ${value}`), ...equipmentSummary(record).batteries.map((value) => `Baterie: ${value}`)].filter(Boolean).join("; "));
  };
  useEffect(() => {
    const id = form.pros_id || (linkedPros.length === 1 ? linkedPros[0].id : "");
    const record = linkedPros.find((item) => item.id === id);
    if (!record) return;
    setSelectedProsId(id);
    if (form.pros_id !== id) {
      choosePros(id);
      return;
    }
    const equipment = equipmentSummary(record);
    if (!form.kind) setVal("kind", "Loc de consum și de producere (prosumator)");
    if (!form.supply && (record.supply || record.cef?.grid?.supply)) setVal("supply", record.supply || record.cef.grid.supply);
    if (!form.pv_kw && equipment.panelPower) setVal("pv_kw", Number(equipment.panelPower.toFixed(3)));
    if (!form.p_evac_kw && equipment.power) setVal("p_evac_kw", equipment.power);
    if (!form.current_supply_desc) {
      setVal("current_supply_desc", [record.request_type, ...equipment.inverters.map((value) => `Invertor: ${value}`), ...equipment.panels.map((value) => `Panouri: ${value}`), ...equipment.batteries.map((value) => `Baterie: ${value}`)].filter(Boolean).join("; "));
    }
  }, [linkedProsKey, form.pros_id, form.client_id]);
  const renderField = (f) => {
    const common = {
      className: "den-input w-full",
      value: form[f.name] ?? "",
      onChange: (e) => setVal(f.name, e.target.value),
      "data-testid": `field-${f.name}`,
    };
    return <label key={f.name} className={`den-field ${f.full ? "sm:col-span-2" : ""}`}>
      <span>{label(f)}{f.required ? " *" : ""}</span>
      {f.type === "textarea"
        ? <textarea {...common} rows={2} />
        : f.type === "select"
          ? <select {...common}><option value="">Alege...</option>{form[f.name] && !f.options.includes(form[f.name]) && <option value={form[f.name]}>{form[f.name]}</option>}{(f.options || []).map((o) => <option key={o} value={o}>{o}</option>)}</select>
          : f.type === "ref"
            ? <select {...common}><option value="">Alege client...</option>{form[f.name] && !clients.some((c) => c.label === form[f.name]) && <option value={form[f.name]}>{form[f.name]} · extras din document</option>}{clients.map((c) => <option key={c.id} value={c.label}>{c.label}</option>)}</select>
            : <input {...common} type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} step={f.type === "number" ? "any" : undefined} />}
    </label>;
  };

  return <div className="space-y-4" data-testid="atr-quick-form">
    <div>
      <h3 className="text-sm font-bold mb-1">Datele de bază ale cererii</h3>
      <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Alege clientul; datele cunoscute din fișa clientului se preiau automat. Completează POD-ul de pe factură și confirmă tipul solicitării.</p>
      <div className="grid sm:grid-cols-2 gap-3">{basic.map(renderField)}</div>
    </div>
    {form.client_id && <section className="rounded-xl border p-4 sm:p-5" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="atr-linked-equipment">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="text-sm font-bold">Echipamente transferate în cererea ATR</h3>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Date preluate din dosarul prosumator ales. Fișele tehnice și declarațiile existente în catalog intră automat în ZIP-ul ATR.</p></div>
        {linkedPros.length > 1 && <label className="den-field min-w-[240px]"><span>Alege dosarul prosumator</span>
          <select className="den-input" value={selectedProsId} onChange={(e) => choosePros(e.target.value)}>
            <option value="">Alege dosarul...</option>{linkedPros.map((p) => <option key={p.id} value={p.id}>{p.number || p.client_name || "Dosar"} · {p.operator || "operator neconfirmat"}</option>)}
          </select></label>}
      </div>
      {!selectedPros ? <p className="mt-3 text-sm text-amber-800">{linkedPros.length ? "Selectează dosarul prosumator pentru a transfera echipamentele și puterile în cererea ATR." : "Clientul nu are încă un dosar prosumator asociat. Cererea ATR poate fi salvată, dar echipamentele și puterile nu vor fi completate automat."}</p>
        : <div className="mt-4 grid sm:grid-cols-2 gap-3 text-sm">
          {[["Invertor(e)", equipment.inverters], ["Panouri", equipment.panels], ["Putere panouri c.c.", equipment.panelPower ? [`${equipment.panelPower.toFixed(3)} kWp`] : []], ["Baterie / BESS", equipment.batteries], ["Putere evacuată c.a.", equipment.power ? [`${equipment.power} kW`] : []], ["Stringuri", equipment.strings ? [equipment.strings] : []], ["Branșament", [selectedPros.supply || selectedPros.cef?.grid?.supply].filter(Boolean)]].map(([name, values]) =>
            <div key={name} className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }}>
              <div className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>{name}</div>
              <div className="mt-1 font-semibold">{values.length ? values.join(", ") : "Nu este completat în dosarul prosumator"}</div>
            </div>)}
          <p className="sm:col-span-2 text-xs" style={{ color: "var(--muted)" }}>Confirmați modelul și puterile cu fișele tehnice. Dacă documentul operatorului nu are câmp pentru baterie, aceasta rămâne listată în anexa tehnică a pachetului.</p>
        </div>}
    </section>}
    <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-extra-fields">
      <summary className="cursor-pointer text-sm font-semibold">Alte date pentru formularul ATR</summary>
      <div className="grid sm:grid-cols-2 gap-3 mt-3">{advanced.map(renderField)}</div>
    </details>
  </div>;
}
