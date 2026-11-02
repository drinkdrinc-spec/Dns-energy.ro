import axios from "axios";

const API = `${(process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "")}/api`;

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

export async function openAuthenticatedFile(path) {
  const tab = window.open("about:blank", "_blank");
  if (!tab) { window.alert("Permite deschiderea ferestrei pentru a vedea documentul."); return; }
  tab.document.title = "Se pregătește documentul…";
  try {
    const response = await api.get(path, { responseType: "blob" });
    const blob = response.data.type ? response.data : new Blob([response.data], { type: response.headers["content-type"] || "application/pdf" });
    const objectUrl = URL.createObjectURL(blob);
    tab.location.replace(objectUrl);
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
  } catch (error) {
    tab.close();
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
