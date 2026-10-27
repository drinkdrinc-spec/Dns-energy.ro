import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Btn } from "@/components/Layout";
import { ExternalLink, RefreshCw, Trash2, Check } from "lucide-react";

const ST = { "valid": ["#ecfdf3", "#166534"], "versiune nouă detectată": ["#fff8e6", "#8a5a00"], "link invalid": ["#fff0f0", "#9b2c2c"],
  "neverificabil automat": ["#eef4ff", "#1e40af"], "neverificat": ["#f3f4f6", "#6b7280"] };
const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Eroare");

function Row({ f, admin, reload }) {
  const c = ST[f.status] || ST["neverificat"];
  const lc = f.last_check || {};
  const act = async (fn, ok) => { try { await fn(); toast.success(ok); reload(); } catch (e) { err(e); } };
  return (
    <div className="border-t py-3 flex flex-wrap gap-3 items-start" style={{ borderColor: "var(--line)" }} data-testid={`form-row-${f.id}`}>
      <div className="flex-1 min-w-[260px]">
        <div className="text-[11px] font-bold uppercase" style={{ color: "var(--blue)" }}>{f.operator} · {f.kind}</div>
        <b className="text-sm">{f.title}</b>
        <div className="text-[11px] mt-0.5" style={{ color: "var(--muted)" }}>
          Versiune confirmată: <b>{f.version || "—"}</b>{lc.detected_version ? ` · detectată: ${lc.detected_version}` : ""}{lc.at ? ` · verificat ${new Date(lc.at).toLocaleString("ro-RO")}` : ""}{lc.http ? ` · HTTP ${lc.http}` : ""}</div>
        <a href={f.url} target="_blank" rel="noopener noreferrer" className="text-[11px] font-bold inline-flex items-center gap-1 mt-1 break-all" style={{ color: "var(--blue)" }} data-testid={`form-link-${f.id}`}>{f.url} <ExternalLink size={11} /></a>
        {f.status === "neverificabil automat" && <div className="text-[11px] mt-1" style={{ color: "#1e40af" }}>Site-ul operatorului blochează verificarea automată — deschideți linkul și confirmați manual versiunea.</div>}
      </div>
      <span className="text-[11px] font-bold rounded-full px-2 py-0.5" style={{ background: c[0], color: c[1] }} data-testid={`form-status-${f.id}`}>{f.status}</span>
      {admin && <div className="flex gap-3 text-xs font-bold">
        <button onClick={() => act(() => api.post(`/forms/check?fid=${f.id}`), "Verificat")} style={{ color: "var(--blue)" }} data-testid={`form-check-${f.id}`}><RefreshCw size={13} /></button>
        <button onClick={() => { const v = window.prompt("Versiunea confirmată (ex. cod formular / ediție / dată):", lc.detected_version || f.version || ""); if (v !== null) act(() => api.post(`/forms/${f.id}/confirm`, { version: v }), "Versiune confirmată"); }} style={{ color: "#166534" }} data-testid={`form-confirm-${f.id}`}><Check size={13} /></button>
        <button onClick={() => window.confirm("Ștergeți formularul din registru?") && act(() => api.delete(`/forms/${f.id}`), "Șters")} data-testid={`form-delete-${f.id}`}><Trash2 size={13} style={{ color: "#b33333" }} /></button>
      </div>}
    </div>
  );
}

function AddForm({ reload }) {
  const [f, setF] = useState({ operator: "DEER", title: "", kind: "", url: "" });
  const save = async () => { try { await api.post("/forms", f); toast.success("Formular adăugat și verificat"); setF({ ...f, title: "", url: "", kind: "" }); reload(); } catch (e) { err(e); } };
  return (
    <div className="den-panel mb-5 grid sm:grid-cols-[150px_1fr_150px_1fr_auto] gap-2 items-end" data-testid="form-add">
      {[["operator", "Operator"], ["title", "Denumire formular"], ["kind", "Tip"], ["url", "Link oficial (https://…)"]].map(([k, l]) => (
        <div key={k} className="den-field"><label>{l}</label><input className="den-input" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`form-add-${k}`} /></div>))}
      <Btn onClick={save} data-testid="form-add-save">Adaugă</Btn>
    </div>
  );
}

export default function FormsRegistry() {
  const { user } = useAuth();
  const [rows, setRows] = useState(null);
  const [op, setOp] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/forms").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const ops = useMemo(() => [...new Set((rows || []).map((r) => r.operator))], [rows]);
  if (!rows) return null;
  const checkAll = async () => { setBusy(true); try { await api.post("/forms/check"); toast.success("Toate linkurile au fost verificate"); load(); } catch (e) { err(e); } setBusy(false); };
  const shown = rows.filter((r) => !op || r.operator === op);
  return (
    <div>
      <PageHeader eyebrow="Racordare" title="Registru formulare oficiale" sub="Linkurile oficiale DEER, Delgaz Grid, Rețele Electrice și Distribuție Energie Oltenia, cu verificare automată săptămânală (luni 06:00) a linkurilor și a versiunilor; administratorul primește e-mail la modificări."
        action={user?.platform && <Btn onClick={checkAll} disabled={busy} data-testid="forms-check-all"><RefreshCw size={15} />{busy ? "Se verifică…" : "Verifică acum toate"}</Btn>} />
      {user?.platform && <AddForm reload={load} />}
      <div className="flex gap-2 flex-wrap mb-4">{["", ...ops].map((o) => <button key={o || "all"} onClick={() => setOp(o)} data-testid={`forms-filter-${o || "all"}`} className="rounded-full px-4 py-2 text-[12px] font-bold border"
        style={o === op ? { background: "var(--navy)", color: "#fff", borderColor: "var(--navy)" } : { background: "#fff", borderColor: "var(--line)" }}>{o || "Toți operatorii"}</button>)}</div>
      <div className="den-panel" data-testid="forms-list">{shown.map((f) => <Row key={f.id} f={f} admin={user?.platform} reload={load} />)}</div>
    </div>
  );
}
