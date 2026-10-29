import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { Save, Upload, FileCheck2 } from "lucide-react";
import { toast } from "sonner";

export default function Settings() {
  const [f, setF] = useState({ company: "", brand: "", rep: "", phone: "", address: "" });
  const [loaded, setLoaded] = useState(false);
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

  const save = async () => {
    await api.put("/settings", f);
    toast.success("Setări salvate");
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
    </div>
  );
}
