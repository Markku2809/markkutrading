'use strict';
const $=id=>document.getElementById(id);
const format=new Intl.NumberFormat('fi-FI',{minimumFractionDigits:2,maximumFractionDigits:2});
const dateFmt=new Intl.DateTimeFormat('fi-FI',{timeZone:'Europe/Helsinki',day:'numeric',month:'numeric',hour:'2-digit',minute:'2-digit'});
const date=x=>x?dateFmt.format(new Date(x)):'ei aikaleimaa';
const num=x=>Number.isFinite(x)?format.format(x):'—';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const link=(url,title,cls='')=>`<a class="${cls}" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(title)} ↗</a>`;
let token='', state=null, seen=new Set(), initial=true, sound=false, audioCtx=null, busy=false, chartKey='';
const rendered=new Map();
function content(id,html){if(rendered.get(id)!==html){$(id).innerHTML=html;rendered.set(id,html);}}
let webSnapshot=null, webWatch=true, webError=false;
function playAlert(){
 if(!sound||!audioCtx)return;
 const osc=audioCtx.createOscillator(),gain=audioCtx.createGain();osc.connect(gain);gain.connect(audioCtx.destination);
 osc.type='sine';osc.frequency.value=660;gain.gain.setValueAtTime(.06,audioCtx.currentTime);gain.gain.exponentialRampToValueAtTime(.001,audioCtx.currentTime+.65);osc.start();osc.stop(audioCtx.currentTime+.7);
}
function renderChart(bars){
 const key=JSON.stringify(bars);if(key===chartKey)return;chartKey=key;
 const svg=$('chart');svg.replaceChildren();$('chartEmpty').hidden=bars.length>1;svg.style.display=bars.length>1?'block':'none';
 if(bars.length<2){$('chartStart').textContent='—';$('chartEnd').textContent='—';return;}
 const values=bars.map(b=>b.close), min=Math.min(...values),max=Math.max(...values),range=max-min||1;
 const point=(b,i)=>[8+(b.ts-bars[0].ts)/(bars.at(-1).ts-bars[0].ts||1)*622,158-(b.close-min)/range*138];
 const add=(tag,attrs,text)=>{const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text)el.textContent=text;svg.append(el);return el;};
 for(let i=0;i<3;i++){const y=20+i*69;add('line',{x1:8,y1:y,x2:635,y2:y,stroke:'#aa916044','stroke-dasharray':'3 6'});add('text',{x:645,y:y+4,fill:'#856b45','font-family':'Georgia','font-size':'12'},num(max-range*i/2));}
 const pts=bars.map(point),path=pts.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ');
 add('path',{d:path+` L630,168 L8,168 Z`,fill:'#7e84551a'});
 add('path',{d:path,fill:'none',stroke:values.at(-1)>=values[0]?'#3e6348':'#8c4432','stroke-width':'2.3','stroke-linejoin':'round'});
 const p=pts.at(-1);add('circle',{cx:p[0],cy:p[1],r:3.5,fill:'#846335'});
 $('chartStart').textContent=date(bars[0].ts*1000);$('chartEnd').textContent=date(bars.at(-1).ts*1000)+' · suljettu M5';
}
function renderNews(){
 if(!state)return;const filter=$('newsFilter').value;
 const items=state.news.filter(n=>!filter||n.source===filter).slice(0,12);
 content('newsList',items.length?items.map(n=>`<article class="news-item ${n.risk?'risk':''}"><span class="topic">${esc(n.topic)}${n.risk?' · Tarkistettava riskiotsikko':''}</span>${link(n.url,n.title)}<span class="meta">${esc(n.source)} · ${date(n.published)}${n.via==='Google News'?' · Google News -välitys':''}</span></article>`).join(''):'<p class="empty">Ei saatavilla olevia otsikoita tästä lähteestä. Tarkista lähteiden tila.</p>');
}
function render(s){
 state=s;const a=s.analysis,m=a.metrics||{},now=new Date(s.now);
 $('today').textContent=new Intl.DateTimeFormat('fi-FI',{timeZone:'Europe/Helsinki',weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(now).toLocaleUpperCase('fi-FI');
 $('outlookTitle').textContent=a.title;document.querySelector('.hero').dataset.direction=a.direction;
 $('confidence').textContent=a.confidence;$('mainReason').textContent=a.reasons[0]||'Tietoa odotetaan.';$('extraReason').textContent=a.reasons.slice(1).join(' ');$('scope').textContent=a.scope;
 const scaleDirection=a.direction==='caution'?'neutral':a.direction;
 document.querySelectorAll('[data-dir]').forEach(el=>el.classList.toggle('active',el.dataset.dir===scaleDirection));
 $('updated').textContent=s.collected_at?'Katsaus haettu '+date(s.collected_at):'Ensimmäinen päivitys käynnissä…';
 $('ticker').innerHTML=['ES=F','NQ=F','^VIX','^N225'].map(symbol=>{const q=s.quotes.find(x=>x.symbol===symbol);if(!q)return '<div class="tick"><span class="tick-label">'+esc(symbol)+'</span><span>—</span><small>Tieto puuttuu</small></div>';return `<div class="tick"><span class="tick-label">${esc(q.label)}</span><span class="tick-price">${num(q.price)}</span><small>${date(q.at)}${q.stale?' · vanha':' · viive mahdollinen'}</small><small class="${q.change>=0?'up':'down'}">${q.change==null?'—':(q.change>0?'+':'')+num(q.change)+' %'}</small></div>`;}).join('');
 const es=s.quotes.find(q=>q.symbol==='ES=F');$('chartContract').textContent=es?.contract||'ES-futuuri';
 renderChart(a.chart);$('activity').textContent=m.activity_label||'Ei ajantasaista arviota';$('pressure').textContent=m.pressure||'Ei ajantasaista arviota';
 $('condition').textContent=a.condition;
 const previous=s.history.find(h=>h.title!==a.title);
 $('changeText').textContent=previous?`Aiempi näkymä: ${previous.title.toLocaleLowerCase('fi-FI')} (${date(previous.at)}). Nyt: ${a.title.toLocaleLowerCase('fi-FI')}.`:'Nykyinen tilanne: '+a.title.toLocaleLowerCase('fi-FI')+'.';
 $('refresh').disabled=busy;$('refresh').textContent='↻  Tarkista uusin katsaus';
 $('refreshStatus').textContent='Uusin julkaistu katsaus tarkistetaan minuutin välein. Painike tarkistaa saman aineiston; uuden katsauksen julkaisu voi viivästyä.';
 $('nextOpen').textContent='Seuraava tavanomainen USA:n osakepörssin avaus '+date(s.next_open)+' Suomen aikaa. Futuurit käyvät kauppaa myös ennen avausta.';
 $('watchToggle').checked=s.watch;
 const failed=s.health.filter(h=>['news','calendar'].includes(h.group)&&!h.ok).length;
 $('watchText').textContent=(s.watch?'Uusien katsausten tarkistus päällä':'Automaattinen tarkistus pois')+(failed?' · lähteitä puuttuu':'')+' · ei reaaliaikainen uutisvahti';
 $('alerts').innerHTML=s.alerts.map(al=>`<div class="alert"><strong>${esc(al.title)}</strong>${link(al.url,al.detail)}<span class="meta">${esc(al.source)} · ${date(al.at)}</span></div>`).join('');
 const newAlerts=s.alerts.filter(al=>!seen.has(al.id));s.alerts.forEach(al=>seen.add(al.id));if(!initial&&s.watch&&newAlerts.length)playAlert();initial=false;
 $('levels').innerHTML=[['Jakson pohja',m.low],['Jakson huippu',m.high],['Volyymipainotettu keskihinta',m.vwap],['Laskevien kynttilöiden volyymi',m.selling]].map(([label,value],i)=>`<div class="level"><small>${label}</small><strong>${num(value)}${i===3&&value!=null?' %':''}</strong></div>`).join('');
 $('igContext').textContent=s.ig?.price?`${s.ig.label}: ${num(s.ig.price)} · ${date(s.ig.at)} · ${s.ig.fresh?'tuore suljettu kynttilä':'vanha tieto'}. ${s.ig.note}`:(s.ig?.note||'IG-scannerin aineistoa odotetaan.');
 for(const[k,id]of [['morning','morningReport'],['premarket','premarketReport']]){const r=s.reports[k];$(id).textContent=r?r.title+' · '+date(r.at)+'. '+r.reason:(k==='morning'?'Tallentuu päivän ensimmäisestä kelvollisesta arviosta klo 5–12 Suomen aikaa.':'Viimeisin kelvollinen ennen avausta tehty arvio säilyy tässä päivän vertailuna.');}
 $('analystCards').innerHTML=s.analysts.length?s.analysts.map(person=>`<article class="analyst"><h4>${esc(person.name)}</h4><span class="role">${esc(person.role)}</span>${!person.fetch_ok?'<p class="no-news">Lähdehaku ei onnistunut.</p>':''}<ul>${person.items.map(n=>`<li>${link(n.url,n.title)}<span class="meta">${esc(n.source)} · ${date(n.published)} · ${n.today?'julkaistu tänään':'aiempi julkaisu'}</span></li>`).join('')}</ul>${!person.items.length?'<p class="no-news">Ei uutta julkista näkemystä saatavilla. Suuntaa ei arvata.</p>':''}<p class="fine">${esc(person.note)}</p>${link(person.url,'Avaa alkuperäinen julkaisukanava','text-link')}</article>`).join(''):'<p class="empty">Haetaan julkisia mainintoja…</p>';
 renderNews();
 $('eventsList').innerHTML=s.events.length?s.events.slice(0,20).map(e=>`<article class="event ${new Date(e.at)<now?'past':''}"><time>${date(e.at)}</time><div><div class="event-name">${esc(e.title_fi)}</div><span class="impact ${e.impact.toLowerCase()}">${({High:'Suuri vaikutus',Medium:'Kohtalainen vaikutus',Low:'Pieni vaikutus','Non-Economic':'Muu tapahtuma'})[e.impact]||'Vaikutus ei tiedossa'}</span>${e.forecast||e.previous?`<span class="meta">Ennuste ${esc(e.forecast||'—')} · Edellinen ${esc(e.previous||'—')}</span>`:''}<span class="meta">${new Date(e.at)<now?'Julkaisuaika ohitettu · toteumaa ei tässä syötteessä':''}</span></div></article>`).join(''):'<p class="empty">Ei tapahtumia saatavilla valitulla aikavälillä. Tämä ei takaa uutisriskitöntä päivää; tarkista lähteen kalenteri.</p>';
 $('sourceHealth').innerHTML=s.health.map(h=>`<div class="health"><strong>${esc(h.name)}</strong><br><span class="${h.ok?'ok':'failed'}">${h.ok?'Haku onnistui':esc(h.error)}</span><span class="meta">${date(h.fetched)}${h.cached?' · välimuisti':''}</span></div>`).join('');
 $('history').innerHTML=s.history.map(h=>`<div class="history-row"><time>${date(h.at)}</time><strong>${esc(h.title)}</strong> · ${esc(h.reason)}</div>`).join('')||'<p class="fine">Ei vielä tallennettuja muutoksia.</p>';
}
function showSnapshot(){
 if(!webSnapshot)return;
 const s=KronikkaWeb.prepare(webSnapshot,Date.now());s.watch=webWatch;
 render(s);
 const age=Math.max(0,Math.floor((Date.now()-Date.parse(s.collected_at))/60000));
 $('updated').textContent='Katsaus '+date(s.collected_at)+' · ikä '+age+' min';
 $('dataNote').textContent='Julkinen verkkokatsaus · hinnat voivat olla viivästettyjä';
 if(s.analysis.direction==='stale'){
  $('refreshStatus').textContent='Julkaisun tai hintalähteen päivitys on viivästynyt. Viimeisin katsaus: '+date(s.collected_at)+'. Uutta julkaisua tarkistetaan'+(webWatch?' automaattisesti minuutin välein.':' päivityspainikkeesta.');
 }
 if(webError){
  $('refreshStatus').textContent='Uusinta katsausta ei voitu hakea. Näytetään aiempi aineisto aikaleimoineen.';
  document.querySelector('.hero').dataset.direction='stale';
  $('outlookTitle').textContent='YHTEYS KATKENNUT';
  $('confidence').textContent='Aiempi arvio ei ole voimassa';
  $('mainReason').textContent='Verkkopäivitystä ei voitu tarkistaa. Yritä uudelleen.';
  document.querySelectorAll('[data-dir]').forEach(el=>el.classList.remove('active'));
 }
}
async function poll(){
 if(busy)return;busy=true;$('refresh').disabled=true;
 try{
  const r=await fetch('./data/state.json?t='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(15000)});
  if(!r.ok)throw Error();
  const candidate=await r.json();KronikkaWeb.prepare(candidate,Date.now());
  webSnapshot=candidate;webError=false;showSnapshot();
 }catch(e){
  webError=true;
  if(webSnapshot)showSnapshot();
  else{
   $('outlookTitle').textContent='KATSAUSTA EI SAATAVILLA';
   document.querySelector('.hero').dataset.direction='unknown';
   $('confidence').textContent='Ei ajantasaista arviota';
   $('mainReason').textContent='Julkaistua katsausta ei saatu. Kokeile hetken kuluttua uudelleen.';
   $('updated').textContent='Päivitysaika ei saatavilla';
   $('refreshStatus').textContent='Verkkokatsauksen lataus epäonnistui.';
  }
 }finally{busy=false;$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',poll);
$('watchToggle').addEventListener('change',e=>{webWatch=e.target.checked;showSnapshot();if(webWatch)poll();});
$('soundToggle').addEventListener('change',e=>{sound=e.target.checked;if(sound){audioCtx??=new (window.AudioContext||window.webkitAudioContext)();audioCtx.resume();}});
$('newsFilter').addEventListener('change',renderNews);
poll();setInterval(()=>{if(webWatch)poll();},60000);
setInterval(showSnapshot,15000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden){showSnapshot();if(webWatch)poll();}});
