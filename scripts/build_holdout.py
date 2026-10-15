
import json

from pathlib import Path

REACTIONS = [
    {'id':'h001','category':'нейтрализация','reagents':[{'formula':'NaOH','moles':0.1,'phase':'aq'},{'formula':'HCl','moles':0.1,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'NaCl','in_scope':True,'note':'1:1, сильная+сильное'},
    {'id':'h002','category':'нейтрализация','reagents':[{'formula':'NaOH','moles':0.2,'phase':'aq'},{'formula':'H2SO4','moles':0.1,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'Na2SO4','in_scope':True,'note':'2:1, средняя соль'},
    {'id':'h003','category':'нейтрализация','reagents':[{'formula':'NaOH','moles':0.1,'phase':'aq'},{'formula':'H2SO4','moles':0.1,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'NaHSO4','in_scope':True,'note':'1:1, кислая соль'},
    {'id':'h004','category':'нейтрализация','reagents':[{'formula':'KOH','moles':0.1,'phase':'aq'},{'formula':'HNO3','moles':0.1,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'KNO3','in_scope':True,'note':'1:1'},
    {'id':'h005','category':'нейтрализация','reagents':[{'formula':'Ba(OH)2','moles':0.05,'phase':'aq'},{'formula':'H2SO4','moles':0.05,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'BaSO4','in_scope':True,'note':'нейтрализация + осадок'},
    {'id':'h006','category':'нейтрализация','reagents':[{'formula':'Ca(OH)2','moles':0.05,'phase':'aq'},{'formula':'HCl','moles':0.1,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'CaCl2','in_scope':True,'note':'двухосновное основание'},
    {'id':'h007','category':'нейтрализация','reagents':[{'formula':'NH3','moles':0.1,'phase':'aq'},{'formula':'HCl','moles':0.1,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'NH4Cl','in_scope':True,'note':'слабое+сильная'},
    {'id':'h008','category':'нейтрализация','reagents':[{'formula':'CH3COOH','moles':0.1,'phase':'aq'},{'formula':'NaOH','moles':0.1,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'CH3COONa','in_scope':True,'note':'слабая+сильное'},
    {'id':'h009','category':'нейтрализация','reagents':[{'formula':'H3PO4','moles':0.1,'phase':'aq'},{'formula':'NaOH','moles':0.1,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'NaH2PO4','in_scope':True,'note':'1:1, дигидрофосфат'},
    {'id':'h010','category':'нейтрализация','reagents':[{'formula':'H3PO4','moles':0.1,'phase':'aq'},{'formula':'NaOH','moles':0.3,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'Na3PO4','in_scope':True,'note':'3:1, средний фосфат'},
    {'id':'h011','category':'осаждение','reagents':[{'formula':'AgNO3','moles':0.01,'phase':'aq'},{'formula':'NaCl','moles':0.01,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'AgCl','in_scope':True,'note':'белый осадок'},
    {'id':'h012','category':'осаждение','reagents':[{'formula':'BaCl2','moles':0.02,'phase':'aq'},{'formula':'Na2SO4','moles':0.02,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'BaSO4','in_scope':True,'note':'Ksp 1e-10'},
    {'id':'h013','category':'осаждение','reagents':[{'formula':'Pb(NO3)2','moles':0.01,'phase':'aq'},{'formula':'KI','moles':0.02,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'PbI2','in_scope':True,'note':'жёлтый осадок 1:2'},
    {'id':'h014','category':'осаждение','reagents':[{'formula':'AgNO3','moles':0.01,'phase':'aq'},{'formula':'KI','moles':0.01,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'AgI','in_scope':True,'note':'Ksp 8e-17'},
    {'id':'h015','category':'осаждение','reagents':[{'formula':'CaCl2','moles':0.01,'phase':'aq'},{'formula':'Na2CO3','moles':0.01,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'CaCO3','in_scope':True,'note':'Ksp 3e-9'},
    {'id':'h016','category':'осаждение','reagents':[{'formula':'CuSO4','moles':0.01,'phase':'aq'},{'formula':'Na2S','moles':0.01,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'CuS','in_scope':True,'note':'Ksp 6e-37'},
    {'id':'h017','category':'осаждение','reagents':[{'formula':'FeCl3','moles':0.01,'phase':'aq'},{'formula':'NaOH','moles':0.03,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'Fe(OH)3','in_scope':True,'note':'бурый осадок 1:3'},
    {'id':'h018','category':'осаждение','reagents':[{'formula':'MgCl2','moles':0.01,'phase':'aq'},{'formula':'NaOH','moles':0.02,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'Mg(OH)2','in_scope':True,'note':'Ksp 5e-12'},
    {'id':'h019','category':'осаждение','reagents':[{'formula':'Na2CO3','moles':0.01,'phase':'aq'},{'formula':'HCl','moles':0.02,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'NaCl','in_scope':True,'note':'с газом, не осаждение'},
    {'id':'h020','category':'осаждение','reagents':[{'formula':'AlCl3','moles':0.01,'phase':'aq'},{'formula':'NaOH','moles':0.03,'phase':'aq'}],'temperature_K':298.15,'volume_L':1.0,'solvent':'water','expected_main':'Al(OH)3','in_scope':True,'note':'амфотерный, точная стех.'},
]


def main():
    out = Path(__file__).parent.parent / 'tests' / 'fixtures' / 'holdout_100.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(REACTIONS, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(REACTIONS)} reactions to {out}')


if __name__ == '__main__':
    main()
