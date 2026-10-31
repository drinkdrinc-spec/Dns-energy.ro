import axios from "axios";

const API = `${(process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "")}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("den_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function fileUrl(storagePath) {
  const token = localStorage.getItem("den_token");
  return `${API}/files/${storagePath}?auth=${token}`;
}

export function formatApiErrorDetail(detail) {
  if (detail == null) return "A apărut o eroare. Încearcă din nou.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export { API };

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
    const detail = error.response?.data?.detail;
    window.alert(typeof detail === "string" ? detail : "Nu am putut genera documentul. Verifică datele și încearcă din nou.");
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
    const detail = error.response?.data?.detail;
    window.alert(typeof detail === "string" ? detail : "Nu am putut genera documentul. Verifică datele și încearcă din nou.");
  }
}
