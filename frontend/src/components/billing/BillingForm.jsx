const PF = [["full_name", "Nume și prenume *"], ["cnp", "CNP (opțional)"], ["address", "Adresă de facturare *", true]];
const PJ = [["company_name", "Denumire firmă *"], ["cui", "CUI / CIF *"], ["regcom", "Nr. Registrul Comerțului *"], ["hq_address", "Sediu social *", true],
  ["rep_name", "Nume și prenume reprezentant *"]];
const COMMON = [["locality", "Localitate *"], ["county", "Județ *"], ["country", "Țară *"], ["postal_code", "Cod poștal"],
  ["billing_email", "E-mail facturare *"], ["phone", "Telefon *"], ["contact_person", "Persoană de contact (dacă diferă)"], ["contact_phone", "Telefon persoană de contact"],
  ["bank", "Banca (opțional)"], ["iban", "IBAN (opțional)"]];

export function BillingForm({ value, onChange }) {
  const v = value || {};
  const set = (k, x) => onChange({ ...v, [k]: x });
  const type = v.client_type || "";
  const fields = [...(type === "pj" ? PJ : type === "pf" ? PF : []), ...(type ? COMMON : [])];
  return (
    <div data-testid="billing-form">
      <div className="flex gap-2 mb-3">
        {[["pf", "Persoană fizică"], ["pj", "Persoană juridică"]].map(([k, l]) => (
          <button type="button" key={k} onClick={() => set("client_type", k)} data-testid={`billing-type-${k}`}
            className="rounded-full px-4 py-2 text-[12px] font-bold border transition-colors"
            style={type === k ? { background: "var(--navy)", color: "#fff", borderColor: "var(--navy)" } : { background: "#fff", borderColor: "var(--line)" }}>{l}</button>
        ))}
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        {fields.map(([k, l, full]) => (
          <div key={k} className={`den-field ${full ? "sm:col-span-2" : ""}`}><label>{l}</label>
            <input className="den-input" value={v[k] ?? (k === "country" ? "România" : "")} onChange={(e) => set(k, e.target.value)} data-testid={`billing-${k}`} /></div>
        ))}
        {type === "pj" && <label className="text-xs flex items-center gap-2 sm:col-span-2"><input type="checkbox" checked={!!v.vat_payer} onChange={(e) => set("vat_payer", e.target.checked)} data-testid="billing-vat-payer" /> Firma este plătitoare de TVA</label>}
      </div>
      {type && <p className="text-[11px] mt-2" style={{ color: "var(--muted)" }}>Datele sunt folosite doar pentru facturare și sunt vizibile numai dvs. și administratorului platformei (GDPR — minimizarea datelor).</p>}
    </div>
  );
}
