import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { BrandMark } from "@/components/BrandMark";
import { Btn } from "@/components/Layout";
import { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("drinkdrinc@gmail.com");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
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
          <p className="mt-4 text-sm max-w-md" style={{ color: "#aab8d1" }}>Dosare DI-U, dosar de prosumator, scheme monofilare, tablouri, PRAM, catalog tehnic și simulări — într-un singur loc, cu stocare persistentă.</p>
        </div>
        <div className="text-xs" style={{ color: "#7f91ae" }}>© {new Date().getFullYear()} D-ENERGY · DNS HOSTESS S.R.L.</div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-12" style={{ background: "var(--bg)" }}>
        <form onSubmit={submit} className="w-full max-w-sm den-panel" data-testid="login-form">
          <div className="lg:hidden flex items-center gap-3 mb-6"><BrandMark size={40} /><span className="text-xl font-extrabold">D-ENERGY</span></div>
          <h1 className="text-2xl font-extrabold">Autentificare</h1>
          <p className="text-sm mb-6" style={{ color: "var(--muted)" }}>Accesează spațiul tău de lucru.</p>

          <div className="den-field mb-4">
            <label>Email</label>
            <input data-testid="login-email" className="den-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="den-field mb-4">
            <label>Parolă</label>
            <input data-testid="login-password" className="den-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>

          {err && <div data-testid="login-error" className="text-[13px] mb-4 rounded-lg px-3 py-2" style={{ background: "#fff0f0", color: "#b33333" }}>{err}</div>}

          <Btn type="submit" data-testid="login-submit" className="w-full justify-center" disabled={loading}>
            {loading ? "Se verifică..." : "Intră în cont"}
          </Btn>
        </form>
      </div>
    </div>
  );
}
