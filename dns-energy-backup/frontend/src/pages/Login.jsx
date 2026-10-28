import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { BrandMark } from "@/components/BrandMark";
import { Btn } from "@/components/Layout";
import { api, formatApiErrorDetail } from "@/lib/api";
import { BillingForm } from "@/components/billing/BillingForm";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [billing, setBilling] = useState({});
  const [gdpr, setGdpr] = useState(false);
  const reg = mode === "register";

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      if (reg) {
        if (!gdpr) { setErr("Confirmați acordul privind prelucrarea datelor pentru facturare"); return; }
        const { data } = await api.post("/auth/register", { email, password, name, billing: { ...billing, billing_email: billing.billing_email || email } });
        if (data.pending) { toast.success(data.message); setMode("login"); return; }
      }
      await login(email, password);
      toast.success("Autentificare reușită");
    } catch (ex) {
      setErr(formatApiErrorDetail(ex.response?.data?.detail) || ex.message);
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between p-12 text-white relative overflow-hidden" style={{ background: "linear-gradient(160deg, var(--navy), #0c1424)" }}>
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

      <div className="flex items-center justify-center p-6 sm:p-12" style={{ background: "var(--bg)" }}>
        <form onSubmit={submit} className={`w-full ${reg ? "max-w-2xl" : "max-w-sm"} den-panel`} data-testid="login-form">
          <div className="lg:hidden flex items-center gap-3 mb-6"><BrandMark size={40} /><span className="text-xl font-extrabold">D-ENERGY</span></div>
          <h1 className="text-2xl font-extrabold">{reg ? "Cont nou" : "Autentificare"}</h1>
          <p className="text-sm mb-6" style={{ color: "var(--muted)" }}>{reg ? "Contul devine activ după aprobarea administratorului. Apoi alegeți și plătiți abonamentul." : "Accesează spațiul tău de lucru."}</p>
          {reg && <div className="den-field mb-4"><label>Nume complet</label><input data-testid="register-name" className="den-input" value={name} onChange={(e) => setName(e.target.value)} required /></div>}
          <div className="den-field mb-4"><label>Email (cont)</label>
            <input data-testid="login-email" className="den-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
          <div className="den-field mb-4"><label>Parolă{reg ? " (minimum 8 caractere)" : ""}</label>
            <input data-testid="login-password" className="den-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>
          {reg && <>
            <h2 className="text-base font-extrabold mt-2 mb-2">Date de facturare</h2>
            <BillingForm value={billing} onChange={setBilling} />
            <label className="text-xs flex items-start gap-2 mt-3"><input type="checkbox" checked={gdpr} onChange={(e) => setGdpr(e.target.checked)} data-testid="register-gdpr" />
              Sunt de acord cu prelucrarea datelor de mai sus exclusiv pentru administrarea contului și facturare (GDPR).</label>
          </>}
          {err && <div data-testid="login-error" className="text-[13px] my-4 rounded-lg px-3 py-2" style={{ background: "#fff0f0", color: "#b33333" }}>{err}</div>}
          <Btn type="submit" data-testid="login-submit" className="w-full justify-center mt-4" disabled={loading}>
            {loading ? "Se verifică..." : reg ? "Trimite cererea de cont" : "Intră în cont"}
          </Btn>
          <button type="button" className="text-xs font-bold mt-4 w-full" style={{ color: "var(--blue)" }} onClick={() => { setMode(reg ? "login" : "register"); setErr(""); }} data-testid="toggle-register">
            {reg ? "Am deja cont — autentificare" : "Nu ai cont? Creează un cont nou"}</button>
        </form>
      </div>
    </div>
  );
}
