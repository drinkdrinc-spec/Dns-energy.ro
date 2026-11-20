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

const TRANSIENT_API_STATUSES = new Set([502, 503, 504]);
const SAFE_API_RETRIES = 5;
const API_RETRY_DELAYS_MS = [1000, 2000, 4000, 6000, 6000];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    if (!config) return Promise.reject(error);
    const method = String(config.method || "get").toLowerCase();
    const safeRequest = ["get", "head"].includes(method) || config.dnsRetrySafe === true;
    const transientResponse = TRANSIENT_API_STATUSES.has(error.response?.status);
    const temporaryNetworkFailure = !error.response
      && !(typeof navigator !== "undefined" && navigator.onLine === false);
    const attempts = Number(config.__dnsRetryCount || 0);
    if (!safeRequest || (!transientResponse && !temporaryNetworkFailure) || attempts >= SAFE_API_RETRIES) {
      return Promise.reject(error);
    }

    config.__dnsRetryCount = attempts + 1;
    const wait = API_RETRY_DELAYS_MS[Math.min(attempts, API_RETRY_DELAYS_MS.length - 1)];
    await new Promise((resolve) => window.setTimeout(resolve, wait));
    return api.request(config);
  },
);

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

function openBlobInCurrentTab(blob) {
  // Mobile browsers can render a PDF in a top-level tab but show a blank page
  // for the same blob URL inside an iframe or a newly opened about:blank tab.
  const objectUrl = URL.createObjectURL(blob);
  window.location.assign(objectUrl);
}

function downloadBlob(blob, filename) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename || "document";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
}

export async function openAuthenticatedFile(path, fallbackName = "document") {
  try {
    const response = await api.get(path, { responseType: "blob" });
    const disposition = response.headers["content-disposition"] || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
    let filename = fallbackName && fallbackName !== "document" ? fallbackName : (plain || "document");
    try { if (encoded && (!fallbackName || fallbackName === "document")) filename = decodeURIComponent(encoded); } catch { /* keep fallback */ }
    const headerType = (response.headers["content-type"] || response.data.type || "").split(";")[0].toLowerCase();
    const extensionType = /\.pdf$/i.test(filename) ? "application/pdf"
      : /\.(png|jpe?g|gif|webp)$/i.test(filename) ? (/\.png$/i.test(filename) ? "image/png" : /\.gif$/i.test(filename) ? "image/gif" : /\.webp$/i.test(filename) ? "image/webp" : "image/jpeg")
      : "";
    const blob = response.data.type && response.data.type !== "application/octet-stream"
      ? response.data
      : new Blob([response.data], { type: extensionType || headerType || "application/pdf" });
    const contentType = blob.type || extensionType || headerType;
    if (contentType === "application/pdf" || contentType.startsWith("image/")) {
      openBlobInCurrentTab(blob);
    } else {
      downloadBlob(blob, filename);
    }
  } catch (error) {
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

      const inferredType = /\.pdf$/i.test(filename) ? "application/pdf"
        : /\.png$/i.test(filename) ? "image/png" : /\.(jpe?g)$/i.test(filename) ? "image/jpeg" : "";
      const contentType = (response.headers["content-type"] || blob.type || inferredType || "").split(";")[0].toLowerCase();
      const canDisplay = contentType === "application/pdf" || contentType.startsWith("image/");
      const isDownload = requestedDownload || /attachment/i.test(disposition) || !canDisplay;
      if (isDownload) {
        const objectUrl = URL.createObjectURL(blob);
        const downloadLink = document.createElement("a");
        downloadLink.href = objectUrl;
        downloadLink.download = filename;
        downloadLink.style.display = "none";
        document.body.appendChild(downloadLink);
        downloadLink.click();
        downloadLink.remove();
      } else {
        const viewBlob = blob.type && blob.type !== "application/octet-stream"
          ? blob
          : new Blob([blob], { type: inferredType || contentType || "application/pdf" });
        openBlobInCurrentTab(viewBlob);
      }
    } catch (error) {
      window.alert(await apiErrorMessage(error));
    }
  }, true);
}

