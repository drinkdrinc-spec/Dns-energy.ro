import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, API, formatApiErrorDetail } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { PencilLine, RefreshCw } from "lucide-react";

export function SldEditor({ id, onSaved }) {
  const [d, setD] = useState(null);
  const [vals, setVals] = useState({});
  const [ver, setVer] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/sld/${id}/values`).then((r) => { setD(r.data); setVals({}); });
  useEffect(() => { load(); }, [id]); // eslint-disable-line
  if (!d) return null;
  const save = async () => {
    setBusy(true);
    try { await api.put(`/sld/${id}/values`, { values: vals }); toast.success("Valori aplicate — previzualizarea a fost regenerată"); await load(); setVer(Date.now()); onSaved?.(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Eroare"); }
    setBusy(false);
  };
  const n = Object.keys(vals).length;
  return (
    <div className="mt-4 grid lg:grid-cols-[minmax(320px,420px)_1fr] gap-4" data-testid="sld-editor">
      <div className="rounded-xl border p-3 max-h-[640px] overflow-y-auto" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center gap-2 mb-2"><PencilLine size={14} style={{ color: "var(--blue)" }} /><b className="text-sm">Editare manuală — protecții, cabluri, componente</b></div>
        {d.from_legacy && <div className="text-[11px] mb-2" style={{ color: "#8a5a00" }}>Preluați întâi datele în configuratorul CEF pentru a putea edita valorile.</div>}
        {d.groups.map((g) => (
          <div key={g.title} className="mb-3">
            <div className="text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--blue)" }}>{g.title}</div>
            {g.rows.map((r) => {
              const v = vals[r.path] ?? r.value ?? "";
              return (
                <label key={r.path} className="grid grid-cols-[1fr_130px] gap-2 items-center py-0.5 text-xs">
                  <span>{r.label}{r.manual && <b className="ml-1 text-[10px]" style={{ color: "#8a5a00" }} data-testid={`sld-manual-${r.path}`}>manual</b>}{r.auto && !r.manual && <span className="ml-1 text-[10px]" style={{ color: "var(--muted)" }}>propus</span>}</span>
                  <input className="den-input !py-1 text-xs" type={r.type === "num" ? "number" : "text"} value={v} disabled={d.from_legacy}
                    style={vals[r.path] !== undefined ? { borderColor: "var(--blue)" } : undefined}
                    onChange={(e) => setVals({ ...vals, [r.path]: e.target.value })} data-testid={`sld-val-${r.path}`} />
                </label>);
            })}
          </div>))}
        <Btn type="button" onClick={save} disabled={busy || !n} data-testid="sld-values-save"><RefreshCw size={14} />{busy ? "Se aplică…" : `Aplică ${n || ""} modificări și previzualizează`}</Btn>
      </div>
      <iframe title="Previzualizare schemă" src={`${API}/sld/${id}/pdf?auth=${localStorage.getItem("den_token")}&v=${ver}`} className="w-full h-[640px] rounded-xl border" style={{ borderColor: "var(--line)" }} data-testid="sld-preview-frame" />
    </div>
  );
}
