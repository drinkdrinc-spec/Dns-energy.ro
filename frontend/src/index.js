import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";
import { queryClient } from "@/lib/queryClient";

// Enable installation as a PWA on supported mobile browsers. Keep API and
// authenticated document traffic out of the service-worker cache.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.error("DNS Energy service worker registration failed:", error);
    });
  });
}

// An already-open PWA tab keeps its old JavaScript bundle after a deploy.
// Compare the entry asset with the current HTML when the app is revisited, and
// let the user refresh deliberately so unsaved forms are not silently lost.
if (import.meta.env.PROD) {
  let updatePromptShown = false;
  const checkForNewBuild = async () => {
    if (document.visibilityState !== "visible" || updatePromptShown) return;
    try {
      const response = await fetch(`/?dns_build_check=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) return;
      const html = await response.text();
      const latestDocument = new DOMParser().parseFromString(html, "text/html");
      const currentSrc = document.querySelector('script[type="module"][src]')?.getAttribute("src");
      const latestSrc = latestDocument.querySelector('script[type="module"][src]')?.getAttribute("src");
      if (!currentSrc || !latestSrc || new URL(currentSrc, location.href).pathname === new URL(latestSrc, location.href).pathname) return;
      updatePromptShown = true;
      if (window.confirm("DNS Energy s-a actualizat. Reîncarcă pagina pentru a folosi versiunea nouă? Formularele nesalvate pot fi pierdute.")) {
        window.location.reload();
      } else {
        updatePromptShown = false;
      }
    } catch {
      // Keep the current session usable if the version check is temporarily unavailable.
    }
  };
  window.addEventListener("focus", checkForNewBuild);
  window.setInterval(checkForNewBuild, 5 * 60 * 1000);
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
