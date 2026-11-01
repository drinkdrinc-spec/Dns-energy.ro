NOTE = "Date orientative — verificați fișa tehnică oficială a modelului exact."

SEED_BACKFILL_FIELDS = ("i_max", "coupling", "voltage_1ph", "voltage_3ph", "i_max_source_url")


def missing_seed_values(existing: dict, seed: dict) -> dict:
    """Return only documented values that are absent from an existing catalogue row."""
    updates = {}
    for field in SEED_BACKFILL_FIELDS:
        current = existing.get(field)
        is_missing = current is None or current == "" or (field in ("i_max", "voltage_1ph", "voltage_3ph") and current == 0)
        if is_missing and seed.get(field) not in (None, ""):
            updates[field] = seed[field]
    return updates

SEED = [
    {"category": "Invertor", "brand_model": "Solis S6-EH3P12K02-NV-YD-L", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 12, "p_max_kw": 13.2,
     "vdc_max": 1000, "mppt_min": 200, "mppt_max": 850, "mppt_count": 2, "imax_mppt": 20, "battery_voltage": "LV 48 V",
     "datasheet_url": "https://www.solisinverters.com/uploads/file/S6-EH3P(8-15)K-IT-Flyer-V2,0.pdf"},
    {"category": "Invertor", "brand_model": "Huawei SUN2000-10KTL-M1", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 10, "p_max_kw": 11,
     "vdc_max": 1100, "mppt_min": 140, "mppt_max": 980, "mppt_count": 2, "imax_mppt": 13.5, "battery_voltage": "HV (LUNA2000)",
     "datasheet_url": "https://solar.huawei.com/-/media/Solar/attachment/pdf/in/datasheet/SUN2000-3-10KTL-M1.pdf",
     "conformity_url": "https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/service/residential/product/certification/SUN2000-3-10M0_CE_EMC_Cert_BV.pdf"},
    {"category": "Invertor", "brand_model": "Deye SUN-10K-SG04LP3-EU", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 10, "p_max_kw": 11,
     "vdc_max": 800, "mppt_min": 200, "mppt_max": 650, "mppt_count": 2, "imax_mppt": 26, "battery_voltage": "LV 48 V",
     "datasheet_url": "https://www.deyeinverter.com/deyeinverter/2023/12/11/datasheet_sun-5-12k-sg04lp3_231211_en.pdf",
     "conformity_url": "https://it.deyeinverter.com/deyeinverter/2025/04/17/hybridinverter_eudeclaration-sun-5-12k-sg04lp3-eu%2B240628001.pdf"},
    {"category": "Invertor", "brand_model": "Deye SUN-6K-SG03LP1-EU", "type": "Hibrid", "phases": "Monofazat", "p_nom_kw": 6, "p_max_kw": 6.6,
     "vdc_max": 500, "mppt_min": 125, "mppt_max": 425, "mppt_count": 2, "imax_mppt": 13, "battery_voltage": "LV 48 V",
     "datasheet_url": "https://www.deyeinverter.com/deyeinverter/2023/12/11/datasheet_sun-3.6-6k-sg03lp1_231211_en.pdf",
     "conformity_url": "https://www.deyeinverter.com/deyeinverter/2023/09/28/eudeclaration-sun-3-6k-sg03lp1-eu%2B230926006.pdf"},
    {"category": "Invertor", "brand_model": "Fronius Symo 10.0-3-M", "type": "On-grid", "phases": "Trifazat", "p_nom_kw": 10, "p_max_kw": 10,
     "vdc_max": 1000, "mppt_min": 270, "mppt_max": 800, "mppt_count": 2, "imax_mppt": 27,
     "datasheet_url": "https://www.fronius.com/~/downloads/Solar%20Energy/Datasheets/SE_DS_Fronius_Symo_EN.pdf",
     "conformity_url": "https://www.fronius.com/~/downloads/Solar%20Energy/Declaration%20of%20Conformity/SE_EC_Declaration_of_Conformity_Fronius_Symo_20K-M_Light_MULTI.pdf"},
    {"category": "Invertor", "brand_model": "Victron MultiPlus-II 48/5000", "type": "Invertor de baterie (AC)", "phases": "Monofazat", "p_nom_kw": 4,
     "p_max_kw": 4, "vdc_max": 0, "mppt_count": 0, "battery_voltage": "LV 48 V"},
    {"category": "Panou", "brand_model": "AIKO-A475-MCE54Mb", "w": 475, "voc": 40.8, "vmp": 34.4, "isc": 14.76, "imp": 13.81,
     "coef_voc": -0.22, "temp_pmax": -0.26,
     "datasheet_url": "https://aikosolar.com/wp-content/uploads/2026/10/Neostar-3S54_193-AIKO-A-MCE54Mb_460-475W-1762%C3%971134%C3%9730_202608_V1_1_EN.pdf",
     "conformity_url": "https://aikosolar.com/wp-content/uploads/2025/11/281-MCS_MCS-005-010-011-cert_SGDG.pdf",
     "notes": "Valori STC din fișa AIKO 202608 V1.1; certificat TÜV Rheinland MCS include familia MCE54Mb 440–495 W."},
    {"category": "Panou", "brand_model": "LONGi Hi-MO 6 LR5-54HTH-440M (fișă oficială)", "w": 440, "voc": 39.53, "vmp": 33.24, "isc": 14.30, "imp": 13.24, "coef_voc": -0.23, "temp_pmax": -0.29,
     "datasheet_url": "https://static.longi.com/L_Gi_LE_PM_T_PMD_059_F130_LR_5_54_HTH_420_440_M_V1_30_30_and_15_Frame_Explorer_V19_96aefb02d4.pdf",
     "conformity_url": "https://static.longi.com/TUV_SUD_Certificate_1500_V_New_Standard_5db81e5b40.pdf"},
    {"category": "Panou", "brand_model": "JinkoSolar Tiger Neo JKM440N-54HL4-V", "w": 440, "voc": 39.3, "vmp": 32.7, "isc": 14.03, "imp": 13.47, "coef_voc": -0.25,
     "conformity_url": "https://jinkosolar.eu/wp-content/uploads/2024/11/IEC61215IEC61730-Single-Glass_2025-02-24_Rev-08.pdf"},
    {"category": "Baterie", "brand_model": "Ecobat Tower X 51.2V 314Ah", "kwh": 16.08, "ah": 314, "voltage": 51.2, "tech": "LV"},
    {"category": "Baterie", "brand_model": "Pylontech US5000", "kwh": 4.8, "ah": 100, "voltage": 48, "tech": "LV",
     "i_max": 100, "coupling": "DC", "voltage_1ph": 48, "voltage_3ph": 48,
     "i_max_source_url": "https://en.pylontech.com.cn/products/c23/134.html",
     "datasheet_url": "https://solarshop.baywa-re.lv/en/documents/pylontech-batteries-05-600007-05-600007-0/382/296.pdf",
     "conformity_url": "https://solarshop.baywa-re.lv/en/documents/pylontech-batteries-05-600007-05-600007-0/382/293.pdf",
     "notes": "Curent normal încărcare/descărcare 100 A; limita de 101–120 A este specificată numai pentru 15 min, iar 121–200 A numai pentru 15 s. PDF-urile sunt fișa US5000 și certificatul IEC 62619 listate de BayWa r.e.; valorile tehnice sunt confirmate pe pagina producătorului Pylontech. Nu se deduce o siguranță externă din curentul BMS."},
    {"category": "Baterie", "brand_model": "Deye SE-G5.1 Pro-B", "kwh": 5.12, "ah": 100, "voltage": 51.2, "tech": "LV",
     "i_max": 100, "coupling": "DC", "voltage_1ph": 51.2, "voltage_3ph": 51.2,
     "breaker_integrated": True, "breaker_a": 125, "breaker_poles": 2, "breaker_voltage_dc": 60,
     "i_max_source_url": "https://deyeess.com/wp-content/uploads/2025/12/Deye-SE-G5.1-Pro-B-Series_Brochure_20260907V1.0.pdf",
     "breaker_source_url": "https://deyeess.com/wp-content/uploads/2025/12/Deye-SE-G5.1-Pro-B-Series_Brochure_20260907V1.0.pdf",
     "datasheet_url": "https://deyeess.com/wp-content/uploads/2025/12/Deye-SE-G5.1-Pro-B-Series_Brochure_20260907V1.0.pdf",
     "conformity_url": "https://deyeess.com/wp-content/uploads/2025/12/Deye-ESS-User-Manual-SE-G5.1-Pro-B-EUEN-V06_20260526.pdf",
     "notes": "Model exact EU; întrerupător integrat 125 A, 2P, 60 Vdc. Curent max. încărcare/descărcare 100 A; vârf 150 A/2 min. Fișa și manualul Deye EU includ lista de certificări și declarația UE din anexă. Nu se adaugă întrerupător extern automat."},
    {"category": "Baterie", "brand_model": "Pylontech US5000-B", "kwh": 4.8, "ah": 100, "voltage": 48, "tech": "LV",
     "i_max": 100, "coupling": "DC", "voltage_1ph": 48, "voltage_3ph": 48,
     "breaker_integrated": True, "breaker_a": 125, "breaker_voltage_dc": 60, "breaker_icu_ka": 10,
     "i_max_source_url": "https://en.pylontech.com.cn/products/c23/134.html",
     "breaker_source_url": "https://solarshop.baywa-re.lv/en/documents/pylontech-batteries-05-600007-05-600007-0/382/297.pdf",
     "datasheet_url": "https://solarshop.baywa-re.lv/en/documents/pylontech-batteries-05-600007-05-600007-0/382/296.pdf",
     "conformity_url": "https://solarshop.baywa-re.lv/en/documents/pylontech-batteries-05-600007-05-600007-0/382/293.pdf",
     "notes": "Model US5000-B cu întrerupător integrat tip C, 125 A, 60 Vdc, Icu 10 kA conform manualului Pylontech. Curent normal 100 A; fișa tehnică și certificatul IEC 62619 sunt listate pentru familia US5000/US5000-B. Nu se adaugă întrerupător extern automat."},
    {"category": "Baterie", "brand_model": "Deye SE-G5.1 Pro", "kwh": 5.12, "ah": 100, "voltage": 51.2, "tech": "LV",
     "i_max": 100, "coupling": "DC", "voltage_1ph": 51.2, "voltage_3ph": 51.2,
     "i_max_source_url": "https://deyeess.com/wp-content/uploads/2023/08/SE-G5.1-Pro-V1.5.pdf",
     "datasheet_url": "https://deyeess.com/wp-content/uploads/2023/08/SE-G5.1-Pro-V1.5.pdf",
     "conformity_url": "https://www.deyeinverter.com/deyeinverter/2024/07/01/certificate_iec62619-3.pdf",
     "notes": "Curent maxim încărcare/descărcare 100 A; vârf 150 A timp de 2 min, din fișa producătorului. Certificat CB IEC 62619:2022 pentru SE-G5.1 Pro; nu reprezintă declarația UE de conformitate. Nu se auto-completează o siguranță fără specificație de proiect."},
    {"category": "Baterie", "brand_model": "Huawei LUNA2000-5-S0", "kwh": 5, "ah": 100, "voltage": 450, "voltage_1ph": 450, "voltage_3ph": 600, "i_max": 7.5, "coupling": "DC", "tech": "HV",
     "i_max_source_url": "https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/certificate/residential/LUNA2000-5KW-C0_E0_IEC62477_CB_cert.pdf",
     "datasheet_url": "https://solar.huawei.com/admin/asset/v1/pro/view/cc3f55c9603845749334087ea716cc23.pdf",
     "conformity_url": "https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/certificate/residential/LUNA2000-5-S0_CERT_N8A.pdf",
     "notes": "Imax baterie 7,5 A din certificatul Huawei/TÜV pentru LUNA2000-5-E0. Tensiune nominală sistem: 450 V monofazat / 600 V trifazat; confirmați compatibilitatea cu invertorul ales. Siguranța DC maximă nu este declarată aici și nu se auto-completează."},
    {"category": "Smart meter", "brand_model": "Eastron SDM630 Modbus", "phases": "Trifazat"},

    # Modele solicitate pentru configurarea reală a sistemelor. Parametrii care diferă
    # între variante sunt lăsați necompletați până la atașarea fișei oficiale exacte.
    {"category": "Invertor", "brand_model": "Solis S6-EH3P10K-H", "type": "Hibrid", "phases": "Trifazat", "notes": "Familie S6; confirmați sufixul exact și parametrii din fișa tehnică."},
    {"category": "Invertor", "brand_model": "Solis S6 30 kW", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 30, "notes": "Modelul complet/SKU și parametrii DC/MPPT se confirmă din plăcuță și fișa oficială."},
    {"category": "Invertor", "brand_model": "Solis S6 50 kW", "type": "On-grid", "phases": "Trifazat", "p_nom_kw": 50, "notes": "Modelul complet/SKU și parametrii DC/MPPT se confirmă din plăcuță și fișa oficială."},
    {"category": "Baterie", "brand_model": "Deye BOS-G 100 kW system", "tech": "HV", "notes": "Familie de stocare HV. Configurația de 100 kW se validează cu modelul exact de invertor, rackuri și fișa oficială."},
    {"category": "Invertor", "brand_model": "FoxESS H3 Smart / H3 series", "type": "Hibrid", "phases": "Trifazat",
     "datasheet_url": "https://www.fox-ess.com/Public/Uploads/uploadfile/files/20251203/ENH3SmartDatasheetV1.920250411.pdf",
     "conformity_url": "https://www.fox-ess.com/Public/Uploads/uploadfile/files/20261021/4479925406749234.pdf",
     "notes": "Familie de modele 5–15 kW; selectați și confirmați codul exact înainte de dimensionare."},
    {"category": "Baterie", "brand_model": "Dyness STACK100", "tech": "HV", "notes": "Familie STACK100; capacitatea utilizabilă și numărul de module se completează conform configurației exacte."},
    {"category": "Baterie", "brand_model": "Dyness STACK280", "tech": "HV", "notes": "Familie STACK280; capacitatea utilizabilă și numărul de module se completează conform configurației exacte."},
    {"category": "Baterie", "brand_model": "Deye BOS-G HV battery rack", "tech": "HV", "notes": "Alegeți configurația exactă de module/rack și atașați fișa tehnică și declarația UE de conformitate."},
    {"category": "Baterie", "brand_model": "FoxESS high-voltage battery (model de completat)", "tech": "HV", "notes": "Selectați modelul exact compatibil cu invertorul."},
    {"category": "Panou", "brand_model": "JinkoSolar Tiger Neo 440 W", "w": 440, "notes": "Familia are variante diferite; completați codul exact și valorile din fișa oficială."},
    {"category": "Panou", "brand_model": "LONGi Hi-MO 7 (model de completat)", "notes": "Completați codul exact al modulului și parametrii electrici din fișa oficială."},
    {"category": "Panou", "brand_model": "AIKO Neostar (model de completat)", "notes": "Completați puterea și codul exact al modulului din fișa oficială."},
    # FoxESS H3 Smart exact model SKUs; DC limits shared by the official v1.9 family datasheet.
    # p_max_kw remains at rated active power; apparent power is not silently treated as active kW.
    *({"category": "Invertor", "brand_model": f"FoxESS H3-{kw:.1f}-Smart", "type": "Hibrid", "phases": "Trifazat",
       "p_nom_kw": kw, "p_max_kw": kw, "vdc_max": 1000, "mppt_min": 120, "mppt_max": 950,
       "mppt_count": 3, "imax_mppt": 20, "isc_max_mppt": 25, "battery_voltage": "HV (FoxESS-compatible)",
       "datasheet_url": "https://www.fox-ess.com/Public/Uploads/uploadfile/files/20251203/ENH3SmartDatasheetV1.920250411.pdf",
       "conformity_url": "https://www.fox-ess.com/Public/Uploads/uploadfile/files/20261021/4479925406749234.pdf",
       "notes": "Puterea Pmax este păstrată la Pn; fișa raportează separat puterea aparentă maximă în VA. Certificatul de familie este CE-LVD; verificați certificatele de conectare aplicabile operatorului din România."}
      for kw in [5.0, 6.0, 8.0, 9.9, 10.0, 12.0, 15.0]),
    # GoodWe ET LV exact model SKUs; electrical limits and powers from the current official family datasheet.
    *({"category": "Invertor", "brand_model": f"GoodWe GW{kw}K-ET-L-G10", "type": "Hibrid", "phases": "Trifazat",
       "p_nom_kw": kw, "p_max_kw": max_kw, "vdc_max": 1000, "mppt_min": 150, "mppt_max": 850,
       "mppt_count": mppt, "imax_mppt": 20, "battery_voltage": "LV 48 V",
       "datasheet_url": "https://en.goodwe.com/Public/Uploads/uploadfile/files/20260123/GW_ET-LV_Datasheet-EN.pdf",
       "conformity_url": "https://en.goodwe.com/Ftp/EN/Downloads/Certificate/GW_ET-LV_Certificate-IEC62116_IEC61727.pdf",
       "notes": "Fișă GoodWe ET LV; certificatul atașat este test certificate IEC 61727/62116 pentru familia indicată. Confirmați cerința de conectare a operatorului din România."}
      for kw, max_kw, mppt in [(5, 5.5, 2), (6, 6.6, 2), (8, 8.8, 2), (10, 11, 3), (12, 13.2, 3), (15, 16.5, 4), (20, 22, 4)]),
    # Trina Vertex S+ exact SKUs; shared datasheet lists each power-bin electrical value.
    *({"category": "Panou", "brand_model": f"Trina Solar TSM-{w}NEG9R.28", "w": w, "voc": voc, "vmp": vmp,
       "isc": isc, "imp": imp, "coef_voc": -0.24, "temp_pmax": -0.29,
       "datasheet_url": "https://static.trinasolar.com/sites/default/files/Datasheet%20Vertex%20S%2B_NEG9R.28_EN_2024_C_web.pdf",
       "notes": "Parametri STC/coeficienți din fișa oficială Trina Vertex S+ NEG9R.28 v2024-C. Declarația/certificatele exacte se atașează separat din documentația modelului livrat."}
      for w, voc, vmp, isc, imp in [(430, 51.4, 43.2, 10.59, 9.96), (440, 52.2, 44.0, 10.67, 10.01),
                                    (450, 52.9, 44.6, 10.74, 10.09), (460, 53.8, 45.4, 10.81, 10.14)]),
    # Huawei exact MB0 variants; ratings and DC limits transcribed from the official family datasheet.
    *({"category": "Invertor", "brand_model": f"Huawei SUN2000-{kw}K-MB0", "type": "Hibrid", "phases": "Trifazat",
       "p_nom_kw": kw, "p_max_kw": pmax, "vdc_max": 1100, "mppt_min": 200, "mppt_max": 1000,
       "mppt_count": 2, "imax_mppt": 30, "battery_voltage": "HV (LUNA2000-S0/S1)",
       "datasheet_url": "https://solar.huawei.com/admin/asset/v1/pro/view/07801fff280d458d8e4975b6dd9f411e.pdf",
       "notes": "Date tehnice din fișa oficială Huawei MB0 v02-202403. Declarația UE de conformitate exactă nu este atașată în catalog; adăugați documentul potrivit SKU-ului și cerinței OD."}
      for kw, pmax in [(12, 13.2), (15, 16.5), (17, 18.7), (20, 22), (25, 27.5)]),

]
