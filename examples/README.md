# Примеры

| Файл | Что показывает |
|---|---|
| neutralization.json | Полная схема входа из ТЗ: NaOH + H2SO4, ручные энергии, атмосфера, профиль температуры |
| redox.json | KMnO4 + FeSO4 + H2SO4: окислительно-восстановительная реакция в кислой среде |
| precipitation.json | AgNO3 + NaCl: осаждение AgCl |
| complexation.json | CuSO4 + избыток NH3: аммиачный комплекс меди |
| decomposition.json | CaCO3 при 900-1300 K без растворителя: разложение до CaO и CO2 |
| catalysis.json | Синтез NH3 при 700 K и 200 атм: катализатор меняет только скорость (барьер задан) |
| atmosphere_effect.json | Fe(OH)2 на воздухе окисляется до Fe(OH)3 |
| temperature_ramp.json | NH4Cl + NaOH при нагреве 20-90 °C |
| custom_energies.json | Ручное значение dGf(BaSO4) с высшим приоритетом |

Запуск: `run_cli.bat predict --input examples\redox.json --output html --open`

Готовые отчеты лежат в `examples\reports\`.
