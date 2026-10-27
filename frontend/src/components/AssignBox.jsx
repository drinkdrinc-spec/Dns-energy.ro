import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export function AssignBox({ value, onChange }) {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const isAdmin = (user?.role || "admin") === "admin";
  useEffect(() => { if (isAdmin) api.get("/admin/users").then((r) => setUsers(r.data.users.filter((u) => u.role !== "admin"))).catch(() => {}); }, [isAdmin]);
  if (!isAdmin || !users.length) return null;
  const sel = value || [];
  return (
    <div className="mt-6 rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="assign-box">
      <h3 className="font-bold text-sm mb-1">Acces la dosar</h3>
      <p className="text-[11px] mb-2" style={{ color: "var(--muted)" }}>Utilizatorii bifați (instalatori, electricieni, ingineri) pot vedea și completa acest dosar, în limitele rolului lor.</p>
      <div className="grid sm:grid-cols-2 gap-1">{users.map((u) => (
        <label key={u.id} className="text-xs flex items-center gap-2"><input type="checkbox" checked={sel.includes(u.id)} data-testid={`assign-${u.email}`}
          onChange={(e) => onChange(e.target.checked ? [...sel, u.id] : sel.filter((x) => x !== u.id))} />{u.name} · {u.email} ({u.role}{u.status !== "active" ? `, ${u.status}` : ""})</label>))}</div>
    </div>
  );
}
