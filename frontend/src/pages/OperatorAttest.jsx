import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Upload, FileDown } from "lucide-react";
import { api, API } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";

const F = [["company", "Denumirea firmei"], ["cui", "CUI"], ["regcom", "Nr. Registrul Comerțului"], ["contact_name", "Persoană de contact"], ["contact_phone", "Telefon"],
  ["contact_email", "E-mail"], ["attest_no", "Numărul atestatului ANRE"], ["attest_valid", "Valabil până la", "date"], ["holder_name", "Titularul atestatului (firma)"], ["holder_role", "Reprezentant / funcție"]];
const COL = { "aprobat": "#166534", "respins": "#9b2c2c", "expirat": "#9b2c2c", "în așteptare": "#8a5a00" };

export default function OperatorAttest() {
  const { refresh } = useAuth();
  const [d, setD] = useState(null);
  const [f, setF] = useState({});
  const load = () => api.get("/operator").then((r) => { setD(r.data); setF(r.data.operator || {}); });
  useEffect(() => { load(); }, []);
  if (!d) return null;
  const o = d.operator || {};
  const types = f.attest_types || [];
  const save = async () => { try { await api.put("/operator", f); toast.success("Datele au fost trimise spre verificare"); load(); refresh?.(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  const up = async (file) => {
    const fd = new FormData(); fd.append("file", file);
    try { await api.post("/operator/document", fd, { headers: { "Content-Type": "multipart/form-data" } }); toast.success("Document încărcat"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
  };
  return (
    <div data-testid="operator-attest-page">
      <PageHeader eyebrow="Cont firmă" title="Atestat ANRE al operatorului economic" sub="Accesul la funcțiile profesionale se acordă firmelor cu atestat ANRE verificat de administrator și abonament plătit. Se verifică atestatul firmei, nu al fiecărui angajat." />
      <div className="den-panel mb-4 text-sm" data-testid="attest-status">Status verificare: <b style={{ color: COL[o.status] || "#6b7280" }}>{o.status || "netrimis"}</b>
        {o.verified_at && <> · verificat la {new Date(o.verified_at).toLocaleDateString("ro-RO")}</>}{o.admin_notes && <div className="text-xs mt-1">Observații administrator: {o.admin_notes}</div>}
        {d.attest && d.attest !== "aprobat" && <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>Documentul încărcat nu este considerat dovadă de valabilitate până la verificarea manuală.</div>}</div>
      <div className="den-panel grid sm:grid-cols-3 gap-2">
        {F.map(([k, l, t]) => <div key={k} className="den-field"><label>{l}</label><input className="den-input" type={t || "text"} value={f[k] ?? ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`op-${k}`} /></div>)}
        <div className="den-field sm:col-span-3"><label>Tipul atestatului (unul sau mai multe)</label>
          <div className="flex flex-wrap gap-2">{d.types.map((t) => (
            <label key={t} className="text-xs flex items-center gap-1 rounded border px-2 py-1" style={{ borderColor: "var(--line)" }}>
              <input type="checkbox" checked={types.includes(t)} onChange={(e) => setF({ ...f, attest_types: e.target.checked ? [...types, t] : types.filter((x) => x !== t) })} data-testid={`op-type-${t}`} />{t}</label>))}
            <input className="den-input !w-48" placeholder="Alt tip (opțional)" value={f.attest_other ?? ""} onChange={(e) => setF({ ...f, attest_other: e.target.value })} data-testid="op-attest_other" /></div></div>
      </div>
      <div className="den-panel mt-4 flex flex-wrap items-center gap-3">
        <label className="den-btn den-btn-secondary cursor-pointer inline-flex items-center gap-2 text-sm font-bold" data-testid="op-upload"><Upload size={14} /> Încarcă atestatul (PDF/JPG/PNG)
          <input type="file" accept="application/pdf,image/jpeg,image/png" className="hidden" onChange={(e) => e.target.files[0] && up(e.target.files[0])} data-testid="op-upload-input" /></label>
        {o.has_document && <a href={`${API}/operator/document?auth=${localStorage.getItem("den_token")}`} target="_blank" rel="noopener noreferrer" className="text-sm font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} data-testid="op-doc-view"><FileDown size={14} /> {o.doc_name}</a>}
        <Btn className="ml-auto" onClick={save} data-testid="op-save">Trimite spre verificare</Btn>
      </div>
    </div>
  );
}
