import { useCallback, useEffect, useRef, useState } from "react";
import { Paperclip, Send } from "lucide-react";
import { toast } from "sonner";
import { api, API, fileUrl } from "@/lib/api";
import { Btn } from "@/components/Layout";

export function DossierMessages({ id }) {
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const picker = useRef(null);
  const load = useCallback(() => api.get(`/prosumator/${id}/messages`).then((r) => setMessages(r.data.messages || [])).catch(() => {}), [id]);
  useEffect(() => { load(); }, [load]);

  const upload = async (e) => {
    const selected = [...(e.target.files || [])];
    const available = Math.max(0, 5 - files.length);
    const accepted = selected.slice(0, available);
    const errors = selected.slice(available).map((file) => `${file.name}: poți atașa cel mult 5 fișiere`);
    if (!accepted.length) { toast.error("Poți atașa cel mult 5 fișiere"); e.target.value = ""; return; }
    setBusy(true);
    try {
      const uploaded = [];
      for (const file of accepted) {
        try {
          if (file.size > 10 * 1024 * 1024) throw new Error("depășește 10 MB");
          const fd = new FormData(); fd.append("file", file);
          const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } }); uploaded.push(data);
        } catch (err) { errors.push(`${file.name}: ${err.response?.data?.detail || err.message || "încărcare eșuată"}`); }
      }
      if (uploaded.length) setFiles((old) => [...old, ...uploaded]);
      if (errors.length) toast.error(`Unele fișiere nu s-au încărcat: ${errors.join("; ")}`);
      else if (uploaded.length) toast.success(`${uploaded.length} fișiere încărcate`);
    } finally { setBusy(false); e.target.value = ""; }
  };

  const send = async () => {
    if (!content.trim()) return;
    setBusy(true);
    try { await api.post(`/prosumator/${id}/messages`, { content: content.trim(), files }); setContent(""); setFiles([]); await load(); toast.success("Mesaj trimis"); }
    catch (e) { toast.error(e.response?.data?.detail || "Mesajul nu s-a putut trimite"); }
    finally { setBusy(false); }
  };

  return <section className="mt-5 rounded-xl border p-4" style={{ borderColor: "var(--line)" }} data-testid="dossier-messages">
    <div className="mb-3"><h3 className="font-bold">Mesaje către client</h3><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Clientul vede conversația în pagina deschisă din linkul de semnare. Notele interne se păstrează în jurnal.</p></div>
    <div className="mb-3 max-h-72 space-y-2 overflow-y-auto rounded-lg p-3" style={{ background: "var(--bg)" }}>
      {messages.length ? messages.map((m) => <article key={m.id} className={`max-w-[92%] rounded-lg border p-3 text-xs ${m.author_type === "client" ? "mr-auto" : "ml-auto"}`} style={{ borderColor: "var(--line)", background: "white" }} data-testid="dossier-message">
        <div className="mb-1 flex justify-between gap-3"><b>{m.author_type === "client" ? "Client" : m.author || "DNS Energy"}</b><time style={{ color: "var(--muted)" }}>{new Date(m.at).toLocaleString("ro-RO")}</time></div>
        <p className="whitespace-pre-wrap">{m.content}</p>
        {!!m.files?.length && <div className="mt-2 flex flex-wrap gap-2">{m.files.map((f, i) => <a key={i} href={fileUrl(f.storage_path)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline" style={{ color: "var(--blue)" }}>{f.original_filename || "Atașament"}</a>)}</div>}
      </article>) : <p className="py-6 text-center text-xs" style={{ color: "var(--muted)" }}>Nicio conversație încă.</p>}
    </div>
    <textarea className="den-input" rows={3} maxLength={2000} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Mesaj pentru client…" data-testid="dossier-message-input" />
    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <input ref={picker} type="file" multiple accept="application/pdf,image/*" className="hidden" onChange={upload} />
        <button type="button" disabled={busy || files.length >= 5} onClick={() => picker.current?.click()} className="inline-flex items-center gap-1 font-semibold" style={{ color: "var(--muted)" }} data-testid="dossier-message-attach"><Paperclip size={14} /> Atașează fișiere ({files.length}/5)</button>
        {files.map((f, i) => <button key={f.storage_path} onClick={() => setFiles((old) => old.filter((_, j) => j !== i))} title="Elimină atașamentul">{f.original_filename} ×</button>)}
      </div>
      <Btn disabled={busy || !content.trim()} onClick={send} data-testid="dossier-message-send"><Send size={14} /> Trimite clientului</Btn>
    </div>
  </section>;
}

export function ClientMessagePortal({ token }) {
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const picker = useRef(null);
  const url = `${API}/public/sign/${token}`;
  const load = useCallback(() => fetch(`${url}/messages`).then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.detail || "Nu s-au putut încărca mesajele"); setMessages(d.messages || []); }).catch(() => {}), [url]);
  useEffect(() => { load(); }, [load]);
  const upload = async (e) => {
    const selected = [...(e.target.files || [])];
    const available = Math.max(0, 5 - files.length);
    const accepted = selected.slice(0, available);
    const errors = selected.slice(available).map((file) => `${file.name}: poți atașa cel mult 5 fișiere`);
    if (!accepted.length) { toast.error("Poți atașa cel mult 5 fișiere"); e.target.value = ""; return; }
    setBusy(true);
    try {
      const uploaded = [];
      for (const file of accepted) {
        try {
          const fd = new FormData(); fd.append("file", file);
          const r = await fetch(`${url}/messages/upload`, { method: "POST", body: fd }); const d = await r.json();
          if (!r.ok) throw new Error(d.detail || "Fișier invalid"); uploaded.push(d);
        } catch (err) { errors.push(`${file.name}: ${err.message || "încărcare eșuată"}`); }
      }
      if (uploaded.length) setFiles((old) => [...old, ...uploaded]);
      if (errors.length) toast.error(`Unele fișiere nu s-au încărcat: ${errors.join("; ")}`);
      else if (uploaded.length) toast.success(`${uploaded.length} fișiere încărcate`);
    }
    finally { setBusy(false); e.target.value = ""; }
  };
  const send = async () => {
    if (!content.trim()) return;
    setBusy(true);
    try { const r = await fetch(`${url}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: content.trim(), files }) }); const d = await r.json(); if (!r.ok) throw new Error(d.detail || "Mesajul nu s-a putut trimite"); setContent(""); setFiles([]); await load(); }
    catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };
  return <section className="mt-5 rounded-xl border bg-white p-4" style={{ borderColor: "#dbe3ee" }} data-testid="client-message-portal">
    <h2 className="font-bold">Mesaje cu instalatorul</h2>
    <div className="mt-3 max-h-64 space-y-2 overflow-y-auto rounded-lg bg-[#f6f8fb] p-3">{messages.length ? messages.map((m) => <article key={m.id} className="rounded-lg border bg-white p-3 text-xs"><b>{m.author_type === "client" ? "Dvs." : m.author || "DNS Energy"}</b><p className="mt-1 whitespace-pre-wrap">{m.content}</p>{m.files?.map((f, i) => <a key={i} className="mt-1 block underline" style={{ color: "#2878f0" }} href={`${window.location.origin}${f.url}`} target="_blank" rel="noreferrer">{f.name}</a>)}</article>) : <p className="py-4 text-center text-xs text-slate-500">Nicio conversație încă.</p>}</div>
    <textarea className="den-input mt-3" rows={3} maxLength={2000} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Scrie un mesaj pentru instalator…" />
    <div className="mt-2 flex flex-wrap items-center justify-between gap-2"><input ref={picker} type="file" multiple accept="application/pdf,image/*" className="hidden" onChange={upload} /><button disabled={busy || files.length >= 5} onClick={() => picker.current?.click()} className="inline-flex items-center gap-1 text-xs"><Paperclip size={14} /> Atașează ({files.length}/5)</button><button disabled={busy || !content.trim()} onClick={send} className="inline-flex items-center gap-2 rounded-lg bg-[#2878f0] px-4 py-2 text-sm font-bold text-white disabled:opacity-40"><Send size={14} /> Trimite</button></div>
  </section>;
}
