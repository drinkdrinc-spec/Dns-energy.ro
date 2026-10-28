import { useEffect, useRef, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { toast } from "sonner";
import { Upload, FileText, ClipboardCheck, UserRoundCog, Trash2, Download, RefreshCw } from "lucide-react";

const TYPES = [["prosumator","Dosar de prosumator"],["diu","Dosar de utilizare (DIU)"],["atr","Dosar ATR / spor de putere"],["pram","Buletin PRAM"],["anre","Dosar ANRE"],["electric","Dosar instalație electrică"],["other","Alt tip de dosar"]];
const LABELS = {cerere:"Cerere / formular",atr:"ATR / certificat de racordare",schema:"Schemă monofilară",pram:"Buletin PRAM",ci:"Act identitate / CUI",cf:"Carte funciară / act proprietate",fisa:"Fișe tehnice / certificate",diu:"Dosar de utilizare (DIU)"};
const STATUS = {complete:"Finalizat (confirmat manual)",incomplete:"Incomplet",manual_review:"Necesită verificare manuală",needs_review:"Necesită revizuire"};
function reviewFiles(files, kind) {
 const names=(files||[]).map(f=>f.original_filename||"").join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
 const hints=kind==="pram"?["pram"]:kind==="diu"?["diu","schema","ci"]:kind==="atr"?["cerere","atr","ci"]:kind==="anre"?["cerere","fisa","ci"]:kind==="prosumator"?["cerere","schema","pram","ci","fisa"]:["cerere","schema","ci"];
 const checks=hints.map(key=>({key,label:LABELS[key]||key,found:names.includes(key)}));
 const missing=checks.filter(c=>!c.found).map(c=>c.label);
 return {checks,missing,status:!(files||[]).length?"needs_review":missing.length?"incomplete":"manual_review",reviewed_at:new Date().toISOString(),note:"Verificare preliminară numai după denumirea fișierelor. Conținutul, valabilitatea, semnăturile și conformitatea trebuie verificate manual."};
}
export default function ArchivedDossiers(){
 const [items,setItems]=useState([]),[clients,setClients]=useState([]),[files,setFiles]=useState([]),[busy,setBusy]=useState(false);
 const [form,setForm]=useState({title:"",client_id:"",kind:"prosumator",reference:"",delegated_to:"",due_date:"",notes:""});
 const inputRef=useRef(null); const set=(k,v)=>setForm(p=>({...p,[k]:v}));
 const load=()=>Promise.all([api.get("/data/archived_dossiers").then(r=>setItems(r.data||[])).catch(()=>{}),api.get("/data/clients").then(r=>setClients(r.data||[])).catch(()=>{})]);
 useEffect(()=>{load()},[]);
 const upload=async()=>{if(!form.title.trim())return toast.error("Completează denumirea dosarului.");if(!files.length)return toast.error("Selectează fișierele dosarului.");setBusy(true);try{
  const saved=[];for(const file of files){const fd=new FormData();fd.append("file",file);const {data}=await api.post("/upload",fd,{headers:{"Content-Type":"multipart/form-data"}});saved.push({storage_path:data.storage_path,original_filename:data.original_filename,content_type:data.content_type,size:data.size});}
  const client=clients.find(c=>c.id===form.client_id),review=reviewFiles(saved,form.kind);
  await api.post("/data/archived_dossiers",{...form,client_name:client?.name||"",files:saved,review,status:review.status,history:[{at:new Date().toISOString(),action:"Dosar vechi încărcat și revizuit preliminar"}]});
  toast.success("Dosar arhivat și revizuit preliminar.");setForm({title:"",client_id:"",kind:"prosumator",reference:"",delegated_to:"",due_date:"",notes:""});setFiles([]);if(inputRef.current)inputRef.current.value="";await load();
 }catch(e){toast.error(e.response?.data?.detail||"Eroare la încărcare.");}finally{setBusy(false)}};
 const update=async(item,patch,action)=>{try{await api.put("/data/archived_dossiers/"+item.id,{...item,...patch,history:[...(item.history||[]),{at:new Date().toISOString(),action}]});toast.success("Dosar actualizat.");await load()}catch(e){toast.error(e.response?.data?.detail||"Nu am putut actualiza dosarul.")}};
 const recheck=item=>{const review=reviewFiles(item.files,item.kind);update(item,{review,status:review.status},"Revizuire preliminară reluată")};
 const delegate=item=>{const v=window.prompt("Numele sau e-mailul responsabilului",item.delegated_to||"");if(v!==null)update(item,{delegated_to:v},"Delegare actualizată")};
 const complete=item=>{if(window.confirm("Confirmi că ai verificat manual documentele și dosarul este complet?"))update(item,{status:"complete",completed_at:new Date().toISOString()},"Finalizat după verificare manuală")};
 const remove=async item=>{if(!window.confirm("Ștergi înregistrarea? Fișierele din stocare nu sunt șterse automat."))return;try{await api.delete("/data/archived_dossiers/"+item.id);await load()}catch(e){toast.error("Nu am putut șterge înregistrarea.")}};
 return <div data-testid="archived-dossiers-page"><PageHeader eyebrow="Registru și delegare" title="Dosare vechi — arhivă și revizuire" sub="Încarcă dosare existente, verifică preliminar lipsurile și deleagă responsabilitatea. Finalizarea se confirmă manual."/>
 <div className="den-panel mb-6"><h2 className="text-lg font-bold mb-4">Încarcă dosar vechi</h2><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
 <div className="den-field"><label>Denumire dosar *</label><input className="den-input" value={form.title} onChange={e=>set("title",e.target.value)} placeholder="Ex. Dosar prosumator Popescu"/></div>
 <div className="den-field"><label>Tip dosar</label><select className="den-input" value={form.kind} onChange={e=>set("kind",e.target.value)}>{TYPES.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></div>
 <div className="den-field"><label>Client asociat</label><select className="den-input" value={form.client_id} onChange={e=>set("client_id",e.target.value)}><option value="">Fără client asociat</option>{clients.map(c=><option key={c.id} value={c.id}>{c.name||c.company||c.id}</option>)}</select></div>
 <div className="den-field"><label>Număr / referință</label><input className="den-input" value={form.reference} onChange={e=>set("reference",e.target.value)}/></div>
 <div className="den-field"><label>Delegat (nume/e-mail)</label><input className="den-input" value={form.delegated_to} onChange={e=>set("delegated_to",e.target.value)} placeholder="Responsabil de dosar"/></div>
 <div className="den-field"><label>Termen</label><input type="date" className="den-input" value={form.due_date} onChange={e=>set("due_date",e.target.value)}/></div>
 <div className="den-field sm:col-span-2 lg:col-span-3"><label>Observații / ce trebuie făcut</label><textarea className="den-input" rows={2} value={form.notes} onChange={e=>set("notes",e.target.value)}/></div>
 <div className="den-field sm:col-span-2 lg:col-span-3"><label>Fișiere (PDF, imagini, DOC/DOCX, XLS/XLSX) *</label><input ref={inputRef} className="den-input" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx" onChange={e=>setFiles(Array.from(e.target.files||[]))}/><p className="text-xs mt-1" style={{color:"var(--muted)"}}>Revizuirea preliminară folosește denumirile fișierelor, nu confirmă conținutul juridic/tehnic.</p></div></div>
 <div className="mt-4"><Btn onClick={upload} disabled={busy}><Upload size={15}/>{busy?"Se încarcă...":"Încarcă, arhivează și revizuiește"}</Btn></div></div>
 <div className="den-panel"><h2 className="text-lg font-bold mb-4">Registru dosare ({items.length})</h2>{!items.length?<div className="py-8 text-center text-sm" style={{color:"var(--muted)"}}>Nu există încă dosare arhivate.</div>:<div className="space-y-4">{items.map(item=><div key={item.id} className="rounded-xl border p-4" style={{borderColor:"var(--line)"}} data-testid={"archived-"+item.id}>
 <div className="flex flex-wrap items-start gap-3"><div className="h-10 w-10 rounded-lg grid place-items-center" style={{background:"#eef4ff"}}><FileText size={20}/></div><div className="flex-1 min-w-0"><div className="font-bold">{item.title}</div><div className="text-xs mt-1" style={{color:"var(--muted)"}}>{TYPES.find(t=>t[0]===item.kind)?.[1]||item.kind} · {item.client_name||"Fără client"} {item.reference?"· Ref. "+item.reference:""}</div></div><span className="text-xs font-bold rounded-full px-3 py-1" style={{background:item.status==="complete"?"#dcfce7":item.status==="incomplete"?"#fef3c7":"#e5e7eb"}}>{STATUS[item.status]||STATUS.needs_review}</span></div>
 <div className="grid sm:grid-cols-2 gap-3 mt-4 text-sm"><div><b>Delegat:</b> {item.delegated_to||"Neatribuit"}<br/><b>Termen:</b> {item.due_date||"Nespecificat"}</div><div><b>Observații:</b> {item.notes||"—"}<br/><b>Fișiere:</b> {(item.files||[]).length}</div></div>
 <div className="mt-3 space-y-1">{(item.files||[]).map((f,i)=><div key={f.storage_path||i} className="flex items-center gap-2 text-xs"><FileText size={13}/><span className="flex-1 truncate">{f.original_filename}</span><a className="underline" href={fileUrl(f.storage_path)} target="_blank" rel="noreferrer"><Download size={13} className="inline"/> Deschide</a></div>)}</div>
 {item.review&&<div className="mt-3 rounded-lg p-3 text-xs" style={{background:"var(--bg)"}}><div className="font-bold mb-1"><ClipboardCheck size={14} className="inline mr-1"/>Revizuire preliminară</div>{(item.review.checks||[]).map(c=><div key={c.key}>{c.found?"✓":"•"} {c.label}: {c.found?"posibil identificat în denumirea fișierului":"nu a fost identificat după denumire"}</div>)}<p className="mt-2">{item.review.note}</p>{item.review.missing?.length>0&&<p className="mt-1 font-semibold">De verificat: {item.review.missing.join(", ")}</p>}</div>}
 <div className="flex flex-wrap gap-2 mt-4"><Btn variant="secondary" onClick={()=>recheck(item)}><RefreshCw size={14}/>Reia revizuirea</Btn><Btn variant="secondary" onClick={()=>delegate(item)}><UserRoundCog size={14}/>Deleagă</Btn><Btn onClick={()=>complete(item)} disabled={item.status==="complete"}>Confirmă finalizarea</Btn><Btn variant="secondary" onClick={()=>remove(item)}><Trash2 size={14}/>Șterge înregistrarea</Btn></div>
 </div>)}</div>}</div></div>;
}