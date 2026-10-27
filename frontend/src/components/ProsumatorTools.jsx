import { useRef, useState } from "react";
import { api, API } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Sparkles, FileDown, FileText, Paperclip } from "lucide-react";
import { toast } from "sonner";

const DOCS = [
  ["notificare", "Notificare Anexa 2 (OD)"], ["imputernicire", "Împuternicire"],
  ["declaratie_beneficiar", "Declarație beneficiar"], ["declaratie_executant", "Declarație executant"],
  ["declaratie_conformitate", "Declarație de conformitate"], ["pv_receptie", "PV recepție lucrări"],
  ["pv_pif", "PV punere în funcțiune"], ["buletin_priza", "Buletin priză de pământ"],
  ["buletin_reglaj", "Buletin reglaj invertor"], ["declaratie_autenticitate", "Declarație autenticitate"],
  ["schema", "Schema monofilară"],
];

const docUrl = (type, id) => `${API}/docs/${type}/${id}?auth=${localStorage.getItem("den_token")}`;

export function AiImportButton({ onExtracted }) {
  const ref = useRef();
  const [busy, setBusy] = useState(false);
  const pick = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    const t = toast.loading("Citesc documentul cu AI... (poate dura până la 1 minut)");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/ai/extract", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 240000 });
      onExtracted({ ...data.data, files: [data.file] });
      toast.success("Date extrase — verifică formularul și salvează", { id: t });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Nu am putut citi documentul", { id: t });
    } finally { setBusy(false); ref.current.value = ""; }
  };
  return (
    <>
      <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" onChange={pick} data-testid="ai-import-input" />
      <Btn variant="secondary" disabled={busy} onClick={() => ref.current.click()} data-testid="ai-import-btn">
        <Sparkles size={15} /> {busy ? "Se citește..." : "Import din PDF (AI)"}
      </Btn>
    </>
  );
}

export function GeneratedDocs({ id, files }) {
  return (
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="generated-docs">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <h3 className="font-bold text-sm">Documente generate automat</h3>
        <a href={docUrl("all", id)} target="_blank" rel="noopener noreferrer" data-testid="doc-all">
          <Btn><FileDown size={15} /> Dosar complet (PDF)</Btn>
        </a>
      </div>
      {!id ? <p className="text-xs" style={{ color: "var(--muted)" }}>Salvează dosarul pentru a genera documentele.</p> : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {DOCS.map(([k, label]) => (
            <a key={k} href={docUrl(k, id)} target="_blank" rel="noopener noreferrer" data-testid={`doc-${k}`}
              className="flex items-center gap-2 rounded-lg border bg-white px-3 py-2.5 text-sm hover:border-[var(--blue)] transition-colors" style={{ borderColor: "var(--line)" }}>
              <FileText size={15} style={{ color: "var(--blue)" }} /> {label}
            </a>
          ))}
        </div>
      )}
      {files?.length > 0 && (
        <div className="mt-3 text-xs flex flex-wrap gap-2">
          {files.map((f) => (
            <a key={f.storage_path} href={`${API}/files/${f.storage_path}?auth=${localStorage.getItem("den_token")}`} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 underline" style={{ color: "var(--blue)" }} data-testid="attached-file">
              <Paperclip size={12} /> {f.original_filename}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
