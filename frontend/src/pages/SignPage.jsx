import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { BrandMark } from "@/components/BrandMark";

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
  useEffect(() => { axios.get(`${API}/${token}`).then((r) => setInfo(r.data)).catch((e) => setErr(e.response?.data?.detail || "Link invalid")); }, [token]);
  const call = async (path, body, ok) => {
    setBusy(true); setMsg("");
    try { const r = await axios.post(`${API}/${token}/${path}`, body); ok(r.data); } catch (e) { setMsg(e.response?.data?.detail || "Eroare"); } finally { setBusy(false); }
  };
  if (err) return <Shell><p className="text-center font-bold" data-testid="sign-error">{err}</p></Shell>;
  if (!info) return <Shell><p className="text-center">Se încarcă…</p></Shell>;
  if (done) return <Shell><div className="text-center" data-testid="sign-done"><h2 className="text-xl font-extrabold mb-2">{done}</h2><p className="text-sm">Linkul nu mai poate fi folosit. Poți închide această pagină.</p></div></Shell>;
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
          onClick={() => call("sign", f, () => setDone("Document semnat. Mulțumim!"))} data-testid="sign-submit">Semnează documentul</button>
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
