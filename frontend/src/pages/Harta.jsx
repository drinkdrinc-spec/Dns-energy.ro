import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { MapPin, Search } from "lucide-react";

const STAGES = ["CER", "Așteaptă depunere", "Dosar depus", "Factură ATR", "Așteaptă instalare", "Instalat", "PV Teste / PIF", "Finalizat"];
const C = {
  "satu mare":[29,11],"maramureș":[38,13],"maramures":[38,13],"suceava":[66,15],"botoșani":[80,12],"botosani":[80,12],
  "iași":[83,30],"iasi":[83,30],"bistrița-năsăud":[53,25],"bistrita-nasaud":[53,25],"sălaj":[33,29],"salaj":[33,29],
  "bihor":[19,27],"cluj":[39,33],"mureș":[55,42],"mures":[55,42],"harghita":[69,42],"neamț":[74,36],"neamt":[74,36],
  "vaslui":[86,44],"arad":[13,43],"alba":[41,48],"sibiu":[49,57],"brașov":[66,56],"brasov":[66,56],
  "bacău":[77,49],"bacau":[77,49],"vrancea":[85,55],"galați":[91,57],"galati":[91,57],"timiș":[11,57],"timis":[11,57],
  "hunedoara":[33,57],"caraș-severin":[18,68],"caras-severin":[18,68],"gorj":[39,69],"vâlcea":[49,69],"valcea":[49,69],
  "argeș":[61,68],"arges":[61,68],"prahova":[69,67],"buzău":[79,67],"buzau":[79,67],"brăila":[89,69],"braila":[89,69],
  "tulcea":[95,76],"mehedinți":[30,79],"mehedinti":[30,79],"dolj":[43,80],"olt":[54,78],"dâmbovița":[65,75],"dambovita":[65,75],
  "ilfov":[70,84],"bucurești":[73,86],"bucuresti":[73,86],"ialomița":[80,80],"ialomita":[80,80],
  "călărași":[78,90],"calarasi":[78,90],"constanța":[93,88],"constanta":[93,88],"teleorman":[61,90],"giurgiu":[70,93],
};
const countyKey = (s) => (s || "").trim().toLocaleLowerCase("ro");
const isOld = (d) => { const t = Date.parse(d.updated_at || d.created_at || ""); const x = new Date(); x.setMonth(x.getMonth() - 6); return Number.isFinite(t) && t < x.getTime(); };

export default function Harta() {
  const [items, setItems] = useState([]);
  const [stage, setStage] = useState("");
  const [query, setQuery] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [county, setCounty] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api.get("/data/prosumator").then((r) => setItems(r.data || [])).catch(() => setError("Nu am putut încărca dosarele. Verifică legătura cu serverul.")); }, []);

  const rows = useMemo(() => items.filter((d) => {
    const hay = [d.number,d.client_name,d.address,d.locality,d.county,d.operator,d.pod].filter(Boolean).join(" ").toLocaleLowerCase("ro");
    return (includeArchived || !isOld(d)) && (!stage || d.status === stage) && (!county || countyKey(d.county) === county)
      && (!query || hay.includes(query.toLocaleLowerCase("ro")));
  }), [items, stage, county, query, includeArchived]);
  const grouped = useMemo(() => rows.reduce((acc, d) => { const k = d.county || "Județ neprecizat"; acc[k] = (acc[k] || 0) + 1; return acc; }, {}), [rows]);
  const counties = Object.keys(grouped).sort((a,b) => a.localeCompare(b,"ro"));
  const points = Object.entries(grouped).map(([name,count]) => ({name,count,pos:C[countyKey(name)]})).filter((x)=>x.pos);

  return <div>
    <PageHeader eyebrow="Lucrări" title="Harta lucrărilor" sub="Distribuția dosarelor pe județe și acces rapid la fiecare lucrare. Pozițiile sunt orientative, la nivel de județ." />
    <div className="den-panel">
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="den-field min-w-[210px] flex-1"><span className="sr-only">Caută dosar</span><div className="relative"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{color:"var(--muted)"}}/><input className="den-input pl-9" placeholder="Client, POD, localitate…" value={query} onChange={(e)=>setQuery(e.target.value)}/></div></label>
        <label className="den-field min-w-[175px]"><span className="sr-only">Filtrează după etapă</span><select className="den-input" value={stage} onChange={(e)=>setStage(e.target.value)}><option value="">Toate etapele</option>{STAGES.map((s)=><option key={s}>{s}</option>)}</select></label>
        <label className="den-field min-w-[160px]"><span className="sr-only">Filtrează după județ</span><select className="den-input" value={county} onChange={(e)=>setCounty(e.target.value)}><option value="">Toate județele</option>{counties.map((s)=><option key={s} value={countyKey(s)}>{s} ({grouped[s]})</option>)}</select></label>
        <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={includeArchived} onChange={(e)=>setIncludeArchived(e.target.checked)}/> și arhivate</label>
        <span className="pb-2 text-xs" style={{color:"var(--muted)"}}>{rows.length} din {items.length} dosare</span>
      </div>
      {error ? <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p> : <>
        <div className="grid gap-5 xl:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.1fr)]">
          <div className="rounded-xl border p-3 sm:p-5" style={{borderColor:"var(--line)",background:"#f5f8f6"}}>
            <div className="mb-2 flex items-center gap-2 text-sm font-bold"><MapPin size={16} style={{color:"var(--green)"}}/> Dosare pe județe</div>
            <svg viewBox="0 0 100 100" role="img" aria-label="Hartă orientativă a României, dosare grupate pe județ" className="w-full">
              <path d="M 10 39 L 16 26 L 28 17 L 40 18 L 48 9 L 62 13 L 74 9 L 86 17 L 94 29 L 90 42 L 95 54 L 91 66 L 97 76 L 87 88 L 75 93 L 67 86 L 56 92 L 45 85 L 35 87 L 25 78 L 17 70 L 12 57 Z" fill="#e4eee8" stroke="#9eb6a7" strokeWidth="1.2"/>
              {points.map((p)=>{const active=countyKey(p.name)===county;return <g key={p.name} role="button" tabIndex="0" aria-label={`${p.name}: ${p.count} dosare`} onClick={()=>setCounty(active?"":countyKey(p.name))} onKeyDown={(e)=>e.key==="Enter"&&setCounty(active?"":countyKey(p.name))} style={{cursor:"pointer"}}>
                <circle cx={p.pos[0]} cy={p.pos[1]} r={Math.min(2.2+Math.log2(p.count+1)*.65,5.3)} fill={active?"#176a43":"#26915a"} stroke="white" strokeWidth="1.1"/><text x={p.pos[0]} y={p.pos[1]+.8} textAnchor="middle" fill="white" fontSize="2.2" fontWeight="700">{p.count}</text>
              </g>})}
            </svg>
            <p className="mt-2 text-[10px]" style={{color:"var(--muted)"}}>Selectează un cerc pentru a filtra dosarele județului. Harta nu folosește coordonate exacte ale clienților.</p>
          </div>
          <div className="max-h-[520px] overflow-auto rounded-xl border" style={{borderColor:"var(--line)"}}>
            {rows.length===0 ? <p className="p-8 text-center text-sm" style={{color:"var(--muted)"}}>Nu sunt lucrări care să corespundă filtrelor.</p> : rows.map((d)=><Link key={d.id} to={`/prosumator?edit=${encodeURIComponent(d.id)}`} className="flex items-start gap-3 border-b p-3 hover:bg-[#f7faf8]" style={{borderColor:"var(--line)"}}>
              <MapPin size={16} className="mt-0.5 shrink-0" style={{color:"var(--green)"}}/><span className="min-w-0 flex-1"><b className="block truncate text-sm">{d.client_name||"Beneficiar neprecizat"}</b><span className="block truncate text-xs" style={{color:"var(--muted)"}}>{[d.address,d.locality,d.county].filter(Boolean).join(", ")||"Amplasament necompletat"}</span><span className="mt-1 block text-[10px]" style={{color:"var(--muted)"}}>{[d.number&&`Dosar ${d.number}`,d.operator,d.status,d.power&&`${d.power} kW`].filter(Boolean).join(" · ")}</span></span></Link>)}
          </div>
        </div>
        {counties.some((n)=>!C[countyKey(n)])&&<div className="mt-4 rounded-lg p-3 text-xs" style={{background:"#fff8e6",color:"#7a5412"}}>Dosare listate fără reper pe harta orientativă: {counties.filter((n)=>!C[countyKey(n)]).join(", ")}.</div>}
      </>}
    </div>
  </div>;
}
