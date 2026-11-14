import { useCallback, useEffect, useState } from "react";
import { Download, FilePlus2, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, API } from "@/lib/api";
import { Btn, PageHeader } from "@/components/Layout";

const today = () => new Date().toISOString().slice(0, 10);
const soilOptions = [["uscat", "Uscat · coeficient 1,1"], ["mediu", "Umiditate medie · coeficient 1,3"], ["foarte umed", "Foarte umed · coeficient 1,5"]];

export default function PramRegistry() {
  const [records, setRecords] = useState([]);
  const [clients, setClients] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [staff, setStaff] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ client_id: "", address: "", date: today(), soil: "mediu", earth_ohm: "", earth_limit: "4", instrument_id: "", verifier_id: "" });

  const load = useCallback(async () => {
    try {
      const [p, c, i, s] = await Promise.all([api.get("/data/pram"), api.get("/data/clients"), api.get("/data/instruments"), api.get("/data/staff")]);
      setRecords(p.data.filter((x) => x.source === "Individual").sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")));
      setClients(c.data); setInstruments(i.data); setStaff(s.data);
    } catch (e) { toast.error(e.response?.data?.detail || "Datele PRAM nu s-au putut încărca"); }
  }, []);

  useEffect(() => { load(); }, [load]);
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const client = clients.find((c) => c.id === form.client_id);
  const newRecord = async (print) => {
    setSaving(true);
    try {
      const { data } = await api.post("/pram/create", form);
      toast.success(`Buletin ${data.number} salvat`);
      setOpen(false); setForm({ client_id: "", address: "", date: today(), soil: "mediu", earth_ohm: "", earth_limit: "4", instrument_id: "", verifier_id: "" });
      await load();
      if (print) window.open(`${API}/pram/${data.id}/pdf?auth=${localStorage.getItem("den_token") || ""}`, "_blank", "noopener,noreferrer");
    } catch (e) { toast.error(e.response?.data?.detail || "Buletinul nu s-a putut salva"); }
    finally { setSaving(false); }
  };

  return <div>
    <PageHeader eyebrow="Măsurători electrice" title="Buletine PRAM" sub="Emite și păstrează buletine de verificare a prizei de pământ, independent de un dosar de prosumator."
      action={<div className="flex gap-2"><Btn variant="secondary" onClick={load}><RefreshCw size={15} /> Reîncarcă</Btn><Btn onClick={() => setOpen((v) => !v)}><Plus size={15} /> Buletin nou</Btn></div>} />

    {open && <section className="den-panel mb-5" data-testid="pram-individual-form">
      <h2 className="mb-4 text-base font-bold">Măsurătoare PRAM nouă</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="den-field"><span>Client *</span><select className="den-input" value={form.client_id} onChange={(e) => { const c = clients.find((x) => x.id === e.target.value); set("client_id", e.target.value); if (c && !form.address) set("address", c.address || ""); }}><option value="">Alege clientul…</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.name}{c.phone ? ` · ${c.phone}` : ""}</option>)}</select></label>
        <label className="den-field"><span>Adresă punct de măsură *</span><input className="den-input" value={form.address} onChange={(e) => set("address", e.target.value)} placeholder={client?.address || "Stradă, număr, localitate"} /></label>
        <label className="den-field"><span>Data măsurătorii *</span><input className="den-input" type="date" value={form.date} onChange={(e) => set("date", e.target.value)} /></label>
        <label className="den-field"><span>Starea solului *</span><select className="den-input" value={form.soil} onChange={(e) => set("soil", e.target.value)}>{soilOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="den-field"><span>Rezistență măsurată Rd (Ω) *</span><input className="den-input" type="number" min="0.01" step="any" value={form.earth_ohm} onChange={(e) => set("earth_ohm", e.target.value)} placeholder="Valoarea citită de pe aparat" /></label>
        <label className="den-field"><span>Valoare admisă (Ω) *</span><input className="den-input" type="number" min="0.01" step="any" value={form.earth_limit} onChange={(e) => set("earth_limit", e.target.value)} /></label>
      <label className="den-field"><span>Aparat de măsură *</span><select className="den-input" value={form.instrument_id} onChange={(e) => set("instrument_id", e.target.value)}><option value="">Alege aparatul…</option>{instruments.filter((i) => i.active !== false && i.measures_grounding !== false).map((i) => <option key={i.id} value={i.id}>{i.maker_model || i.name || "Aparat"}{i.serial ? ` · ${i.serial}` : ""}</option>)}</select></label>
        <label className="den-field"><span>Verificator PRAM *</span><select className="den-input" value={form.verifier_id} onChange={(e) => set("verifier_id", e.target.value)}><option value="">Alege verificatorul…</option>{staff.filter((s) => s.active !== false).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      </div>
      {(!clients.length || !instruments.length || !staff.length) && <p className="mt-3 rounded-lg px-3 py-2 text-xs" style={{ color: "#8a5a00", background: "#fff8e6" }}>Pentru emitere, completează mai întâi Contacte, aparatul PRAM și personalul în Setări.</p>}
      <div className="mt-5 flex flex-wrap gap-2 border-t pt-4" style={{ borderColor: "var(--line)" }}>
        <Btn disabled={saving} onClick={() => newRecord(false)}><FilePlus2 size={15} /> Salvează</Btn>
        <Btn variant="secondary" disabled={saving} onClick={() => newRecord(true)}><Download size={15} /> Salvează + PDF</Btn>
        <Btn variant="secondary" onClick={() => setOpen(false)}>Anulează</Btn>
      </div>
    </section>}

    <section className="den-panel" data-testid="pram-individual-list">
      <h2 className="mb-4 text-base font-bold">Buletine individuale ({records.length})</h2>
      {!records.length ? <p className="rounded-lg py-8 text-center text-sm" style={{ color: "var(--muted)", background: "var(--bg)" }}>Nu ai emis încă buletine PRAM individuale.</p> : <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left" style={{ color: "var(--muted)" }}>{["Număr", "Dată", "Client", "Adresă", "Rd măsurat", "Aparat / verificator", ""].map((x) => <th key={x} className="px-3 py-2 font-semibold">{x}</th>)}</tr></thead><tbody>{records.map((r) => <tr key={r.id} className="border-t" style={{ borderColor: "var(--line)" }}><td className="px-3 py-3 font-bold">{r.number}</td><td className="px-3 py-3 whitespace-nowrap">{r.date}</td><td className="px-3 py-3">{r.client_name}</td><td className="px-3 py-3">{r.address}</td><td className="px-3 py-3 whitespace-nowrap">{r.earth_ohm} Ω</td><td className="px-3 py-3">{r.instrument} · {r.verifier}</td><td className="px-3 py-3"><a className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} href={`${API}/pram/${r.id}/pdf?auth=${localStorage.getItem("den_token") || ""}`} target="_blank" rel="noreferrer"><Download size={14} /> PDF</a></td></tr>)}</tbody></table></div>}
    </section>
  </div>;
}
