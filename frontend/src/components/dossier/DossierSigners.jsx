import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const ROLES = [
  ["designer", "Proiectat / desenat (schemă)"],
  ["verifier", "Verificator (schemă)"],
  ["executant", "Semnatar PIF / executant"],
  ["resp_tehnic", "Responsabil tehnic cu execuția"],
  ["electrician", "Electrician autorizat"],
  ["measurer", "Inginer măsurători PRAM"],
];

export function DossierSigners({ id, form, setVal }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/sld/${id}`).then(({ data: result }) => setData(result));
  useEffect(() => { let active = true; api.get(`/sld/${id}`).then(({ data: result }) => { if (active) setData(result); }).catch(() => { if (active) setData({ error: true }); }); return () => { active = false; }; }, [id]);
  const choose = async (role, staffId) => {
    setBusy(true);
    try {
      await api.put(`/sld/${id}/signers`, { signers: { [role]: staffId } });
      if (role === "executant") setVal("signers", { ...(form.signers || {}), executant: staffId || null });
      await load();
      toast.success("Responsabilii dosarului au fost salvați");
    } catch (error) { toast.error(error.response?.data?.detail || "Nu am putut salva responsabilul"); }
    finally { setBusy(false); }
  };

  return <section className="rounded-xl border bg-white p-4" style={{ borderColor: "var(--line)" }} data-testid="dossier-team-signers">
    <h4 className="font-bold text-sm">Echipa și semnături</h4>
    <p className="mt-1 mb-3 text-xs" style={{ color: "var(--muted)" }}>Selectează persoanele din Setări → Personal. Autorizațiile și datele verificate se folosesc în documentele dosarului.</p>
    {data?.error ? <div className="text-sm text-red-700">Nu s-au putut încărca responsabilii. <button className="underline font-semibold" onClick={() => load().catch(() => setData({ error: true }))}>Reîncearcă</button></div> : !data ? <p className="text-sm" style={{ color: "var(--muted)" }}>Se încarcă personalul…</p> : <>
      <div className="grid gap-3 sm:grid-cols-2">
        {ROLES.map(([role, label]) => <label className="den-field" key={role}><span>{label}</span>
          <select className="den-input" value={data.selected_signers?.[role] || ""} disabled={busy} onChange={(event) => choose(role, event.target.value)} data-testid={`dossier-signer-${role}`}>
            <option value="">Neselectat</option>
            {(data.staff_options || []).map((person) => <option key={person.id} value={person.id}>{person.name}{person.eligible ? " · autorizație verificată" : " · verifică autorizația în Personal"}</option>)}
          </select>
        </label>)}
      </div>
      {!data.staff_options?.length && <p className="mt-2 text-xs" style={{ color: "#8a5a00" }}>Adaugă personalul și documentele de autorizare în Setări → Personal.</p>}
      <p className="mt-4 rounded-lg p-3 text-xs" style={{ background: "#f7f4ed", color: "var(--muted)" }}>Autorizațiile firmei și certificatul metrologic se atașează din documentele încărcate în Setări și din aparatul selectat la PRAM.</p>
    </>}
  </section>;
}
