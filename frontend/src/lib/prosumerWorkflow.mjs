const text = (value) => String(value ?? "").trim();
const number = (value) => Number(String(value ?? "").replace(",", ".")) || 0;

function batteryIsSelected(inverter, cef) {
  if (inverter.battery_mode === "own") return Boolean(text(inverter.battery?.model));
  if (inverter.battery_mode === "shared") {
    return (cef.shared_batteries || []).some((battery) =>
      battery?.id === inverter.shared_battery_id && text(battery.model));
  }
  return false;
}

function inverterInstallationIsConfigured(inverter, cef) {
  if (!text(inverter.brand_model || inverter.model || inverter.inverter)) return false;

  const batteryOnly = Boolean(inverter.battery_only || inverter.no_panels);
  const acBatteryInverter = text(inverter.type).toLocaleLowerCase("ro-RO").includes("invertor de baterie (ac)");
  if (batteryOnly || acBatteryInverter) return batteryIsSelected(inverter, cef);

  const hasPanelModel = Boolean(text(inverter.panel_model || inverter.panel));
  const hasPopulatedString = (inverter.strings || []).some((row) => number(row?.panels) > 0);
  return hasPanelModel && hasPopulatedString;
}

export function installationIsConfigured(value) {
  const cef = value && typeof value === "object" ? value : {};
  const inverters = Array.isArray(cef.inverters) ? cef.inverters : [];
  return inverters.length > 0 && inverters.every((inverter) =>
    inverter && typeof inverter === "object" && inverterInstallationIsConfigured(inverter, cef));
}

