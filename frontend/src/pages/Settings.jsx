import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { Save } from "lucide-react";
import { toast } from "sonner";

export default function Settings() {
  const [f, setF] = useState({ company: "", brand: "", rep: "", phone: "", address: "" });
  const [loaded, setLoaded] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  useEffect(() => { api.get("/settings").then((r) => setF({ company: "", brand: "", rep: "", phone: "", address: "", ...r.data })).catch(() => {}).finally(() => setLoaded(true)); }, []);

  const save = async () => {
    await api.put("/settings", f);
    toast.success("Setări salvate");
  };

  const fields = [
    ["company", "Denumire firmă"], ["brand", "Brand aplicație"], ["rep", "Reprezentant"],
    ["phone", "Telefon firmă"], ["cui", "CUI"], ["regcom", "Nr. Registrul Comerțului"],
    ["anre_attest", "Nr. atestat ANRE"], ["address", "Adresă firmă", true],
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
        <div className="mt-6"><Btn onClick={save} disabled={!loaded} data-testid="save-settings"><Save size={15} /> Salvează setările</Btn></div>
      </div>
    </div>
  );
}
