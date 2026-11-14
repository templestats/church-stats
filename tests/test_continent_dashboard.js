const assert = require('node:assert/strict');
const ui = require('../dashboard.js');
const rows = [
  {date:'2026-11-10',type:'country',name:'Ghana',country:'Ghana',continent:'Africa',
    members:100,annualized_endowments:50,rate:0.5},
  {date:'2026-11-10',type:'country',name:'Nigeria',country:'Nigeria',continent:'Africa',
    members:300,annualized_endowments:0,rate:0},
  {date:'2026-11-10',type:'country',name:'Kenya',country:'Kenya',continent:'Africa',
    members:200,annualized_endowments:0,rate:0},
  {date:'2026-11-10',type:'state',name:'Utah',country:'United States',continent:'North America',
    members:1000,annualized_endowments:700,rate:0.7}
];
ui.state.rows = rows;
ui.state.selectedContinents = new Set(['Africa']);
const keys = ui.selectedKeys();
assert.deepEqual(new Set(keys),new Set(['country|Ghana','country|Nigeria','country|Kenya']));
let series = ui.makeAggregateSeries(rows,keys);
assert.equal(series.length,1);
assert.equal(series[0].members,600);
assert.equal(series[0].annualizedSessions,50);
assert.equal(series[0].rate,50/600);
ui.state.excludedCountries.add('Nigeria');
series = ui.makeAggregateSeries(rows,ui.selectedKeys());
assert.equal(series[0].members,300);
assert.equal(series[0].rate,50/300);
ui.state.references.worldwide=[{date:'2026-11-10',members:12000,annualizedSessions:750,rate:750/12000}];
ui.state.references.usa=[{date:'2026-11-10',members:4000,annualizedSessions:700,rate:700/4000}];
assert.equal(ui.makeReferenceSeries('worldwide')[0].members,12000);
assert.equal(ui.makeReferenceSeries('usa')[0].members,4000);
assert.equal(ui.formatInteger(12345.683),'12,346');
console.log('Browser continent aggregation and full-population references: OK');
