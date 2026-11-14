const assert=require('node:assert/strict');const {attendanceTotals}=require('./dist/attendance.js');
const a={people:[{id:'a',name:'Ana'},{id:'b',name:'Bia'}],minutes:[
 {date:'2025-01-02',kind:'Plenário ordinário',rows:[{personId:'a',status:'Presente'},{personId:'b',status:'Licença'}]},
 {date:'2025-01-03',kind:'Plenário ordinário',rows:[{personId:'a',status:'Ausência justificada'},{personId:'b',status:'Afastamento'}]},
 {date:'2025-01-04',kind:'Plenário ordinário',rows:[{personId:'a',status:'Revisão necessária'}]},
 {date:'2025-01-05',kind:'Plenário ordinário',duplicateMeeting:true,rows:[{personId:'a',status:'Ausência citada sem classificação'}]},
 {date:'2025-01-03',kind:'Plenário extraordinário',rows:[{personId:'a',status:'Ausência citada sem classificação'}]},
 {date:'2024-12-03',kind:'Plenário ordinário',rows:[{personId:'a',status:'Ausência citada sem classificação'}]}
]};let r=attendanceTotals(a,'2025-01-01','2025-12-31','Plenário ordinário');assert.equal(r.totals[0].absences,1);assert.equal(r.totals[0].denominator,2);assert.equal(r.totals[0].rate,50);assert.equal(r.totals[0].conflict,1);assert.equal(r.totals[1].rate,null);assert.equal(r.totals[1].license,1);assert.equal(r.totals[1].leave,1);console.log('Contagens, percentuais, licenças, afastamentos, contradições e duplicidade: OK');
