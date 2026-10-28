import { useMemo, useState } from "react";
import { PageHeader } from "@/components/Layout";
import { ExternalLink } from "lucide-react";

const CATALOG = [
  ["Invertor", "Deye", "SUN-SG / SUN-G series", "Fișe tehnice, manuale și certificate UE.", "https://deye-inverters.com/ro/downloads/"],
  ["Invertor", "Solis", "S6 / S5, on-grid și hibrid", "Product Technical Specification, Manual, Certificate.", "https://www.solisinverters.com/global/downloadcenter"],
  ["Invertor", "Huawei", "SUN2000", "Portalul producătorului — selectează modelul/regiunea.", "https://solar.huawei.com/"],
  ["Invertor", "Sungrow", "SG / SH series", "Fișe tehnice și documente de produs.", "https://en.sungrowpower.com/"],
  ["Invertor", "GoodWe", "DNS / SDT / ET series", "Documentație tehnică după model și regiune.", "https://en.goodwe.com/"],
  ["Invertor", "Fronius", "Primo / Symo / GEN24", "Documentație și certificate oficiale.", "https://www.fronius.com/"],
  ["Panou fotovoltaic", "AIKO", "Neostar / ABC series", "Fișa tehnică după model și generație.", "https://aikosolar.com/"],
  ["Panou fotovoltaic", "LONGi", "Hi-MO series", "Documentație oficială produse/descărcări.", "https://www.longi.com/"],
  ["Panou fotovoltaic", "JinkoSolar", "Tiger Neo series", "Selectează codul complet al modulului.", "https://www.jinkosolar.com/"],
  ["Panou fotovoltaic", "Trina Solar", "Vertex series", "Fișe tehnice și certificate după model.", "https://www.trinasolar.com/"],
  ["Panou fotovoltaic", "Canadian Solar", "TOPHiKu / TOPCon series", "Fișe tehnice după serie și cod exact.", "https://www.canadiansolar.com/"],
  ["Baterie", "Dyness", "PowerBrick / Stack / Tower", "Verifică tensiunea, modelul, compatibilitatea.", "https://www.dyness.com/"],
  ["Baterie", "Pylontech", "US / Force series", "Documente și liste de compatibilitate.", "https://www.pylontech.com.cn/"],
  ["Baterie", "BYD", "Battery-Box Premium", "Manual, fișă tehnică și compatibilitate.", "https://www.bydbatterybox.com/"],
  ["Baterie", "Huawei", "LUNA2000 series", "Documente specifice modelului.", "https://solar.huawei.com/"],
  ["Baterie", "Deye", "LV / HV battery series", "Fișe tehnice, manuale și certificate UE.", "https://deye-batteries.com/en/downloads/"],
  ["BESS", "Deye", "BESS comercial/industrial și hibride", "Arhitectură, PCS, capacitate, tensiune.", "https://deyeinverters.com/ro/downloads/"],
  ["BESS", "Sungrow", "PowerStack / PowerTitan", "Sisteme BESS; selectează configurația.", "https://en.sungrowpower.com/"],
  ["BESS", "Huawei", "LUNA2000 C&I / ESS", "Configurație completă, PCS, capacitate.", "https://solar.huawei.com/"],
  ["BESS", "BYD", "Battery-Box / stocare", "Documentație după model și integrare aprobată.", "https://www.bydbatterybox.com/"],
  ["BESS", "Dyness", "C&I / Stack / stocare", "Tensiune, curenți, module, compatibilitate BMS.", "https://www.dyness.com/"],
];

const CATS = ["", "Invertor", "Panou fotovoltaic", "Baterie", "BESS"];

export default function Catalog() {
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const rows = useMemo(() => CATALOG.filter(([c, m, s]) =>
    (!cat || c === cat) && (!q || `${m} ${s}`.toLowerCase().includes(q.toLowerCase()))), [cat, q]);

  return (
    <div>
      <PageHeader eyebrow="Bibliotecă tehnică" title="Catalog tehnic"
        sub="Producători și linkuri către fișe tehnice, manuale și certificate publicate de surse oficiale." />

      <div className="den-panel mb-6">
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="den-field"><label>Categorie</label>
            <select className="den-input" value={cat} onChange={(e) => setCat(e.target.value)} data-testid="catalog-cat">
              {CATS.map((c) => <option key={c} value={c}>{c || "Toate categoriile"}</option>)}
            </select>
          </div>
          <div className="den-field"><label>Caută producător / model</label>
            <input className="den-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Deye, Solis, AIKO, Dyness..." data-testid="catalog-search" />
          </div>
        </div>
      </div>

      <div className="den-panel">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left" style={{ background: "#f8fafd", color: "var(--muted)" }}>
              {["Categorie", "Producător", "Serii orientative", "Documentație", "Acces"].map((h) => <th key={h} className="px-3 py-2.5 font-semibold text-[12px]">{h}</th>)}
            </tr></thead>
            <tbody>
              {rows.map(([c, m, s, d, url], i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--line)" }}>
                  <td className="px-3 py-3 whitespace-nowrap">{c}</td>
                  <td className="px-3 py-3 font-bold">{m}</td>
                  <td className="px-3 py-3">{s}</td>
                  <td className="px-3 py-3" style={{ color: "var(--muted)" }}>{d}</td>
                  <td className="px-3 py-3"><a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[12px] font-bold" style={{ color: "var(--blue)" }}>Deschide <ExternalLink size={13} /></a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="den-notice mt-5">Linkurile duc la centrele de documentație ale producătorilor; selectează codul exact, regiunea UE și versiunea curentă. O fișă tehnică nu înlocuiește declarația UE de conformitate sau certificatele de rețea.</div>
      </div>
    </div>
  );
}
