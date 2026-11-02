const NO_BATTERY = new Set(["", "0", "0.0", "-", "—", "none", "no", "nu", "n/a", "nespecificat", "fără baterie", "fara baterie"]);

function declared(value) {
  if (value == null || value === false) return false;
  if (typeof value === "number") return value > 0;
  return !NO_BATTERY.has(String(value).trim().toLocaleLowerCase("ro-RO"));
}

function configuredBattery(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    if (declared(value.model)) return true;
    return ["kwh", "ah", "voltage", "i_max"].some((key) => Number(value[key]) > 0);
  }
  return declared(value);
}

export function hasConfiguredStorage(record) {
  if (!record || typeof record !== "object") return false;
  if (configuredBattery(record.battery)
      || ["battery_kwh", "battery_ah", "battery_v"].some((key) => Number(record[key]) > 0)) return true;

  const cef = record.cef && typeof record.cef === "object" ? record.cef : record;
  const shared = Array.isArray(cef.shared_batteries) ? cef.shared_batteries : [];
  if (shared.some(configuredBattery)) return true;
  const sharedIds = new Set(shared.filter(configuredBattery).map((battery) => String(battery.id || "")));

  return (cef.inverters || []).some((inverter) => {
    if (inverter.battery_mode === "own") return configuredBattery(inverter.battery);
    return inverter.battery_mode === "shared"
      && inverter.shared_battery_id != null
      && sharedIds.has(String(inverter.shared_battery_id));
  });
}
