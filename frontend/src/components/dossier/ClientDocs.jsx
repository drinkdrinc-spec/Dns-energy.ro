import { useRef } from "react";
import { api, fileUrl } from "@/lib/api";
import { Upload, FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";

const SLOTS = [["factura", "Factură furnizor de energie"], ["certificat", "Certificat de înregistrare (PJ)"], ["constatator", "Certificat constatator (PJ)"],
  ["ci", "Act de identitate (PF / reprezentant)"], ["cf", "Extras de carte funciară"]];

export const uploadFile = async (file) => {
  const fd = new FormData(); fd.append("file", file);
  const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
  return data;
};

function Slot({ k, label, files, add, remove }) {
  const ref = useRef();
  return (
    <div className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }} data-testid={`client-doc-${k}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-bold">{label}</span>
        <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" data-testid={`client-doc-input-${k}`}
          onChange={async (e) => { const f = e.target.files?.[0]; if (f) { await add(k, await uploadFile(f)); ref.current.value = ""; } }} />
        <button onClick={() => ref.current.click()} className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} data-testid={`client-doc-upload-${k}`}><Upload size={13} /> Încarcă</button>
      </div>
      {(files || []).map((f, i) => (
        <div key={f.storage_path} className="flex items-center justify-between text-xs mt-2">
          <a href={fileUrl(f.storage_path)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline" style={{ color: "var(--blue)" }}><FileText size={12} /> {f.original_filename}</a>
          <button onClick={() => remove(k, i)} data-testid={`client-doc-remove-${k}-${i}`}><Trash2 size={13} style={{ color: "#b33333" }} /></button>
        </div>
      ))}
    </div>
  );
}

export function ClientDocs({ client, onChange }) {
  const docs = client.docs || {};
  const persist = async (next) => {
    await api.put(`/data/clients/${client.id}`, { docs: next });
    onChange(next); toast.success("Documente client actualizate");
  };
  return (
    <div className="mt-6" data-testid="client-docs">
      <h3 className="font-bold text-sm mb-1">Documentele clientului</h3>
      <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Se încarcă o singură dată și se preiau automat în toate dosarele clientului (pozițiile 11–13 din opis).</p>
      <div className="grid sm:grid-cols-2 gap-2">
        {SLOTS.map(([k, l]) => <Slot key={k} k={k} label={l} files={docs[k]} add={(s, f) => persist({ ...docs, [s]: [...(docs[s] || []), f] })}
          remove={(s, i) => persist({ ...docs, [s]: (docs[s] || []).filter((_, j) => j !== i) })} />)}
      </div>
    </div>
  );
}
