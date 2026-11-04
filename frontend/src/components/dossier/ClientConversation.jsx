import { useEffect, useState } from "react";
import { MessageCircle, Send } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";

export function ClientConversation({ dossierId }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [audience, setAudience] = useState("client");
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try { const { data } = await api.get(`/dossier/${encodeURIComponent(dossierId)}/client-messages`); setMessages(data.messages || []); }
    catch (error) { toast.error(formatApiErrorDetail(error.response?.data?.detail) || "Nu am putut încărca mesajele dosarului."); }
  };
  useEffect(() => { load(); }, [dossierId]);
  const send = async (event) => {
    event.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      await api.post(`/dossier/${encodeURIComponent(dossierId)}/client-messages`, { text: text.trim(), audience });
      setText(""); await load();
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
        <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-5">{message.text}</p>
      </article>)}
    </div>
    <form className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_150px_auto]" onSubmit={send}>
      <textarea className="den-input min-h-10" rows={2} maxLength={2000} value={text} onChange={(event) => setText(event.target.value)} placeholder="Scrie un mesaj pentru client sau o notă internă…" data-testid="client-message-text" />
      <select className="den-input" value={audience} onChange={(event) => setAudience(event.target.value)} data-testid="client-message-audience"><option value="client">Vizibil clientului</option><option value="internal">Doar echipa DNS</option></select>
      <button className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-3 text-xs font-bold text-white disabled:opacity-50" style={{ background: "var(--blue)" }} disabled={busy || !text.trim()} data-testid="client-message-send"><Send size={14} />{busy ? "Se salvează…" : "Adaugă mesaj"}</button>
    </form>
    <p className="mt-2 text-[10px] leading-4" style={{ color: "var(--muted)" }}>Mesajele nu se trimit prin e-mail. Clientul le vede când deschide linkul activ primit pentru semnare; răspunsurile sale apar aici.</p>
  </section>;
}
