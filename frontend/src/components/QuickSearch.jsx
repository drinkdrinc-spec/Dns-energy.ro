import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, Loader2, Search, X } from "lucide-react";
import { api } from "@/lib/api";

export function QuickSearch() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [unavailable, setUnavailable] = useState([]);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    const term = query.trim();
    if (!open || term.length < 2) {
      setResults([]);
      setUnavailable([]);
      setFailed(false);
      setLoading(false);
      return undefined;
    }
    let current = true;
    setResults([]);
    setUnavailable([]);
    setFailed(false);
    setLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const { data } = await api.get("/quick-search", { params: { q: term } });
        if (current) setResults(Array.isArray(data.results) ? data.results : []);
        if (current) setUnavailable(Array.isArray(data.unavailable) ? data.unavailable : []);
        if (current) setFailed(false);
      } catch {
        if (current) {
          setResults([]);
          setUnavailable([]);
          setFailed(true);
        }
      } finally {
        if (current) setLoading(false);
      }
    }, 220);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [open, query]);

  const close = () => {
    setOpen(false);
    setQuery("");
    setResults([]);
    setUnavailable([]);
    setFailed(false);
  };

  return <>
    <button type="button" onClick={() => setOpen(true)} aria-label="Căutare rapidă în baza de date"
      className="mb-5 flex min-h-11 w-full items-center gap-3 rounded-xl border bg-white px-4 text-left text-sm shadow-sm transition hover:border-blue-300"
      style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid="quick-search-open">
      <Search size={17} style={{ color: "var(--blue)" }} />
      <span className="flex-1">Caută client, POD sau număr de dosar…</span>
      <kbd className="hidden rounded border px-1.5 py-0.5 text-[10px] sm:inline" style={{ borderColor: "var(--line)" }}>Ctrl K</kbd>
    </button>

    {open && <div className="fixed inset-0 z-[70] flex items-start justify-center bg-slate-950/45 px-3 pt-[12vh] sm:px-6"
      role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="quick-search-title"
        className="w-full max-w-2xl overflow-hidden rounded-2xl border bg-white shadow-2xl" style={{ borderColor: "var(--line)" }}>
        <h2 id="quick-search-title" className="sr-only">Căutare rapidă în baza de date</h2>
        <div className="flex items-center gap-3 border-b px-4" style={{ borderColor: "var(--line)" }}>
          <Search size={19} style={{ color: "var(--blue)" }} />
          <input ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => { if (event.key === "Enter" && results[0]) { navigate(results[0].href); close(); } }}
            className="h-14 min-w-0 flex-1 bg-transparent text-sm outline-none" placeholder="Nume, telefon, email, CNP, POD sau număr…"
            aria-label="Caută în clienți și dosare" data-testid="quick-search-input" autoComplete="off" />
          {loading && <Loader2 size={17} className="animate-spin" aria-label="Se caută" />}
          <button type="button" onClick={close} aria-label="Închide căutarea" className="rounded-md p-2 hover:bg-slate-100"><X size={17} /></button>
        </div>
        <div className="max-h-[58vh] overflow-y-auto p-2" data-testid="quick-search-results">
          {query.trim().length < 2 ? <p className="px-3 py-6 text-center text-sm" style={{ color: "var(--muted)" }}>Introdu cel puțin 2 caractere pentru a căuta în baza firmei.</p>
            : !loading && failed ? <p className="px-3 py-6 text-center text-sm text-rose-700" role="alert">Căutarea nu este disponibilă momentan. Verifică conexiunea și încearcă din nou.</p>
              : !loading && results.length === 0 ? <p className="px-3 py-6 text-center text-sm" style={{ color: "var(--muted)" }}>Nu am găsit clienți sau dosare care să corespundă.</p>
              : results.map((item) => <button key={`${item.module}:${item.id}`} type="button" onClick={() => { navigate(item.href); close(); }}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-blue-50 focus:bg-blue-50 focus:outline-none"
                data-testid={`quick-search-result-${item.module}`}>
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg" style={{ background: "#edf4ff", color: "var(--blue)" }}><Search size={16} /></span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-bold" style={{ color: "var(--ink)" }}>{item.title}</span>
                  <span className="block truncate text-xs" style={{ color: "var(--muted)" }}>{item.label}{item.detail ? ` · ${item.detail}` : ""}</span>
                </span>
                <ArrowUpRight size={16} className="shrink-0" style={{ color: "var(--muted)" }} />
              </button>)}
          {unavailable.length > 0 && <p className="px-3 py-2 text-xs text-amber-800" role="status">Căutare parțială: module indisponibile — {unavailable.join(", ")}.</p>}
        </div>
        <div className="border-t px-4 py-2 text-[11px]" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>Căutarea este limitată la datele la care are acces contul tău.</div>
      </section>
    </div>}
  </>;
}

