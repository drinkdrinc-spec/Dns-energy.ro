import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { Save, Upload, FileCheck2 } from "lucide-react";
import { toast } from "sonner";

export default function Settings() {
  const [f, setF] = useState({ company: "", brand: "", rep: "", phone: "", address: "" });
  const [loaded, setLoaded] = useState(false);
  const [companyExtract, setCompanyExtract] = useState(null);
  const [companyExtracting, setCompanyExtracting] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [passwordSaving, setPasswordSaving] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  useEffect(() => { api.get("/settings").then((r) => setF({ company: "", brand: "", rep: "", phone: "", address: "", ...r.data })).catch(() => {}).finally(() => setLoaded(true)); }, []);

  const uploadSettingFile = async (key, file) => {
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    try {
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setF((p) => ({ ...p, [key]: data }));
      toast.success("Fișier încărcat; apasă Salvează setările pentru a-l păstra.");
    } catch { toast.error("Eroare la încărcarea fișierului"); }
  };

  const extractCompanyProfile = async (file) => {
    if (!file) return;
    setCompanyExtracting(true);
    setCompanyExtract(null);
    const fd = new FormData(); fd.append("file", file);
    try {
      const { data } = await api.post("/ai/extract-company", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setCompanyExtract(data.data || {});
      toast.success("Datele au fost citite. Verifică-le înainte să le aplici.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Nu am putut citi documentul.");
    } finally {
      setCompanyExtracting(false);
    }
  };

  const applyCompanyExtract = () => {
    if (!companyExtract) return;
    const allowed = ["company", "cui", "regcom", "address", "rep", "phone", "email", "anre_attest"];
    setF((current) => {
      const next = { ...current };
      for (const key of allowed) {
        const value = String(companyExtract[key] || "").trim();
        if (value && !String(next[key] || "").trim()) next[key] = value;
      }
      return next;
    });
    toast.success("Am completat doar câmpurile goale. Verifică și salvează setările.");
  };

  const save = async () => {
    await api.put("/settings", f);
    toast.success("Setări salvate");
  };

  const changePassword = async () => {
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error("Confirmarea parolei noi nu corespunde.");
      return;
    }
    if (passwordForm.new_password.length < 12) {
      toast.error("Parola nouă trebuie să aibă cel puțin 12 caractere.");
      return;
    }
    setPasswordSaving(true);
    try {
      await api.post("/auth/change-password", { current_password: passwordForm.current_password, new_password: passwordForm.new_password });
      setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
      toast.success("Parola a fost schimbată.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Nu am putut schimba parola.");
    } finally {
      setPasswordSaving(false);
    }
  };

  const fields = [
    ["company", "Denumire firmă"], ["brand", "Brand aplicație"], ["rep", "Reprezentant"],
    ["phone", "Telefon firmă"], ["cui", "CUI"], ["regcom", "Nr. Registrul Comerțului"],
    ["anre_attest", "Nr. atestat ANRE"], ["iban", "IBAN încasări (proforme, OP)"], ["bank", "Banca"], ["address", "Adresă firmă", true],
  ];

  return (
    <div>
      <PageHeader eyebrow="Configurare aplicație" title="Setări"
        sub="Datele firmei folosite în antetul fișelor și documentelor." />
      <div className="den-panel max-w-2xl">
        <div className="rounded-xl border p-3 mb-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="company-profile-import">
          <h3 className="font-bold text-sm">Importă date din certificatul firmei</h3>
          <p className="text-xs mt-1 mb-2" style={{ color: "var(--muted)" }}>Încarcă certificatul de înregistrare, constatator sau atestatul ANRE. AI propune doar datele vizibile; verifică-le înainte să le aplici. Fișierul este procesat pentru extragere și nu se atașează automat dosarelor.</p>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp" disabled={!loaded || companyExtracting} onChange={(e) => { extractCompanyProfile(e.target.files?.[0]); e.target.value = ""; }} data-testid="company-profile-source" />
          {companyExtracting && <p className="text-xs mt-2">Se citesc datele...</p>}
          {!!companyExtract && <div className="mt-3" data-testid="company-profile-preview">
            <p className="text-xs font-semibold mb-1">Previzualizare — nimic nu este salvat încă</p>
            <dl className="grid sm:grid-cols-2 gap-x-3 text-xs">{[["company","Denumire firmă"],["cui","CUI"],["regcom","Nr. Registrul Comerțului"],["address","Adresă firmă"],["rep","Reprezentant"],["phone","Telefon"],["email","E-mail"],["anre_attest","Nr. atestat ANRE"]].map(([key,label]) => <div key={key}><dt className="inline font-semibold">{label}: </dt><dd className="inline">{companyExtract[key] || "Nu a fost identificat"}</dd></div>)}</dl>
            <Btn className="mt-2" variant="secondary" onClick={applyCompanyExtract} data-testid="apply-company-extract">Completează câmpurile goale</Btn>
          </div>}
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          {fields.map(([k, label, full]) => (
            <div key={k} className={`den-field ${full ? "sm:col-span-2" : ""}`}>
              <label>{label}</label>
              <input className="den-input" disabled={!loaded} value={f[k] || ""} onChange={(e) => set(k, e.target.value)} data-testid={`set-${k}`} />
            </div>
          ))}
        </div>
        <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--line)" }}>
        <h3 className="font-bold text-sm mb-1">Documente firmă și semnare automată</h3>
        <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Încarcă fișierele reale o singură dată. Semnăturile persoanelor se gestionează la Personal și autorizări. Ștampila se aplică doar unde documentul și setările permit.</p>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="den-field"><label>Atestat ANRE al firmei — fișier</label><input type="file" accept=".pdf,.jpg,.jpeg,.png" disabled={!loaded} onChange={(e) => uploadSettingFile("anre_file", e.target.files?.[0])} data-testid="set-anre-file" />{f.anre_file?.storage_path && <p className="text-xs mt-1"><FileCheck2 size={13} className="inline" /> Fișier încărcat: {f.anre_file.original_filename || f.anre_file.filename || "atestat ANRE"}</p>}</div>
          <div className="den-field"><label>Ștampila firmei — imagine PNG/JPG</label><input type="file" accept="image/png,image/jpeg" disabled={!loaded} onChange={(e) => uploadSettingFile("stamp", e.target.files?.[0])} data-testid="set-stamp-file" />{f.stamp?.storage_path && <p className="text-xs mt-1"><FileCheck2 size={13} className="inline" /> Ștampilă încărcată: {f.stamp.original_filename || f.stamp.filename || "ștampilă"}</p>}</div>
        </div>
      </div>
      <div className="mt-6"><Btn onClick={save} disabled={!loaded} data-testid="save-settings"><Save size={15} /> Salvează setările</Btn></div>
      </div>
      <section className="den-panel max-w-2xl mt-5" aria-labelledby="password-change-title" data-testid="account-password-change">
        <h2 id="password-change-title" className="font-bold text-base">Securitatea contului</h2>
        <p className="text-xs mt-1 mb-4" style={{ color: "var(--muted)" }}>Schimbă parola contului conectat. Folosește minimum 12 caractere; parola actuală este necesară pentru confirmare.</p>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="den-field sm:col-span-2"><label htmlFor="current-password">Parola actuală</label><input id="current-password" className="den-input" type="password" autoComplete="current-password" value={passwordForm.current_password} onChange={(e) => setPasswordForm((p) => ({ ...p, current_password: e.target.value }))} data-testid="current-password" /></div>
          <div className="den-field"><label htmlFor="new-password">Parolă nouă</label><input id="new-password" className="den-input" type="password" autoComplete="new-password" value={passwordForm.new_password} onChange={(e) => setPasswordForm((p) => ({ ...p, new_password: e.target.value }))} data-testid="new-password" /></div>
          <div className="den-field"><label htmlFor="confirm-password">Confirmă parola nouă</label><input id="confirm-password" className="den-input" type="password" autoComplete="new-password" value={passwordForm.confirm_password} onChange={(e) => setPasswordForm((p) => ({ ...p, confirm_password: e.target.value }))} data-testid="confirm-password" /></div>
        </div>
        <Btn className="mt-4" onClick={changePassword} disabled={passwordSaving} data-testid="change-password">{passwordSaving ? "Se salvează..." : "Schimbă parola"}</Btn>
      </section>
    </div>
  );
}
