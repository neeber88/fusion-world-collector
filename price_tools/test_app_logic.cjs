const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let js=fs.readFileSync(__dirname+'/../app.js','utf8');
const before="window.addEventListener('DOMContentLoaded',";
const tests=String.raw`
state={...DEFAULT,ownedIds:['FS01-01#BASE','FS01-16#ALT-1'],quantities:{'FS01-01#BASE':3,'FS01-16#ALT-1':2},prices:{},marketPrices:{},purchases:[],favorites:[]};
cards=[{id:'FS01-01#BASE',variant:'NORMAL'},{id:'FS01-16#ALT-1',variant:'ALT'}];
cardById=new Map(cards.map(x=>[x.id,x]));
const fixture={kind:'fusion-world-market-prices',schema_version:1,updated_at:'2026-10-16',prices:{'FS01-01#BASE':{amount:0.13},'FS01-16#ALT-1':{amount:42.17},'BOGUS':{amount:99}}};
const got=normalizePriceFeed(fixture);if(Object.keys(got.incoming).length!==2||got.unknown.length!==1)throw Error('Price feed parsing failed');
state.marketPrices=got.incoming;
let t=valueTotals();
if(Math.abs(t.single-42.30)>0.00001||Math.abs(t.duplicates-42.43)>0.00001||Math.abs(t.total-84.73)>0.00001)throw Error('All-copies valuation failed '+JSON.stringify(t));
if(t.totalCopies!==5||t.duplicateCopies!==3||t.normalCopies!==3||t.altCopies!==2||t.pricedCopies!==5)throw Error('Copy counters incorrect '+JSON.stringify(t));
if(Math.abs(t.normalAll-0.39)>0.00001||Math.abs(t.altAll-84.34)>0.00001)throw Error('All-copies breakdown incorrect '+JSON.stringify(t));
state.prices['FS01-01#BASE']={amount:1.00,date:'2026-10-16',source:'Manuell'};
t=valueTotals();if(Math.abs(t.total-87.34)>0.00001)throw Error('Manual override failed '+JSON.stringify(t));
// An owned item without a price must count as a physical card but not add an invented dollar value.
state.ownedIds.push('FS01-03#BASE');state.quantities['FS01-03#BASE']=4;cards.push({id:'FS01-03#BASE',variant:'NORMAL'});
t=valueTotals();if(t.totalCopies!==9||t.unpricedCopies!==4||t.count!==3||t.pricedCopies!==5||Math.abs(t.total-87.34)>0.00001)throw Error('Unpriced copies must be excluded from total USD but counted physically '+JSON.stringify(t));
const legacy=normalizeExtras({prices:{'FS01-01#BASE':{amount:1}}});if(Object.keys(legacy.marketPrices).length!==0||legacy.prices['FS01-01#BASE'].amount!==1)throw Error('Legacy backup failed');
console.log('PASS: matching, Normal/ALT, all physical copies, duplicates, missing prices, manual overrides, legacy backups');
`;
if(!js.includes(before))throw Error('init anchor missing');
js=js.replace(before,tests+'\n'+before);
vm.runInNewContext(js,{window:{addEventListener:()=>{}},document:{addEventListener:()=>{}},console,URL,Intl,Date,Number,Math,String,Map,Set,Array,Object,JSON,crypto:{},setTimeout,clearTimeout});