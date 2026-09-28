'use strict';
// Recheck timestamps in every browser, including a tab left open overnight.
const KronikkaWeb={prepare(snapshot,nowMs){
 if(snapshot?.schema_version!==1||!snapshot.analysis||!Array.isArray(snapshot.quotes)||!Array.isArray(snapshot.events))throw Error('Invalid snapshot');
 const s=JSON.parse(JSON.stringify(snapshot)),a=s.analysis;
 const collected=Date.parse(s.collected_at),until=Date.parse(s.valid_until);
 if(!Number.isFinite(collected)||!Number.isFinite(until))throw Error('Missing timestamp');
 s.now=new Date(nowMs).toISOString();
 s.quotes.forEach(q=>{const age=nowMs-Date.parse(q.at);q.stale=!Number.isFinite(age)||age>1200000||age< -60000;});
 const quote=s.quotes.find(q=>q.symbol==='ES=F');
 const bars=a.chart||[],last=bars.at(-1);
 const stale=collected>nowMs+60000||nowMs>Math.min(until,collected+900000)||
  (['up','down','neutral','caution'].includes(a.direction)&&(!quote||quote.stale||!last||nowMs>(last.ts+300)*1000+1200000));
 if(stale){
  Object.assign(a,{title:'KATSAUS VANHENTUNUT',direction:'stale',confidence:'Aiempi arvio ei ole voimassa',
   reasons:['Verkkokatsaus tai sen hintatieto on vanhentunut. Odota seuraavaa onnistunutta päivitystä.'],
   condition:'Uusi suunta-arvio näytetään vasta tuoreen katsauksen saavuttua.',metrics:{}});
 }
 // A scheduled release may enter its caution window between publications.
 const near=s.events.filter(e=>e.impact==='High'&&Date.parse(e.at)-nowMs<=900000&&Date.parse(e.at)-nowMs>=-600000);
 for(const e of near){
  const id='event-'+e.at+e.title;
  if(!s.alerts.some(x=>x.id===id))s.alerts.push({id,kind:'event',title:'Merkittävä talousjulkaisu lähellä',detail:e.title_fi,at:e.at,url:e.url,source:'Forex Factory'});
 }
 if(near.length&&['up','down','neutral'].includes(a.direction)){
  Object.assign(a,{title:'TILANNE EPÄVARMA',direction:'caution',confidence:'Talousjulkaisu lähellä'});
  a.reasons.unshift('Merkittävän talousjulkaisun varoaika on alkanut. Aiempi suuntanäkymä on keskeytetty.');
 }
 return s;
}};
if(typeof module!=='undefined')module.exports=KronikkaWeb;
