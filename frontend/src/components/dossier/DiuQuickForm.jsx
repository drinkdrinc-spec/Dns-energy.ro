import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const CORE = new Set(["client_name", "type", "power", "address", "operator", "atr", "status"]);
const norm = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");

function Field({ f, form, setVal, refOptions }) {
  if (f.type === "section") return <h4 className="sm:col-span-2 mt-3 border-t pt-3 text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)", borderColor: "var(--line)" }}>{f.label}</h4>;
  const value = form[f.name] ?? "";
  const common = { className: "den-input", value, onChange: (e) => setVal(f.name, e.target.value), "data-testid": `field-${f.name}` };
  return <label className={`den-field ${f.full ? "sm:col-span-2" : ""}`} key={f.name}><span>{f.label}</span>
    {f.type === "textarea" ? <textarea {...common} rows={3} />
      : f.type === "select" ? <select {...common}><option value="">Alege...</option>
        {value && !(f.options || []).includes(value) && <option value={value}>{value} · de confirmat</option>}
        {(f.options || []).map((option) => <option key={option} value={option}>{option}</option>)}</select>
        : f.type === "ref" ? <select {...common}><option value="">Alege...</option>{(refOptions[f.ref] || []).map((option) => <option key={option.id} value={option.label}>{option.label}</option>)}</select>
          : <input {...common} type={f.type === "date" ? "date" : f.type === "number" ? "number" : "text"} step={f.type === "number" ? "any" : undefined} />}
  </label>;
}

export function DiuQuickForm({ cfg, form, setVal, refOptions }) {
  const [pros, setPros] = useState([]);
  useEffect(() => { api.get("/data/prosumator").then((r) => setPros(Array.isArray(r.data) ? r.data : [])).catch(() => {}); }, []);
  const showTests = new URLSearchParams(window.location.search).get("showTests") === "1";
  const clients = (refOptions.clients || []).filter((c) => showTests || !/\bTEST\b/i.test(String(c.label || "")));
  const selectedClient = clients.find((c) => c.label === form.client_name);
  const linked = pros.filter((p) => selectedClient
    ? p.client_id ? p.client_id === selectedClient.id : norm(p.client_name) === norm(selectedClient.label)
    : false).filter((p) => showTests || !/\bTEST\b/i.test([p.number, p.client_name].filter(Boolean).join(" ")));
  const chosenPros = linked.find((p) => p.id === form.pros_id) || null;
  const choosePros = (id) => {
    setVal("pros_id", id);
    const p = linked.find((item) => item.id === id);
    if (!p) return;
    const hasBattery = Boolean(p.battery || /hibrid/i.test(String(p.system_type || "")) || p.cef?.shared_batteries?.length
      || p.cef?.inverters?.some((x) => x.battery_mode === "own" ? Boolean(x.battery?.model) : x.battery_mode === "shared" && Boolean(x.shared_battery_id)));
    const values = {
      client_name: selectedClient?.label || p.client_name || "",
      client_id: selectedClient?.id || p.client_id || "",
      address: p.address || selectedClient?.address || "",
      operator: p.operator || selectedClient?.operator || "",
      power: p.inverter_kw || p.power || p.cef?.total_kw || "",
      atr: p.atr || "",
      type: hasBattery ? "Sistem fotovoltaic hibrid" : "Sistem fotovoltaic on-grid",
      supply: p.supply || "",
      status: form.status || "În lucru",
    };
    Object.entries(values).forEach(([key, value]) => { if (value !== "" && value !== undefined) setVal(key, value); });
  };
  const chooseClient = (label) => {
    const client = clients.find((c) => c.label === label);
    setVal("client_name", label);
    setVal("client_id", client?.id || "");
    setVal("pros_id", "");
    setVal("address", client?.address || "");
    setVal("operator", client?.operator || "");
    setVal("status", form.status || "În lucru");
    const matches = pros.filter((p) => client && (p.client_id ? p.client_id === client.id : norm(p.client_name) === norm(label)));
    if (matches.length === 1) {
      const p = matches[0];
      const hasBattery = Boolean(p.battery || /hibrid/i.test(String(p.system_type || "")) || p.cef?.shared_batteries?.length
        || p.cef?.inverters?.some((x) => x.battery_mode === "own" ? Boolean(x.battery?.model) : x.battery_mode === "shared" && Boolean(x.shared_battery_id)));
      setVal("pros_id", p.id);
      setVal("client_id", client.id);
      for (const [key, value] of Object.entries({
        address: p.address || client.address || "", operator: p.operator || client.operator || "",
        power: p.inverter_kw || p.power || p.cef?.total_kw || "", atr: p.atr || "",
        type: hasBattery ? "Sistem fotovoltaic hibrid" : "Sistem fotovoltaic on-grid",
        supply: p.supply || "", status: form.status || "În lucru",
      })) if (value !== "") setVal(key, value);
    }
  };
  const fieldByName = (name) => (cfg.fields || []).find((f) => f.name === name);
  const extras = (cfg.fields || []).filter((f) => f.type === "section" || !CORE.has(f.name));

  return <div className="space-y-4" data-testid="diu-quick-form">
    <section className="rounded-2xl border p-4 sm:p-5" style={{ borderColor: "var(--line)", background: "linear-gradient(135deg, #f2f7ff 0%, #fff 76%)" }}>
      <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)" }}>Predare lucrare · DI-U</p>
      <h3 className="mt-1 text-lg font-bold">Pornește din client și instalație</h3>
      <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>Selectează clientul. Dacă are dosar de prosumator asociat, datele cunoscute se completează automat.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="den-field sm:col-span-2"><span>Beneficiar / client *</span><select className="den-input" value={form.client_name || ""} onChange={(e) => chooseClient(e.target.value)} data-testid="diu-client-select">
          <option value="">Selectează clientul...</option>{clients.map((c) => <option key={c.id} value={c.label}>{c.label}</option>)}
        </select></label>
        {selectedClient && linked.length > 1 && <label className="den-field sm:col-span-2"><span>Dosar prosumator asociat</span><select className="den-input" value={form.pros_id || ""} onChange={(e) => choosePros(e.target.value)} data-testid="diu-pros-select">
          <option value="">Selectează locul de consum...</option>{linked.map((p) => <option key={p.id} value={p.id}>{p.number || "Dosar"} · POD {p.pod || "—"} · {p.address || p.client_name}</option>)}
        </select></label>}
        {!selectedClient && <p className="sm:col-span-2 text-xs" style={{ color: "var(--muted)" }}>Alege întâi clientul pentru a vedea dosarele de prosumator asociate.</p>}
        {(["type", "power", "address", "operator", "atr", "status"].map((name) => {
          const f = fieldByName(name); return f && <Field key={name} f={f} form={form} setVal={setVal} refOptions={refOptions} />;
        }))}
        {chosenPros && <div className="sm:col-span-2 rounded-lg border bg-white px-3 py-2 text-xs" style={{ borderColor: "var(--line)" }} data-testid="diu-linked-summary">
          <b>Date preluate din dosarul prosumator:</b> POD {chosenPros.pod || "—"} · {chosenPros.operator || "operator necompletat"} · invertor {chosenPros.inverter_kw || chosenPros.power || "—"} kW
          {chosenPros.cef?.inverters?.some((x) => x.battery_mode === "own" && x.battery?.model) && " · baterie inclusă"}
        </div>}
      </div>
    </section>
    <details className="rounded-xl border px-4" style={{ borderColor: "var(--line)" }} data-testid="diu-advanced-fields">
      <summary className="cursor-pointer py-3 text-sm font-semibold">Date tehnice și de recepție suplimentare</summary>
      <div className="grid gap-3 pb-4 sm:grid-cols-2">{extras.map((f, i) => f.type === "section"
        ? <Field key={`section-${i}`} f={f} form={form} setVal={setVal} refOptions={refOptions} />
        : <Field key={f.name} f={f} form={form} setVal={setVal} refOptions={refOptions} />)}</div>
    </details>
  </div>;
}
