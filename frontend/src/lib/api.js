import axios from "axios";

const configuredBackend = (process.env.REACT_APP_BACKEND_URL || "").trim().replace(/\/$/, "");
const isLocalHost = typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname);
// Render hosts the SPA and API as separate services. Keep a production fallback
// so a missing static-site build variable cannot silently send API calls to the SPA.
const backendOrigin = configuredBackend || (isLocalHost ? "" : "https://dns-energy-api.onrender.com");
const API = `${backendOrigin}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("den_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function formatApiErrorDetail(detail) {
  if (detail == null) return "A apărut o eroare. Încearcă din nou.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export { API };

async function apiErrorMessage(error) {
  let data = error.response?.data;
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    try { data = JSON.parse(await data.text()); } catch { data = null; }
  }
  return typeof data?.detail === "string" ? data.detail : "Nu am putut genera documentul. Verifică datele și încearcă din nou.";
}

export async function downloadAuthenticatedFile(path, fallbackName = "document") {
  try {
    const response = await api.get(path, { responseType: "blob" });
    const disposition = response.headers["content-disposition"] || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
    let filename = fallbackName;
    try { filename = encoded ? decodeURIComponent(encoded) : (plain || fallbackName); } catch { filename = plain || fallbackName; }
    const blob = response.data.type ? response.data : new Blob([response.data], { type: response.headers["content-type"] || "application/octet-stream" });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
  } catch (error) {
    window.alert(await apiErrorMessage(error));
  }
}

export async function openAuthenticatedFile(path, fallbackName = "document") {
  // Keep the preview in the current app tab. Opening an about:blank tab and
  // navigating it to a blob URL works on desktop browsers but can produce a
  // permanently blank tab in iOS Safari / in-app browsers.
  const previous = document.getElementById("den-auth-file-preview");
  previous?.remove();
  const overlay = document.createElement("div");
  overlay.id = "den-auth-file-preview";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Previzualizare document");
  Object.assign(overlay.style, {
    position: "fixed", inset: "0", zIndex: "2147483000", display: "flex",
    flexDirection: "column", background: "#f4f6fa", color: "#172033",
    fontFamily: "system-ui, sans-serif"
  });
  const bar = document.createElement("div");
  Object.assign(bar.style, {
    minHeight: "56px", display: "flex", alignItems: "center", gap: "12px",
    padding: "8px 14px", paddingTop: "max(8px, env(safe-area-inset-top))",
    background: "#111b31", color: "white"
  });
  const title = document.createElement("strong");
  title.textContent = "Document";
  Object.assign(title.style, { flex: "1", fontSize: "15px" });
  const download = document.createElement("a");
  download.textContent = "Descarcă";
  download.setAttribute("aria-label", "Descarcă documentul");
  Object.assign(download.style, { color: "white", fontSize: "14px", fontWeight: "600", padding: "8px" });
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Închide";
  Object.assign(close.style, {
    border: "1px solid #71809b", borderRadius: "8px", background: "transparent",
    color: "white", padding: "8px 10px", fontSize: "14px", fontWeight: "600"
  });
  const frame = document.createElement("iframe");
  frame.title = "Previzualizare document";
  Object.assign(frame.style, { flex: "1", width: "100%", border: "0", background: "white" });
  overlay.append(bar, frame);
  bar.append(title, download, close);
  document.body.appendChild(overlay);
  const oldOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  let objectUrl = "";
  const cleanup = () => {
    if (!overlay.isConnected) return;
    overlay.remove();
    document.body.style.overflow = oldOverflow;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    document.removeEventListener("keydown", onKeyDown);
  };
  const onKeyDown = (event) => { if (event.key === "Escape") cleanup(); };
  close.addEventListener("click", cleanup);
  document.addEventListener("keydown", onKeyDown);
  try {
    const response = await api.get(path, { responseType: "blob" });
    const disposition = response.headers["content-disposition"] || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
    let filename = fallbackName || plain || "document";
    try { if (encoded && !fallbackName) filename = decodeURIComponent(encoded); } catch { /* keep fallback */ }
    const headerType = (response.headers["content-type"] || "").split(";")[0].toLowerCase();
    const extensionType = /\.pdf$/i.test(filename) ? "application/pdf"
      : /\.(png|jpe?g|gif|webp)$/i.test(filename) ? ( /\.png$/i.test(filename) ? "image/png" : /\.gif$/i.test(filename) ? "image/gif" : /\.webp$/i.test(filename) ? "image/webp" : "image/jpeg" )
      : "";
    const blob = response.data.type && response.data.type !== "application/octet-stream"
      ? response.data
      : new Blob([response.data], { type: extensionType || headerType || "application/pdf" });
    objectUrl = URL.createObjectURL(blob);
    title.textContent = filename;
    download.href = objectUrl;
    download.download = filename;
    frame.src = objectUrl;
  } catch (error) {
    cleanup();
    window.alert(await apiErrorMessage(error));
  }
}

/*
 * Legacy anchors carry an access token in ?auth= so browsers can navigate to API
 * documents. Intercept them and make the same request through Axios instead:
 * its request interceptor supplies Authorization: Bearer, keeping credentials out
 * of the address bar, browser history, and referrer URLs.
 */
if (typeof document !== "undefined" && typeof window !== "undefined" && !window.__denAuthLinkInterceptor) {
  window.__denAuthLinkInterceptor = true;
  document.addEventListener("click", async (event) => {
    const target = event.target instanceof Element ? event.target.closest("a[href]") : null;
    if (!target || event.defaultPrevented || event.button !== 0) return;

    let linkUrl;
    let apiUrl;
    try {
      linkUrl = new URL(target.href, window.location.href);
      apiUrl = new URL(API, window.location.origin);
    } catch { return; }

    if (!linkUrl.searchParams.has("auth")) return;
    const apiPath = apiUrl.pathname.replace(/\/$/, "");
    if (linkUrl.origin !== apiUrl.origin || !(linkUrl.pathname === apiPath || linkUrl.pathname.startsWith(apiPath + "/"))) return;

    event.preventDefault();
    event.stopPropagation();
    linkUrl.searchParams.delete("auth");
    const requestPath = linkUrl.pathname.slice(apiPath.length) + linkUrl.search;
    const requestedDownload = target.hasAttribute("download");
    const tab = requestedDownload ? null : window.open("about:blank", "_blank");
    if (!requestedDownload && !tab) {
      window.alert("Permite deschiderea ferestrei pentru a vedea documentul.");
      return;
    }

    try {
      const response = await api.get(requestPath, { responseType: "blob" });
      const blob = response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: response.headers["content-type"] || "application/octet-stream" });
      const disposition = response.headers["content-disposition"] || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
      let filename = target.getAttribute("download") || plainName || "document";
      try { if (encodedName) filename = decodeURIComponent(encodedName); } catch { /* keep fallback */ }

      const contentType = (response.headers["content-type"] || blob.type || "").split(";")[0].toLowerCase();
      const canDisplay = contentType === "application/pdf" || contentType.startsWith("image/");
      const isDownload = requestedDownload || /attachment/i.test(disposition) || !canDisplay;
      const objectUrl = URL.createObjectURL(blob);
      if (isDownload) {
        const downloadLink = document.createElement("a");
        downloadLink.href = objectUrl;
        downloadLink.download = filename;
        downloadLink.style.display = "none";
        document.body.appendChild(downloadLink);
        downloadLink.click();
        downloadLink.remove();
        tab?.close();
      } else if (tab && !tab.closed) {
        tab.location.replace(objectUrl);
      } else {
        URL.revokeObjectURL(objectUrl);
      }
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    } catch (error) {
      tab?.close();
      window.alert(await apiErrorMessage(error));
    }
  }, true);
}
