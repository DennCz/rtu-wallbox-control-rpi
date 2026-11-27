'use strict';
// Hardware- und browserfreier Test der Sprachwahl (nur Node.js-Bordmittel).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname,'..');
const catalog = fs.readFileSync(path.join(root,'static/i18n.js'),'utf8');
const app = fs.readFileSync(path.join(root,'static/wallbox.js'),'utf8');
const textKeys = new Set([...catalog.matchAll(/^    '([^']+)':\[/gm)].map(m=>m[1]));
// Jede dynamisch verwendete Übersetzung besitzt einen Katalogeintrag.
for(const match of app.matchAll(/\bt\('([^']+)'/g))assert(textKeys.has(match[1].trim()),match[1]);
function makeBrowser(language, saved) {
  const textNodes = [{nodeValue:'  Einstellungen '},{nodeValue:'Ladevorgang starten'},{nodeValue:'Monatssummen · abgeschlossene Ladungen · Fiktive Beispieldaten'}];
  const attrs={'aria-label':'Person auswählen',alt:'Wallbox ohne Fahrzeug',placeholder:'26,00'};
  const element={getAttribute:k=>attrs[k]||null,setAttribute:(k,v)=>{attrs[k]=v;}};
  const select={value:null},store=new Map();
  if(saved)store.set('wallbox.language',saved);
  const state={URL,Intl,Date,localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},
    location:{href:`http://127.0.0.1:5000/${language?'?lang='+language+'&settings=costs':''}`,assign(url){this.assigned=url;}},
    history:{replaceState(state,title,url){this.replaced=String(url);}},NodeFilter:{SHOW_TEXT:4},
    document:{documentElement:{},body:{},createTreeWalker(){let i=0;return {nextNode:()=>textNodes[i++]||null};},
      querySelectorAll:()=>[element],getElementById:()=>select}};
  vm.createContext(state);
  vm.runInContext(catalog+'\nthis.result=I18N;',state);
  return {state,i18n:state.result,textNodes,attrs,select,store};
}
const cases={
 de:['Einstellungen','Ladevorgang starten','Person auswählen','Wallbox ohne Fahrzeug','26,00','Start in 2 Std. 05 Min.','Person nicht gefunden.'],
 en:['Settings','Start charging','Select person','Wallbox without vehicle','26.00','Starts in 2 h 05 min','Person not found.'],
 fr:['Paramètres','Démarrer la recharge','Choisir une personne','Borne sans véhicule','26,00','Démarrage dans 2 h 05 min','Personne introuvable.'],
 es:['Ajustes','Iniciar carga','Seleccionar persona','Cargador sin vehículo','26,00','Inicio en 2 h 05 min','Persona no encontrada.']
};
for(const [lang,expected] of Object.entries(cases)){
 const {state,i18n,textNodes,attrs,select,store}=makeBrowser(lang,'de');
 assert.equal(i18n.language,lang);
 assert.equal(state.document.documentElement.lang,lang);
 assert.equal(select.value,lang);
 assert.equal(store.get('wallbox.language'),lang);
 assert.equal(textNodes[0].nodeValue,'  '+expected[0]+' ');
 assert.equal(textNodes[1].nodeValue,expected[1]);
 assert.equal(attrs['aria-label'],expected[2]);
 assert.equal(attrs.alt,expected[3]);
 assert.equal(attrs.placeholder,expected[4]);
 assert.equal(i18n.t('Start in {hours} Std. {minutes} Min.',{hours:2,minutes:'05'}),expected[5]);
 assert.equal(i18n.apiError('Person nicht gefunden.'),expected[6]);
 assert.equal(i18n.resumeTab,'costs');
 assert.equal(state.history.replaced,`http://127.0.0.1:5000/?lang=${lang}`);
 assert.equal(i18n.formatSchedule(null),'—');
 assert.match(i18n.formatSchedule(Date.UTC(2026,0,1,12)/1000),/13:00/);
 // Fahrzeugstatus, Aktionen und Fehlermeldungen müssen in jeder Sprache
 // einen nichtleeren Wert liefern. Personen-Namen werden nicht übersetzt.
 for(const key of textKeys)assert(i18n.t(key).length>0,key);
 assert.equal(i18n.t('Alex Beispiel'), 'Alex Beispiel');
 i18n.changeLanguage(lang==='es'?'en':'es','auto');
 assert.match(state.location.assigned,/settings=auto/);
}
assert.equal(makeBrowser(null,'fr').i18n.language,'fr');
assert.equal(makeBrowser('xx','es').i18n.language,'es');
assert.equal(makeBrowser(null,null).i18n.language,'de');
console.log('i18n: all four languages, static labels, errors, countdowns, date/time, persistence and navigation passed.');

// Der tatsächliche Card-Renderer und beide Button-Handler, ohne Browser.
async function testAutoCards(){
 const source=app.slice(app.indexOf('function renderAutoState('),app.indexOf('function selectPerson('));
 assert(source.includes('changeAutoSkip'));
 for(const lang of Object.keys(cases)){
   const {i18n}=makeBrowser(lang,'de');
   const elements=new Map();
   const $=id=>{
     if(!elements.has(id))elements.set(id,{classList:{toggle(name,on){this[name]=on;}}});
     return elements.get(id);
   };
   const due=Date.UTC(2026,10,27,0)/1000;
   const live={auto_enabled:true,auto_pending:{due,person:'Alex Beispiel',skipped:false},server_now:due-3600,raw_status:2,scheduled_charge:null};
   const calls=[];
   const sandbox={I18N:i18n,t:i18n.t,$,live,busy:false,Date,
     post:async(url,body)=>{calls.push([url,body.due]);return {status:url==='/auto-cancel'?'skipped':'restored',due:body.due};},
     toast:()=>{},fetchData:async()=>{}};
   vm.createContext(sandbox);
   vm.runInContext(source+'\nthis.render=renderAutoPending;',sandbox);
   sandbox.render(live);
   assert.equal($('autoPendingCard').hidden,false);
   assert.equal($('autoCancel').hidden,false);
   assert.equal($('autoCancel').disabled,false);
   assert.equal($('autoResume').hidden,true);
   assert.equal($('autoPendingHint').textContent,i18n.t('Zur gewählten Uhrzeit wird geladen, wenn ein Fahrzeug angeschlossen ist und die Wallbox laden kann.'));
   await $('autoCancel').onclick();
   assert.deepEqual(calls[0],['/auto-cancel',due]);
   assert.equal(live.auto_pending.skipped,true);
   assert.equal($('autoCancel').hidden,true);
   assert.equal($('autoResume').hidden,false);
   assert.equal($('autoResume').disabled,false);
   assert.equal($('autoPendingCard').classList.skipped,true);
   assert.equal($('autoPendingCountdown').textContent,i18n.t('Dieser Ladestart wird ausgelassen'));
   // Auch beim manuellen Plan bleibt die Ausnahme sichtbar und widerrufbar.
   live.scheduled_charge={due:due+3600,person:'Alex Beispiel'};
   sandbox.render(live);
   assert.equal($('autoPendingCard').hidden,false);
   await $('autoResume').onclick();
   assert.deepEqual(calls[1],['/auto-resume',due]);
   assert.equal(live.auto_pending.skipped,false);
   assert.equal($('autoCancel').hidden,false);
   assert.equal($('autoResume').hidden,true);
   live.auto_stale=true;
   sandbox.render(live);
   assert.equal($('autoCancel').disabled,true);
   live.auto_stale=false;
   live.server_now=due;
   sandbox.render(live);
   assert.equal($('autoCancel').disabled,true);
   assert.equal($('autoResume').disabled,true);
   live.auto_enabled=false;live.auto_pending=null;
   sandbox.render(live);
   assert.equal($('autoPendingCard').hidden,true);
 }
 console.log('Automatic charging card: skip, undo, disabled/stale state, and all four languages passed.');
}
testAutoCards().catch(error=>{console.error(error);process.exitCode=1;});
