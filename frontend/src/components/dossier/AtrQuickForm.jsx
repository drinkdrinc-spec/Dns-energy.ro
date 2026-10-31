const BASIC = new Set(["client_name", "pod", "operator", "kind", "request_type", "deer_case", "applicant_type", "submission_mode", "address", "supply", "p_abs_kw"]);
const label = (f) => (f.label || "").replace(/\s*\*$/, "");

export function AtrQuickForm({ cfg, form, setVal, refOptions }) {
  const fields = cfg.fields || [];
  const isDeer = /deer|distribuție energie electrică|distributie energie electrica/i.test(String(form.operator || ""));
  const basic = fields.filter((f) => BASIC.has(f.name) && (f.name !== "deer_case" || isDeer));
  const advanced = fields.filter((f) => !BASIC.has(f.name));
  const clients = refOptions.clients || [];
  const pros = refOptions.prosumator || [];
  const norm = (v) => String(v || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO");
  const linkedPros = pros.filter((p) => (form.pros_id && p.id === form.pros_id) || (form.client_id && p.client_id === form.client_id)
    || (form.client_name && norm(p.client_name) === norm(form.client_name)));
  const selectedPros = linkedPros.length === 1 ? linkedPros[0] : null;
  const annexIssues = (() => {
    if (!isDeer || !form.deer_case) return [];
    const issues = [];
    const request = String(form.request_type || "").toLocaleLowerCase("ro-RO");
    if (form.deer_case.includes("loc nou") && !request.includes("utilizator nou")) issues.push("Anexa 1 pentru loc nou cere solicitarea «utilizator nou definitiv».");
    if (form.deer_case.includes("spor de putere") && !request.includes("spor de putere")) issues.push("Anexa 1 pentru spor cere solicitarea «spor de putere».");
    if (form.deer_case.includes("actualizare CRR") && !request.includes("administrativ")) issues.push("Anexa 3 pentru actualizare CRR cere solicitarea administrativă.");
    if (form.deer_case.includes("≤10,8")) {
      const invs = selectedPros?.cef?.inverters || [];
      const panelKw = invs.reduce((sum, inv) => sum + (inv.strings || []).reduce((n, st) => n + (Number(st.panels) || 0), 0) * (Number(inv.panel_w) || 0) / 1000 * (Number(inv.count) || 1), 0);
      const power = Number(form.pv_kw) || Number(selectedPros?.cef?.total_kwp) || Number(selectedPros?.panel_kwp) || panelKw || Number(selectedPros?.inverter_kw);
      if (!power) issues.push("Completează puterea instalată de producere pentru verificarea limitei de 10,8 kW.");
      else if (power > 10.8) issues.push("Anexa 5 este eligibilă doar pentru putere instalată de maximum 10,8 kW.");
      const supply = String(form.supply || selectedPros?.supply || selectedPros?.cef?.grid?.supply || "").toLowerCase();
      if (!supply) issues.push("Selectează tipul branșamentului pentru verificarea Anexei 5.");
      else if (supply.includes("trifaz") || supply.includes("400")) issues.push("Anexa 5 selectată cere conexiune diferită de trifazic.");
    }
    if (form.deer_case.includes(">400")) {
      const invs = selectedPros?.cef?.inverters || [];
      const panelKw = invs.reduce((sum, inv) => sum + (inv.strings || []).reduce((n, st) => n + (Number(st.panels) || 0), 0) * (Number(inv.panel_w) || 0) / 1000 * (Number(inv.count) || 1), 0);
      const power = Number(form.pv_kw) || Number(selectedPros?.cef?.total_kwp) || Number(selectedPros?.panel_kwp) || panelKw || Number(selectedPros?.inverter_kw);
      if (!power) issues.push("Completează puterea instalată de producere pentru procedura dedicată.");
      else if (power <= 400) issues.push("Procedura dedicată DEER este pentru putere instalată mai mare de 400 kW.");
    }
    return issues;
  })();

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
      {annexIssues.length > 0 && <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900" role="alert" data-testid="atr-deer-annex-warning"><strong>Verifică încadrarea procedurii:</strong><ul className="mt-1 list-disc pl-4">{annexIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul></div>}
    </div>
    <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-extra-fields">
      <summary className="cursor-pointer text-sm font-semibold">Alte date pentru formularul ATR</summary>
      <div className="grid sm:grid-cols-2 gap-3 mt-3">{advanced.map(renderField)}</div>
    </details>
  </div>;
}
