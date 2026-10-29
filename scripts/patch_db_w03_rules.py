"""Миграция crc.db для v2.5 (W-03): правила кинетики из rules.yaml -> kinetic_barriers, complex_constants.

1. kinetic_barriers получает колонки kind, priority, title, why, conditions (JSON), effect (JSON).
   Сюда переезжают 29 правил rules.yaml v2.4 (36 записей минус 6 фундаментальных минус дубль).
   Порог "T_below: X" заменен энергией активации: Ea такова, что по Эйрингу при T = X
   период полупревращения ровно 1 ч (k = kT/h exp(-Ea/RT) = ln2/3600 с^-1).
   Реакция заблокирована, если при текущей T полупревращение дольше 1 ч, то есть T < X:
   поведение совпадает с v2.4. Ea округлена вниз до 0.01 кДж/моль, порог не выше исходного.
   ea_kj_mol = NULL - правило селективности без температурного порога.
   priority - порядок в rules.yaml v2.4: decouple по одному элементу перезаписывается, порядок важен.
2. complex_constants - суммарные константы устойчивости lg beta (25 C) для W-02 (staged balancer).

Идемпотентен: повторный запуск обновляет строки.
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
SOURCE = "rules.yaml v2.4; Ea по Эйрингу (t1/2 = 1 ч при T_ref)"

KINETIC_RULES = json.loads(r'''
[
 {
  "id": "nitrogen_redox_lowT",
  "priority": 1,
  "kind": "redox",
  "ea_kj_mol": 143.76,
  "T_ref": 450,
  "title": "Азот: нитрат восстанавливается только до NO/NO2/HNO2",
  "why": "При T < 450 K нитрат и азотная кислота восстанавливаются до оксидов азота; NH4+, N2O, N2 из нитрата кинетически не образуются.",
  "conditions": {},
  "effect": {
   "decouple": {
    "element": "N",
    "groups": [
     [
      5,
      4,
      3,
      2
     ],
     [
      -3
     ],
     [
      1
     ],
     [
      0
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "nitrogen_redox_lowT_dilute_active",
  "priority": 2,
  "kind": "redox",
  "ea_kj_mol": 143.76,
  "T_ref": 450,
  "title": "Очень разбавленная HNO3 с активным металлом: до NH4+",
  "why": "С Mg, Zn, Al очень разбавленная азотная кислота (< 1 М) восстанавливается до иона аммония.",
  "conditions": {
   "reagent_present": "HNO3",
   "acid_conc_below": {
    "acid": "HNO3",
    "M": 1.0
   },
   "active_metal_reagent": true
  },
  "effect": {
   "decouple": {
    "element": "N",
    "groups": [
     [
      5,
      4,
      3,
      2,
      -3
     ],
     [
      1
     ],
     [
      0
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "nitrate_neutral_inert",
  "priority": 3,
  "kind": "redox",
  "ea_kj_mol": 143.76,
  "T_ref": 450,
  "title": "Нитрат в нейтральной среде не окисляет металлы",
  "why": "Без кислоты нитрат-ион кинетически инертен.",
  "conditions": {
   "no_acid": true
  },
  "effect": {
   "decouple": {
    "element": "N",
    "groups": [
     [
      5
     ],
     [
      4,
      3,
      2
     ],
     [
      -3
     ],
     [
      1
     ],
     [
      0
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "conc_nitric_no2",
  "priority": 4,
  "kind": "formation",
  "ea_kj_mol": null,
  "T_ref": null,
  "title": "Концентрированная HNO3 дает NO2",
  "why": "В концентрированной азотной кислоте NO окисляется до NO2.",
  "conditions": {
   "acid_conc_at_least": {
    "acid": "HNO3",
    "M": 6.0
   }
  },
  "effect": {
   "forbid_new": [
    "NO",
    "HNO2",
    "NO2-"
   ]
  }
 },
 {
  "id": "dilute_nitric_no",
  "priority": 5,
  "kind": "formation",
  "ea_kj_mol": null,
  "T_ref": null,
  "title": "Разбавленная HNO3 дает NO",
  "why": "В разбавленной кислоте основной газ - NO; NO2 диспропорционирует.",
  "conditions": {
   "acid_conc_below": {
    "acid": "HNO3",
    "M": 6.0
   },
   "reagent_present": "HNO3"
  },
  "effect": {
   "forbid_new": [
    "NO2",
    "N2O4"
   ]
  }
 },
 {
  "id": "sulfate_inert",
  "priority": 6,
  "kind": "redox",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Сульфат не восстанавливается",
  "why": "SO4(2-) кинетически инертен: разбавленная H2SO4 окисляет металлы ионом H+, а не серой(VI).",
  "conditions": {
   "no_conc_sulfuric_hot": true,
   "no_strong_oxidant": true
  },
  "effect": {
   "decouple": {
    "element": "S",
    "groups": [
     [
      6
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "conc_sulfuric_so2",
  "priority": 7,
  "kind": "redox",
  "ea_kj_mol": null,
  "T_ref": null,
  "title": "Горячая концентрированная H2SO4 восстанавливается до SO2",
  "why": "Концентрированная серная кислота при нагревании - окислитель; основной продукт восстановления - SO2.",
  "conditions": {
   "conc_sulfuric_hot": true
  },
  "effect": {
   "decouple": {
    "element": "S",
    "groups": [
     [
      6,
      4
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "chlorine_oxoanions",
  "priority": 8,
  "kind": "redox",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Хлорат и перхлорат инертны при низкой температуре",
  "why": "ClO3- и ClO4- в разбавленных растворах кинетически устойчивы.",
  "conditions": {
   "acid_conc_below": {
    "acid": "HCl",
    "M": 6.0
   }
  },
  "effect": {
   "decouple": {
    "element": "Cl",
    "groups": [
     [
      7
     ],
     [
      5
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "no_new_o2",
  "priority": 10,
  "kind": "formation",
  "ea_kj_mol": 143.76,
  "T_ref": 450,
  "title": "O2 не выделяется из воды и оксоанионов",
  "why": "Окисление воды до O2 кинетически заторможено; O2 выделяется только из пероксидов или при T > 450 K.",
  "conditions": {
   "no_peroxide": true
  },
  "effect": {
   "forbid_new": [
    "O2",
    "O3"
   ]
  }
 },
 {
  "id": "no_new_ozone",
  "priority": 11,
  "kind": "formation",
  "ea_kj_mol": null,
  "T_ref": null,
  "title": "Озон не образуется",
  "why": "Озон при обычных условиях термодинамически и кинетически не образуется.",
  "conditions": {},
  "effect": {
   "forbid_new": [
    "O3"
   ]
  }
 },
 {
  "id": "no_new_peroxide",
  "priority": 12,
  "kind": "formation",
  "ea_kj_mol": null,
  "T_ref": null,
  "title": "Пероксиды не образуются",
  "why": "Пероксиды метастабильны; при равновесии распадаются.",
  "conditions": {},
  "effect": {
   "forbid_new_class": "peroxide"
  }
 },
 {
  "id": "no_pyrite_lowT",
  "priority": 14,
  "kind": "formation",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Дисульфиды (пирит) не образуются при низкой температуре",
  "why": "FeS2 образуется медленно (геологические времена); в лабораторных условиях из FeS не получается.",
  "conditions": {},
  "effect": {
   "forbid_new_class": "pyrite"
  }
 },
 {
  "id": "no_hydrides_in_water",
  "priority": 16,
  "kind": "formation",
  "ea_kj_mol": null,
  "T_ref": null,
  "title": "Гидриды металлов не образуются в воде",
  "why": "Солеобразные гидриды (NaH, MgH2, CaH2) бурно разлагаются водой.",
  "conditions": {
   "aqueous": true
  },
  "effect": {
   "forbid_new_class": "metal_hydrides"
  }
 },
 {
  "id": "no_new_carbon_lowT",
  "priority": 19,
  "kind": "formation",
  "ea_kj_mol": 193.12,
  "T_ref": 600,
  "title": "Графит не образуется при низкой температуре",
  "why": "Распад органики и CO до углерода при T < 600 K кинетически заторможен.",
  "conditions": {},
  "effect": {
   "forbid_new": [
    "C"
   ]
  }
 },
 {
  "id": "carbon_redox_lowT",
  "priority": 20,
  "kind": "redox",
  "ea_kj_mol": 193.12,
  "T_ref": 600,
  "title": "Углерод(IV) не восстанавливается при низкой температуре",
  "why": "Карбонаты и CO2 при T < 600 K кинетически устойчивы к восстановлению.",
  "conditions": {
   "no_strong_oxidant": true
  },
  "effect": {
   "decouple": {
    "element": "C",
    "groups": [
     [
      4
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "carbon_redox_lowT_oxidant",
  "priority": 21,
  "kind": "redox",
  "ea_kj_mol": 193.12,
  "T_ref": 600,
  "title": "Сильный окислитель окисляет органику и оксалат до CO2",
  "why": "Перманганат, дихромат окисляют оксалат до CO2.",
  "conditions": {
   "strong_oxidant": true
  },
  "effect": {
   "decouple": {
    "element": "C",
    "groups": [
     [
      4,
      3
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "dry_lowT_inert",
  "priority": 22,
  "kind": "inert_reagent",
  "ea_kj_mol": 160.17,
  "T_ref": 500,
  "title": "Твердые неметаллы не горят при низкой температуре",
  "why": "C, S, P, Si в твердом виде при T < 500 K с O2 практически не реагируют (нужно поджечь).",
  "conditions": {},
  "effect": {
   "inert_reagent": {
    "formulas": [
     "C",
     "S",
     "Si"
    ]
   }
  }
 },
 {
  "id": "passivation_conc_acids",
  "priority": 23,
  "kind": "inert_reagent",
  "ea_kj_mol": 107.83,
  "T_ref": 340,
  "title": "Пассивация Fe, Al, Cr в концентрированных HNO3 и H2SO4",
  "why": "На холоду концентрированные кислоты покрывают Fe, Al, Cr оксидной пленкой.",
  "conditions": {
   "passivating_acid": true
  },
  "effect": {
   "inert_reagent": {
    "formulas": [
     "Fe",
     "Al",
     "Cr"
    ]
   }
  }
 },
 {
  "id": "mn_alkaline_stop",
  "priority": 24,
  "kind": "redox",
  "ea_kj_mol": 143.76,
  "T_ref": 450,
  "title": "Марганец в щелочной среде: остановка на манганате (Mn6+)",
  "why": "В щелочной среде MnO4- + e- -> MnO4^2- (зелёный манганат).",
  "conditions": {
   "aqueous": true,
   "alkaline_reagent": true
  },
  "effect": {
   "decouple": {
    "element": "Mn",
    "groups": [
     [
      7,
      6
     ],
     [
      4
     ],
     [
      2,
      3
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "mn_neutral_stop",
  "priority": 25,
  "kind": "redox",
  "ea_kj_mol": 143.76,
  "T_ref": 450,
  "title": "Марганец в нейтральной среде: остановка на MnO2 (Mn4+)",
  "why": "В нейтральной среде MnO4- + 2 H2O + 3 e- -> MnO2 + 4 OH-.",
  "conditions": {
   "aqueous": true,
   "no_acid": true,
   "no_alkaline": true
  },
  "effect": {
   "decouple": {
    "element": "Mn",
    "groups": [
     [
      7,
      6,
      4
     ],
     [
      2,
      3
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "phosphorus_iii_stable",
  "priority": 26,
  "kind": "formation",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Фосфор(III) не диспропорционирует в воде",
  "why": "H3PO3 (фосфористая кислота) кинетически устойчива.",
  "conditions": {
   "aqueous": true
  },
  "effect": {
   "forbid_new": [
    "H3P",
    "PH3",
    "P2H4"
   ]
  }
 },
 {
  "id": "carbide_hydrolysis_acetylene",
  "priority": 27,
  "kind": "formation",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Гидролиз карбида кальция даёт ацетилен",
  "why": "CaC2 + 2 H2O -> Ca(OH)2 + C2H2. Термодинамически выгоднее CH4 и карбонат, но связь C≡C в ацетилене кинетически не разрывается в воде.",
  "conditions": {
   "aqueous": true,
   "reagent_class": "alkaline_earth_carbide"
  },
  "effect": {
   "forbid_new_class": [
    "alkane",
    "alkene"
   ]
  }
 },
 {
  "id": "carbide_hydrolysis_methane",
  "priority": 28,
  "kind": "formation",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Гидролиз карбида алюминия даёт метан",
  "why": "Al4C3 + 12 H2O -> 4 Al(OH)3 + 3 CH4.",
  "conditions": {
   "aqueous": true,
   "reagent_present": "Al4C3"
  },
  "effect": {
   "forbid_new_class": "alkyne"
  }
 },
 {
  "id": "fe3_no_redox_without_reducer",
  "priority": 29,
  "kind": "ligand",
  "ea_kj_mol": null,
  "T_ref": null,
  "title": "Fe3+ не окисляет SCN- без явного восстановителя",
  "why": "Железо(III) не восстанавливается тиоцианатом в отсутствие активного металла.",
  "conditions": {
   "reagent_present": "KSCN",
   "no_strong_reducer": true
  },
  "effect": {
   "forbid_new": [
    "Fe+2",
    "Fe(OH)2",
    "FeO",
    "S",
    "SO4-2",
    "SO3-2"
   ]
  }
 },
 {
  "id": "dry_manganese_redox",
  "priority": 31,
  "kind": "redox",
  "ea_kj_mol": 326.11,
  "T_ref": 1000,
  "title": "Марганец при сухом нагреве не восстанавливается до Mn3+",
  "why": "Термическое разложение перманганатов и оксидов марганца идет до Mn(VI) (манганат) или Mn(IV) (MnO2). Прямое восстановление до Mn(III) (Mn2O3) кинетически заторможено.",
  "conditions": {
   "aqueous": false
  },
  "effect": {
   "decouple": {
    "element": "Mn",
    "groups": [
     [
      7,
      6,
      4
     ],
     [
      2
     ],
     [
      "others"
     ]
    ]
   }
  }
 },
 {
  "id": "thiocyanate_inert",
  "priority": 32,
  "kind": "ligand",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Тиоцианат кинетически инертен",
  "why": "Связь C-S в тиоцианате прочная. Без сильных окислителей или высоких температур он не разлагается.",
  "conditions": {
   "reagent_class": "thiocyanate",
   "aqueous": true
  },
  "effect": {
   "forbid_new": [
    "CO",
    "CO2",
    "S",
    "SO2",
    "SO3",
    "H2S",
    "CS2"
   ],
   "forbid_new_class": "sulfate"
  }
 },
 {
  "id": "cyanide_complexes_stable",
  "priority": 33,
  "kind": "ligand",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Прочные цианидные комплексы не разрушаются в воде",
  "why": "Гексацианоферраты (K3[Fe(CN)6], K4[Fe(CN)6]) кинетически инертны. Разрыв связи C-N требует жестких условий (кипячение с конц. кислотами).",
  "conditions": {
   "aqueous": true,
   "reagent_class": "cyanide_complex"
  },
  "effect": {
   "forbid_new": [
    "NH3",
    "HCN",
    "CN-",
    "C2O4-2",
    "CO2",
    "CO"
   ],
   "forbid_new_class": "free_cyanide"
  }
 },
 {
  "id": "ferricyanide_stable",
  "priority": 34,
  "kind": "ligand",
  "ea_kj_mol": 127.39,
  "T_ref": 400,
  "title": "Гексацианоферрат(III) не восстанавливается без восстановителя",
  "why": "В щелочной среде K3[Fe(CN)6] устойчив, так как цианидные лиганды прочно удерживают железо в степени окисления +3.",
  "conditions": {
   "aqueous": true,
   "no_strong_reducer": true,
   "reagent_class": "cyanide_complex"
  },
  "effect": {
   "forbid_new": [
    "Fe(CN)6-4",
    "K4Fe(CN)6",
    "K4(Fe(CN)6)"
   ]
  }
 },
 {
  "id": "thiosulfate_iodine_titration",
  "priority": 35,
  "kind": "formation",
  "ea_kj_mol": null,
  "T_ref": null,
  "title": "Йодометрия тиосульфата",
  "why": "Йод окисляет тиосульфат только до тетратионата (S4O6-2). Дальнейшее окисление серы (до сульфатов, персульфатов и т.д.) кинетически заторможено.",
  "conditions": {
   "reagents_present": [
    "Na2S2O3",
    "I2"
   ]
  },
  "effect": {
   "forbid_new": [
    "SO4-2",
    "SO2",
    "HSO3-",
    "SO3-2",
    "NaHSO3",
    "Na2SO4",
    "HSO4-",
    "H2SO3",
    "S",
    "S2O8-2",
    "Na2S2O8",
    "S2O6-2",
    "Na2S2O6"
   ]
  }
 }
]
''')

# complex, центральный ион, лиганд, n, lg beta_n (25 C), sigma, источник
# Справочные значения (Лурье 1989; NIST SRD 46). Разброс между источниками в sigma.
COMPLEXES = [
    ("FeSCN+2", "Fe+3", "SCN-", 1, 3.03, 0.9, "Lurie1989"),
    ("Fe(CN)6-3", "Fe+3", "CN-", 6, 42.0, 1.5, "Lurie1989"),
    ("Fe(CN)6-4", "Fe+2", "CN-", 6, 35.0, 1.5, "Lurie1989"),
    ("Cu(NH3)4+2", "Cu+2", "NH3", 4, 13.0, 0.4, "Lurie1989"),
    ("Ag(NH3)2+", "Ag+", "NH3", 2, 7.23, 0.1, "Lurie1989"),
    ("Zn(NH3)4+2", "Zn+2", "NH3", 4, 9.0, 0.4, "Lurie1989"),
    ("Ni(NH3)6+2", "Ni+2", "NH3", 6, 8.5, 0.3, "Lurie1989"),
    ("Co(NH3)6+3", "Co+3", "NH3", 6, 35.2, 0.5, "Lurie1989"),
    ("Ag(CN)2-", "Ag+", "CN-", 2, 20.9, 0.4, "Lurie1989"),
    ("Cu(CN)4-3", "Cu+", "CN-", 4, 30.3, 1.0, "Lurie1989"),
    ("Ag(S2O3)2-3", "Ag+", "S2O3-2", 2, 13.46, 0.2, "Lurie1989"),
    ("AgCl2-", "Ag+", "Cl-", 2, 5.25, 0.2, "Lurie1989"),
    ("HgI4-2", "Hg+2", "I-", 4, 29.8, 0.5, "Lurie1989"),
    ("Zn(OH)4-2", "Zn+2", "OH-", 4, 15.5, 1.0, "Lurie1989"),
    ("Al(OH)4-", "Al+3", "OH-", 4, 33.0, 0.7, "Lurie1989"),
    ("Fe(C2O4)3-3", "Fe+3", "C2O4-2", 3, 20.2, 1.0, "Lurie1989"),
]


def main():
    if not DB_PATH.exists():
        print(f"База не найдена: {DB_PATH}")
        return
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(kinetic_barriers)")}
    for col, typ in (("kind", "TEXT"), ("priority", "INTEGER"), ("title", "TEXT"), ("why", "TEXT"),
                     ("conditions", "TEXT"), ("effect", "TEXT"), ("T_ref", "REAL")):
        if col not in cols:
            cur.execute(f"ALTER TABLE kinetic_barriers ADD COLUMN {col} {typ}")
    for r in KINETIC_RULES:
        vals = (r["ea_kj_mol"], SOURCE, r["kind"], r["priority"], r["title"], r["why"],
                json.dumps(r["conditions"], ensure_ascii=False), json.dumps(r["effect"], ensure_ascii=False),
                r["T_ref"])
        if cur.execute("SELECT 1 FROM kinetic_barriers WHERE reaction_key = ?", (r["id"],)).fetchone():
            cur.execute("UPDATE kinetic_barriers SET ea_kj_mol=?, source=?, kind=?, priority=?, title=?, why=?, "
                        "conditions=?, effect=?, T_ref=? WHERE reaction_key=?", (*vals, r["id"]))
        else:
            cur.execute("INSERT INTO kinetic_barriers (ea_kj_mol, source, kind, priority, title, why, conditions, "
                        "effect, T_ref, reaction_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*vals, r["id"]))
    print(f"kinetic_barriers: {len(KINETIC_RULES)} правил")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS complex_constants (
            complex TEXT PRIMARY KEY,
            metal TEXT,
            ligand TEXT,
            n INTEGER,
            log_beta REAL,
            sigma REAL,
            T_K REAL DEFAULT 298.15,
            source TEXT
        )""")
    cur.executemany("INSERT OR REPLACE INTO complex_constants (complex, metal, ligand, n, log_beta, sigma, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)", COMPLEXES)
    print(f"complex_constants: {len(COMPLEXES)} комплексов")
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
