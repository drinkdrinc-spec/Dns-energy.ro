import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";

export function SldCompare({ id, history }) {
  const opts = history.filter((h) => h.has_values);
  const [a, setA] = useState(opts[1]?.index ?? "");
  const [b, setB] = useState(opts[0]?.index ?? "");
  const [d, setD] = useState(null);
  const [all, setAll] = useState(false);
  if (opts.length < 2) return <p className="text-[11px] mt-2" style={{ color: "var(--muted)" }}>Compararea este disponibilă când există cel puțin două versiuni aprobate.</p>;
  const run = () => api.get(`/sld/${id}/compare`, { params: { a, b } }).then((r) => setD(r.data)).catch((e) => toast.error(e.response?.data?.detail || "Eroare"));
  const label = (h) => `rev. ${h.revision} · ${String(h.at).slice(0, 16).replace("T", " ")} · ${h.name}`;
  const rows = d ? (all ? d.rows : d.rows.filter((r) => r.changed)) : [];
  return (
    <div className="mt-3 rounded-lg border p-3" style={{ borderColor: "var(--line)" }} data-testid="sld-compare">
      <div className="flex flex-wrap items-end gap-2">
        {[[a, setA, "Versiunea A", "sld-compare-a"], [b, setB, "Versiunea B", "sld-compare-b"]].map(([v, set, l, t]) => (
          <div key={t} className="den-field"><label>{l}</label>
            <select className="den-input" value={v} onChange={(e) => set(Number(e.target.value))} data-testid={t}>{opts.map((h) => <option key={h.index} value={h.index}>{label(h)}</option>)}</select></div>
        ))}
        <Btn variant="secondary" onClick={run} data-testid="sld-compare-run">Compară</Btn>
      </div>
      {d && (
        <div className="mt-3">
          <div className="flex justify-between text-xs mb-1"><b data-testid="sld-compare-count">{d.changed} valori modificate</b>
            <button className="font-bold" style={{ color: "var(--blue)" }} onClick={() => setAll(!all)} data-testid="sld-compare-all">{all ? "Doar diferențele" : "Toate valorile"}</button></div>
          <div className="overflow-x-auto"><table className="w-full text-xs" data-testid="sld-compare-table">
            <thead><tr className="text-left"><th className="py-1 pr-2">Mărime</th><th className="py-1 pr-2">rev. {d.a.revision}</th><th className="py-1">rev. {d.b.revision}</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.key} className="border-t" style={{ borderColor: "var(--line)", background: r.changed ? "#fff8e6" : undefined }}>
                <td className="py-1 pr-2">{r.key}</td><td className="py-1 pr-2">{r.a}</td><td className="py-1 font-semibold">{r.b}</td></tr>))}
            </tbody></table>{!rows.length && <p className="text-xs py-2">Nicio diferență.</p>}</div>
        </div>
      )}
    </div>
  );
}
