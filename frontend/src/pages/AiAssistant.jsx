import { useEffect, useRef, useState } from "react";
import { Plus, Send, Trash2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { streamAI } from "@/lib/ai";
import { PageHeader, Btn } from "@/components/Layout";

function Bubble({ m }) {
  const me = m.role === "user";
  return (
    <div className={`flex ${me ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap" data-testid={`ai-msg-${m.role}`}
        style={me ? { background: "var(--blue)", color: "#fff" } : { background: "#fff", border: "1px solid var(--line)" }}>{m.content}</div>
    </div>
  );
}

export default function AiAssistant() {
  const [sessions, setSessions] = useState([]);
  const [sid, setSid] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  const loadSessions = () => api.get("/ai/sessions").then((r) => { setSessions(r.data); return r.data; });
  useEffect(() => { loadSessions().then((s) => s[0] && setSid(s[0].id)).catch(() => {}); }, []);
  useEffect(() => { if (sid) api.get(`/ai/sessions/${sid}/messages`).then((r) => setMsgs(r.data)); else setMsgs([]); }, [sid]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const newSession = async () => { const { data } = await api.post("/ai/sessions"); await loadSessions(); setSid(data.id); return data.id; };
  const del = async (id) => { await api.delete(`/ai/sessions/${id}`); const s = await loadSessions(); setSid(s[0]?.id || null); };
  const send = async () => {
    const q = text.trim(); if (!q || busy) return;
    const id = sid || await newSession();
    setText(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "..." }]);
    try { await streamAI(`/ai/sessions/${id}/message`, { text: q }, (full) => setMsgs((m) => [...m.slice(0, -1), { role: "assistant", content: full }])); loadSessions(); }
    catch (e) { toast.error(e.message); setMsgs((m) => m.slice(0, -1)); }
    finally { setBusy(false); }
  };

  return (
    <div data-testid="ai-assistant-page">
      <PageHeader eyebrow="Inteligență artificială" title="Asistent tehnic AI" sub="ChatGPT (GPT 6 Sol) pentru întrebări despre instalații, normative, PRAM, ATR și dosare. Răspunsurile sunt orientative." />
      <div className="grid md:grid-cols-[240px_1fr] gap-4">
        <div className="den-panel !p-3 space-y-1" data-testid="ai-sessions">
          <Btn className="w-full mb-2" onClick={newSession} data-testid="ai-new-session"><Plus size={14} /> Conversație nouă</Btn>
          {sessions.map((s) => (
            <div key={s.id} className={`flex items-center gap-2 rounded-lg px-2 py-2 text-xs cursor-pointer ${s.id === sid ? "bg-[#eef4ff] font-bold" : "hover:bg-slate-50"}`} onClick={() => setSid(s.id)} data-testid={`ai-session-${s.id}`}>
              <span className="truncate flex-1">{s.title}</span>
              <button onClick={(e) => { e.stopPropagation(); window.confirm("Ștergi conversația?") && del(s.id); }} data-testid={`ai-session-del-${s.id}`}><Trash2 size={12} style={{ color: "#b33333" }} /></button>
            </div>))}
        </div>
        <div className="den-panel flex flex-col min-h-[60vh]">
          <div className="flex-1 space-y-3 overflow-y-auto max-h-[60vh] pr-1" data-testid="ai-messages">
            {!msgs.length && <div className="text-sm flex items-center gap-2" style={{ color: "var(--muted)" }}><Sparkles size={16} /> Întreabă, de exemplu: „Ce secțiune de cablu AC pentru un invertor trifazat de 10 kW la 25 m?”</div>}
            {msgs.map((m, i) => <Bubble key={i} m={m} />)}
            <div ref={end} />
          </div>
          <div className="flex gap-2 mt-3">
            <textarea className="den-input flex-1" rows={2} placeholder="Scrie întrebarea..." value={text} onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} data-testid="ai-input" />
            <Btn onClick={send} disabled={busy || !text.trim()} data-testid="ai-send"><Send size={14} /> {busy ? "..." : "Trimite"}</Btn>
          </div>
        </div>
      </div>
    </div>
  );
}
