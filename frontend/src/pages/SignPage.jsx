import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { BrandMark } from "@/components/BrandMark";
import { CheckCircle2, Download, FileText, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/public/sign`;

function Pad({ onChange }) {
  const ref = useRef();
  const drawing = useRef(false);
  const [has, setHas] = useState(false);
  useEffect(() => {
    const c = ref.current; const r = c.getBoundingClientRect();
    c.width = r.width * 2; c.height = r.height * 2;
    const ctx = c.getContext("2d"); ctx.scale(2, 2); ctx.lineWidth = 2.4; ctx.lineCap = "round"; ctx.strokeStyle = "#0b1f3a";
  }, []);
  const pos = (e) => { const r = ref.current.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  const down = (e) => { drawing.current = true; const ctx = ref.current.getContext("2d"); ctx.beginPath(); ctx.moveTo(...pos(e)); ref.current.setPointerCapture(e.pointerId); };
  const move = (e) => { if (!drawing.current) return; const ctx = ref.current.getContext("2d"); ctx.lineTo(...pos(e)); ctx.stroke(); setHas(true); };
  const up = () => { if (drawing.current) { drawing.current = false; onChange(ref.current.toDataURL("image/png")); } };
  const clear = () => { const c = ref.current; c.getContext("2d").clearRect(0, 0, c.width, c.height); setHas(false); onChange(null); };
  return (
    <div>
      <canvas ref={ref} className="w-full h-40 rounded-lg border-2 border-dashed bg-white touch-none" style={{ borderColor: "#b8c4d6" }}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerLeave={up} data-testid="sign-pad" />
      <div className="flex justify-between text-xs mt-1" style={{ color: "#5a6b85" }}><span>{has ? "Semnătură trasată" : "Semnează cu degetul sau mouse-ul"}</span><button onClick={clear} data-testid="sign-pad-clear">Șterge</button></div>
    </div>
  );
}


function ClientPortal({ info, token, messages, reply, setReply, onReply, busy, notice, onRefresh, refreshing }) {
  const portal = info.portal;
  const activeIndex = Number.isInteger(portal.stage_index) ? portal.stage_index : -1;
  return <>
    <header className="mb-5 rounded-2xl bg-white p-5 shadow-sm" data-testid="client-portal-header">
      <div className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "#2878f0" }}>{info.company} · portal client</div>
      <h1 className="mt-1 text-2xl font-extrabold">Dosarul tău</h1>
      <p className="mt-1 text-sm" style={{ color: "#5a6b85" }}>{info.client_name}{info.signed_at ? \` · semnat la \${new Date(info.signed_at).toLocaleString("ro-RO")}\` : ""}</p>
    </header>
    <section className="mb-4 rounded-2xl border bg-white p-4" style={{ borderColor: "#dbe3ee" }} data-testid="client-portal-status">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><p className="text-xs font-semibold" style={{ color: "#5a6b85" }}>Stadiul curent</p><h2 className="text-lg font-extrabold">{portal.status}</h2></div>
        <button type="button" onClick={onRefresh} disabled={refreshing} className="inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 text-xs font-bold disabled:opacity-60" style={{ borderColor: "#dbe3ee", color: "#2878f0" }} data-testid="client-portal-refresh"><RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />Actualizează</button>
      </div>
      {activeIndex >= 0 && <ol className="mt-4 grid gap-2 sm:grid-cols-2" aria-label="Etapele dosarului">
        {portal.stages.map((stage, index) => <li key={stage} className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs" style={{ background: index === activeIndex ? "#eaf1ff" : "#f8fafd", color: index <= activeIndex ? "#173968" : "#76859a", fontWeight: index === activeIndex ? 700 : 500 }} aria-current={index === activeIndex ? "step" : undefined}>
          <CheckCircle2 size={15} style={{ color: index <= activeIndex ? "#2878f0" : "#aab5c4", flex: "none" }} />{stage}
        </li>)}
      </ol>}
      {portal.signed_document_available && <a href={\`\${API}/\${token}/signed-document\`} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold text-white sm:w-auto" style={{ background: "#2878f0" }} data-testid="client-portal-signed-download"><Download size={16} />Descarcă documentul semnat</a>}
      <p className="mt-3 text-[11px]" style={{ color: "#6b7789" }}>Linkul portalului este valabil 180 de zile de la semnare. Păstrează-l privat.</p>
    </section>
    <section className="rounded-2xl border bg-white p-4" style={{ borderColor: "#dbe3ee" }} data-testid="sign-client-messages">
      <h2 className="text-sm font-bold">Mesaje despre dosar</h2>
      <div className="mt-3 max-h-64 space-y-2 overflow-y-auto" data-testid="sign-client-message-list">
        {!messages.length && <p className="text-xs" style={{ color: "#5a6b85" }}>Nu există mesaje în acest dosar.</p>}
        {messages.map((item) => <article key={item.id} className="rounded-lg border p-3" style={{ borderColor: "#dbe3ee", background: "#f8fafd" }}>
          <div className="flex justify-between gap-2 text-[11px] font-semibold"><span>{item.sender === "client" ? "Tu" : item.sender_name || "Echipa DNS"}</span><time style={{ color: "#5a6b85" }}>{item.created_at ? new Date(item.created_at).toLocaleString("ro-RO") : ""}</time></div>
          {item.text && <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-5">{item.text}</p>}
          {!!item.attachments?.length && <div className="mt-2 flex flex-wrap gap-2">{item.attachments.map((file, index) => <a key={\`\${item.id}-\${index}\`} href={\`\${API}/\${token}/message-files/\${encodeURIComponent(item.id)}/\${index}\`} className="inline-flex items-center gap-1 text-xs underline" style={{ color: "#2878f0" }}><FileText size={12} />{file.original_filename || "Atașament"}</a>)}</div>}
        </article>)}
      </div>
      <form className="mt-3 space-y-2" onSubmit={onReply}>
        <textarea className="den-input" rows={2} maxLength={2000} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Scrie un mesaj către echipa DNS…" data-testid="sign-client-message-input" />
        <button className="min-h-10 rounded-lg px-4 py-2 text-xs font-bold text-white disabled:opacity-50" style={{ background: "#2878f0" }} disabled={busy || !reply.trim()} data-testid="sign-client-message-send">{busy ? "Se trimite…" : "Trimite mesajul"}</button>
      </form>
      {notice && <p className="mt-2 text-xs font-semibold" style={{ color: notice.includes("nu a putut") ? "#9b2c2c" : "#166534" }} role="status">{notice}</p>}
    </section>
  </>;
}

export default function SignPage() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState("");
  const [f, setF] = useState({ declared_name: "", intent: false, otp: "", signature: null });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const [refusing, setRefusing] = useState(false);
  const [reason, setReason] = useState("");
  const [clientMessages, setClientMessages] = useState([]);
  const [clientReply, setClientReply] = useState("");
  const [replyBusy, setReplyBusy] = useState(false);
  useEffect(() => { axios.get(`${API}/${token}`).then((r) => { setInfo(r.data); setClientMessages(r.data.client_messages || []); }).catch((e) => setErr(e.response?.data?.detail || "Link invalid")); }, [token]);
  const call = async (path, body, ok) => {
    setBusy(true); setMsg("");
    try { const r = await axios.post(`${API}/${token}/${path}`, body); await ok(r.data); } catch (e) { setMsg(e.response?.data?.detail || "Eroare"); } finally { setBusy(false); }
  };
  const sendClientReply = async (event) => {
    event.preventDefault();
    if (!clientReply.trim() || replyBusy) return;
    setReplyBusy(true); setMsg("");
    try {
      await axios.post(`${API}/${token}/messages`, { text: clientReply.trim() });
      const { data } = await axios.get(`${API}/${token}/messages`);
      setClientMessages(data.messages || []); setClientReply(""); setMsg("Mesajul a fost adăugat la dosar.");
    } catch (e) { setMsg(e.response?.data?.detail || "Mesajul nu a putut fi trimis."); }
    finally { setReplyBusy(false); }
  };
  if (err) return <Shell><p className="text-center font-bold" data-testid="sign-error">{err}</p></Shell>;
  if (!info) return <Shell><p className="text-center">Se încarcă…</p></Shell>;
  if (done) return <Shell><div className="text-center" data-testid="sign-done"><h2 className="text-xl font-extrabold mb-2">{done}</h2><p className="text-sm">Linkul nu mai poate fi folosit. Poți închide această pagină.</p></div></Shell>;
  if (info.portal) return <Shell><ClientPortal info={info} token={token} messages={clientMessages} reply={clientReply} setReply={setClientReply} onReply={sendClientReply} busy={replyBusy} notice={msg} onRefresh={async () => {
    try { const { data } = await axios.get(`${API}/${token}`); setInfo(data); setClientMessages(data.client_messages || []); setMsg(""); }
    catch (e) { setMsg(e.response?.data?.detail || "Portalul nu a putut fi actualizat."); }
  }} refreshing={busy} /></Shell>;
  if (!info.pages) return <Shell><p className="text-center font-bold" data-testid="sign-closed">{info.status === "Semnat" ? `Documentul a fost deja semnat${info.signed_at ? ` la ${new Date(info.signed_at).toLocaleString("ro-RO")}` : ""}.` : info.status === "Refuzat" ? "Semnarea acestui document a fost refuzată." : "Acest link a expirat. Cere emitentului un link nou."}</p></Shell>;
  const ok = f.declared_name.trim() && f.intent && f.otp.length === 6 && f.signature;
  return (
    <Shell>
      <div className="mb-4" data-testid="sign-info">
        <div className="text-[11px] uppercase tracking-wider font-bold" style={{ color: "#2878f0" }}>{info.company} · cerere de semnare</div>
        <h1 className="text-2xl font-extrabold">{info.doc_title}</h1>
        <p className="text-sm" style={{ color: "#5a6b85" }}>Pentru: <b>{info.signer_name}</b> ({info.role}) · dosar {info.client_name} · valabil până la {new Date(info.expires_at).toLocaleString("ro-RO")}</p>
      </div>
      <div className="rounded-xl border bg-[#eef1f5] p-2 space-y-2 max-h-[70vh] overflow-y-auto" data-testid="sign-document">
        {[...Array(info.pages).keys()].map((i) => <a key={i} href={`${API}/${token}/page/${i}`} target="_blank" rel="noopener noreferrer"><img src={`${API}/${token}/page/${i}`} alt={`Pagina ${i + 1}`} className="w-full bg-white shadow-sm" style={{ aspectRatio: "210 / 297" }} loading="lazy" /></a>)}
      </div>
      <a href={`${API}/${token}/document`} target="_blank" rel="noopener noreferrer" className="text-xs underline mt-1 inline-block" style={{ color: "#2878f0" }} data-testid="sign-download-original">Descarcă documentul (PDF)</a>
      <section className="mt-5 rounded-xl border bg-white p-4" style={{ borderColor: "#dbe3ee" }} data-testid="sign-client-messages">
        <h2 className="text-sm font-bold">Mesaje despre dosar</h2>
        <div className="mt-3 max-h-56 space-y-2 overflow-y-auto" data-testid="sign-client-message-list">
          {!clientMessages.length && <p className="text-xs" style={{ color: "#5a6b85" }}>Nu există mesaje în acest dosar.</p>}
          {clientMessages.map((item) => <article key={item.id} className="rounded-lg border p-3" style={{ borderColor: "#dbe3ee", background: "#f8fafd" }}>
            <div className="flex justify-between gap-2 text-[11px] font-semibold"><span>{item.sender === "client" ? "Tu" : item.sender_name || "Echipa DNS"}</span><time style={{ color: "#5a6b85" }}>{item.created_at ? new Date(item.created_at).toLocaleString("ro-RO") : ""}</time></div>
            {item.text && <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-5">{item.text}</p>}
            {!!item.attachments?.length && <div className="mt-2 flex flex-wrap gap-2">{item.attachments.map((file, index) => <a key={`${item.id}-${index}`} href={`${API}/${token}/message-files/${encodeURIComponent(item.id)}/${index}`} className="inline-flex items-center gap-1 text-xs underline" style={{ color: "#2878f0" }}><FileText size={12} />{file.original_filename || "Atașament"}</a>)}</div>}
          </article>)}
        </div>
        <form className="mt-3 space-y-2" onSubmit={sendClientReply}>
          <textarea className="den-input" rows={2} maxLength={2000} value={clientReply} onChange={(e) => setClientReply(e.target.value)} placeholder="Scrie un mesaj către echipa DNS…" data-testid="sign-client-message-input" />
          <button className="rounded-lg px-4 py-2 text-xs font-bold text-white disabled:opacity-50" style={{ background: "#2878f0" }} disabled={replyBusy || !clientReply.trim()} data-testid="sign-client-message-send">{replyBusy ? "Se trimite…" : "Trimite mesajul"}</button>
        </form>
      </section>
      <div className="mt-6 rounded-xl border bg-white p-4 space-y-4" style={{ borderColor: "#dbe3ee" }}>
        <div className="den-field"><label>Numele complet al semnatarului</label><input className="den-input" value={f.declared_name} onChange={(e) => setF({ ...f, declared_name: e.target.value })} data-testid="sign-name" /></div>
        <div>
          <button className="rounded-lg border px-4 py-2 text-sm font-bold" style={{ borderColor: "#2878f0", color: "#2878f0" }} disabled={busy}
            onClick={() => call("otp", {}, (d) => setMsg(`Cod trimis la ${d.email_masked}. Valabil 10 minute.`))} data-testid="sign-send-otp">Trimite-mi codul pe e-mail ({info.email_masked})</button>
          <input className="den-input mt-2" inputMode="numeric" maxLength={6} placeholder="Codul de 6 cifre" value={f.otp} onChange={(e) => setF({ ...f, otp: e.target.value.replace(/\D/g, "") })} data-testid="sign-otp" />
        </div>
        <Pad onChange={(s) => setF((p) => ({ ...p, signature: s }))} />
        <label className="flex gap-2 text-sm items-start"><input type="checkbox" className="mt-1" checked={f.intent} onChange={(e) => setF({ ...f, intent: e.target.checked })} data-testid="sign-intent" />
          <span>Am citit integral documentul și îmi exprim explicit intenția de a-l semna electronic. Înțeleg că aceasta este o <b>semnătură electronică simplă</b> (eIDAS), cu înregistrarea datei, orei, adresei IP și a dispozitivului.</span></label>
        {msg && <p className="text-sm font-bold" style={{ color: msg.startsWith("Cod trimis") ? "#166534" : "#9b2c2c" }} data-testid="sign-msg">{msg}</p>}
        <button className="w-full rounded-xl py-3 font-extrabold text-white disabled:opacity-40" style={{ background: "#2878f0" }} disabled={!ok || busy}
          onClick={() => call("sign", f, async () => { const { data } = await axios.get(`${API}/${token}`); setInfo(data); setClientMessages(data.client_messages || []); })} data-testid="sign-submit">Semnează documentul</button>
        {!refusing ? <button className="w-full text-sm" style={{ color: "#9b2c2c" }} onClick={() => setRefusing(true)} data-testid="sign-refuse-open">Refuz să semnez</button> : (
          <div className="space-y-2"><textarea className="den-input" placeholder="Motivul refuzului (opțional)" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="sign-refuse-reason" />
            <button className="w-full rounded-xl py-2 font-bold border" style={{ color: "#9b2c2c", borderColor: "#9b2c2c" }} onClick={() => call("refuse", { reason }, () => setDone("Ai refuzat semnarea documentului."))} data-testid="sign-refuse-submit">Confirm refuzul</button></div>
        )}
      </div>
    </Shell>
  );
}

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-[#f6f8fb] px-4 py-6">
      <div className="max-w-2xl mx-auto"><div className="mb-5"><BrandMark /></div>{children}</div>
    </div>
  );
}
