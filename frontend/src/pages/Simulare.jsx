import { useEffect, useMemo, useRef, useState } from "react";
import { PageHeader, Btn } from "@/components/Layout";
import { api, openAuthenticatedFile } from "@/lib/api";
import { ClipboardCheck, Plus, Save, Search, ExternalLink, MapPin, Ruler, TriangleAlert, CheckCircle2, Upload, FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";

const EMPTY = {
  name: "", number: "", client_id: "", client_name: "", address: "", locality: "", county: "",
  site: "Acoperiș înclinat", status: "În lucru", drawing_source: "", roof_geometry: "",
  roof_scale_verified: false, roof_geometry_verified: false, obstacles_checked: false,
  north_verified: false, equipment_positions_verified: false, panel_id: "", inverter_id: "",
  battery_id: "", dossier_id: "", dossier_number: "", engineer_notes: "",
};
const GATES = [
  ["roof_scale_verified", "Planul este calibrat după o dimensiune măsurată"],
  ["roof_geometry_verified", "Conturul și cotele reale ale suprafețelor sunt introduse"],
  ["obstacles_checked", "Obstacolele și zonele excluse sunt înregistrate"],
  ["north_verified", "Orientarea nord este verificată"],
  ["equipment_positions_verified", "Pozițiile echipamentelor și tablourilor sunt marcate"],
];
const text = (value) => value == null ? "" : String(value);

export default function Simulare() {
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [dossiers, setDossiers] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [form, setForm] = useState(null);
  const [outline, setOutline] = useState([]);
  const [equipmentMarks, setEquipmentMarks] = useState([]);
  const [drawingMode, setDrawingMode] = useState("roof");
  const [markType, setMarkType] = useState("Panou");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const planInput = useRef(null);

  const load = async () => {
    setLoading(true); setError("");
    try {
      const responses = await Promise.all([api.get("/data/projects"), api.get("/data/clients"), api.get("/data/catalog")]);
      setProjects(Array.isArray(responses[0].data) ? responses[0].data : []);
      setClients(Array.isArray(responses[1].data) ? responses[1].data.filter((x) => !x.is_test && !/\bTEST\b/i.test(String(x.name || ""))) : []);
      setCatalog(Array.isArray(responses[2].data) ? responses[2].data.filter((x) => !/\bTEST\b/i.test(String(x.brand_model || ""))) : []);
      const dossierResponse = await api.get("/data/prosumator").catch(() => ({ data: [] }));
      setDossiers(Array.isArray(dossierResponse.data) ? dossierResponse.data.filter((x) => !x.is_test && !/\bTEST\b/i.test(String(x.client_name || x.number || ""))) : []);
    } catch (e) {
      setError(e.response?.data?.detail || "Proiectele nu s-au putut încărca. Verifică accesul și încearcă din nou.");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => projects.filter((p) => {
    const s = query.trim().toLocaleLowerCase("ro-RO");
    return !s || [p.name, p.number, p.client_name, p.address, p.locality, p.county]
      .some((v) => String(v || "").toLocaleLowerCase("ro-RO").includes(s));
  }), [projects, query]);

  const startNew = () => { setSelectedId(""); setForm({ ...EMPTY }); setOutline([]); setEquipmentMarks([]); setDrawingMode("roof"); };
  const selectProject = (p) => {
    setSelectedId(p.id); setForm({ ...EMPTY, ...p });
    setOutline(Array.isArray(p.roof_outline) ? p.roof_outline : []);
    setEquipmentMarks(Array.isArray(p.equipment_marks) ? p.equipment_marks : []);
    setDrawingMode("roof");
  };
  const addPlanPoint = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(800, ((event.clientX - rect.left) / rect.width) * 800));
    const y = Math.max(0, Math.min(420, ((event.clientY - rect.top) / rect.height) * 420));
    const point = { x: Number(x.toFixed(1)), y: Number(y.toFixed(1)) };
    if (drawingMode === "roof") setOutline((old) => [...old, point]);
    else setEquipmentMarks((old) => [...old, { ...point, label: markType }]);
  };
  const set = (key, value) => setForm((old) => ({ ...old, [key]: value }));
  const pickDossier = (id) => {
    const dossier = dossiers.find((x) => x.id === id);
    setForm((old) => ({ ...old, dossier_id: id, dossier_number: dossier?.number || "" }));
  };
  const pickClient = (id) => {
    const c = clients.find((x) => x.id === id);
    setForm((old) => ({ ...old, client_id: id, client_name: c?.name || "",
      address: c?.address || old.address, locality: c?.locality || old.locality, county: c?.county || old.county }));
  };
  const save = async () => {
    if (!form?.name?.trim()) return toast.error("Dă un nume proiectului.");
    setSaving(true);
    try {
      const payload = { ...form, roof_outline: outline, equipment_marks: equipmentMarks, name: form.name.trim(), updated_at: new Date().toISOString() };
      const response = selectedId
        ? await api.put("/data/projects/" + selectedId, payload)
        : await api.post("/data/projects", payload);
      setSelectedId(response.data.id);
      setForm({ ...EMPTY, ...response.data });
      setOutline(Array.isArray(response.data.roof_outline) ? response.data.roof_outline : outline);
      setEquipmentMarks(Array.isArray(response.data.equipment_marks) ? response.data.equipment_marks : equipmentMarks);
      await load();
      toast.success("Proiect salvat.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Proiectul nu a putut fi salvat.");
    } finally { setSaving(false); }
  };

  const uploadPlan = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !form) return;
    const data = new FormData(); data.append("file", file);
    try {
      const response = await api.post("/upload", data, { headers: { "Content-Type": "multipart/form-data" } });
      set("plan_file", response.data);
      set("drawing_source", file.name);
      toast.success("Planul a fost încărcat la proiect.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Planul nu a putut fi încărcat.");
    } finally {
      if (planInput.current) planInput.current.value = "";
    }
  };
  const gateCount = GATES.filter(([key]) => Boolean(form?.[key])).length;
  const ready = gateCount === GATES.length;
  const options = (category) => catalog.filter((item) => item.category === category);

  return (
    <div>
      <PageHeader eyebrow="Proiectare fotovoltaică" title="Proiecte și verificări"
        sub="Creează un proiect independent, leagă-l de un client și pregătește datele reale pentru verificarea tehnică. Nu se estimează producție sau dimensionări din valori presupuse."
        action={<Btn onClick={startNew}><Plus size={15} /> Proiect nou</Btn>} />
      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="den-panel h-fit">
          <label className="den-field block"><span className="mb-1 block text-xs font-semibold">Caută proiecte</span>
            <span className="relative block"><Search size={15} className="absolute left-3 top-3" style={{ color: "var(--muted)" }} />
              <input className="den-input pl-9" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nume, client, adresă" /></span>
          </label>
          <div className="mt-4 space-y-2">
            {loading && <p className="text-sm" style={{ color: "var(--muted)" }}>Se încarcă proiectele…</p>}
            {error && <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error} <button onClick={load} className="underline">Reîncearcă</button></div>}
            {!loading && !error && filtered.map((p) => <button key={p.id} onClick={() => selectProject(p)}
              className="block w-full rounded-lg border p-3 text-left hover:bg-slate-50"
              style={{ borderColor: selectedId === p.id ? "var(--blue)" : "var(--line)", background: selectedId === p.id ? "#eff6ff" : "#fff" }}>
              <span className="block truncate text-sm font-bold">{p.name || "Proiect fără nume"}</span>
              <span className="mt-1 block truncate text-xs" style={{ color: "var(--muted)" }}>{p.client_name || p.address || "Fără client asociat"}</span>
              <span className="mt-2 inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[10px]">{p.status || "În lucru"}</span>
            </button>)}
            {!loading && !error && !filtered.length && <p className="py-3 text-sm" style={{ color: "var(--muted)" }}>Nu există proiecte aici. Începe cu „Proiect nou”.</p>}
          </div>
        </aside>

        {!form ? <section className="den-panel flex min-h-64 flex-col items-center justify-center text-center">
          <ClipboardCheck size={34} style={{ color: "var(--blue)" }} />
          <h2 className="mt-3 text-lg font-bold">Spațiu de proiectare</h2>
          <p className="mt-1 max-w-lg text-sm" style={{ color: "var(--muted)" }}>Alege un proiect sau creează unul. Datele geometrice, sursa planului și echipamentele rămân asociate proiectului.</p>
          <Btn className="mt-4" onClick={startNew}><Plus size={15} /> Proiect nou</Btn>
        </section> : <section className="min-w-0 space-y-5">
          <div className="den-panel">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div><p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)" }}>Date proiect</p>
                <h2 className="text-lg font-bold">{selectedId ? "Proiect existent" : "Proiect nou"}</h2></div>
              <Btn onClick={save} disabled={saving}><Save size={15} /> {saving ? "Se salvează…" : "Salvează proiectul"}</Btn>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Nume proiect *"><input className="den-input" value={text(form.name)} onChange={(e) => set("name", e.target.value)} placeholder="Ex. Sistem fotovoltaic — locație" /></Field>
              <Field label="Număr / referință"><input className="den-input" value={text(form.number)} onChange={(e) => set("number", e.target.value)} /></Field>
              <Field label="Client existent"><select className="den-input" value={form.client_id || ""} onChange={(e) => pickClient(e.target.value)}>
                <option value="">Fără client asociat</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select></Field>
              <Field label="Stare"><select className="den-input" value={form.status || "În lucru"} onChange={(e) => set("status", e.target.value)}>
                {["În lucru", "Date în așteptare", "În verificare inginerească", "Verificat", "Arhivat"].map((s) => <option key={s}>{s}</option>)}
              </select></Field>
              <Field label="Dosar prosumator asociat"><select className="den-input" value={form.dossier_id || ""} onChange={(e) => pickDossier(e.target.value)}>
                <option value="">Fără dosar asociat</option>{dossiers.map((d) => <option key={d.id} value={d.id}>{[d.client_name || "Client fără nume", d.number].filter(Boolean).join(" · ")}</option>)}
              </select></Field>
              <Field label="Adresă obiectiv"><input className="den-input" value={text(form.address)} onChange={(e) => set("address", e.target.value)} /></Field>
              <Field label="Localitate"><input className="den-input" value={text(form.locality)} onChange={(e) => set("locality", e.target.value)} /></Field>
              <Field label="Județ"><input className="den-input" value={text(form.county)} onChange={(e) => set("county", e.target.value)} /></Field>
              <Field label="Tip amplasament"><select className="den-input" value={form.site || EMPTY.site} onChange={(e) => set("site", e.target.value)}>
                {["Acoperiș înclinat", "Acoperiș plat", "Teren", "Parcare / carport", "Alt amplasament"].map((s) => <option key={s}>{s}</option>)}
              </select></Field>
            </div>
          </div>

          <div className="den-panel">
            <div className="mb-4 flex items-start gap-3"><MapPin size={19} style={{ color: "var(--blue)" }} />
              <div><h2 className="font-bold">Plan și geometrie</h2><p className="text-xs" style={{ color: "var(--muted)" }}>Înregistrează sursa și cotele reale înainte de calcul. Acest ecran nu inventează măsurători și nu desenează geometria în locul proiectantului.</p></div></div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Sursa planului / fișierului"><input className="den-input" value={text(form.drawing_source)} onChange={(e) => set("drawing_source", e.target.value)} placeholder="Nume fișier, link sau număr plan" /></Field>
              <div className="den-field block"><span className="mb-1 block text-xs font-semibold">Plan atașat (PDF sau imagine)</span>
                <input ref={planInput} type="file" accept="application/pdf,image/*" className="hidden" onChange={uploadPlan} />
                <div className="flex min-h-10 flex-wrap items-center gap-2">
                  <Btn type="button" variant="secondary" onClick={() => planInput.current?.click()}><Upload size={14} /> Încarcă plan</Btn>
                  {form.plan_file?.storage_path && <>
                    <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold underline" style={{ color: "var(--blue)" }} onClick={() => openAuthenticatedFile("/files/" + form.plan_file.storage_path)}><FileText size={14} /> {form.plan_file.original_filename || form.plan_file.filename || "Deschide planul"}</button>
                    <button type="button" title="Elimină planul atașat" onClick={() => set("plan_file", null)} className="rounded border p-2" style={{ borderColor: "var(--line)" }}><Trash2 size={14} /></button>
                  </>}
                </div>
                <small className="mt-1 block text-xs" style={{ color: "var(--muted)" }}>Fișierul se atașează proiectului curent; cotele și orientarea trebuie verificate de proiectant.</small>
              </div>
              <Field label="Geometrie și cote măsurate"><textarea className="den-input min-h-24" value={text(form.roof_geometry)} onChange={(e) => set("roof_geometry", e.target.value)} placeholder="Notează separat fiecare versant/zonă și dimensiunile verificate." /></Field>
            </div>
            <div className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--line)" }} data-testid="project-plan-editor">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div><h3 className="text-sm font-bold">Schiță de amplasament</h3><p className="text-xs" style={{ color: "var(--muted)" }}>Adaugă puncte pentru contur, apoi marchează echipamentele. Schița nu este la scară și nu înlocuiește planul măsurat.</p></div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setDrawingMode("roof")} aria-pressed={drawingMode === "roof"} className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: drawingMode === "roof" ? "var(--blue)" : "var(--line)", color: drawingMode === "roof" ? "var(--blue)" : "var(--ink)" }}>Desenează contur</button>
                  <button type="button" onClick={() => setDrawingMode("equipment")} aria-pressed={drawingMode === "equipment"} className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: drawingMode === "equipment" ? "var(--blue)" : "var(--line)", color: drawingMode === "equipment" ? "var(--blue)" : "var(--ink)" }}>Marchează echipamente</button>
                </div>
              </div>
              {drawingMode === "equipment" && <div className="mb-3 flex flex-wrap items-center gap-2">
                <label htmlFor="project-mark-type" className="text-xs font-semibold">Marcaj:</label>
                <select id="project-mark-type" className="den-input max-w-48" value={markType} onChange={(e) => setMarkType(e.target.value)}>
                  {["Panou", "Invertor", "Baterie", "Tablou"].map((kind) => <option key={kind}>{kind}</option>)}
                </select>
                <span className="text-xs" style={{ color: "var(--muted)" }}>Apasă pe schiță pentru fiecare poziție.</span>
              </div>}
              <svg viewBox="0 0 800 420" role="img" aria-label="Schiță de amplasament editabilă, fără scară" onClick={addPlanPoint} className="block w-full cursor-crosshair rounded-lg border bg-white" style={{ borderColor: "var(--line)", touchAction: "none" }}>
                <defs><pattern id="project-grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e8edf4" strokeWidth="1" /></pattern></defs>
                <rect width="800" height="420" fill="url(#project-grid)" />
                {outline.length > 2 && <polygon points={outline.map((p) => p.x + "," + p.y).join(" ")} fill="#dbeafe" fillOpacity="0.55" stroke="#2563eb" strokeWidth="3" />}
                {outline.length > 0 && <polyline points={outline.map((p) => p.x + "," + p.y).join(" ")} fill="none" stroke="#2563eb" strokeWidth="3" strokeDasharray={outline.length > 2 ? undefined : "8 5"} />}
                {outline.map((p, index) => <g key={"outline-" + index}><circle cx={p.x} cy={p.y} r="6" fill="#2563eb" /><text x={p.x + 9} y={p.y - 9} fontSize="12" fill="#1e3a8a">{index + 1}</text></g>)}
                {equipmentMarks.map((p, index) => <g key={"mark-" + index}><circle cx={p.x} cy={p.y} r="9" fill={p.label === "Baterie" ? "#7c3aed" : p.label === "Invertor" ? "#ea580c" : p.label === "Tablou" ? "#334155" : "#16a34a"} stroke="white" strokeWidth="2" /><text x={p.x + 12} y={p.y + 4} fontSize="12" fontWeight="bold" fill="#172554">{p.label}</text></g>)}
              </svg>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Btn type="button" variant="secondary" onClick={() => setOutline((old) => old.slice(0, -1))} disabled={!outline.length}>Undo contur</Btn>
                <Btn type="button" variant="secondary" onClick={() => setEquipmentMarks((old) => old.slice(0, -1))} disabled={!equipmentMarks.length}>Undo marcaj</Btn>
                <Btn type="button" variant="secondary" onClick={() => { setOutline([]); setEquipmentMarks([]); }}>Șterge schița</Btn>
                <span className="text-xs" style={{ color: "var(--muted)" }}>{outline.length} puncte de contur · {equipmentMarks.length} marcaje</span>
              </div>
            </div>
            <div className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--line)" }}>
              <div className="mb-3 flex items-center justify-between gap-2"><h3 className="text-sm font-bold">Poarta 1 · verificarea datelor de intrare</h3><span className="text-xs font-semibold">{gateCount}/{GATES.length}</span></div>
              <div className="space-y-3">{GATES.map(([key, label]) => <label key={key} className="flex cursor-pointer items-start gap-3 text-sm">
                <input type="checkbox" checked={Boolean(form[key])} onChange={(e) => set(key, e.target.checked)} className="mt-0.5 h-4 w-4 accent-blue-600" />{label}
              </label>)}</div>
              <div className="mt-4 flex items-start gap-2 rounded-lg p-3 text-xs" style={{ background: ready ? "#ecfdf5" : "#fff8e6", color: ready ? "#166534" : "#8a5a00" }}>
                {ready ? <CheckCircle2 size={16} /> : <TriangleAlert size={16} />}
                <span>{ready ? "Datele de intrare sunt declarate pregătite pentru verificare inginerească. Validarea nu confirmă conformitatea tehnică sau normativă." : "Dimensionarea rămâne indisponibilă până când datele reale lipsă sunt completate și verificate."}</span>
              </div>
            </div>
          </div>

          <div className="den-panel">
            <h2 className="mb-1 font-bold">Echipamente propuse din catalogul DNS</h2>
            <p className="mb-4 text-xs" style={{ color: "var(--muted)" }}>Alegerea se păstrează la proiect. Compatibilitatea electrică trebuie verificată din fișele producătorului de către proiectant.</p>
            <div className="grid gap-4 sm:grid-cols-3">
              {[["panel_id", "Panou", "Panou"], ["inverter_id", "Invertor", "Invertor"], ["battery_id", "Baterie", "Baterie"]].map(([key, label, category]) => <Field key={key} label={label}>
                <select className="den-input" value={form[key] || ""} onChange={(e) => set(key, e.target.value)}>
                  <option value="">Neselectat</option>{options(category).map((item) => <option key={item.id} value={item.id}>{item.brand_model}</option>)}
                </select>
              </Field>)}
            </div>
            <Field label="Note pentru verificarea inginerească" className="mt-4"><textarea className="den-input min-h-20" value={text(form.engineer_notes)} onChange={(e) => set("engineer_notes", e.target.value)} placeholder="Clarificări, condiții de amplasament, verificări cerute." /></Field>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Btn onClick={save} disabled={saving}><Save size={15} /> {saving ? "Se salvează…" : "Salvează proiectul"}</Btn>
              <a href="/catalog-echipamente" className="inline-flex items-center gap-1 text-sm font-semibold underline">Deschide catalogul DNS <ExternalLink size={13} /></a>
              {form.dossier_id ? <a href={`/prosumator?edit=${encodeURIComponent(form.dossier_id)}`} className="inline-flex items-center gap-1 text-sm font-semibold underline">Deschide dosarul asociat <ExternalLink size={13} /></a> : <a href="/prosumator" className="inline-flex items-center gap-1 text-sm font-semibold underline">Dosare prosumator <ExternalLink size={13} /></a>}
            </div>
          </div>
          <p className="flex items-start gap-2 px-1 text-xs" style={{ color: "var(--muted)" }}><Ruler size={15} className="shrink-0" />Nu se generează dimensionări, estimări de producție sau confirmări de conformitate aici. Acestea necesită geometrie măsurată și verificarea proiectantului.</p>
        </section>}
      </div>
    </div>
  );
}

function Field({ label, className = "", children }) {
  return <label className={"den-field block " + className}><span className="mb-1 block text-xs font-semibold">{label}</span>{children}</label>;
}
