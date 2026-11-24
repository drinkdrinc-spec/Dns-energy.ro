import { useMemo, useState } from "react";
import { PageHeader } from "@/components/Layout";
import { ExternalLink } from "lucide-react";

const OPERATORS = [
  {
    name: "DEER — Transilvania Nord",
    counties: "Bihor, Bistrița-Năsăud, Cluj, Maramureș, Satu Mare, Sălaj",
    url: "https://avize.distributie-energie.ro/",
    label: "Portal dedicat pentru cereri și documente",
  },
  {
    name: "DEER — Transilvania Sud",
    counties: "Alba, Brașov, Covasna, Harghita, Mureș, Sibiu",
    url: "https://avize.distributie-energie.ro/",
    label: "Portal dedicat pentru cereri și documente",
  },
  {
    name: "DEER — Muntenia Nord",
    counties: "Brăila, Buzău, Dâmbovița, Galați, Prahova, Vrancea",
    url: "https://avize.distributie-energie.ro/",
    label: "Portal dedicat pentru cereri și documente",
  },
  {
    name: "Delgaz Grid",
    counties: "Bacău, Botoșani, Iași, Neamț, Suceava, Vaslui",
    url: "https://delgaz.ro/login",
    label: "Cont și depunere cereri",
  },
  {
    name: "Distribuție Energie Oltenia",
    counties: "Argeș, Dolj, Gorj, Mehedinți, Olt, Teleorman, Vâlcea",
    url: "https://portal.distributieoltenia.ro/",
    label: "Portal DEO Connect",
  },
  {
    name: "Rețele Electrice România",
    counties: "Arad, București, Caraș-Severin, Constanța, Giurgiu, Hunedoara, Ialomița, Ilfov, Timiș, Tulcea",
    url: "https://contulmeu.reteleelectrice.ro/",
    label: "Cont online și cereri de racordare",
  },
];

export default function Operators() {
  const [q, setQ] = useState("");
  const rows = useMemo(
    () => OPERATORS.filter(({ name, counties }) => !q || `${name} ${counties}`.toLowerCase().includes(q.toLowerCase())),
    [q],
  );

  return (
    <div>
      <PageHeader
        eyebrow="Racordare în România"
        title="Distribuitori de energie"
        sub="Selectează operatorul de distribuție după zona locului de consum. Furnizorul nu este același lucru cu distribuitorul."
      />
      <div className="den-panel mb-6">
        <div className="den-field">
          <label>Caută operator / județ</label>
          <input
            className="den-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ex. Satu Mare, DEER, Iași..."
            data-testid="op-search"
          />
        </div>
      </div>
      <div className="den-panel">
        <div className="divide-y" style={{ borderColor: "var(--line)" }}>
          {rows.map(({ name, counties, url, label }) => (
            <div key={name} className="py-4">
              <b className="text-[15px]">{name}</b>
              <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>{counties}</p>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[12px] font-bold mt-2"
                style={{ color: "var(--blue)" }}
              >
                {label} <ExternalLink size={13} />
              </a>
            </div>
          ))}
        </div>
        <div className="den-notice mt-5">
          Operatorul corect se determină după adresa locului de consum, nu după preferința clientului. Portalul se deschide într-o filă nouă a browserului; autentificarea rămâne la operator, iar DNS Energy nu colectează parola și nu depune automat cererea.
        </div>
      </div>
    </div>
  );
}
