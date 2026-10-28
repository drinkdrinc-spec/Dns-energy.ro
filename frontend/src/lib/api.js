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
