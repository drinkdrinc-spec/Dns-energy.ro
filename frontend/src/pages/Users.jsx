import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Layout";

const ST = { pending: ["În așteptare", "#fff8e6", "#8a5a00"], active: ["Activ", "#ecfdf3", "#166534"], suspended: ["Suspendat", "#fff0f0", "#9b2c2c"], disabled: ["Dezactivat", "#f3f4f6", "#6b7280"] };

export default function Users() {
  const [d, setD] = useState(null);
  const [staff, setStaff] = useState([]);
  const load = () => api.get("/admin/users").then((r) => setD(r.data)).catch((e) => toast.error(e.response?.data?.detail || "Eroare"));
  useEffect(() => { load(); api.get("/data/staff").then((r) => setStaff(r.data)).catch(() => {}); }, []);
  const upd = async (id, body) => {
    try { await api.put(`/admin/users/${id}`, body); toast.success("Salvat"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
  };
  if (!d) return null;
  return (
    <div>
      <PageHeader eyebrow="Administrare" title="Utilizatori și roluri" sub="Aprobați, suspendați sau dezactivați conturile. Instalatorii văd doar dosarele create de ei sau atribuite lor." />
      <div className="den-panel overflow-x-auto" data-testid="users-table">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs" style={{ color: "var(--muted)" }}><th className="py-2">Nume / e-mail</th><th>Rol</th><th>Stare</th><th>Profil personal (autorizații)</th><th>Acțiuni</th></tr></thead>
          <tbody>{d.users.map((u) => {
            const st = ST[u.status] || ST.active;
            const main = u.role === "admin" && !u.tenant && u.id === d.users[0]?.id;
            return (
              <tr key={u.id} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`user-row-${u.email}`}>
                <td className="py-2"><b>{u.name}</b><div className="text-xs" style={{ color: "var(--muted)" }}>{u.email}</div></td>
                <td><select className="den-input" value={u.role} disabled={main} onChange={(e) => upd(u.id, { role: e.target.value })} data-testid={`user-role-${u.email}`}>
                  {Object.entries(d.roles).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></td>
                <td><span className="text-xs font-bold rounded-full px-2 py-1" style={{ background: st[1], color: st[2] }} data-testid={`user-status-${u.email}`}>{st[0]}</span></td>
                <td><select className="den-input" value={u.staff_id || ""} disabled={main} onChange={(e) => upd(u.id, { staff_id: e.target.value })} data-testid={`user-staff-${u.email}`}>
                  <option value="">— neasociat —</option>{staff.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></td>
                <td className="whitespace-nowrap text-xs space-x-2">{!main && <>
                  {u.status !== "active" && <button className="font-bold" style={{ color: "#166534" }} onClick={() => upd(u.id, { status: "active" })} data-testid={`user-approve-${u.email}`}>Aprobă / activează</button>}
                  {u.status === "active" && <button className="font-bold" style={{ color: "#8a5a00" }} onClick={() => upd(u.id, { status: "suspended" })} data-testid={`user-suspend-${u.email}`}>Suspendă</button>}
                  {u.status !== "disabled" && <button className="font-bold" style={{ color: "#9b2c2c" }} onClick={() => upd(u.id, { status: "disabled" })} data-testid={`user-disable-${u.email}`}>Dezactivează</button>}
                </>}{main && <span style={{ color: "var(--muted)" }}>administrator principal</span>}</td>
              </tr>);
          })}</tbody>
        </table>
      </div>
    </div>
  );
}
