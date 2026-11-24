import { useEffect, useRef, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { MODULES } from "@/config/modules";
import { PageHeader, Btn } from "@/components/Layout";
import { Upload, FileText, Trash2, Download } from "lucide-react";
import { toast } from "sonner";

const DOC_TYPES = {
  PF: ["Carte de identitate", "Adeverință domiciliu", "Factură de energie", "Carte funciară", "ATR", "Alt document"],
  PJ: ["CUI", "Certificat constatator", "CI administrator", "ATR", "Factură de energie", "Carte funciară", "Alt document"],
};

export default function Documents() {
  const [clients, setClients] = useState([]);
  const [docs, setDocs] = useState([]);
  const [clientId, setClientId] = useState("");
  const [kind, setKind] = useState("PF");
  const [docType, setDocType] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef();

  const load = () => {
    api.get("/data/clients").then((r) => setClients(r.data)).catch(() => {});
    api.get("/data/documents").then((r) => setDocs(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!clientId) return toast.error("Alege clientul");
    if (!file) return toast.error("Alege un fișier");
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const client = clients.find((c) => c.id === clientId);
      await api.post("/data/documents", {
        client_id: clientId, client_name: client?.name || "", kind, doc_type: docType || "Document",
        storage_path: data.storage_path, original_filename: data.original_filename,
        content_type: data.content_type, size: data.size,
      });
      toast.success("Document încărcat");
      fileRef.current.value = ""; setDocType(""); load();
    } catch (e) { toast.error("Eroare la încărcare"); }
    finally { setUploading(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("Ștergi documentul?")) return;
    await api.delete(`/data/documents/${id}`); toast.success("Șters"); load();
  };

  return (
    <div>
      <PageHeader eyebrow="Arhivă de lucru" title="Documente client"
        sub="Încarcă documente PDF și fotografii, asociate unui client și unui tip de solicitant. Stocare persistentă reală." />

      <div className="den-panel mb-6">
        <h2 className="text-lg font-bold mb-5">Încărcare document</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="den-field"><label>Client</label>
            <select className="den-input" data-testid="doc-client" value={clientId} onChange={(e) => setClientId(e.target.value)}>
              <option value="">Alege client</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{MODULES.clients.display(c)}</option>)}
            </select>
          </div>
          <div className="den-field"><label>Tip solicitant</label>
            <select className="den-input" value={kind} onChange={(e) => { setKind(e.target.value); setDocType(""); }}>
              <option value="PF">Persoană fizică</option><option value="PJ">Persoană juridică</option>
            </select>
          </div>
          <div className="den-field"><label>Tip document</label>
            <select className="den-input" value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="">Alege...</option>{DOC_TYPES[kind].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="den-field"><label>Fișier (PDF, imagine, document)</label>
            <input ref={fileRef} data-testid="doc-file" className="den-input" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx" />
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <Btn onClick={upload} disabled={uploading} data-testid="upload-btn"><Upload size={15} /> {uploading ? "Se încarcă..." : "Încarcă document"}</Btn>
        </div>
      </div>

      <div className="den-panel">
        <h2 className="text-lg font-bold mb-4">Documente încărcate ({docs.length})</h2>
        {docs.length === 0 ? (
          <div className="text-sm py-8 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>Nu sunt documente încărcate.</div>
        ) : (
          <div className="divide-y" style={{ borderColor: "var(--line)" }}>
            {docs.map((d) => (
              <div key={d.id} className="flex items-center gap-3 py-3">
                <div className="h-9 w-9 rounded-lg grid place-items-center" style={{ background: "#eef4ff" }}><FileText size={18} style={{ color: "var(--blue)" }} /></div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-sm truncate">{d.original_filename}</div>
                  <div className="text-[12px]" style={{ color: "var(--muted)" }}>{d.client_name} · {d.kind} · {d.doc_type}</div>
                </div>
                <a href={fileUrl(d.storage_path)} target="_blank" rel="noopener noreferrer" className="p-2 rounded hover:bg-[#eef4ff]" data-testid={`download-${d.id}`}><Download size={16} style={{ color: "var(--blue)" }} /></a>
                <button onClick={() => remove(d.id)} className="p-2 rounded hover:bg-[#fff0f0]" data-testid={`del-doc-${d.id}`}><Trash2 size={16} style={{ color: "#b33333" }} /></button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
