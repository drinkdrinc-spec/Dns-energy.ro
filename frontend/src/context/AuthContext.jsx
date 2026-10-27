import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=guest, obj=logged
  useEffect(() => {
    const token = localStorage.getItem("den_token");
    if (!token) { setUser(false); return; }
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => {
      localStorage.removeItem("den_token");
      setUser(false);
    });
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("den_token", data.access_token);
    setUser(data.user);
  };
  const refresh = () => api.get("/auth/me").then((r) => setUser(r.data)).catch(() => {});
  const logout = () => {
    localStorage.removeItem("den_token");
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, login, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
