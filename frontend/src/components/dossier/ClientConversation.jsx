import { useEffect, useRef, useState } from "react";
import { FileText, MessageCircle, Paperclip, Send, X } from "lucide-react";
import { api, formatApiErrorDetail, openAuthenticatedFile } from "@/lib/api";
import { toast } from "sonner";
import { uploadFile } from "@/components/dossier/ClientDocs";

export function ClientConversation({ dossierId }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [audience, setAudience] = useState("client");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);
  const load = async () => {
    try { const { data } = await api.get(`/dossier/${encodeURIComponent(dossierId)}/client-messages`); setMessages(data.messages || []); }
    catch (error) { toast.error(formatApiErrorDetail(error.response?.data?.detail) || "Nu am putut încărca mesajele dosarului."); }
  };
  useEffect(() => { load(); }, [dossierId]);
  const send = async (event) => {
    event.preventDefault();
    if ((!text.trim() && !files.length) || busy) return;
    setBusy(true);
    try {
      const attachments = audience === "client" ? await Promise.all(files.map(uploadFile)) : [];
      await api.post(`/dossier/${encodeURIComponent(dossierId)}/client-messages`, { text: text.trim(), audience, attachments });
      setText(""); setFiles([]); await load();
      toast.success(audience === "client" ? "Mesajul apare în pagina securizată a clientului." : "Nota internă a fost adăugată în dosar.");
    } catch (error) { toast.error(formatApiErrorDetail(error.response?.data?.detail) || "Mesajul nu a putut fi salvat."); }
    finally { setBusy(false); }
  };
  return <section className="mt-4 rounded-xl border bg-white p-4" style={{ borderColor: "var(--line)" }} data-testid="client-conversation">
    <div className="flex items-center gap-2"><MessageCircle size={16} style={{ color: "var(--blue)" }} /><h3 className="text-sm font-bold">Comunicare cu clientul</h3><span className="ml-auto text-[11px]" style={{ color: "var(--muted)" }}>{messages.length} mesaje</span></div>
    <p className="mt-1 text-xs leading-5" style={{ color: "var(--muted)" }}>Mesajele către client apar pe linkul activ de semnare al dosarului. Notele interne rămân vizibile doar echipei DNS.</p>
    <div className="mt-3 max-h-64 space-y-2 overflow-y-auto" data-testid="client-conversation-list">
      {!messages.length && <p className="rounded-lg p-3 text-xs" style={{ background: "#f8fafd", color: "var(--muted)" }}>Nu există mesaje în acest dosar.</p>}
      {messages.map((message) => <article key={message.id} className="rounded-lg border p-3" style={{ borderColor: "var(--line)", background: message.audience === "internal" ? "#fffaf0" : "#f8fafd" }}>
        <div className="flex flex-wrap justify-between gap-2 text-[11px] font-semibold"><span>{message.sender === "client" ? "Client" : message.sender_name || "Echipa DNS"}{message.audience === "internal" ? " · notă internă" : ""}</span><time style={{ color: "var(--muted)" }}>{message.created_at ? new Date(message.created_at).toLocaleString("ro-RO") : ""}</time></div>
        {message.text && <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-5">{message.text}</p>}
        {!!message.attachments?.length && <div className="mt-2 flex flex-wrap gap-2">{message.attachments.map((file, index) => <button type="button" key={file.storage_path || index} className="inline-flex items-center gap-1 text-xs underline" style={{ color: "var(--blue)" }} onClick={() => openAuthenticatedFile(`/files/${file.storage_path}`)}><FileText size={12} />{file.original_filename || "Atașament"}</button>)}</div>}
      </article>)}
    </div>
    <form className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_150px_auto]" onSubmit={send}>
      <textarea className="den-input min-h-10" rows={2} maxLength={2000} value={text} onChange={(event) => setText(event.target.value)} placeholder="Scrie un mesaj pentru client sau o notă internă…" data-testid="client-message-text" />
      <select className="den-input" value={audience} onChange={(event) => setAudience(event.target.value)} data-testid="client-message-audience"><option value="client">Vizibil clientului</option><option value="internal">Doar echipa DNS</option></select>
      <div className="flex gap-2"><input ref={inputRef} type="file" multiple accept="application/pdf,image/*,.doc,.docx,.xlsx" className="hidden" onChange={(event) => { const chosen = Array.from(event.target.files || []); setFiles((current) => [...current, ...chosen].slice(0, 5)); event.target.value = ""; }} />
        <button type="button" title="Atașează fișiere" className="inline-flex min-h-10 items-center justify-center rounded-lg border px-3" style={{ borderColor: "var(--line)" }} disabled={busy || audience === "internal" || files.length >= 5} onClick={() => inputRef.current?.click()}><Paperclip size={15} /></button>
        <button className="inline-flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg px-3 text-xs font-bold text-white disabled:opacity-50" style={{ background: "var(--blue)" }} disabled={busy || (!text.trim() && files.length === 0)} data-testid="client-message-send"><Send size={14} />{busy ? "Se salvează…" : "Trimite"}</button></div>
    </form>
    {!!files.length && <ul className="mt-2 space-y-1">{files.map((file, index) => <li key={`${file.name}-${index}`} className="flex items-center gap-2 text-xs"><FileText size={12} />{file.name}<button type="button" aria-label={`Elimină ${file.name}`} onClick={() => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))}><X size={12} /></button></li>)}</ul>}
    <p className="mt-2 text-[10px] leading-4" style={{ color: "var(--muted)" }}>Mesajele nu se trimit prin e-mail. Clientul le vede când deschide linkul activ primit pentru semnare; răspunsurile sale apar aici.</p>
  </section>;
}
