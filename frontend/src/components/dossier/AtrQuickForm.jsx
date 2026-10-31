const BASIC = new Set(["client_name", "pod", "operator", "kind", "request_type", "deer_case", "applicant_type", "submission_mode", "address", "supply", "p_abs_kw"]);
const label = (f) => (f.label || "").replace(/\s*\*$/, "");

export function AtrQuickForm({ cfg, form, setVal, refOptions }) {
  const fields = cfg.fields || [];
  const isDeer = /deer|distribuție energie electrică|distributie energie electrica/i.test(String(form.operator || ""));
  const basic = fields.filter((f) => BASIC.has(f.name) && (f.name !== "deer_case" || isDeer));
  const advanced = fields.filter((f) => !BASIC.has(f.name));
  const clients = refOptions.clients || [];

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
    <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-extra-fields">
      <summary className="cursor-pointer text-sm font-semibold">Alte date pentru formularul ATR</summary>
      <div className="grid sm:grid-cols-2 gap-3 mt-3">{advanced.map(renderField)}</div>
    </details>
  </div>;
}
