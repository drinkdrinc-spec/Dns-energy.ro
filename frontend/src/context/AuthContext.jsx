import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);
const SESSION_CHECK_TIMEOUT_MS = 45000;
const AUTH_SERVICE_UNAVAILABLE = "Serverul DNS Energy nu a răspuns. Sesiunea a fost păstrată; verifică conexiunea și încearcă din nou.";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=guest, obj=logged
  const [authIssue, setAuthIssue] = useState("");
  const [authChecking, setAuthChecking] = useState(false);
  const checkSequence = useRef(0);

  const refresh = useCallback(async () => {
    const requestId = ++checkSequence.current;
    const token = localStorage.getItem("den_token");
    if (!token) {
      setAuthIssue("");
      setUser(false);
      setAuthChecking(false);
      return;
    }

    setAuthChecking(true);
    setAuthIssue("");
    try {
      const { data } = await api.get("/auth/me", { timeout: SESSION_CHECK_TIMEOUT_MS });
      if (requestId !== checkSequence.current) return;
      setUser(data);
    } catch (error) {
      if (requestId !== checkSequence.current) return;
      const status = error.response?.status;
      if (status === 401) {
        localStorage.removeItem("den_token");
        setAuthIssue("");
      } else if (!error.response || status >= 500) {
        // A transient network/server failure must not invalidate a possibly valid session.
        setAuthIssue(AUTH_SERVICE_UNAVAILABLE);
      } else {
        setAuthIssue(error.response?.data?.detail || "Sesiunea nu a putut fi verificată. Încearcă din nou.");
      }
      setUser(false);
    } finally {
      if (requestId === checkSequence.current) setAuthChecking(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return () => { checkSequence.current += 1; };
  }, [refresh]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password }, { timeout: SESSION_CHECK_TIMEOUT_MS });
    localStorage.setItem("den_token", data.access_token);
    setAuthIssue("");
    setUser(data.user);
  };

  const logout = () => {
    checkSequence.current += 1;
    localStorage.removeItem("den_token");
    setAuthIssue("");
    setAuthChecking(false);
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, login, refresh, logout, authIssue, authChecking }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
