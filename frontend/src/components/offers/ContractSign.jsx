import { useState } from "react";
import { toast } from "sonner";
import { Copy, MessageCircle, Mail, FileDown } from "lucide-react";
import { api, openAuthenticatedFile } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export function ContractSign({ c, open, onClose, onDone }) {
  const [s, setS] = useState({ name: "", email: "", phone: "" });
  const [res, setRes] = useState(null);
  const [reqs, setReqs] = useState([]);
  const init = () => {
    api.get(`/contracts/${c.id}`).then((r) => { const b = r.data.offer?.beneficiary || {}; setS((x) => ({ name: x.name || b.name || "", email: x.email || b.email || "", phone: x.phone || b.phone || "" })); });
    api.get(`/contracts/${c.id}/sign-requests`).then((r) => setReqs(r.data));
  };
  const link = res ? `${window.location.origin}/semneaza/${res.token}` : "";
  const create = async () => { try { const { data } = await api.post(`/contracts/${c.id}/sign`, { signer: s }); setRes(data); onDone(); toast.success("Link de semnare generat (valabil 7 zile)"); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  const sent = (ch) => res && api.post(`/sign/requests/${res.id}/sent`, { channel: ch });
  const msg = `Bună ziua, vă transmitem spre semnare electronică ${res?.doc_title || "contractul"}: ${link} (link valabil 7 zile; codul de verificare îl primiți pe e-mail).`;
  return (
    <Dialog open={open} onOpenChange={(v) => { if (v) init(); else { setRes(null); onClose(); } }}>
      <DialogContent className="max-w-xl" data-testid="contract-sign-dialog" onOpenAutoFocus={init}>
        <DialogHeader><DialogTitle>Semnare online — contract nr. {c.number}</DialogTitle></DialogHeader>
        {!res ? <>
          <p className="text-xs" style={{ color: "var(--muted)" }}>Clientul primește un link separat pentru contract (inclusiv Anexele 1 și 2). Varianta semnată se salvează automat la contract și în Documente.</p>
          {[["name", "Nume beneficiar / reprezentant"], ["email", "E-mail (pentru codul de verificare)"], ["phone", "Telefon"]].map(([k, l]) => (
            <div key={k} className="den-field"><label>{l}</label><input className="den-input" value={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.value })} data-testid={`csign-${k}`} /></div>))}
          {reqs.length > 0 && <div className="text-xs" data-testid="csign-history">Cereri anterioare: {reqs.map((r) => `${r.status} (${new Date(r.created_at).toLocaleDateString("ro-RO")})`).join(", ")}</div>}
          <div className="flex justify-end gap-2"><Btn variant="secondary" onClick={onClose}>Anulează</Btn><Btn onClick={create} data-testid="csign-create">Generează linkul</Btn></div>
        </> : <div className="space-y-2 text-sm" data-testid="csign-result">
          <div className="den-input !text-xs break-all" data-testid="csign-link">{link}</div>
          <div className="flex flex-wrap gap-3 text-xs font-bold">
            <button className="inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => { navigator.clipboard?.writeText(link); toast.success("Link copiat"); sent("copiat"); }} data-testid="csign-copy"><Copy size={13} /> Copiază</button>
            <a className="inline-flex items-center gap-1" style={{ color: "#15803d" }} href={`https://wa.me/${s.phone.replace(/\D/g, "").replace(/^0(?=7)/, "40")}?text=${encodeURIComponent(msg)}`} target="_blank" rel="noopener noreferrer" onClick={() => sent("WhatsApp")} data-testid="csign-whatsapp"><MessageCircle size={13} /> WhatsApp</a>
            <a className="inline-flex items-center gap-1" style={{ color: "var(--blue)" }} href={`mailto:${s.email}?subject=${encodeURIComponent(`Contract nr. ${c.number} — semnare`)}&body=${encodeURIComponent(msg)}`} onClick={() => sent("e-mail")} data-testid="csign-email"><Mail size={13} /> E-mail</a>
          </div></div>}
      </DialogContent>
    </Dialog>
  );
}

export const SignedLink = ({ c }) => c.signed ? <button type="button" onClick={() => openAuthenticatedFile(`/contracts/${c.id}/signed-pdf`)} title="Contract semnat" aria-label="Deschide contractul semnat" data-testid={`contract-signed-pdf-${c.number}`}><FileDown size={16} style={{ color: "#166534" }} /></button> : null;
