import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileDown, Copy, Eye, FileSignature, Save, ArrowLeft, Trash2 } from "lucide-react";
import { api, API } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { OfferItems } from "./OfferItems";
import { ContractDialog } from "./ContractDialog";

const ST = ["Ciornă", "Trimisă", "Acceptată", "Respinsă", "Expirată"];
const BEN = [["name", "Nume și prenume / denumire societate"], ["cui_cnp", "CUI / CNP"], ["reg_com", "Nr. Registrul Comerțului", "PJ"], ["ci_series", "Serie CI", "PF"], ["ci_number", "Număr CI", "PF"],
  ["address", "Adresa beneficiarului"], ["install_address", "Adresa locului de instalare"], ["billing", "Date de facturare (dacă diferă)"], ["phone", "Telefon"], ["email", "E-mail"],
  ["rep_name", "Reprezentant legal", "PJ"], ["rep_role", "Funcția reprezentantului", "PJ"]];
const tok = () => localStorage.getItem("den_token");
const money = (v, c) => `${(v || 0).toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${c === "EUR" ? "€" : "lei"}`;

export function OfferEditor({ id, onBack, onOpen }) {
  const [o, setO] = useState(null);
  const [prev, setPrev] = useState(false);
  const [cd, setCd] = useState(false);
  const load = () => api.get(`/offers/${id}`).then((r) => setO(r.data));
  useEffect(() => { let alive = true; api.get(`/offers/${id}`).then((r) => alive && setO(r.data)); return () => { alive = false; }; }, [id]);
  if (!o) return null;
  const set = (k, v) => setO({ ...o, [k]: v });
  const b = o.beneficiary || {};
  const save = async (confirm = false) => {
    try { const { data } = await api.put(`/offers/${id}`, { ...o, confirm_contract_change: confirm }); setO(data); toast.success("Oferta a fost salvată"); return true; }
    catch (e) {
      if (e.response?.status === 409 && window.confirm(`${e.response.data.detail}\n\nSalvezi modificările?`)) return save(true);
      toast.error(e.response?.data?.detail || "Eroare"); return false;
    }
  };
  const status = async (st) => { if (await save()) { try { await api.post(`/offers/${id}/status`, { status: st }); load(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } } };
  const dup = async () => { const { data } = await api.post(`/offers/${id}/duplicate`); toast.success(`Ofertă nouă nr. ${data.number}`); onOpen(data.id); };
  const pdf = `${API}/offers/${id}/pdf?auth=${tok()}`;
  const ta = (k, l, rows = 3) => <div className="den-field sm:col-span-2"><label>{l}</label><textarea className="den-input" rows={rows} value={o[k] ?? ""} onChange={(e) => set(k, e.target.value)} data-testid={`offer-${k}`} /></div>;
  const t = o.totals || {};
  return (
    <div className="space-y-4" data-testid="offer-editor">
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={onBack} className="inline-flex items-center gap-1 text-sm font-bold" data-testid="offer-back"><ArrowLeft size={15} /> Oferte</button>
        <h2 className="text-xl font-extrabold ml-2" data-testid="offer-title-number">Ofertă de preț nr. {o.number}</h2>
        <span className="text-xs rounded-full px-2 py-0.5 bg-slate-100" data-testid="offer-version">v{o.version}</span>
        <select className="den-input !py-1 !text-sm ml-auto" style={{ width: 140 }} value={o.status} onChange={(e) => status(e.target.value)} data-testid="offer-status">{ST.map((s) => <option key={s}>{s}</option>)}</select>
        <Btn onClick={() => save()} data-testid="offer-save"><Save size={14} /> Salvează</Btn>
        <Btn variant="secondary" onClick={async () => (await save()) && setPrev(true)} data-testid="offer-preview"><Eye size={14} /> Previzualizare</Btn>
        <a href={pdf} target="_blank" rel="noopener noreferrer" data-testid="offer-pdf"><Btn variant="secondary"><FileDown size={14} /> PDF</Btn></a>
        <Btn variant="secondary" onClick={dup} data-testid="offer-duplicate"><Copy size={14} /> Duplică</Btn>
        {o.status === "Ciornă" && !o.contract_id && <Btn variant="secondary" onClick={async () => { if (!window.confirm(`Ștergi oferta nr. ${o.number}? Numărul rămâne rezervat.`)) return; try { await api.delete(`/offers/${id}`); toast.success("Ofertă ștearsă"); onBack(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } }} data-testid="offer-delete"><Trash2 size={14} /> Șterge</Btn>}
        {o.status === "Acceptată" && <Btn onClick={async () => (await save()) && setCd(true)} data-testid="offer-generate-contract"><FileSignature size={14} /> Generează contract</Btn>}
      </div>
      {o.contract_outdated && <div className="den-panel text-sm" style={{ background: "#fff8e6" }} data-testid="offer-contract-outdated">Oferta a fost modificată după generarea contractului. Contractul existent NU s-a modificat — îl poți regenera din „Generează contract” (versiunea veche rămâne în istoric).</div>}
      <div className="den-panel">
        <h3 className="font-bold mb-2">Beneficiar</h3>
        <div className="flex gap-4 text-sm mb-2">{[["PF", "Persoană fizică"], ["PJ", "Persoană juridică"]].map(([k, l]) => (
          <label key={k} className="flex items-center gap-2"><input type="radio" checked={(b.kind || "PF") === k} onChange={() => set("beneficiary", { ...b, kind: k })} data-testid={`offer-ben-kind-${k}`} /> {l}</label>))}</div>
        <div className="grid sm:grid-cols-3 gap-2">{BEN.filter(([, , only]) => !only || only === (b.kind || "PF")).map(([k, l]) => (
          <div key={k} className="den-field"><label>{l}</label><input className="den-input" value={b[k] ?? ""} onChange={(e) => set("beneficiary", { ...b, [k]: e.target.value })} data-testid={`offer-ben-${k}`} /></div>))}</div>
      </div>
      <div className="den-panel grid sm:grid-cols-2 gap-2">
        <div className="den-field sm:col-span-2"><label>Titlul ofertei (ex. Achiziție sistem fotovoltaic hibrid 15 kWp)</label><input className="den-input" value={o.title ?? ""} onChange={(e) => set("title", e.target.value)} data-testid="offer-title" /></div>
        <div className="den-field sm:col-span-2"><label>Descrierea sistemului fotovoltaic propus</label><textarea className="den-input" rows={2} value={o.system?.description ?? ""} onChange={(e) => set("system", { ...(o.system || {}), description: e.target.value })} data-testid="offer-system-description" /></div>
      </div>
      <div className="den-panel"><h3 className="font-bold mb-2">Echipamente și servicii</h3><OfferItems items={o.items || []} onChange={(v) => set("items", v)} currency={o.currency} /></div>
      <div className="den-panel">
        <h3 className="font-bold mb-2">Prețuri și TVA</h3>
        <div className="grid sm:grid-cols-6 gap-2 items-end">
          <div className="den-field"><label>Moneda</label><select className="den-input" value={o.currency} onChange={(e) => set("currency", e.target.value)} data-testid="offer-currency"><option>RON</option><option>EUR</option></select></div>
          {o.currency === "EUR" && <div className="den-field"><label>Curs (lei/€)</label><input className="den-input" value={o.exchange_rate ?? ""} onChange={(e) => set("exchange_rate", e.target.value)} data-testid="offer-exchange_rate" /></div>}
          <div className="den-field"><label>Cota TVA (%)</label><input className="den-input" value={o.vat_rate ?? ""} onChange={(e) => set("vat_rate", e.target.value)} data-testid="offer-vat_rate" /></div>
          <label className="text-xs flex items-center gap-2 sm:col-span-2"><input type="checkbox" checked={!!o.prices_include_vat} onChange={(e) => set("prices_include_vat", e.target.checked)} data-testid="offer-prices_include_vat" /> Prețurile unitare includ TVA (TVA se extrage, nu se adaugă)</label>
          <div className="den-field"><label>Reducere</label><div className="flex gap-1">
            <select className="den-input !w-16" value={o.discount?.type || "percent"} onChange={(e) => set("discount", { ...(o.discount || {}), type: e.target.value })} data-testid="offer-discount-type"><option value="percent">%</option><option value="amount">sumă</option></select>
            <input className="den-input" value={o.discount?.value ?? ""} onChange={(e) => set("discount", { type: "percent", ...(o.discount || {}), value: e.target.value })} data-testid="offer-discount-value" /></div></div>
        </div>
        <div className="grid sm:grid-cols-4 gap-2 mt-3 text-sm" data-testid="offer-totals">
          {[["Echipamente", t.equipment], ["Manoperă și servicii", t.services], ["Subtotal", t.subtotal], ["Reducere", t.discount], ["Total fără TVA", t.net], [`TVA ${t.vat_rate ?? ""}%`, t.vat], ["Total cu TVA", t.gross]].map(([l, v]) => (
            <div key={l} className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}><div className="text-[11px]" style={{ color: "var(--muted)" }}>{l}</div><b data-testid={`offer-total-${l}`}>{money(v, t.currency)}</b></div>))}
          {t.ron && <div className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}><div className="text-[11px]">Echivalent RON cu TVA</div><b>{money(t.ron.gross, "RON")}</b></div>}
        </div>
        <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Totalurile se recalculează la „Salvează”; TVA se aplică o singură dată pe totalul net după reducere.</p>
      </div>
      <div className="den-panel grid sm:grid-cols-2 gap-2">
        {ta("includes", "Prețul include (câte un rând)")}{ta("warranties", "Garanții (câte un rând)")}{ta("commercial_notes", "Observații comerciale (câte un rând)")}{ta("maintenance", "Mentenanță opțională (text, pagină separată)", 5)}
        <div className="den-field"><label>Valabilitate ofertă (zile)</label><input className="den-input" value={o.validity_days ?? ""} onChange={(e) => set("validity_days", e.target.value)} data-testid="offer-validity_days" /></div>
        <div className="den-field"><label>Data emiterii</label><input className="den-input" type="date" value={o.date ?? ""} onChange={(e) => set("date", e.target.value)} data-testid="offer-date" /></div>
        <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={o.show_line_prices !== false} onChange={(e) => set("show_line_prices", e.target.checked)} data-testid="offer-show_line_prices" /> Afișează prețurile pe fiecare poziție în PDF</label>
      </div>
      <Dialog open={prev} onOpenChange={setPrev}><DialogContent className="max-w-5xl h-[90vh]" data-testid="offer-preview-dialog"><DialogHeader><DialogTitle>Previzualizare ofertă nr. {o.number}</DialogTitle></DialogHeader>
        {prev && <iframe title="preview" src={pdf} className="w-full h-full rounded border" />}</DialogContent></Dialog>
      <ContractDialog offer={o} open={cd} onClose={() => setCd(false)} onDone={load} />
    </div>
  );
}
