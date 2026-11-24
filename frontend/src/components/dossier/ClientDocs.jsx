import { useRef } from "react";
import { api, openAuthenticatedFile } from "@/lib/api";
import { Upload, FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";

const SLOTS = [["factura", "Factură furnizor de energie"], ["certificat", "Certificat de înregistrare (PJ)"], ["constatator", "Certificat constatator (PJ)"],
  ["ci", "Act de identitate (PF / reprezentant)"], ["cf", "Extras de carte funciară"], ["semnate", "Documente semnate electronic (salvate automat)"]];

export const uploadFile = async (file) => {
  const fd = new FormData(); fd.append("file", file);
  const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
  return data;
};

const clean = (value) => typeof value === "string" ? value.trim() : value == null ? "" : String(value).trim();

function operatorLabel(value) {
  const op = clean(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (op.includes("delgaz")) return "Delgaz Grid S.A.";
  if (op.includes("oltenia")) return "Distribuție Energie Oltenia S.A.";
  if (op.includes("retele electrice")) {
    if (op.includes("banat")) return "Rețele Electrice Banat S.A.";
    if (op.includes("dobrogea")) return "Rețele Electrice Dobrogea S.A.";
    if (op.includes("muntenia")) return "Rețele Electrice Muntenia S.A.";
    return "";
  }
  if (op.includes("deer") || op.includes("distributie energie electrica romania")) {
    if (op.includes("transilvania nord")) return "Distribuție Energie Electrică Romania Sucursala Transilvania Nord";
    if (op.includes("transilvania sud")) return "Distribuție Energie Electrică Romania Sucursala Transilvania Sud";
    if (op.includes("muntenia nord")) return "Distribuție Energie Electrică Romania Sucursala Muntenia Nord";
  }
  return "";
}

function fieldsFromExtraction(data, client, slot) {
  const patch = {};
  const assign = (field, value) => {
    const normalized = clean(value);
    if (normalized && !clean(client[field])) patch[field] = normalized;
  };
  assign("name", data.client_name || (slot === "cf" ? data.owner_name : ""));
  assign("idcode", data.cnp);
  assign("hq_address", data.hq_address);
  assign("ci_series", [data.id_series, data.id_number].filter(Boolean).join(" "));
  assign("address", data.consumption_address || data.address);
  assign("county", data.county);
  assign("locality", data.locality);
  assign("pod", data.pod);
  assign("supplier", data.supplier);
  assign("phone", data.phone);
  assign("email", data.email);
  assign("cf_nr", data.cf_nr);
  assign("cadastral_nr", data.cadastral_nr);
  assign("operator", operatorLabel(data.operator));
  return patch;
}

async function readAndUpload(file, slot) {
  if (slot === "semnate") return { file: await uploadFile(file), fields: {}, warning: "" };
  const docType = slot === "ci" ? "ci" : slot === "factura" ? "factura" : slot === "cf" ? "cf" : "other";
  const fd = new FormData();
  fd.append("file", file);
  fd.append("doc_type", docType);
  try {
    const { data } = await api.post("/ai/extract", fd, { headers: { "Content-Type": "multipart/form-data" } });
    return { file: data.file, fields: data.data || {}, warning: data.warning || "" };
  } catch (error) {
    // Keep uploads useful when AI is disabled or temporarily unavailable.
    const attached = await uploadFile(file);
    const detail = error?.response?.data?.detail;
    return { file: attached, fields: {}, warning: detail || "citirea automată nu a fost disponibilă" };
  }
}

function Slot({ k, label, files, add, remove }) {
  const ref = useRef();
  return (
    <div className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }} data-testid={`client-doc-${k}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-bold">{label}</span>
        <input ref={ref} type="file" accept="application/pdf,image/*,.docx,.xlsx" className="hidden" data-testid={`client-doc-input-${k}`}
          onChange={async (e) => { const f = e.target.files?.[0]; if (f) { try { await add(k, f); } finally { ref.current.value = ""; } } }} />
        <button onClick={() => ref.current.click()} className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} data-testid={`client-doc-upload-${k}`}><Upload size={13} /> Încarcă și citește</button>
      </div>
      {(files || []).map((f, i) => (
        <div key={f.storage_path} className="flex items-center justify-between text-xs mt-2">
          <button type="button" onClick={() => openAuthenticatedFile(`/files/${f.storage_path}`)} className="inline-flex items-center gap-1 underline text-left" style={{ color: "var(--blue)" }}><FileText size={12} /> {f.original_filename}</button>
          <button onClick={() => remove(k, i)} data-testid={`client-doc-remove-${k}-${i}`}><Trash2 size={13} style={{ color: "#b33333" }} /></button>
        </div>
      ))}
    </div>
  );
}

export function ClientDocs({ client, onChange }) {
  const docs = client.docs || {};
  const persistDocs = async (next) => {
    if (client.id) await api.put(`/data/clients/${client.id}`, { docs: next });
    onChange(next, {});
  };
  const add = async (slot, sourceFile) => {
    try {
      const result = await readAndUpload(sourceFile, slot);
      if (!result.file?.storage_path) throw new Error("Fișierul nu a fost salvat");
      const nextDocs = { ...docs, [slot]: [...(docs[slot] || []), result.file] };
      await persistDocs(nextDocs);
      const patch = fieldsFromExtraction(result.fields, client, slot);
      if (Object.keys(patch).length) {
        if (!client.id) {
          onChange(nextDocs, patch);
          toast.success(`Document atașat; completate automat ${Object.keys(patch).length} câmpuri. Salvează clientul pentru a păstra datele.`);
          return;
        }
        try {
          await api.put(`/data/clients/${client.id}`, patch);
          onChange(nextDocs, patch);
          toast.success(`Document atașat; completate automat ${Object.keys(patch).length} câmpuri`);
          return;
        } catch {
          toast.warning("Documentul a fost atașat, dar datele extrase nu s-au putut salva. Verifică și salvează câmpurile manual.");
          return;
        }
      }
      if (result.warning) toast.warning(`Document atașat; ${result.warning}. Completează datele neidentificate manual.`);
      else toast.success("Document atașat și analizat; verifică datele extrase.");
    } catch (error) {
      toast.error(error?.response?.data?.detail || error?.message || "Nu am putut atașa documentul");
    }
  };
  const remove = async (slot, index) => {
    try {
      await persistDocs({ ...docs, [slot]: (docs[slot] || []).filter((_, i) => i !== index) });
      toast.success("Documente client actualizate");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Nu am putut actualiza documentele");
    }
  };
  return (
    <div className="mt-6" data-testid="client-docs">
      <h3 className="font-bold text-sm mb-1">Documentele clientului</h3>
      <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Încarcă o singură dată CI, factura și cartea funciară. Aplicația încearcă să extragă datele și completează doar câmpurile goale; verifică rezultatul înainte de folosire.</p>
      <div className="grid sm:grid-cols-2 gap-2">
        {SLOTS.map(([k, l]) => <Slot key={k} k={k} label={l} files={docs[k]} add={add}
          remove={(s, i) => remove(s, i)} />)}
      </div>
    </div>
  );
}
