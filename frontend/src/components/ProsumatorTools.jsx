import { useEffect, useRef, useState } from "react";
import { api, API } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Sparkles, FileDown, FileText, Paperclip, BookOpen } from "lucide-react";
import { toast } from "sonner";

const DOCS = [
  ["notificare", "Notificare Anexa 2 pentru operator"],
  ["date_stocare", "Date despre instalația de stocare"],
  ["schema_cef", "Schema monofilară CEF"],
  ["declaratie_afm", "Declarație accesare fonduri AFM"],
  ["buletin_reglaj", "Buletin reglaj invertor"],
  ["buletin_priza", "Buletin priză de pământ"],
  ["pv_pif", "Proces-verbal de punere în funcțiune"],
  ["pv_teste", "Proces-verbal teste și verificări PIF"],
  ["pv_receptie", "Proces-verbal recepție lucrări"],
  ["serii", "Anexă cu seriile echipamentelor"],
  ["declaratie_executant", "Declarația executantului"],
  ["declaratie_conformitate", "Declarație de conformitate"],
  ["imputernicire", "Împuternicire"],
  ["declaratie_autenticitate", "Declarație de autenticitate a datelor"],
  ["declaratie_beneficiar", "Declarație beneficiar"],
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

function CatalogFiles({ id }) {
  const [list, setList] = useState([]);
  useEffect(() => { api.get(`/prosumator/${id}/catalog-files`).then((r) => setList(r.data)).catch(() => {}); }, [id]);
  const attach = async () => {
    const { data } = await api.post(`/prosumator/${id}/attach-catalog`);
    toast.success(data.added ? `${data.added} documente adăugate la client` : "Documentele sunt deja la client");
  };
  return (
    <div className="mt-4" data-testid="catalog-files">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <h4 className="font-bold text-xs uppercase tracking-wider" style={{ color: "var(--blue)" }}>Fișe din catalog pentru echipamentele CEF ({list.length})</h4>
        {list.length > 0 && <div className="flex gap-2">
          <Btn variant="secondary" onClick={attach} data-testid="attach-catalog-btn"><BookOpen size={14} /> Adaugă la documentele clientului</Btn>
          <a href={docUrl("all", id) + "&attach=1"} target="_blank" rel="noopener noreferrer" data-testid="doc-all-attach"><Btn variant="secondary"><FileDown size={14} /> Dosar + fișe tehnice</Btn></a>
        </div>}
      </div>
      {list.length === 0 ? <p className="text-xs" style={{ color: "var(--muted)" }}>Alege echipamentele din catalog în configurarea CEF și încarcă fișele în Catalog echipamente.</p> : (
        <div className="flex flex-wrap gap-2 text-xs">
          {list.map((f) => <a key={f.storage_path} href={`${API}/files/${f.storage_path}?auth=${localStorage.getItem("den_token")}`} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-lg border bg-white px-2 py-1.5" style={{ borderColor: "var(--line)" }} data-testid="catalog-file-link"><FileText size={12} /> {f.kind} — {f.model}</a>)}
        </div>
      )}
    </div>
  );
}

export function GeneratedDocs({ id, files }) {
  const [showIndividual, setShowIndividual] = useState(false);
  return (
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="generated-docs">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <div><h3 className="font-bold text-sm">Dosar generat automat</h3>
          <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>PDF-ul complet include documentele disponibile, schema CEF și fișele tehnice din catalog.</p></div>
        {id && <a href={docUrl("all", id)} target="_blank" rel="noopener noreferrer" data-testid="doc-all">
          <Btn><FileDown size={15} /> Generează dosarul complet (PDF)</Btn>
        </a>}
      </div>
      {!id ? <p className="text-xs" style={{ color: "var(--muted)" }}>Salvează datele dosarului și configurația echipamentelor pentru generare.</p> : <>
        <p className="text-[11px] mb-3" style={{ color: "var(--muted)" }}>Nu trebuie să creezi și să reîncarci manual șabloanele DNS. Completează valorile reale de măsurare la PIF; aplicația nu le estimează.</p>
        <button type="button" className="text-xs font-bold underline" style={{ color: "var(--blue)" }} onClick={() => setShowIndividual((v) => !v)} data-testid="docs-individual-toggle">
          {showIndividual ? "Ascunde documentele individuale" : "Alege un document individual"}
        </button>
        {showIndividual && <div className="mt-2 divide-y rounded-lg border bg-white px-3" style={{ borderColor: "var(--line)" }}>
          {DOCS.map(([k, label]) => (
            <a key={k} href={docUrl(k, id)} target="_blank" rel="noopener noreferrer" data-testid={"doc-" + k}
              className="flex items-center gap-2 py-2 text-sm font-medium hover:underline" style={{ color: "var(--green)", borderColor: "var(--line)" }}>
              <FileDown size={14} /> {label}
            </a>
          ))}
        </div>}
      </>}
      {id && <CatalogFiles id={id} />}
      {files?.length > 0 && (
        <div className="mt-3 text-xs flex flex-wrap gap-2">
          {files.map((f) => (
            <a key={f.storage_path} href={API + "/files/" + f.storage_path + "?auth=" + localStorage.getItem("den_token")} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 underline" style={{ color: "var(--blue)" }} data-testid="attached-file">
              <Paperclip size={12} /> {f.original_filename}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}


