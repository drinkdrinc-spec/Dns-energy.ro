import { useState } from "react";
import { Sparkles, Copy, MessageCircle, Smartphone, Mail } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { streamAI } from "@/lib/ai";

export function AiClientMessage({ dossierId, items, linkOf, onSent }) {
  const [channel, setChannel] = useState("whatsapp");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const r0 = items[0].r;
  const gen = async () => {
    setBusy(true); setText("");
    try { await streamAI("/ai/sign-message", { dossier_id: dossierId, channel, links: items.map(({ r, token }) => ({ title: r.doc_title, url: linkOf(token) })) }, setText); }
    catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };
  const sent = async (ch) => { await Promise.all(items.map(({ r }) => api.post(`/sign/requests/${r.id}/sent`, { channel: `${ch} (mesaj AI)` }))); onSent(); };
  const subj = text.match(/^Subiect:\s*(.+)$/m)?.[1] || "Documente de semnat";
  const body = text.replace(/^Subiect:.*\n?/m, "").trim();
  const phone = (r0.signer_phone || "").replace(/\D/g, "").replace(/^0(?=7)/, "40");
  return (
    <div className="rounded-lg border p-3 mb-3 text-xs" style={{ borderColor: "var(--line)", background: "#f7fbff" }} data-testid="ai-client-message">
      <div className="flex flex-wrap items-center gap-2">
        <b className="inline-flex items-center gap-1"><Sparkles size={13} style={{ color: "var(--blue)" }} /> Mesaj AI pentru client — {items.length} linkuri într-un singur mesaj</b>
        <select className="den-input !py-1 !text-xs" style={{ width: 120 }} value={channel} onChange={(e) => setChannel(e.target.value)} data-testid="ai-msg-channel">
          <option value="whatsapp">WhatsApp</option><option value="sms">SMS</option><option value="email">E-mail</option></select>
        <button className="font-bold" style={{ color: "var(--blue)" }} onClick={gen} disabled={busy} data-testid="ai-msg-generate">{busy ? "Se scrie..." : "Scrie mesajul"}</button>
      </div>
      {text && <>
        <textarea className="den-input mt-2" rows={8} value={text} onChange={(e) => setText(e.target.value)} data-testid="ai-msg-text" />
        <div className="flex flex-wrap gap-3 mt-2">
          <button className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} onClick={() => { navigator.clipboard?.writeText(body); toast.success("Mesaj copiat"); sent("copiat"); }} data-testid="ai-msg-copy"><Copy size={13} /> Copiază</button>
          <a className="inline-flex items-center gap-1 font-bold" style={{ color: "#15803d" }} href={`https://wa.me/${phone}?text=${encodeURIComponent(body)}`} target="_blank" rel="noopener noreferrer" onClick={() => sent("WhatsApp")} data-testid="ai-msg-whatsapp"><MessageCircle size={13} /> WhatsApp</a>
          <a className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} href={`sms:${r0.signer_phone || ""}?&body=${encodeURIComponent(body)}`} onClick={() => sent("SMS")} data-testid="ai-msg-sms"><Smartphone size={13} /> SMS</a>
          <a className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} href={`mailto:${r0.signer_email}?subject=${encodeURIComponent(subj)}&body=${encodeURIComponent(body)}`} onClick={() => sent("e-mail")} data-testid="ai-msg-email"><Mail size={13} /> E-mail</a>
        </div>
        <p className="mt-1" style={{ color: "var(--muted)" }}>Verifică textul și linkurile înainte de trimitere.</p>
      </>}
    </div>
  );
}
