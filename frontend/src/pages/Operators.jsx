import { useMemo, useState } from "react";
import { PageHeader } from "@/components/Layout";
import { ExternalLink } from "lucide-react";

const OPERATORS = [
  ["DEER — Transilvania Nord", "Bihor, Bistrița-Năsăud, Cluj, Maramureș, Satu Mare, Sălaj", "https://www.distributie-energie.ro/"],
  ["DEER — Transilvania Sud", "Alba, Brașov, Covasna, Harghita, Mureș, Sibiu", "https://www.distributie-energie.ro/"],
  ["DEER — Muntenia Nord", "Brăila, Buzău, Dâmbovița, Galați, Prahova, Vrancea", "https://www.distributie-energie.ro/"],
  ["Delgaz Grid", "Bacău, Botoșani, Iași, Neamț, Suceava, Vaslui", "https://delgaz.ro/"],
  ["Distribuție Energie Oltenia", "Argeș, Dolj, Gorj, Mehedinți, Olt, Teleorman, Vâlcea", "https://www.distributieoltenia.ro/ro"],
  ["Rețele Electrice România", "Arad, București, Caraș-Severin, Constanța, Giurgiu, Hunedoara, Ialomița, Ilfov, Timiș, Tulcea", "https://www.reteleelectrice.ro/racordare"],
];

export default function Operators() {
  const [q, setQ] = useState("");
  const rows = useMemo(() => OPERATORS.filter(([n, z]) => !q || `${n} ${z}`.toLowerCase().includes(q.toLowerCase())), [q]);
  return (
    <div>
      <PageHeader eyebrow="Racordare în România" title="Distribuitori de energie"
        sub="Selectează operatorul de distribuție după zona locului de consum. Furnizorul nu este același lucru cu distribuitorul." />
      <div className="den-panel mb-6">
        <div className="den-field"><label>Caută operator / județ</label>
          <input className="den-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ex. Satu Mare, DEER, Iași..." data-testid="op-search" />
        </div>
      </div>
      <div className="den-panel">
        <div className="divide-y" style={{ borderColor: "var(--line)" }}>
          {rows.map(([name, zone, url]) => (
            <div key={name} className="py-4">
              <b className="text-[15px]">{name}</b>
              <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>{zone}</p>
              <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[12px] font-bold mt-2" style={{ color: "var(--blue)" }}>Site oficial / racordare <ExternalLink size={13} /></a>
            </div>
          ))}
        </div>
        <div className="den-notice mt-5">Operatorul corect se determină după adresa locului de consum, nu după preferința clientului. Verifică formularul și instrucțiunile actuale de pe site-ul operatorului.</div>
      </div>
    </div>
  );
}
