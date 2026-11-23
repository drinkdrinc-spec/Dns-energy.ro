import React from "react";

export default class AppErrorBoundary extends React.Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error("DNS Energy page render failed", error, info?.componentStack || "");
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main role="alert" style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24, background: "#f5f7fb", color: "#1f2937", fontFamily: "system-ui, sans-serif" }}>
        <section style={{ width: "min(100%, 480px)", padding: 24, border: "1px solid #dfe4ec", borderRadius: 18, background: "#fff", textAlign: "center", boxShadow: "0 8px 24px rgba(15, 23, 42, .06)" }}>
          <h1 style={{ margin: "0 0 8px", fontSize: 21, fontWeight: 700 }}>Pagina nu s-a încărcat corect</h1>
          <p style={{ margin: "0 0 20px", color: "#64748b", lineHeight: 1.5 }}>Reîncarcă pagina. Dacă problema continuă, contactează administratorul DNS Energy.</p>
          <button type="button" onClick={() => window.location.reload()} style={{ minHeight: 44, padding: "0 18px", border: 0, borderRadius: 10, background: "#198754", color: "#fff", font: "inherit", fontWeight: 700 }}>Reîncarcă pagina</button>
        </section>
      </main>
    );
  }
}
