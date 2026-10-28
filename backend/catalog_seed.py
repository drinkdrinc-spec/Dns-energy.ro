NOTE = "Date orientative — verificați fișa tehnică oficială a modelului exact."

SEED = [
    {"category": "Invertor", "brand_model": "Solis S6-EH3P12K02-NV-YD-L", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 12, "p_max_kw": 13.2,
     "vdc_max": 1000, "mppt_min": 160, "mppt_max": 850, "mppt_count": 2, "imax_mppt": 32, "battery_voltage": "LV 48 V"},
    {"category": "Invertor", "brand_model": "Huawei SUN2000-10KTL-M1", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 10, "p_max_kw": 11,
     "vdc_max": 1100, "mppt_min": 140, "mppt_max": 980, "mppt_count": 2, "imax_mppt": 13.5, "battery_voltage": "HV (LUNA2000)"},
    {"category": "Invertor", "brand_model": "Deye SUN-10K-SG04LP3-EU", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 10, "p_max_kw": 11,
     "vdc_max": 800, "mppt_min": 200, "mppt_max": 650, "mppt_count": 2, "imax_mppt": 26, "battery_voltage": "LV 48 V"},
    {"category": "Invertor", "brand_model": "Deye SUN-6K-SG03LP1-EU", "type": "Hibrid", "phases": "Monofazat", "p_nom_kw": 6, "p_max_kw": 6.6,
     "vdc_max": 500, "mppt_min": 125, "mppt_max": 425, "mppt_count": 2, "imax_mppt": 13, "battery_voltage": "LV 48 V"},
    {"category": "Invertor", "brand_model": "Fronius Symo 10.0-3-M", "type": "On-grid", "phases": "Trifazat", "p_nom_kw": 10, "p_max_kw": 10,
     "vdc_max": 1000, "mppt_min": 270, "mppt_max": 800, "mppt_count": 2, "imax_mppt": 27},
    {"category": "Invertor", "brand_model": "Victron MultiPlus-II 48/5000", "type": "Invertor de baterie (AC)", "phases": "Monofazat", "p_nom_kw": 4,
     "p_max_kw": 4, "vdc_max": 0, "mppt_count": 0, "battery_voltage": "LV 48 V"},
    {"category": "Panou", "brand_model": "Aiko Neostar 475 W", "w": 475, "voc": 40.2, "vmp": 33.6, "isc": 14.9, "imp": 14.15, "coef_voc": -0.26},
    {"category": "Panou", "brand_model": "LONGi Hi-MO 6 LR5-54HTH-440M", "w": 440, "voc": 39.9, "vmp": 33.3, "isc": 14.04, "imp": 13.22, "coef_voc": -0.23},
    {"category": "Panou", "brand_model": "JinkoSolar Tiger Neo JKM440N-54HL4-V", "w": 440, "voc": 39.3, "vmp": 32.7, "isc": 14.03, "imp": 13.47, "coef_voc": -0.25},
    {"category": "Baterie", "brand_model": "Ecobat Tower X 51.2V 314Ah", "kwh": 16.08, "ah": 314, "voltage": 51.2, "tech": "LV", "coupling": "DC"},
    {"category": "Baterie", "brand_model": "Pylontech US5000", "kwh": 4.8, "ah": 100, "voltage": 48, "tech": "LV", "coupling": "DC"},
    {"category": "Baterie", "brand_model": "Deye SE-G5.1 Pro", "kwh": 5.12, "ah": 100, "voltage": 51.2, "tech": "LV", "coupling": "DC"},
    {"category": "Baterie", "brand_model": "Huawei LUNA2000-5-S0", "kwh": 5, "ah": 0, "voltage": 360, "tech": "HV", "coupling": "DC"},
    {"category": "Smart meter", "brand_model": "Eastron SDM630 Modbus", "phases": "Trifazat"},

    # Modele solicitate pentru configurarea reală a sistemelor. Parametrii care diferă
    # între variante sunt lăsați necompletați până la atașarea fișei oficiale exacte.
    {"category": "Invertor", "brand_model": "Solis S6-EH3P10K-H", "type": "Hibrid", "phases": "Trifazat", "notes": "Familie S6; confirmați sufixul exact și parametrii din fișa tehnică."},
    {"category": "Invertor", "brand_model": "Solis S6 30 kW", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 30, "notes": "Modelul complet/SKU și parametrii DC/MPPT se confirmă din plăcuță și fișa oficială."},
    {"category": "Invertor", "brand_model": "Solis S6 50 kW", "type": "On-grid", "phases": "Trifazat", "p_nom_kw": 50, "notes": "Modelul complet/SKU și parametrii DC/MPPT se confirmă din plăcuță și fișa oficială."},
    {"category": "Baterie", "brand_model": "Deye BOS-G 100 kW system", "tech": "HV", "coupling": "DC", "notes": "Familie de stocare HV. Configurația de 100 kW se validează cu modelul exact de invertor, rackuri și fișa oficială."},
    {"category": "Invertor", "brand_model": "FoxESS H3 Smart / H3 series", "type": "Hibrid", "phases": "Trifazat", "notes": "Selectați ulterior modelul și puterea exactă; nu se folosesc valori generice la dimensionare."},
    {"category": "Baterie", "brand_model": "Dyness STACK100", "tech": "HV", "coupling": "DC", "notes": "Familie STACK100; capacitatea utilizabilă și numărul de module se completează conform configurației exacte."},
    {"category": "Baterie", "brand_model": "Dyness STACK280", "tech": "HV", "coupling": "DC", "notes": "Familie STACK280; capacitatea utilizabilă și numărul de module se completează conform configurației exacte."},
    {"category": "Baterie", "brand_model": "Deye BOS-G HV battery rack", "tech": "HV", "coupling": "DC", "notes": "Alegeți configurația exactă de module/rack și atașați fișa tehnică și declarația UE de conformitate."},
    {"category": "Baterie", "brand_model": "FoxESS high-voltage battery (model de completat)", "tech": "HV", "coupling": "DC", "notes": "Selectați modelul exact compatibil cu invertorul."},
    {"category": "Panou", "brand_model": "JinkoSolar Tiger Neo 440 W", "w": 440, "notes": "Familia are variante diferite; completați codul exact și valorile din fișa oficială."},
    {"category": "Panou", "brand_model": "LONGi Hi-MO 7 (model de completat)", "notes": "Completați codul exact al modulului și parametrii electrici din fișa oficială."},
    {"category": "Panou", "brand_model": "AIKO Neostar (model de completat)", "notes": "Completați puterea și codul exact al modulului din fișa oficială."},
]
