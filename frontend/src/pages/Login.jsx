import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { BrandMark } from "@/components/BrandMark";
import { Btn } from "@/components/Layout";
import { api, API, formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";

export default function Login() {
  const { login, refresh, authIssue, authChecking } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiWarmup, setApiWarmup] = useState("checking");
  const [mode, setMode] = useState(() => new URLSearchParams(window.location.search).get("mode") === "register" ? "register" : "login");
  const [name, setName] = useState("");
  const [gdpr, setGdpr] = useState(false);
  const [accountType, setAccountType] = useState("installer");
  const [certificateNumber, setCertificateNumber] = useState("");
  const [certFile, setCertFile] = useState(null);
  const reg = mode === "register";
  const forgot = mode === "forgot";
  const apiOrigin = API.replace(/\/api\/?$/, "") || window.location.origin;

  useEffect(() => {
    const controller = new AbortController();
    api.get(`${apiOrigin}/readyz`, { timeout: 120000, signal: controller.signal })
      .then(({ data }) => setApiWarmup(data?.status === "ready" ? "ready" : "unavailable"))
      .catch((error) => {
        if (error.code !== "ERR_CANCELED") setApiWarmup("unavailable");
      });
    return () => controller.abort();
  }, [apiOrigin]);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      if (forgot) {
        const { data } = await api.post("/auth/forgot-password", { email });
        setNotice(data?.message || "Dacă există un cont activ pentru această adresă, vei primi instrucțiunile pe e-mail.");
        return;
      }
      if (reg) {
        if (!gdpr) { setErr("Citiți informarea și confirmați acordul privind prelucrarea datelor."); return; }
        if (!certFile) { setErr("Atașați certificatul ANRE pentru verificarea cererii."); return; }
        if (certFile.size > 8 * 1024 * 1024) { setErr("Certificatul ANRE trebuie să aibă maximum 8 MB."); return; }
        const certificateBase64 = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
          reader.onerror = () => reject(new Error("Fișierul certificatului nu a putut fi citit."));
          reader.readAsDataURL(certFile);
        });
        const { data } = await api.post("/auth/register", {
          email, password, name, account_type: accountType,
          anre_certificate_number: certificateNumber,
          anre_certificate_filename: certFile.name,
          anre_certificate_type: certFile.type,
          anre_certificate_base64: certificateBase64,
          gdpr_acknowledged: true,
          gdpr_notice_version: "partner-registration-v1-2026-11"
        });
        if (data.pending) { toast.success(data.message); setMode("login"); return; }
      }
      await login(email, password);
      toast.success("Autentificare reușită");
    } catch (ex) {
      const detail = ex.response?.data?.detail;
      setErr(detail ? formatApiErrorDetail(detail) : !ex.response ? "Serverul nu a răspuns. Verifică conexiunea și încearcă din nou." : formatApiErrorDetail(detail));
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-[100dvh] grid min-w-0 w-full grid-cols-1 lg:grid-cols-2 bg-white" style={{ overflowX: "clip" }}>
      <div className="hidden lg:flex flex-col justify-between p-12 text-white relative overflow-hidden" style={{ backgroundImage: "linear-gradient(160deg, rgba(14,50,91,.84), rgba(12,25,44,.9)), url('/d-energy-blue-brand.jpg')", backgroundSize: "cover", backgroundPosition: "center" }}>
        <div className="flex items-center gap-3">
          <BrandMark size={48} />
          <div><div className="text-2xl font-extrabold tracking-wide">D-ENERGY</div><div className="text-xs" style={{ color: "#aab8d1" }}>DNS HOSTESS S.R.L.</div></div>
        </div>
        <div>
          <h2 className="text-4xl font-extrabold leading-tight">Manager instalații<br />electrice & fotovoltaice</h2>
          <p className="mt-4 text-sm max-w-md" style={{ color: "#aab8d1" }}>Dosare DI-U, dosar de prosumator, scheme monofilare, tablouri, PRAM, catalog tehnic și simulări — într-un singur loc. Abonamente START, PRO și FULL.</p>
        </div>
        <div className="text-xs" style={{ color: "#7f91ae" }}>© {new Date().getFullYear()} D-ENERGY · DNS HOSTESS S.R.L.</div>
      </div>

      <div className="flex min-w-0 w-full items-center justify-center px-5 py-8 sm:p-12" style={{ background: "var(--bg)" }}>
        <form onSubmit={submit} className={`min-w-0 w-full ${reg ? "max-w-2xl" : "max-w-sm"} den-panel`} style={{ maxWidth: "min(100%, calc(100vw - 2.5rem))" }} data-testid="login-form">
          <div className="lg:hidden mb-8 min-h-[150px] rounded-2xl overflow-hidden" role="img" aria-label="D-Energy — Energie pentru un viitor sustenabil" style={{ backgroundImage: "linear-gradient(rgba(8,36,70,.12), rgba(8,36,70,.12)), url('/d-energy-blue-brand.jpg')", backgroundSize: "cover", backgroundPosition: "center" }} />
          <h1 className="text-2xl font-extrabold">{reg ? "Cont nou" : forgot ? "Resetează parola" : "Conectează-te"}</h1>
          <p className="text-sm mb-6" style={{ color: "var(--muted)" }}>{reg ? "Contul devine activ după aprobarea administratorului. Apoi alegeți și plătiți abonamentul." : forgot ? "Îți trimitem un link temporar dacă adresa aparține unui cont activ." : "Intră în contul tău DNS Energy pentru a continua."}</p>
          {reg && <>
            <div className="den-field mb-4"><label>Tip cont</label><select className="den-input" value={accountType} onChange={(e) => setAccountType(e.target.value)}><option value="installer">Instalator</option><option value="partner">Partener</option></select></div>
            <div className="den-field mb-4"><label>Nume complet / firmă</label><input data-testid="register-name" className="den-input" value={name} onChange={(e) => setName(e.target.value)} required /></div>
          </>}
          <div className="den-field mb-4"><label>Email (cont)</label>
            <input data-testid="login-email" className="den-input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
          {!forgot && <div className="den-field mb-4"><label>Parolă{reg ? " (minimum 12 caractere)" : ""}</label>
            <div className="relative">
              <LockKeyhole size={17} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
              <input data-testid="login-password" className="den-input pl-10 pr-12" type={showPassword ? "text" : "password"} autoComplete={reg ? "new-password" : "current-password"} value={password} onChange={(e) => setPassword(e.target.value)} required />
              <button type="button" aria-label={showPassword ? "Ascunde parola" : "Afișează parola"} onClick={() => setShowPassword((visible) => !visible)} className="absolute right-3 top-1/2 -translate-y-1/2 p-1" style={{ color: "var(--muted)" }}>
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div></div>}
          {notice && <div className="text-[13px] my-4 rounded-lg px-3 py-2" style={{ background: "#edf8f1", color: "#23613b" }} role="status" data-testid="password-reset-notice">{notice}</div>}
          {reg && <>
            <div className="den-field mb-4"><label>Număr certificat / atestat ANRE</label><input className="den-input" value={certificateNumber} onChange={(e) => setCertificateNumber(e.target.value)} required maxLength={80} /></div>
            <div className="den-field mb-4"><label>Certificat ANRE (PDF, JPG sau PNG; maximum 8 MB)</label><input className="den-input" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={(e) => setCertFile(e.target.files?.[0] || null)} required /></div>
            <details className="rounded-lg border p-3 text-xs leading-5" style={{ borderColor: "var(--line)", background: "var(--bg)", color: "var(--muted)" }}>
              <summary className="cursor-pointer font-semibold">Informare privind datele personale</summary>
              <p className="mt-2">Operatorul este DNS HOSTESS S.R.L. Datele de identificare, contact și certificatul ANRE sunt folosite pentru verificarea cererii și administrarea contului, ca demers la solicitarea ta înaintea încheierii unei relații de parteneriat. Le pot vedea administratorii autorizați și furnizorii tehnici care găzduiesc aplicația. Datele cererii sunt păstrate până la soluționare; pentru conturile aprobate, pe durata administrării contului și cât cer obligațiile legale. Nu folosim aceste date pentru marketing. Întrebări sau solicitări: <a className="underline" href="mailto:office@dns-energy.ro">office@dns-energy.ro</a>.</p>
              <p>Poți cere acces, rectificare, ștergere sau restricționarea prelucrării, în limitele legale, și poți depune o plângere la autoritatea de supraveghere. Dacă retragi acordul înainte de verificarea cererii, nu o vom putea procesa.</p>
            </details>
            <label className="text-xs flex items-start gap-2 mt-3"><input type="checkbox" checked={gdpr} onChange={(e) => setGdpr(e.target.checked)} data-testid="register-gdpr" required />
              Confirm că am citit informarea și sunt de acord cu prelucrarea datelor furnizate pentru verificarea și administrarea cererii de cont.</label>
          </>}
          {authIssue && <div className="text-[13px] my-4 rounded-lg px-3 py-3" style={{ background: "#fff8e6", color: "#805600" }} role="status" data-testid="auth-service-warning">
            <p>{authIssue}</p>
            <button type="button" onClick={refresh} disabled={authChecking} className="mt-2 font-bold underline disabled:opacity-60" data-testid="auth-retry">
              {authChecking ? "Se verifică sesiunea…" : "Reîncearcă verificarea"}
            </button>
          </div>}
          {apiWarmup !== "ready" && <div className="text-[13px] my-4 rounded-lg px-3 py-3" style={{ background: "#fff8e6", color: "#805600" }} role="status" data-testid="auth-api-warmup">
            {apiWarmup === "checking"
              ? "Se pornește conexiunea la server. După o perioadă fără activitate, prima pornire poate dura aproximativ un minut; completează datele și trimite autentificarea o singură dată."
              : "Serverul nu a răspuns la verificarea inițială. Poate încă pornește; așteaptă și încearcă o singură autentificare, ca să nu declanșezi blocarea temporară."}
          </div>}
          {err && <div data-testid="login-error" className="text-[13px] my-4 rounded-lg px-3 py-2" style={{ background: "#fff0f0", color: "#b33333" }}>{err}</div>}
          <Btn type="submit" data-testid="login-submit" className="w-full justify-center mt-4 min-h-12" disabled={loading}>
            {loading ? "Se verifică..." : reg ? "Trimite cererea de cont" : forgot ? "Trimite link de resetare" : "Intră în cont"}
          </Btn>
          {forgot ? <button type="button" className="mt-4 w-full text-sm font-bold underline" onClick={() => { setMode("login"); setErr(""); setNotice(""); }}>Înapoi la autentificare</button>
            : reg ? <button type="button" className="mt-4 w-full text-sm font-semibold underline" style={{ color: "var(--blue)" }} onClick={() => { setMode("login"); setErr(""); }}>Ai deja cont? Conectează-te</button>
              : <><button type="button" className="mt-4 w-full text-sm font-semibold underline" style={{ color: "var(--blue)" }} onClick={() => { setMode("forgot"); setErr(""); setNotice(""); }}>Ai uitat parola?</button>
                <button type="button" className="mt-3 w-full text-sm font-bold" style={{ color: "var(--green)" }} onClick={() => { setMode("register"); setErr(""); setNotice(""); }}>Creează cont de instalator / partener</button></>}
          <p className="text-[11px] text-center mt-5" style={{color:"var(--muted)"}}>{reg ? "Contul se activează după verificarea certificatului ANRE de către administrator." : "Acces pentru instalatori și parteneri DNS Energy."}</p>
        </form>
      </div>
    </div>
  );
}


