import React from "react";

const protectionRows = [
["Supratensiune treapta I (U>)","Conform profilului OD / ATR","Conform cerinței","De verificat"],
["Supratensiune treapta II (U>>)","Conform profilului OD / ATR","Conform cerinței","De verificat"],
["Subtensiune treapta I (U<)","Conform profilului OD / ATR","Conform cerinței","De verificat"],
["Subtensiune treapta II (U<<)","Conform profilului OD / ATR","Conform cerinței","De verificat"],
["Supr frecvență (f>)","Conform profilului OD / ATR","Conform cerinței","De verificat"],
["Sub frecvență (f<)","Conform profilului OD / ATR","Conform cerinței","De verificat"],
["Protecție antiinsularizare","Conform EN 50549 și cerințelor OD","Activată dacă este cerută","De verificat"],
["Timp reconectare după revenirea tensiunii","900 secunde — conform solicitării","900 s (de confirmat cu OD/ATR)","De verificat"],
["LVRT — Low Voltage Ride Through","Conform profilului OD / certificat","Activat dacă este prevăzut și acceptat","De verificat"],
["HVRT — High Voltage Ride Through","Conform profilului OD / certificat","Conform profilului OD","De verificat"],
["Control putere reactivă (Q(U) / cos φ)","Conform ATR / soluției de racordare","Conform setării aprobate","De verificat"],
["Limitare putere activă / injecție","Conform ATR / limita aprobată","Conform puterii aprobate","De verificat"],
["Rampă de creștere a puterii","Conform cerinței OD, dacă se aplică","Conform profilului aprobat","De verificat"],
["Releu / întreruptor de interfață (SPI)","Conform soluției de racordare","Integrat sau extern, după caz","De verificat"],
["Protecție supracurent AC invertor","Conform calculelor și manualului","Tip și calibru conform proiectului","De verificat"],
["Protecție diferențială AC","Conform manualului invertorului și proiectului","Tip compatibil cu invertorul","De verificat"],
["SPD AC","Tip și nivel conform proiectului / OD","Conform calculului și coordonării","De verificat"],
["SPD DC","Conform tensiunii maxime la rece și manualului","Ucpv adecvat stringurilor","De verificat"],
["Separator DC","Conform tensiunii și curentului DC","Conform fișei tehnice","De verificat"],
["Siguranțe string","Dacă sunt necesare după calcul și fișa panoului","Conform curentului invers admis","De verificat"],
["Protecții baterie / BMS","Conform manualului bateriei și invertorului","Curent, tensiune și temperatură","De verificat"],
];

const cableRows = [
["Branșament – BMP","AC, Cu/Al conform proiect","Calculată după curent, lungime și pozare"],
["BMP – contor / smart meter","Conform schemei și contorului","Conform proiectului"],
["Invertor – tablou AC","AC, Cu/Al conform calculului","Putere, curent, lungime, cădere de tensiune"],
["Panouri – invertor (stringuri)","Cablu solar H1Z2Z2-K","Curent string, Voc la rece, lungime și pozare"],
["Baterie – invertor","Cablu DC conform manualului","Curent maxim, tensiune, lungime și protecție"],
["Conductor PE / echipotențializare","16 mm² Cu — valoare cerută ca regulă de proiect","Se verifică față de normativ, traseu și echipament"],
];

const protectionGroups = [
{title:"Rețea și racordare", items:["Întreruptor general / protecția branșamentului","Contorizare bidirecțională și măsură conform OD","Releu de interfață / SPI, când este prevăzut","Antiinsularizare și setări de rețea"]},
{title:"Tablou AC", items:["Întreruptoare dimensionate prin calcul","SPD AC coordonat cu instalația","Protecție diferențială conform invertorului și proiectului","Limitare injecție și control putere conform ATR"]},
{title:"Partea DC și stocare", items:["Separator DC cu tensiune și curent adecvate","SPD DC dimensionat după Voc maxim la temperatura minimă","Siguranțe de string dacă sunt necesare","Protecție baterie, BMS și cablu baterie–invertor"]},
];

function Header({sheet,subtitle}) {
 return <header className="se-header"><div className="se-brand"><span className="se-mark">D+</span><div><b>DNS ENERGY</b><small>SOLUȚII FOTOVOLTAICE COMPLETE</small></div></div><div className="se-title"><h1>{sheet==="E-01"?"SCHEMA MONOFILARĂ":"TABEL REGLAJE ȘI PROTECȚII INVERTOR"}</h1><p>{subtitle}</p></div><div className="se-meta"><b>Planșă: {sheet}</b><span>Revizie: 0</span><span>Beneficiar: de completat</span><span>Operator / ATR: de completat</span></div></header>;
}
function Block({title,children,className=""}) { return <section className={"se-block "+className}><h3>{title}</h3><div className="se-block-body">{children}</div></section>; }

function SchematicPage(){
 return <div className="se-sheet">
  <Header sheet="E-01" subtitle="Instalație fotovoltaică on-grid / hibridă cu stocare și backup"/>
  <div className="se-projectline"><span>Putere panouri: conform configurației</span><span>Invertor(e): conform selecției</span><span>Branșament: monofazat / trifazat</span><span>Limită injecție: conform ATR</span></div>
  <div className="se-flow">
   <Block title="1. REȚEA OD"><b>Rețea de distribuție</b><p>1~ 230 V sau 3~ 400/230 V</p><small>Conform ATR și branșamentului</small></Block>
   <div className="se-arrow">➜</div>
   <Block title="2. BMP / MĂSURĂ"><b>Contor bidirecțional</b><p>Întreruptor general</p><small>Calibru după branșament</small></Block>
   <div className="se-arrow">➜</div>
   <Block title="3. SMART METER"><b>Contor sistem</b><p>Comunicare cu invertorul</p><small>Model compatibil</small></Block>
   <div className="se-arrow">➜</div>
   <Block title="4. TABLOU GENERAL AC"><b>Protecții AC</b><p>Întreruptoare · SPD AC · RCD</p><small>Conform proiectului și manualului</small></Block>
  </div>
  <div className="se-bus"><span>BARĂ AC / CONEXIUNE LA INSTALAȚIA UTILIZATORULUI</span></div>
  <div className="se-lower">
   <Block title="5. PROTECȚIE DE INTERFAȚĂ"><b>SPI / releu de interfață</b><p>Antiinsularizare</p><p>Reconectare: 900 s*</p><small>*Se confirmă cu ATR și operatorul de distribuție.</small></Block>
   <Block title="6. INVERTOR / INVERTOARE"><b>Model și putere din selecția aplicației</b><p>Monofazat sau trifazat după compatibilitate</p><p>LVRT / HVRT și control de rețea conform profilului OD</p></Block>
   <Block title="7. SISTEM DE STOCARE"><b>Baterie + BMS (opțional)</b><p>Cablu DC dimensionat după curent și manual</p><small>Protecție DC conform producătorului</small></Block>
  </div>
  <div className="se-lower se-lower2">
   <Block title="8. STRINGURI FOTOVOLTAICE"><b>String 1 · String 2 · ...</b><p>Modulele și MPPT-urile alese în aplicație</p><p>Cablu solar H1Z2Z2-K, secțiune calculată</p></Block>
   <Block title="9. TABLOU DC"><b>Separator DC · SPD DC</b><p>Siguranțe de string dacă sunt necesare</p><small>SPD dimensionat după Voc la rece și manual</small></Block>
   <Block title="10. ÎMPĂMÂNTARE ȘI PE"><b>PE și legături echipotențiale</b><p>16 mm² Cu — regulă de proiect solicitată</p><small>Validare conform normativului și configurației</small></Block>
  </div>
  <div className="se-bottomgrid">
   <div><h3>SECȚIUNI CONDUCTOARE — CALCUL AUTOMAT</h3><table><thead><tr><th>Traseu</th><th>Secțiune</th><th>Criteriu</th></tr></thead><tbody>{cableRows.map((r,i)=><tr key={i}><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>)}</tbody></table></div>
   <div><h3>LEGENDĂ ȘI NOTĂ</h3><p><i className="se-line ac"/> Circuit AC</p><p><i className="se-line dc"/> Circuit DC</p><p><i className="se-line pe"/> Conductor PE</p><p className="se-note">Planșă-model. Secțiunile și protecțiile finale se generează după introducerea datelor reale și se verifică de personal autorizat.</p></div>
  </div>
 </div>;
}
function ProtectionPage(){
 return <div className="se-sheet">
  <Header sheet="E-02" subtitle="Conform ANRE, operatorului de distribuție, ATR și documentației producătorilor"/>
  <div className="se-projectline"><span>Invertor(e): din selecția proiectului</span><span>Branșament: din proiect</span><span>Reconectare solicitată: 900 s</span><span>LVRT: conform profilului OD</span></div>
  <div className="se-callout"><b>IMPORTANT:</b> tabelul este completat automat pe baza invertorului, configurației, ATR și cerințelor operatorului. Valorile numerice nu se aplică universal. Câmpurile marcate „De verificat” necesită confirmarea documentată.</div>
  <div className="se-tablewrap"><table className="se-protect-table"><thead><tr><th>Nr.</th><th>Funcție / protecție</th><th>Valoare cerută / referință</th><th>Temporizare</th><th>Setare efectivă</th><th>Verificare / document</th><th>Status</th></tr></thead><tbody>{protectionRows.map((r,i)=><tr key={i}><td>{i+1}</td><td><b>{r[0]}</b></td><td>{r[1]}</td><td>{i===7?"900 s*":"Conform profilului"}</td><td>{r[2]}</td><td>Fișă invertor / ATR / cerință OD</td><td><span className="se-status">De verificat</span></td></tr>)}</tbody></table></div>
  <div className="se-bottomgrid se-bottom-e02">
   <div><h3>DOCUMENTE DE VERIFICAT</h3><ul>{["Certificat de conformitate UE și fișă tehnică invertor","Lista de invertoare acceptate de operator, dacă este publicată","ATR / soluția de racordare și profilul de rețea aplicabil","Manual producător și tabel oficial de setări","Proces-verbal de punere în funcțiune și raport setări","Documentație SPD, RCD, întreruptoare și protecții externe"].map(x=><li key={x}>□ {x}</li>)}</ul></div>
   <div><h3>PROTECȚII PE GRUPURI</h3>{protectionGroups.map(g=><div className="se-group" key={g.title}><b>{g.title}</b><ul>{g.items.map(x=><li key={x}>{x}</li>)}</ul></div>)}</div>
   <div><h3>NOTE TEHNICE</h3><ol><li>900 s este valoarea cerută de utilizator și se aplică numai după confirmarea cerinței OD/ATR.</li><li>LVRT/HVRT se setează conform profilului aprobat și certificatului invertorului; nu se activează automat dacă nu este prevăzut.</li><li>Pragurile, temporizările, protecția de interfață și puterea reactivă se preiau din documentația aplicabilă.</li><li>Planșa nu înlocuiește proiectul tehnic și verificarea de către personal autorizat.</li></ol></div>
  </div>
 </div>;
}

export default function SchemaTehnica(){
 const [page,setPage]=React.useState("E-01");
 return <div className="schema-tehnica-page">
  <style>{`
  .schema-tehnica-page{padding:22px;background:#eef3f8;color:#15314c;min-height:100vh;font-family:Arial,sans-serif}
  .se-toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:0 auto 16px;max-width:1500px}
  .se-toolbar h2{margin:0;font-size:20px}.se-tabs{display:flex;gap:8px}.se-tabs button,.se-print{border:1px solid #c6d4e2;background:#fff;color:#15314c;padding:10px 15px;border-radius:8px;font-weight:700;cursor:pointer}.se-tabs button.active{background:#0d477a;color:#fff}
  .se-sheet{max-width:1500px;margin:0 auto 24px;background:#fff;border:1px solid #b8c9d8;box-shadow:0 5px 22px #183a5715;padding:14px;overflow:auto}
  .se-header{display:grid;grid-template-columns:1.1fr 1.7fr 1fr;border:1px solid #173d63;min-width:900px}
  .se-brand{display:flex;align-items:center;gap:10px;padding:12px;color:#0e765d;border-right:1px solid #b5c9da}.se-brand b{font-size:24px;letter-spacing:1px}.se-brand small{display:block;font-size:10px;letter-spacing:1px}.se-mark{border:3px solid #29996e;border-radius:50%;padding:7px;font-weight:900;font-size:19px}
  .se-title{text-align:center;padding:10px;border-right:1px solid #b5c9da}.se-title h1{font-size:25px;margin:0 0 5px;color:#14385c}.se-title p{margin:0;font-size:12px}
  .se-meta{display:flex;flex-direction:column;gap:4px;padding:9px;font-size:11px}
  .se-projectline{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;border:1px solid #b7c9d8;border-top:0;padding:10px;font-size:11px;background:#f5f9fc}
  .se-flow{display:flex;align-items:stretch;gap:7px;margin-top:17px;min-width:1000px}.se-arrow{align-self:center;color:#d33b32;font-size:25px;font-weight:bold}
  .se-block{border:1.5px dashed #3a8bc6;border-radius:8px;overflow:hidden;background:#fbfdff;min-width:0;flex:1}
  .se-block h3{font-size:12px;text-align:center;margin:0;padding:8px 5px;background:#eaf4fc;border-bottom:1px solid #b8d0e2;color:#143e66}
  .se-block-body{padding:10px;font-size:11px;line-height:1.5}.se-block-body p{margin:5px 0}.se-block-body small{font-size:10px;color:#5b6d7e}
  .se-bus{margin:14px 5% 18px;border-top:4px solid #d83b32;text-align:center;font-size:10px;font-weight:bold;color:#8b2e2a}.se-bus span{background:#fff;padding:0 12px;position:relative;top:-8px}
  .se-lower{display:grid;grid-template-columns:1fr 1.5fr 1fr;gap:12px;margin-top:12px}.se-lower2{grid-template-columns:1.2fr 1fr 1fr}
  .se-lower .se-block:nth-child(2){border-color:#1c79b9}.se-lower .se-block:nth-child(3){border-color:#42a66b}.se-lower2 .se-block:nth-child(3){border-color:#42a66b}
  .se-bottomgrid{display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-top:14px}.se-bottomgrid h3{background:#114a78;color:#fff;font-size:12px;padding:8px;margin:0}.se-bottomgrid table,.se-protect-table{border-collapse:collapse;width:100%;font-size:10px}.se-bottomgrid th,.se-bottomgrid td,.se-protect-table th,.se-protect-table td{border:1px solid #c3d1dc;padding:6px;text-align:left;vertical-align:top}.se-bottomgrid th{background:#e9f2fa}.se-line{display:inline-block;width:28px;border-top:3px solid #d83b32;margin-right:8px}.se-line.dc{border-color:#2476d2}.se-line.pe{border-color:#2ca56a;border-top-style:dashed}.se-note{font-size:11px;line-height:1.5;background:#fff8e8;padding:10px;border-left:3px solid #e3a632}
  .se-callout{background:#fff8e7;border:1px solid #e6c66c;border-radius:6px;padding:12px;margin:12px 0;font-size:12px;line-height:1.5}
  .se-tablewrap{overflow:auto}.se-protect-table{min-width:1120px;font-size:10px}.se-protect-table th{background:#104a79;color:#fff;font-size:10px}.se-protect-table tbody tr:nth-child(even){background:#f5f9fc}.se-status{display:inline-block;border-radius:20px;background:#fff0d0;color:#8b5b00;padding:4px 7px;font-weight:bold;white-space:nowrap}
  .se-bottom-e02{grid-template-columns:1.1fr 1.2fr 1fr}.se-bottom-e02 ul,.se-bottom-e02 ol{margin:8px 0;padding-left:20px;font-size:10px;line-height:1.6}.se-group{padding:6px 8px;border-bottom:1px solid #d5e1e9}.se-group ul{margin:4px 0}.se-print{background:#0d477a;color:#fff}
  @media(max-width:900px){.schema-tehnica-page{padding:8px}.se-header{grid-template-columns:1fr}.se-brand,.se-title{border-right:0;border-bottom:1px solid #b5c9da}.se-lower,.se-lower2,.se-bottomgrid,.se-bottom-e02{grid-template-columns:1fr}.se-flow{min-width:900px}.se-sheet{padding:8px}}
  @media print{.schema-tehnica-page{padding:0;background:#fff}.se-toolbar{display:none}.se-sheet{box-shadow:none;border:0;max-width:none;margin:0;page-break-after:always}.se-sheet:last-child{page-break-after:auto}.se-header,.se-flow,.se-tablewrap{break-inside:avoid}@page{size:A3 landscape;margin:8mm}}
  `}</style>
  <div className="se-toolbar"><h2>DNS Energy · Planșe tehnice</h2><div className="se-tabs"><button className={page==="E-01"?"active":""} onClick={()=>setPage("E-01")}>E-01 · Schema monofilară</button><button className={page==="E-02"?"active":""} onClick={()=>setPage("E-02")}>E-02 · Protecții invertor</button><button className="se-print" onClick={()=>window.print()}>Tipărește / Salvează PDF</button></div></div>
  {page==="E-01"?<SchematicPage/>:<ProtectionPage/>}
 </div>;
}
