const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

test('timed-out request releases the button and allows another refresh',async()=>{
 const elements=new Map(),listeners=new Map();
 const get=id=>{
  if(!elements.has(id))elements.set(id,{dataset:{},addEventListener:(event,fn)=>listeners.set(id+event,fn)});
  return elements.get(id);
 };
 const signal={aborted:true};let requests=0;
 const context=vm.createContext({Intl,Date,Set,Map,console,
  document:{getElementById:get,querySelector:()=>get('hero'),addEventListener:()=>{}},
  setInterval:()=>{},AbortSignal:{timeout:ms=>{assert.equal(ms,15000);return signal;}},
  fetch:async(url,options)=>{
   requests++;assert.equal(options.signal,signal);assert.equal(options.cache,'no-store');
   throw Object.assign(new Error('timeout'),{name:'TimeoutError'});
  }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../../kronikka/ui.js'),'utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(get('refresh').disabled,false);
 assert.equal(get('outlookTitle').textContent,'KATSAUSTA EI SAATAVILLA');
 await listeners.get('refreshclick')();
 assert.equal(requests,2);
 assert.equal(get('refresh').disabled,false);
});
