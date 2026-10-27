import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const col = (v) => (v.days_left < 0 ? "#9b2c2c" : v.days_left <= 30 ? "#8a5a00" : "#166534");

export function VisaPanel({ reloadKey }) {
  const [list, setList] = useState(null);
  useEffect(() => { api.get("/admin/operators/visas").then((r) => setList(r.data)); }, [reloadKey]);
  if (!list) return null;
  return (
    <div className="den-panel mb-4 overflow-x-auto" data-testid="visa-panel">
      <h3 className="font-bold mb-1">Vizări ANRE apropiate (90 de zile) și depășite</h3>
      <table className="w-full text-xs"><thead><tr className="text-left" style={{ color: "var(--muted)" }}><th className="py-1">Firmă</th><th>Atestat</th><th>Data vizării</th><th>Termen</th><th>Contact</th><th>Memento</th></tr></thead>
        <tbody>{list.map((v) => (
          <tr key={v.tenant} className="border-t" style={{ borderColor: "var(--line)", background: v.days_left < 0 ? "#fdecec" : undefined }} data-testid={`visa-row-${v.cui}`}>
            <td className="py-1.5"><b>{v.company}</b><div>CUI {v.cui}</div></td><td>nr. {v.attest_no || "—"}</td>
            <td>{new Date(v.visa_date).toLocaleDateString("ro-RO")}{!v.visa_confirmed && <div style={{ color: "#8a5a00" }}>neconfirmată</div>}</td>
            <td className="font-bold" style={{ color: col(v) }} data-testid={`visa-days-${v.cui}`}>{v.days_left < 0 ? `depășită cu ${-v.days_left} zile` : v.days_left === 0 ? "astăzi" : `în ${v.days_left} zile`}</td>
            <td>{v.contact_name}<div>{v.contact_email} {v.contact_phone}</div></td>
            <td>{v.visa_reminded_at ? `trimis ${new Date(v.visa_reminded_at).toLocaleDateString("ro-RO")}` : "—"}</td></tr>))}
          {!list.length && <tr><td colSpan={6} className="py-4 text-center" style={{ color: "var(--muted)" }}>Nicio vizare în următoarele 90 de zile.</td></tr>}</tbody></table>
    </div>
  );
}
