import { useEffect, useState } from "react";

const STORAGE_KEY = "dns-supplier-markup";
const CHANGE_EVENT = "dns-supplier-markup-changed";

export function readSupplierMarkup() {
  try {
    return Number(window.localStorage.getItem(STORAGE_KEY)) === 20 ? 20 : 15;
  } catch {
    return 15;
  }
}

export function useSupplierMarkup() {
  const [markup, setMarkup] = useState(readSupplierMarkup);

  useEffect(() => {
    const sync = () => setMarkup(readSupplierMarkup());
    window.addEventListener(CHANGE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CHANGE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const updateMarkup = (value) => {
    const next = Number(value) === 20 ? 20 : 15;
    try {
      window.localStorage.setItem(STORAGE_KEY, String(next));
    } catch {
      // Keep the selected value for the current view when storage is unavailable.
    }
    setMarkup(next);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  };

  return [markup, updateMarkup];
}

export function supplierPartnerPrice(raw, markup = readSupplierMarkup()) {
  const match = String(raw || "").match(/\d[\d\s.,]*/);
  if (!match) return "";
  const value = match[0].replace(/\s/g, "");
  const lastComma = value.lastIndexOf(",");
  const lastDot = value.lastIndexOf(".");
  const decimalAt = Math.max(lastComma, lastDot);
  const fractionLength = decimalAt >= 0 ? value.length - decimalAt - 1 : 0;
  const normalized = decimalAt >= 0 && fractionLength > 0 && fractionLength <= 2
    ? `${value.slice(0, decimalAt).replace(/[.,]/g, "")}.${value.slice(decimalAt + 1)}`
    : value.replace(/[.,]/g, "");
  const amount = Number(normalized);
  if (!Number.isFinite(amount) || amount <= 0) return "";
  const currency = /\bEUR\b|€/i.test(raw) ? "EUR" : "RON";
  return new Intl.NumberFormat("ro-RO", { style: "currency", currency, minimumFractionDigits: 2 }).format(amount * (1 + markup / 100));
}
