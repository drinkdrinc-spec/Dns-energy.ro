import { openAuthenticatedFile } from "@/lib/api";
import { lei } from "@/lib/plan";

const ST = { "plătită": ["#ecfdf3", "#166534"], "în așteptarea plății": ["#fff8e6", "#8a5a00"], "eșuată": ["#fff0f0", "#9b2c2c"],
  "anulată": ["#f3f4f6", "#6b7280"], "rambursată": ["#eef4ff", "#1e40af"], "expirată": ["#f3f4f6", "#6b7280"] };

export const pdfUrl = (id) => `/billing/invoices/${id}/pdf`;

export function StatusPill({ s, testid }) {
  const c = ST[s] || ST["anulată"];
  return <span className="text-[11px] font-bold rounded-full px-2 py-0.5 whitespace-nowrap" style={{ background: c[0], color: c[1] }} data-testid={testid}>{s}</span>;
}

export function InvoiceList({ items, actions }) {
  if (!items?.length) return <div className="text-sm py-4" style={{ color: "var(--muted)" }}>Nu există proforme încă.</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="invoice-table">
        <thead><tr className="text-left text-xs" style={{ color: "var(--muted)" }}><th className="py-2">Număr</th><th>Data</th><th>Abonament</th><th>Bază</th><th>TVA</th><th>Total</th><th>Stare</th><th></th></tr></thead>
        <tbody>{items.map((i) => (
          <tr key={i.id} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`invoice-row-${i.number}`}>
            <td className="py-2 font-semibold">{i.number}</td><td>{i.created_at?.slice(0, 10)}</td>
            <td>{i.plan_name} × {i.months}{i.period_to && <div className="text-[11px]" style={{ color: "var(--muted)" }}>{i.period_from} → {i.period_to}</div>}</td>
            <td>{lei(i.net)}</td><td className="whitespace-nowrap pr-2">{i.vat_rate}% · {lei(i.vat)}</td><td className="font-bold">{lei(i.total)}</td>
            <td><StatusPill s={i.status} testid={`invoice-status-${i.number}`} />
              {i.credit > 0 && <div className="text-[10px]" style={{ color: "#166534" }}>credit −{lei(i.credit)}</div>}
              {i.fiscal && <div className="text-[10px]" style={{ color: i.fiscal.status === "emisă" ? "#166534" : "#8a5a00" }} data-testid={`invoice-fiscal-status-${i.number}`} title={i.fiscal.error || i.fiscal.efactura || ""}>
                Factură fiscală: {i.fiscal.status}{i.fiscal.number ? ` ${i.fiscal.series} ${i.fiscal.number}` : ""}</div>}</td>
            <td className="text-xs whitespace-nowrap space-x-2">
              <button type="button" onClick={() => openAuthenticatedFile(pdfUrl(i.id))} className="font-bold" style={{ color: "var(--blue)" }} data-testid={`invoice-pdf-${i.number}`}>Proformă PDF</button>
              {i.fiscal?.status === "emisă" && <button type="button" onClick={() => openAuthenticatedFile(`/billing/invoices/${i.id}/fiscal-pdf`)} className="font-bold" style={{ color: "#166534" }} data-testid={`invoice-fiscal-pdf-${i.number}`}>Factură PDF</button>}
              {actions?.(i)}
            </td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}
