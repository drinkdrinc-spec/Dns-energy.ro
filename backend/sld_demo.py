DEMO_CLIENT = {"name": "EXEMPLU DEMONSTRATIV — Popescu Ion", "address": "Str. Exemplului nr. 1", "locality": "Localitate Demo", "county": "Demo",
               "operator": "Distribuție Energie Electrică România (DEER)", "pod": "RO000E000000000000 (exemplu)"}
DEMO_REC = {
    "project_no": "DEMO-001", "doc_date": "", "sld": {"revision": 0},
    "cef": {
        "tmin": -10,
        "grid": {"supply": "Trifazat", "bransament_kw": 20, "bmp_a": 40, "earthing": "TN-C-S", "ik_ka": 6, "tg_breaker_a": 32,
                 "column_cable": "CYAbY 5×10 mm² Cu", "column_section": 10, "column_length": 25, "column_material": "Cu", "column_install": "D",
                 "meter": "Smart meter trifazat (exemplu)", "sm_ct_ratio": "", "spd_ac": "tip 1+2", "rcd_ma": 300,
                 "grounding_ohm": 3.2, "grounding_limit": 4, "bond_section": 6, "tmin": -10},
        "inverters": [{
            "brand_model": "Invertor hibrid 10 kW (exemplu)", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 10, "p_max_kw": 11, "p_limit_kw": 10,
            "vdc_max": 1000, "mppt_min": 160, "mppt_max": 850, "mppt_count": 2, "imax_mppt": 20,
            "panel_model": "Modul monocristalin 450 W (exemplu)", "panel_w": 450, "panel_voc": 41.0, "panel_vmp": 34.5, "panel_isc": 13.9, "panel_coef_voc": -0.27,
            "strings": [{"panels": 12, "mppt": 1}, {"panels": 12, "mppt": 2}],
            "battery_mode": "own", "battery": {"model": "Baterie LV 10 kWh (exemplu)", "kwh": 10, "voltage": 51.2, "modules": 1, "coupling": "DC", "i_max": 100, "fuse_a": 125, "cable_section": 35, "cable_length": 2},
            "backup": {"enabled": True, "type": "parțial", "breaker": "C16 A 4P", "circuits": "iluminat, centrală termică, frigider"},
            "rcd_type": "Tip A", "rcd_ma": 300,
            "ac": {"cable_type": "CYY-F", "material": "Cu", "install": "C", "length_m": 15, "section": 4, "pe_section": 4, "breaker_a": 20, "icu_ka": 6},
            "dc": {"cable_type": "H1Z2Z2-K", "material": "Cu", "length_m": 25, "section": 6, "spd_ucpv": 1000, "switch": "1000 V / 25 A DC-PV2"}}],
        "shared_batteries": []}}
