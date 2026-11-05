import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { LockKeyhole } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";
import { Btn } from "@/components/Layout";
import { api } from "@/lib/api";

export default function ResetPassword() {
  const location = useLocation();
  const [token] = useState(() => new URLSearchParams(location.hash.slice(1)).get("token") || new URLSearchParams(location.search).get("token") || "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (token) window.history.replaceState(window.history.state, "", window.location.pathname);
  }, [token]);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!token) { setError("Linkul nu conține un token valid. Cere un link nou din ecranul de autentificare."); return; }
    if (password !== confirm) { setError("Parolele nu corespund."); return; }
    if (password.length < 12) { setError("Folosește cel puțin 12 caractere."); return; }
    setSaving(true);
    try {
      const { data } = await api.post("/auth/reset-password", { token, new_password: password });
      setDone(true);
      setPassword("");
      setConfirm("");
      setError(data?.message || "Parola a fost schimbată. Te poți autentifica.");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Linkul nu mai este valid. Cere un link nou și încearcă din nou.");
    } finally { setSaving(false); }
  };

  return <main className="min-h-[100dvh] grid place-items-center px-5 py-8" style={{ background: "var(--bg)" }}>
    <section className="den-panel w-full max-w-md" aria-labelledby="reset-password-title" data-testid="reset-password-form">
      <div className="mb-6 flex flex-col items-center gap-3 text-center"><BrandMark size={52} /><span className="text-xl font-extrabold tracking-wide">DNS ENERGY</span></div>
      <h1 id="reset-password-title" className="text-2xl font-extrabold">{done ? "Parolă actualizată" : "Alege o parolă nouă"}</h1>
      <p className="mt-2 mb-5 text-sm" style={{ color: "var(--muted)" }}>{done ? "Sesiunile vechi au fost revocate. Intră din nou cu parola nouă." : "Linkul este valabil 30 de minute și poate fi folosit o singură dată."}</p>
      {!done && <form onSubmit={submit}>
        <label className="den-field mb-4 block"><span>Parolă nouă (minimum 12 caractere)</span><span className="relative mt-1 block"><LockKeyhole size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} /><input className="den-input pl-10" type="password" autoComplete="new-password" minLength={12} maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} required data-testid="reset-new-password" /></span></label>
        <label className="den-field mb-4 block"><span>Confirmă parola</span><input className="den-input mt-1" type="password" autoComplete="new-password" minLength={12} maxLength={72} value={confirm} onChange={(event) => setConfirm(event.target.value)} required data-testid="reset-confirm-password" /></label>
        {error && <p className="my-4 rounded-lg px-3 py-2 text-sm" style={{ background: "#fff0f0", color: "#b33333" }} role="alert" data-testid="reset-password-error">{error}</p>}
        <Btn type="submit" className="mt-2 min-h-12 w-full justify-center" disabled={saving} data-testid="reset-password-submit">{saving ? "Se schimbă parola…" : "Salvează parola nouă"}</Btn>
      </form>}
      {done && <p className="my-4 rounded-lg px-3 py-2 text-sm" style={{ background: "#edf8f1", color: "#23613b" }} role="status" data-testid="reset-password-success">{error}</p>}
      {(done || !token) && <Link to="/login" className="mt-4 block text-center text-sm font-bold underline" style={{ color: "var(--blue)" }}>Înapoi la autentificare</Link>}
    </section>
  </main>;
}
