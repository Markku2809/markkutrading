const {test}=require('node:test');
const assert=require('node:assert/strict');
const {prepare}=require('../../kronikka/web-state.js');
const now=Date.parse('2026-09-28T09:00:00Z');
function sample(){return {schema_version:1,collected_at:new Date(now).toISOString(),valid_until:new Date(now+900000).toISOString(),quotes:[{symbol:'ES=F',at:new Date(now).toISOString()}],events:[],alerts:[],analysis:{direction:'up',title:'NOUSUPAINOTTEINEN',reasons:[],metrics:{last:6000},chart:[{ts:now/1000-300}]}};}
test('fresh snapshot retains direction and leaves original unchanged',()=>{const s=sample();assert.equal(prepare(s,now).analysis.direction,'up');assert.equal(s.now,undefined);});
test('open tab expires even without another network response',()=>{const s=prepare(sample(),now+901000);assert.equal(s.analysis.direction,'stale');assert.deepEqual(s.analysis.metrics,{});});
test('old quote invalidates a newly published view',()=>{const s=sample();s.quotes[0].at=new Date(now-1201000).toISOString();assert.equal(prepare(s,now).analysis.direction,'stale');});
test('old candles invalidate a newly published view',()=>{const s=sample();s.analysis.chart[0].ts-=1201;assert.equal(prepare(s,now).analysis.direction,'stale');});
test('future timestamp cannot activate a signal',()=>{const s=sample();s.collected_at=new Date(now+120000).toISOString();assert.equal(prepare(s,now).analysis.direction,'stale');});
test('scheduled economic release becomes caution between snapshots',()=>{const s=sample();s.events=[{impact:'High',at:new Date(now+1200000).toISOString(),title:'CPI',title_fi:'Inflaatio'}];assert.equal(prepare(s,now).analysis.direction,'up');assert.equal(prepare(s,now+360000).analysis.direction,'caution');});
test('caution cannot revive an expired snapshot',()=>{const s=sample();s.events=[{impact:'High',at:new Date(now+1200000).toISOString(),title:'CPI'}];assert.equal(prepare(s,now+901000).analysis.direction,'stale');});
test('missing timestamp is rejected',()=>{const s=sample();delete s.valid_until;assert.throws(()=>prepare(s,now));});
