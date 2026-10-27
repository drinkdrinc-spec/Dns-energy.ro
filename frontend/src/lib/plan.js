export const ROUTE_FEATURE = {
  "/clienti": "prosumator", "/prosumator": "prosumator", "/diu": "diu", "/lucrari": "works", "/mono": "mono", "/tablouri": "panels",
  "/antiinsularizare": "anti", "/pram": "pram", "/echipamente": "equipment", "/spor-putere": "power", "/cerere-atr": "atr", "/simulare": "projects",
  "/semnare": "sign_remote", "/catalog-echipamente": "prosumator", "/setari-baza": "prosumator", "/documente": "prosumator",
  "/catalog": "prosumator", "/distribuitori": "prosumator",
};

export const isOff = (user, feat) => !!feat && (user?.plan?.disabled || []).includes(feat);

export function can(user, feat) {
  const p = user?.plan;
  if (isOff(user, feat)) return false;
  if (!p || p.exempt || !feat) return true;
  if (!p.active) return p.policy !== "blocked";
  return p.features.includes("*") || p.features.includes(feat);
}

export const lei = (v) => `${Number(v || 0).toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} lei`;
