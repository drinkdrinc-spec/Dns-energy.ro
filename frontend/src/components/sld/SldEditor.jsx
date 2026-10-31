import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatApiErrorDetail } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { PencilLine, RefreshCw } from "lucide-react";

export function SldEditor({ id, onSaved }) {
  const [d, setD] = useState(null);
  const [vals, setVals] = useState({});
  const [ver, setVer] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const load = () => api.get(`/sld/${id}/values`).then((r) => { setD(r.data); setVals({}); });
  useEffect(() => {
    let live = true;
    api.get(`/sld/${id}/values`).then((r) => { if (live) setD(r.data); });
    return () => { live = false; };
  }, [id]);
  useEffect(() => {
    let live = true;
    let objectUrl = "";
    api.get(`/sld/${id}/pdf?v=${ver}`, { responseType: "blob" })
      .then(({ data }) => {
        if (!live) return;
        objectUrl = URL.createObjectURL(data);
        setPreviewUrl(objectUrl);
      })
      .catch((e) => {
        if (live) toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Nu s-a putut încărca previzualizarea PDF");
      });
    return () => {
      live = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, ver]);
  if (!d) return null;
  const save = async () => {
    setBusy(true);
    try { const { data } = await api.put(`/sld/${id}/values`, { values: vals }); toast.success("Valori aplicate — previzualizarea a fost regenerată"); await load(); setVer(Date.now()); onSaved?.(data.cef); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Eroare"); }
    setBusy(false);
  };
  const n = Object.keys(vals).length;
  return (
    <div className="mt-4 grid lg:grid-cols-[minmax(320px,420px)_1fr] gap-4" data-testid="sld-editor">
      <div className="rounded-xl border p-3 max-h-[640px] overflow-y-auto" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center gap-2 mb-2"><PencilLine size={14} style={{ color: "var(--blue)" }} /><b className="text-sm">Editare manuală — protecții, cabluri, componente</b></div>
        {d.from_legacy && <div className="text-[11px] mb-2" style={{ color: "#8a5a00" }}>Preluați întâi datele în configuratorul CEF pentru a putea edita valorile.</div>}
        <label className="block text-xs font-semibold mb-3">
          Caută un parametru
          <input className="den-input mt-1" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ex.: cablu AC, întreruptor, baterie…" data-testid="sld-field-search" />
        </label>
        <p className="text-[11px] mb-3" style={{ color: "var(--muted)" }}>Grupele sunt pliate ca să nu aglomereze ecranul. Deschide doar secțiunea de care ai nevoie; valorile propuse trebuie verificate cu proiectul și fișele tehnice.</p>
        {d.groups.map((g, gi) => {
          const rows = g.rows.filter((r) => !query || `${r.label} ${r.path}`.toLowerCase().includes(query.toLowerCase()));
          if (!rows.length) return null;
          const changed = rows.filter((r) => vals[r.path] !== undefined).length;
          return (
            <details key={g.title} open={!!query || gi === 0} className="mb-2 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
              <summary className="cursor-pointer text-xs font-bold flex items-center justify-between gap-2">
                <span>{g.title}</span><span className="font-normal" style={{ color: "var(--muted)" }}>{rows.length} parametri{changed ? ` · ${changed} modificați` : ""}</span>
              </summary>
              <div className="mt-2">
                {rows.map((r) => {
                  const v = vals[r.path] ?? r.value ?? "";
                  return (
                    <label key={r.path} className="grid grid-cols-[minmax(0,1fr)_110px] sm:grid-cols-[minmax(0,1fr)_130px] gap-2 items-center py-1 text-xs">
                      <span>{r.label}{r.manual && <b className="ml-1 text-[10px]" style={{ color: "#8a5a00" }} data-testid={`sld-manual-${r.path}`}>manual</b>}{r.auto && !r.manual && <span className="ml-1 text-[10px]" style={{ color: "var(--muted)" }}>propus</span>}</span>
                      <input className="den-input !py-1 text-xs min-w-0" type={r.type === "num" ? "number" : "text"} value={v} disabled={d.from_legacy}
                        style={vals[r.path] !== undefined ? { borderColor: "var(--blue)" } : undefined}
                        onChange={(e) => setVals({ ...vals, [r.path]: e.target.value })} data-testid={`sld-val-${r.path}`} />
                    </label>);
                })}
              </div>
            </details>);
        })}
        <Btn type="button" onClick={save} disabled={busy || !n} data-testid="sld-values-save"><RefreshCw size={14} />{busy ? "Se aplică…" : `Aplică ${n || ""} modificări și previzualizează`}</Btn>
      </div>
      <iframe title="Previzualizare schemă" src={previewUrl || undefined} className="w-full h-[640px] rounded-xl border" style={{ borderColor: "var(--line)" }} data-testid="sld-preview-frame" />
    </div>
  );
}
