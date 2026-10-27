import { API } from "@/lib/api";

export async function streamAI(path, body, onDelta) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("den_token")}` },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    let d = "Eroare";
    try { d = (await res.json()).detail || d; } catch (e) { /* ignore */ }
    throw new Error(d);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "", full = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const p of parts) {
      if (!p.startsWith("data: ")) continue;
      const ev = JSON.parse(p.slice(6));
      if (ev.error) throw new Error(ev.error);
      if (ev.t) { full += ev.t; onDelta(full); }
    }
  }
  return full;
}
