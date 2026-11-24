import { useState } from "react";
import { Issues } from "@/components/cef/CefResults";

const SRC = { introdus: ["#eef4ff", "#1d4ed8"], catalog: ["#f3f0ff", "#6d28d9"], calculat: ["#e7f7ee", "#1e7a46"], "de confirmat": ["#fff4e0", "#8a5a00"] };

function Row({ it, i }) {
  const s = SRC[it.source] || SRC.introdus;
  const ok = it.ok === true ? ["conform", "#1e7a46"] : it.ok === false ? ["NECONFORM", "#b03a2e"] : ["—", "var(--muted)"];
  return (
    <tr className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`sld-item-${i}`}>
      <td className="py-1.5 pr-2 whitespace-nowrap" style={{ color: "var(--muted)" }}>{it.group}</td>
      <td className="py-1.5 pr-2">{it.label}</td>
      <td className="py-1.5 pr-2 font-semibold whitespace-nowrap">{it.value ?? <span style={{ color: "#b03a2e" }}>lipsă</span>}</td>
      <td className="py-1.5 pr-2"><span className="rounded-full px-2 py-0.5 text-[10px] font-bold whitespace-nowrap" style={{ background: s[0], color: s[1] }}>{it.source}</span></td>
      <td className="py-1.5 pr-2 hidden md:table-cell" style={{ color: "var(--muted)" }}>{it.formula}{it.note ? ` · ${it.note}` : ""}</td>
      <td className="py-1.5 font-bold whitespace-nowrap" style={{ color: ok[1] }}>{ok[0]}</td>
    </tr>
  );
}

export function SldChecks({ d }) {
  const [all, setAll] = useState(false);
  const items = all ? d.items : d.items.filter((x) => x.ok === false || x.source === "de confirmat");
  return (
    <div className="mt-4">
      {d.missing.length > 0 && (
        <div className="rounded-lg px-3 py-2 text-xs mb-3" style={{ background: "#fff0f0", color: "#9b2c2c" }} data-testid="sld-missing">
          <b>Date obligatorii lipsă ({d.missing.length}) — schema rămâne CIORNĂ:</b>
          <ul className="list-disc ml-5 mt-1 grid sm:grid-cols-2 gap-x-6">{d.missing.map((m) => <li key={m.path + m.label}>{m.label}</li>)}</ul>
        </div>
      )}
      <Issues errors={d.errors} warnings={d.warnings} testid="sld-issues" />
      <div className="flex items-center justify-between mt-3">
        <b className="text-xs">Calcule și verificări {all ? `(${d.items.length})` : "— neconforme / de confirmat"}</b>
        <button className="text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => setAll(!all)} data-testid="sld-toggle-all">{all ? "Arată doar problemele" : `Arată toate (${d.items.length})`}</button>
      </div>
      <div className="overflow-x-auto mt-1">
        <table className="w-full text-xs" data-testid="sld-items-table"><tbody>{items.map((it, i) => <Row key={i} it={it} i={i} />)}</tbody></table>
        {!items.length && <p className="text-xs py-2" style={{ color: "var(--muted)" }}>Nicio problemă detectată.</p>}
      </div>
    </div>
  );
}
