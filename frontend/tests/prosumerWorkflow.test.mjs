import assert from "node:assert/strict";
import test from "node:test";
import { installationIsConfigured } from "../src/lib/prosumerWorkflow.mjs";

const hybrid = (overrides = {}) => ({
  brand_model: "Hybrid 8 kW",
  battery_mode: "own",
  battery: { model: "Battery 10 kWh" },
  strings: [{ panels: "10" }],
  panel_model: "Panel 500 W",
  ...overrides,
});

test("an ordinary hybrid with a battery but no declared PV or battery-only mode stays incomplete", () => {
  assert.equal(installationIsConfigured({ inverters: [hybrid({ panel_model: "", strings: [{ panels: "" }] })] }), false);
});

test("a hybrid explicitly configured for battery-only operation completes the installation step", () => {
  assert.equal(installationIsConfigured({ inverters: [hybrid({ battery_only: true, no_panels: true, panel_model: "", strings: [] })] }), true);
});

test("a battery-only setting without a selected battery does not complete the installation step", () => {
  assert.equal(installationIsConfigured({ inverters: [hybrid({ battery_only: true, no_panels: true, panel_model: "", strings: [], battery: {} })] }), false);
});

test("an AC battery inverter is complete when its selected shared battery exists", () => {
  const cef = {
    inverters: [{ brand_model: "Battery PCS", type: "Invertor de baterie (AC)", battery_mode: "shared", shared_battery_id: "b1", strings: [] }],
    shared_batteries: [{ id: "b1", model: "Shared Battery" }],
  };
  assert.equal(installationIsConfigured(cef), true);
});

test("every inverter row must be configured, not only one row", () => {
  assert.equal(installationIsConfigured({ inverters: [hybrid(), { brand_model: "", strings: [] }] }), false);
});

test("malformed legacy arrays do not crash the progress indicator", () => {
  assert.equal(installationIsConfigured({ inverters: [{ ...hybrid(), strings: {}, battery_mode: "shared" }], shared_batteries: {} }), false);
});

