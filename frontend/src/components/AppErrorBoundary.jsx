import React from "react";

const clip = (value, max) => String(value || "").slice(0, max);

export default class AppErrorBoundary extends React.Component {
  state = { failed: false, message: "", componentStack: "" };

  static getDerivedStateFromError(error) {
    return { failed: true, message: clip(error?.message || error, 500) };
  }

  componentDidCatch(error, info) {
    const componentStack = clip(info?.componentStack, 2400);
    console.error("DNS Energy page render failed", error, componentStack);
    this.setState({ message: clip(error?.message || error, 500), componentStack });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main role="alert" style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24, background: "#f5f7fb", color: "#1f2937", fontFamily: "system-ui, sans-serif" }}>
        <section style={{ width: "min(100%, 640px)", padding: 24, border: "1px solid #dfe4ec", borderRadius: 18, background: "#fff", textAlign: "center", boxShadow: "0 8px 24px rgba(15, 23, 42, .06)" }}>
          <h1 style={{ margin: "0 0 8px", fontSize: 21, fontWeight: 700 }}>Pagina nu s-a încărcat corect</h1>
          <p style={{ margin: "0 0 20px", color: "#64748b", lineHeight: 1.5 }}>Eroarea a fost oprită pentru a proteja restul aplicației. Reîncarcă pagina sau revino la dosare.</p>
          <div style={{ display: "flex", justifyContent: "center", gap: 10, flexWrap: "wrap" }}>
            <button type="button" onClick={() => window.location.reload()} style={{ minHeight: 44, padding: "0 18px", border: 0, borderRadius: 10, background: "#198754", color: "#fff", font: "inherit", fontWeight: 700 }}>Reîncarcă pagina</button>
            <a href="/prosumator" style={{ minHeight: 44, padding: "11px 18px", border: "1px solid #dfe4ec", borderRadius: 10, color: "#1f2937", font: "inherit", fontWeight: 700, textDecoration: "none" }}>Înapoi la dosare</a>
          </div>
          <details style={{ marginTop: 20, textAlign: "left", borderTop: "1px solid #e5e7eb", paddingTop: 14 }}>
            <summary style={{ cursor: "pointer", color: "#475569", fontWeight: 600 }}>Detalii pentru depanare</summary>
            <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxHeight: 260, overflow: "auto", marginTop: 12, padding: 12, borderRadius: 8, background: "#f8fafc", color: "#334155", fontSize: 12 }}>{this.state.message || "Eroare de randare fără mesaj."}{this.state.componentStack ? "\n\nComponente:\n" + this.state.componentStack : ""}</pre>
          </details>
        </section>
      </main>
    );
  }
}
