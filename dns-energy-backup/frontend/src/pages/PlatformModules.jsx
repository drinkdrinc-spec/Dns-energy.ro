import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export default function PlatformModules() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const load = () => api.get("/platform/modules").then((r) => setData(r.data)).catch((e) => setErr(e.response?.data?.detail || "Eroare"));
  useEffect(() => { load(); }, []);

  const toggle = async (key, enabled) => {
    const disabled = data.modules.filter((m) => (m.key === key ? !enabled : !m.enabled)).map((m) => m.key);
    try { await api.put("/platform/modules", { disabled }); toast.success(enabled ? "Modul activat pentru toți utilizatorii" : "Modul dezactivat pentru toți utilizatorii"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
  };

  if (!user?.platform) return <div className="den-panel" data-testid="platform-modules-denied">Doar administratorul principal al platformei are acces la această pagină.</div>;
  return (
    <div data-testid="platform-modules-page">
      <PageHeader eyebrow="Administrare platformă" title="Module platformă"
        sub="Activează sau dezactivează modulele pentru toți utilizatorii. Un modul dezactivat apare blocat („Indisponibil momentan”); datele existente rămân salvate." />
      {err && <div className="den-panel text-sm" style={{ color: "#9b2c2c" }}>{err}</div>}
      {data && (
        <div className="den-panel max-w-3xl divide-y" style={{ borderColor: "var(--line)" }}>
          {data.modules.map((m) => (
            <div key={m.key} className="flex items-center justify-between gap-4 py-3" data-testid={`module-row-${m.key}`}>
              <div>
                <div className="font-semibold text-sm">{m.label}</div>
                <div className="text-xs" style={{ color: m.enabled ? "#166534" : "#9b2c2c" }} data-testid={`module-state-${m.key}`}>{m.enabled ? "Activ" : "Dezactivat — indisponibil momentan"}</div>
              </div>
              <Switch checked={m.enabled} onCheckedChange={(v) => toggle(m.key, v)} data-testid={`module-toggle-${m.key}`} />
            </div>
          ))}
          {data.updated_at && <p className="text-[11px] pt-3" style={{ color: "var(--muted)" }}>Ultima modificare: {new Date(data.updated_at).toLocaleString("ro-RO")} · {data.updated_by}</p>}
        </div>
      )}
    </div>
  );
}
