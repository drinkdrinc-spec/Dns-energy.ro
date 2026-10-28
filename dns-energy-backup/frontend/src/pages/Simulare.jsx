import { useState } from "react";
import { PageHeader, Btn } from "@/components/Layout";
import { api } from "@/lib/api";
import { MapPin, Calculator, Save } from "lucide-react";
import { toast } from "sonner";

export default function Simulare() {
  const [f, setF] = useState({
    address: "", area: "", site: "Acoperiș înclinat", wp: 600, modArea: 2.6,
    factor: 75, system: "On-grid",
  });
  const [res, setRes] = useState(null);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const calc = () => {
    const area = parseFloat(f.area) || 0;
    const modArea = parseFloat(f.modArea) || 2.6;
    const wp = parseFloat(f.wp) || 600;
    const factor = (parseFloat(f.factor) || 75) / 100;
    const usable = area * factor;
    const modules = Math.floor(usable / modArea);
    const kwp = +((modules * wp) / 1000).toFixed(2);
    // ~1250 kWh/kWp/an medie România, PR 0.8
    const annual = Math.round(kwp * 1250 * 0.8);
    const co2 = Math.round(annual * 0.3); // kg CO2 evitat (~0.3 kg/kWh)
    setRes({ usable: Math.round(usable), modules, kwp, annual, co2 });
  };

  const openMaps = () => {
    if (!f.address) return toast.error("Completează adresa");
    window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(f.address)}`, "_blank");
  };

  const saveSim = async () => {
    if (!res) return toast.error("Calculează mai întâi estimarea");
    await api.post("/data/projects", { ...f, ...res });
    toast.success("Simulare salvată");
  };

  return (
    <div>
      <PageHeader eyebrow="Pre-proiectare" title="Simulare proiect & amplasament"
        sub="Estimare preliminară după suprafață, cu adresă și deschidere în Google Maps. Nu înlocuiește proiectul tehnic." />

      <div className="den-panel mb-6">
        <h2 className="text-lg font-bold mb-5">Amplasament și suprafață disponibilă</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="den-field sm:col-span-2"><label>Adresă completă a obiectivului</label>
            <input className="den-input" value={f.address} onChange={(e) => set("address", e.target.value)} placeholder="Județ, localitate, stradă, număr" data-testid="sim-address" /></div>
          <div className="den-field"><label>Suprafață disponibilă (m²)</label>
            <input className="den-input" type="number" value={f.area} onChange={(e) => set("area", e.target.value)} placeholder="Ex. 500" data-testid="sim-area" /></div>
          <div className="den-field"><label>Tip amplasament</label>
            <select className="den-input" value={f.site} onChange={(e) => set("site", e.target.value)}>
              {["Acoperiș înclinat", "Acoperiș plat", "Teren", "Parcare / carport"].map((o) => <option key={o}>{o}</option>)}</select></div>
          <div className="den-field"><label>Putere modul PV (Wp)</label>
            <input className="den-input" type="number" value={f.wp} onChange={(e) => set("wp", e.target.value)} /></div>
          <div className="den-field"><label>Suprafață estimată / modul (m²)</label>
            <input className="den-input" type="number" value={f.modArea} onChange={(e) => set("modArea", e.target.value)} /></div>
          <div className="den-field"><label>Factor de utilizare a suprafeței (%)</label>
            <input className="den-input" type="number" value={f.factor} onChange={(e) => set("factor", e.target.value)} /></div>
          <div className="den-field"><label>Tip sistem</label>
            <select className="den-input" value={f.system} onChange={(e) => set("system", e.target.value)}>
              {["On-grid", "Hibrid cu baterie", "Off-grid", "BESS comercial/industrial"].map((o) => <option key={o}>{o}</option>)}</select></div>
        </div>
        <div className="flex flex-wrap gap-2 mt-5">
          <Btn onClick={calc} data-testid="sim-calc"><Calculator size={15} /> Calculează estimarea</Btn>
          <Btn variant="secondary" onClick={openMaps}><MapPin size={15} /> Deschide în Google Maps</Btn>
          <Btn variant="secondary" onClick={saveSim}><Save size={15} /> Salvează simularea</Btn>
        </div>
      </div>

      {res && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6" data-testid="sim-result">
          {[
            ["Suprafață utilă", `${res.usable} m²`],
            ["Module estimate", res.modules],
            ["Putere instalabilă", `${res.kwp} kWp`],
            ["Producție anuală est.", `${res.annual.toLocaleString("ro-RO")} kWh`],
          ].map(([l, v]) => (
            <div key={l} className="den-panel">
              <div className="text-[11px] font-bold uppercase" style={{ color: "var(--muted)" }}>{l}</div>
              <div className="text-3xl font-extrabold mt-2" style={{ color: "var(--blue)" }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      <div className="den-notice">Estimarea presupune o suprafață medie/modul și un factor de utilizare introdus de utilizator (producție ≈ 1250 kWh/kWp/an × PR 0.8). Nu verifică umbrirea, orientarea, încărcările structurale, stringurile, limitele MPPT, ATR sau condițiile de racordare.</div>
    </div>
  );
}
