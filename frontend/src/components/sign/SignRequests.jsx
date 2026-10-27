import { useEffect, useState } from "react";
import { api, API } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Copy, Link2, Ban, RefreshCw, FileDown, ChevronDown, Plus, Trash2, MessageCircle, Mail, Smartphone } from "lucide-react";
import { toast } from "sonner";

const BADGE = { "De trimis": ["#f1f5f9", "#334155"], "Link trimis": ["#eef4ff", "#1d4ed8"], Deschis: ["#fff8e6", "#8a5a00"], Semnat: ["#ecfdf3", "#166534"],
  Refuzat: ["#fff0f0", "#9b2c2c"], Expirat: ["#f3f4f6", "#6b7280"] };
const linkOf = (t) => `${window.location.origin}/semneaza/${t}`;

function LinkBox({ r, token, onSent }) {
  const url = linkOf(token);
  const text = `Bună ziua, ${r.signer_name}. Vă rugăm să semnați documentul „${r.doc_title}”: ${url}`;
  const sent = (channel) => api.post(`/sign/requests/${r.id}/sent`, { channel }).then(onSent);
  return (
    <div className="mt-2 rounded-lg p-3 text-xs" style={{ background: "#eef4ff" }} data-testid={`sign-link-${r.id}`}>
      <div className="font-bold mb-1">Link de semnare (se afișează o singură dată — copiază-l acum):</div>
      <div className="break-all font-mono mb-2" data-testid="sign-link-url">{url}</div>
      <div className="flex flex-wrap gap-2">
        <button className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} onClick={() => { navigator.clipboard?.writeText(url); toast.success("Link copiat"); sent("copiat"); }} data-testid="sign-copy"><Copy size={13} /> Copiază</button>
        <a className="inline-flex items-center gap-1 font-bold" style={{ color: "#15803d" }} href={`https://wa.me/${(r.signer_phone || "").replace(/\D/g, "").replace(/^0(?=7)/, "40")}?text=${encodeURIComponent(text)}`} target="_blank" rel="noopener noreferrer" onClick={() => sent("WhatsApp")} data-testid="sign-whatsapp"><MessageCircle size={13} /> WhatsApp</a>
        <a className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} href={`sms:${r.signer_phone || ""}?&body=${encodeURIComponent(text)}`} onClick={() => sent("SMS")} data-testid="sign-sms"><Smartphone size={13} /> SMS</a>
        <a className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} href={`mailto:${r.signer_email}?subject=${encodeURIComponent("Document de semnat — " + r.doc_title)}&body=${encodeURIComponent(text)}`} onClick={() => sent("e-mail")} data-testid="sign-mailto"><Mail size={13} /> E-mail</a>
      </div>
    </div>
  );
}

function Req({ r, token, reload, setToken }) {
  const [open, setOpen] = useState(false);
  const [bg, fg] = BADGE[r.status] || BADGE["De trimis"];
  const act = async (path, body = {}) => {
    try { const { data } = await api.post(`/sign/requests/${r.id}/${path}`, body); if (data.token) setToken(r.id, data.token); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
  };
  const closed = ["Semnat", "Refuzat"].includes(r.status);
  return (
    <div className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }} data-testid={`sign-req-${r.id}`}>
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div>
          <div className="font-bold text-sm">{r.doc_title}</div>
          <div className="text-xs" style={{ color: "var(--muted)" }}>{r.signer_name} · {r.role} · {r.signer_email}{r.client_name ? ` · ${r.client_name}` : ""} · expiră {new Date(r.expires_at).toLocaleString("ro-RO")}</div>
          {r.refused_reason && <div className="text-xs" style={{ color: "#9b2c2c" }}>Motiv refuz: {r.refused_reason}</div>}
        </div>
        <span className="text-[11px] font-bold rounded-full px-2.5 py-1" style={{ background: bg, color: fg }} data-testid={`sign-status-${r.id}`}>{r.status}{r.revoked ? " (revocat)" : ""}</span>
      </div>
      {token && !closed && r.status !== "Expirat" && !r.revoked && <LinkBox r={r} token={token} onSent={reload} />}
      <div className="flex flex-wrap gap-3 mt-2 text-xs">
        {!closed && <button className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} onClick={() => act("new-link", { expires_days: 7 })} data-testid={`sign-newlink-${r.id}`}><RefreshCw size={13} /> {token ? "Link nou" : "Generează link nou / retrimite"}</button>}
        {!closed && r.status !== "Expirat" && <button className="inline-flex items-center gap-1 font-bold" style={{ color: "#9b2c2c" }} onClick={() => window.confirm("Revoci linkul?") && act("revoke")} data-testid={`sign-revoke-${r.id}`}><Ban size={13} /> Revocă</button>}
        {r.has_signed_file && <a className="inline-flex items-center gap-1 font-bold" style={{ color: "#166534" }} href={`${API}/sign/requests/${r.id}/file?auth=${localStorage.getItem("den_token")}`} target="_blank" rel="noopener noreferrer" data-testid={`sign-download-${r.id}`}><FileDown size={13} /> PDF semnat</a>}
        <button className="inline-flex items-center gap-1" onClick={() => setOpen(!open)} data-testid={`sign-history-${r.id}`}><ChevronDown size={13} /> Istoric ({r.history.length})</button>
      </div>
      {open && <div className="mt-2 text-[11px] space-y-1" data-testid={`sign-history-list-${r.id}`}>{r.history.map((h, i) => <div key={i}><b>{new Date(h.at).toLocaleString("ro-RO")}</b> — {h.action}{h.detail ? `: ${h.detail}` : ""}{h.ip ? ` · IP ${h.ip}` : ""}</div>)}
        <div style={{ color: "var(--muted)" }}>SHA-256 document: {r.doc_sha256}{r.signed_sha256 ? ` · PDF semnat: ${r.signed_sha256}` : ""}</div></div>}
    </div>
  );
}

function CreateForm({ dossierId, onCreated }) {
  const [positions, setPositions] = useState([]);
  const [keys, setKeys] = useState([]);
  const [signers, setSigners] = useState([{ name: "", email: "", phone: "", role: "Beneficiar" }]);
  const [days, setDays] = useState(7);
  useEffect(() => { api.get(`/dossier/${dossierId}`).then((r) => setPositions(r.data.positions.filter((p) => p.source === "generat"))); }, [dossierId]);
  const upd = (i, k, v) => setSigners(signers.map((s, j) => (j === i ? { ...s, [k]: v } : s)));
  const create = async () => {
    try { const { data } = await api.post("/sign/requests", { dossier_id: dossierId, pos_keys: keys, signers, expires_days: days }); onCreated(data); setKeys([]); toast.success(`${data.length} cereri de semnare create`); }
    catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
  };
  return (
    <div className="rounded-lg border bg-white p-3 mb-3" style={{ borderColor: "var(--line)" }} data-testid="sign-create">
      <div className="text-xs font-bold mb-2">Documente de semnat</div>
      <div className="grid sm:grid-cols-2 gap-1 mb-3">{positions.map((p) => (
        <label key={p.key} className="text-xs flex gap-2 items-center"><input type="checkbox" checked={keys.includes(p.key)} onChange={(e) => setKeys(e.target.checked ? [...keys, p.key] : keys.filter((k) => k !== p.key))} data-testid={`sign-pick-${p.key}`} />{p.nr}. {p.title}</label>))}</div>
      <div className="text-xs font-bold mb-1">Semnatari (codul de verificare se trimite pe e-mail)</div>
      {signers.map((s, i) => (
        <div key={i} className="grid sm:grid-cols-[1fr_1fr_140px_140px_30px] gap-2 mb-2">
          <input className="den-input" placeholder="Nume complet" value={s.name} onChange={(e) => upd(i, "name", e.target.value)} data-testid={`signer-name-${i}`} />
          <input className="den-input" placeholder="E-mail" value={s.email} onChange={(e) => upd(i, "email", e.target.value)} data-testid={`signer-email-${i}`} />
          <input className="den-input" placeholder="Telefon (WhatsApp/SMS)" value={s.phone} onChange={(e) => upd(i, "phone", e.target.value)} data-testid={`signer-phone-${i}`} />
          <input className="den-input" placeholder="Rol" value={s.role} onChange={(e) => upd(i, "role", e.target.value)} data-testid={`signer-role-${i}`} />
          <button onClick={() => setSigners(signers.filter((_, j) => j !== i))}><Trash2 size={14} style={{ color: "#b33333" }} /></button>
        </div>))}
      <div className="flex flex-wrap items-center gap-3">
        <button className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => setSigners([...signers, { name: "", email: "", phone: "", role: "" }])} data-testid="signer-add"><Plus size={13} /> Semnatar</button>
        <label className="text-xs">Valabilitate link (zile, invalid oricum după semnare): <input type="number" min={1} max={90} className="den-input inline-block w-20 ml-1" value={days} onChange={(e) => setDays(Number(e.target.value))} data-testid="sign-days" /></label>
        <Btn onClick={create} disabled={!keys.length} data-testid="sign-create-btn"><Link2 size={14} /> Generează linkuri</Btn>
      </div>
    </div>
  );
}

export function SignRequests({ dossierId, clientName }) {
  const [list, setList] = useState([]);
  const [tokens, setTokens] = useState({});
  const [show, setShow] = useState(false);
  const q = dossierId ? `?dossier_id=${dossierId}` : clientName ? `?client_name=${encodeURIComponent(clientName)}` : "";
  const load = () => api.get(`/sign/requests${q}`).then((r) => setList(r.data)).catch(() => {});
  useEffect(() => { load(); }, [q]); // eslint-disable-line
  return (
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="sign-section">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <div><h3 className="font-bold">Semnături</h3><p className="text-[11px]" style={{ color: "var(--muted)" }}>Semnătură electronică simplă (eIDAS) cu cod pe e-mail și fișă de evidență — nu este semnătură calificată.</p></div>
        {dossierId && <Btn variant="secondary" onClick={() => setShow(!show)} data-testid="sign-new-toggle"><Plus size={14} /> Cerere de semnare</Btn>}
      </div>
      {show && dossierId && <CreateForm dossierId={dossierId} onCreated={(rs) => { setTokens({ ...tokens, ...Object.fromEntries(rs.map((r) => [r.id, r.token])) }); setShow(false); load(); }} />}
      <div className="space-y-2">{list.length ? list.map((r) => <Req key={r.id} r={r} token={tokens[r.id]} reload={load} setToken={(id, t) => setTokens({ ...tokens, [id]: t })} />)
        : <p className="text-xs" style={{ color: "var(--muted)" }}>Nicio cerere de semnare.</p>}</div>
    </div>
  );
}
