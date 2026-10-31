import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { FileText, Plus, Sparkles, Upload } from "lucide-react";
import { toast } from "sonner";

const TYPES = [
  ["ci", "1. Carte de identitate", "Actul clientului; se extrag numele, CNP-ul și domiciliul."],
  ["factura", "2. Factură de energie", "Se extrag POD-ul, operatorul și adresa locului de consum."],
  ["cf", "3. Carte funciară", "Se extrag numărul CF și numărul cadastral."],
  ["altele", "4. Alte documente", "PDF, imagini, DOCX și XLSX pot fi citite și rezumate; DOC/XLS și alte formate se atașează pentru verificare manuală."],
];

const EMPTY = { client_name: "", cnp: "", hq_address: "", county: "", address: "", pod: "", operator: "", supplier: "", cf_nr: "", cadastral_nr: "", phone: "", email: "" };

function putNonempty(base, next) {
  const out = { ...base };
  for (const [k, v] of Object.entries(next)) if (v !== null && v !== undefined && String(v).trim()) out[k] = String(v).trim();
  return out;
}

export function DossierDocumentStart({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState(EMPTY);
  const [files, setFiles] = useState({ ci: [], factura: [], cf: [], altele: [] });
  const [notes, setNotes] = useState({});
  const [busy, setBusy] = useState("");
  const inputs = useRef({});

  const extract = async (kind, selected) => {
    const list = Array.from(selected || []);
    if (!list.length) return;
    setBusy(kind);
    try {
      const mergedFiles = [...(files[kind] || [])];
      let mergedValues = values;
      const summaries = [];
      for (const file of list) {
        const officeExtractable = /\.(docx|xlsx)$/i.test(file.name);
        const extractable = file.type === "application/pdf" || file.type.startsWith("image/") || officeExtractable;
        let x = {};
        if (kind === "altele" && !extractable) {
          const fd = new FormData(); fd.append("file", file);
          const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
          mergedFiles.push(data);
          summaries.push(`${file.name}: atașat; formatul nu are citire automată, necesită verificare manuală`);
          continue;
        }
        if (!extractable) throw new Error("Pentru citire automată folosește PDF, imagine, DOCX sau XLSX. DOC/XLS și alte formate se atașează pentru verificare manuală.");
        const fd = new FormData(); fd.append("file", file); fd.append("doc_type", kind === "altele" ? "other" : kind);
        const { data } = await api.post("/ai/extract", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 240000 });
        mergedFiles.push(data.file);
        x = data.data || {};
        if (kind === "ci") mergedValues = putNonempty(mergedValues, { client_name: x.client_name, cnp: x.cnp, hq_address: x.hq_address || x.address,
          county: x.county, phone: x.phone, email: x.email, ci_series: x.id_series && x.id_number ? `${x.id_series} ${x.id_number}` : x.id_series || x.id_number });
        if (kind === "factura") mergedValues = putNonempty(mergedValues, { client_name: mergedValues.client_name || x.client_name, cnp: mergedValues.cnp || x.cnp,
          address: x.consumption_address || x.address, pod: x.pod, operator: x.operator, supplier: x.supplier,
          county: mergedValues.county || x.county, phone: mergedValues.phone || x.phone, email: mergedValues.email || x.email });
        if (kind === "cf") mergedValues = putNonempty(mergedValues, { cf_nr: x.cf_nr, cadastral_nr: x.cadastral_nr,
          client_name: mergedValues.client_name || x.owner_name });
        if (kind === "ci") mergedValues = putNonempty(mergedValues, { ci_series: x.id_series && x.id_number ? `${x.id_series} ${x.id_number}` : x.id_series || x.id_number });
        if (kind === "altele" && x.summary) summaries.push(`${file.name}: ${x.doc_type || "document"} — ${x.summary}`);
      }
      setFiles((prev) => ({ ...prev, [kind]: mergedFiles }));
      setValues(mergedValues);
      if (summaries.length) setNotes((prev) => ({ ...prev, altele: [...(prev.altele || []), ...summaries] }));
      toast.success(`${list.length === 1 ? "Document citit" : `${list.length} documente citite`} — verifică datele extrase`);
    } catch (e) { toast.error(e.response?.data?.detail || "Nu am putut citi documentul"); }
    finally { setBusy(""); if (inputs.current[kind]) inputs.current[kind].value = ""; }
  };

  const create = async () => {
    if (!values.client_name.trim()) return toast.error("Completează sau corectează numele clientului din CI.");
    const filesForDossier = Object.entries(files).flatMap(([kind, list]) => list.map((f) => ({
      ...f, kind,
      doc_type: ({ ci: "Carte de identitate", factura: "Factură energie", cf: "Carte funciară", altele: "Document suplimentar" })[kind],
    })));
    const payload = { ...values, client_name: values.client_name.trim(), files: filesForDossier,
      notes: [values.notes, ...(notes.altele || [])].filter(Boolean).join("\n") };
    try {
      setBusy("create");
      const { data } = await api.post("/import/prosumator", payload);
      toast.success("Clientul și dosarul au fost create cu documentele în opis.");
      setOpen(false); onCreated(data);
      setValues(EMPTY); setFiles({ ci: [], factura: [], cf: [], altele: [] }); setNotes({});
    } catch (e) { toast.error(e.response?.data?.detail || "Nu am putut crea dosarul"); }
    finally { setBusy(""); }
  };

  const field = (key, label) => <label className="den-field" key={key}><span>{label}</span>
    <input className="den-input" value={values[key] || ""} onChange={(e) => setValues((p) => ({ ...p, [key]: e.target.value }))} data-testid={`intake-${key}`} /></label>;

  return <>
    <Btn variant="secondary" onClick={() => setOpen(true)} data-testid="dossier-start-documents"><Plus size={15} /> Începe dosarul din documente</Btn>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="dossier-document-start-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><Sparkles size={18} style={{ color: "var(--blue)" }} /> Dosar nou din documente</DialogTitle></DialogHeader>
        <p className="text-xs" style={{ color: "var(--muted)" }}>Încarcă pe rând CI, factura, cartea funciară și documentele suplimentare. AI extrage doar informația tipărită; verifică și corectează câmpurile înainte de creare.</p>
        <div className="grid sm:grid-cols-2 gap-2">
          {TYPES.map(([kind, title, help]) => <div key={kind} className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }}>
            <div className="font-bold text-sm">{title}</div><p className="text-[11px] my-1" style={{ color: "var(--muted)" }}>{help}</p>
            <input ref={(el) => { inputs.current[kind] = el; }} type="file" accept={kind === "altele" ? ".pdf,image/*,.doc,.docx,.xls,.xlsx" : "application/pdf,image/*"} multiple={kind === "altele"} className="hidden"
              onChange={(e) => extract(kind, e.target.files)} data-testid={`intake-file-${kind}`} />
            <button onClick={() => inputs.current[kind]?.click()} disabled={!!busy} className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }}>
              <Upload size={13} /> {busy === kind ? "AI citește…" : "Încarcă și citește"}
            </button>
            {(files[kind] || []).map((f) => <div key={f.storage_path} className="mt-1 text-[11px] flex gap-1 items-center"><FileText size={12} />{f.original_filename}</div>)}
          </div>)}
        </div>
        <div className="grid sm:grid-cols-2 gap-3 pt-2">
          {field("client_name", "Nume client *")}{field("cnp", "CNP / CUI")}
          {field("hq_address", "Domiciliu din CI")}{field("address", "Adresa locului de consum din factură")}
          {field("pod", "POD din factură")}{field("operator", "Operator de distribuție")}
          {field("cf_nr", "Număr carte funciară")}{field("cadastral_nr", "Număr cadastral")}
          {field("county", "Județ")}{field("supplier", "Furnizor energie")}
          {field("phone", "Telefon (dacă apare în document)")}{field("email", "E-mail (dacă apare în document)")}
        </div>
        {notes.altele?.length > 0 && <div className="rounded-lg bg-slate-50 p-3 text-xs"><b>Documente suplimentare:</b><ul className="list-disc pl-5">{notes.altele.map((n, i) => <li key={i}>{n}</li>)}</ul></div>}
        <div className="flex justify-end gap-2 pt-2"><Btn variant="secondary" onClick={() => setOpen(false)}>Închide</Btn>
          <Btn onClick={create} disabled={!!busy || !values.client_name.trim()} data-testid="dossier-start-create">{busy === "create" ? "Creez dosarul…" : "Creează client și dosar"}</Btn></div>
      </DialogContent>
    </Dialog>
  </>;
}

