'use strict';
const t=I18N.t;
const $ = id => document.getElementById(id);
const defaultImage = $('heroImage').getAttribute('src');
let step=1, startMode="now", timeOptions=[], selectedTime=null;
let persons = [], live = null, chosen = null, busy = false, selectedLevel = null, toastTimer, pollBusy = false;
const fmt = (n, decimals=1, unit='') => n == null || !Number.isFinite(Number(n)) ? '—' : Number(n).toLocaleString(I18N.locale,{minimumFractionDigits:decimals,maximumFractionDigits:decimals}) + (unit?' '+unit:'');
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{$('toast').hidden=true},6000)}
async function api(url,options={}){let res;try{res=await fetch(url,{cache:'no-store',...options})}catch{throw Error(t('Webserver nicht erreichbar.'))}let data;try{data=await res.json()}catch{throw Error(t('Ungültige Serverantwort ({status}).',{status:res.status}))}if(!res.ok)throw Error(I18N.apiError(data.error));return data}
function post(url,data){return api(url,{method:'POST',...(data===undefined?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})})}
function setImage(el,url){let src=url||defaultImage;const builtin=/(?:^|\/)wallbox-idle\.webp(?:\?|$)/.test(src);if(builtin&&!src.includes('?'))src+='?v=5';el.classList.toggle('theme-image',builtin);if(el.getAttribute('src')!==src)el.src=src;el.onerror=()=>{el.onerror=null;el.classList.add('theme-image');el.src=defaultImage}}
function activePerson(){return live && (persons.find(p=>p.id===live.current_person_id)|| (live.current_person?persons.find(p=>p.name===live.current_person):null))}
// Alle Fahrzeugmotive nutzen dieselbe 2:1-Kalibrierung, einschließlich eigener Personenbilder.
// Nur das Standardmotiv ohne Fahrzeug behält die separate Idle-Kalibrierung.
function updateChargingGlow(){
  const img=$('heroImage'), overlay=$('chargingGlow');
  const charging=live?.raw_status===7||(live?.raw_status===8&&Number(live.power_kw)>0);
  const path=new URL(img.getAttribute('src')||defaultImage,document.baseURI).pathname;
  const base=new URL(defaultImage,document.baseURI).pathname;
  const kind=path===base?'idle':'vehicle';
  const show=charging&&kind&&img.complete&&img.naturalWidth>0;
  overlay.toggleAttribute('hidden',!show);
  for(const group of overlay.querySelectorAll('[data-glow]'))group.toggleAttribute('hidden',!show||group.dataset.glow!==kind);
  // Alle Personenbilder verwenden den identischen Kabelpfad; das Leermotiv nicht.
  $('cableFlow').toggleAttribute('hidden',!show||kind!=='vehicle');
}
$('heroImage').addEventListener('load',updateChargingGlow);
$('heroImage').addEventListener('error',()=>{$('chargingGlow').setAttribute('hidden','');$('cableFlow').setAttribute('hidden','')});
function updateHero(){
  const connected=live?.demo_mode&&typeof live.demo_connected==='boolean'?live.demo_connected:[4,5,6,7,8].includes(live?.raw_status);
  const assigned=!!(live?.current_person||live?.current_person_id||live?.scheduled_charge);
  const p=connected?(assigned?(activePerson()||persons.find(p=>p.id===live?.scheduled_charge?.person_id)):(live?.demo_mode?persons.find(p=>p.id===live.demo_person_id):null)):null;
  setImage($('heroImage'),p?.image_url);
  $('heroImage').alt=p?.image_url?t('Fahrzeug an einer Wallbox'):t('Wallbox ohne Fahrzeug');
  $('imageLabel').textContent=p?.image_url?(assigned?t('Persönliches Fahrzeug'):t('Fahrzeugvorschau')):live?.raw_status==null?t('Verbindungsstatus unbekannt'):connected?t('Kein Fahrzeugbild hinterlegt'):t('Wallbox ohne Fahrzeug');
  $('current_person').textContent=live?.current_person||(live?.scheduled_charge?live.scheduled_charge.person+t(' (geplant)'):t('Niemand'));
  updateChargingGlow();
}
async function loadPersons(){persons=await api('/persons');updateHero();return persons}
function setView(settings){$('homePage').hidden=settings;$('settingsPage').hidden=!settings;for(const [id,active] of [['navHome',!settings],['navSettings',settings]]){const b=$(id);b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')}window.scrollTo(0,0);if(settings)showSettingsTab(settingsTab)}
$('navHome').onclick=()=>setView(false);$('navSettings').onclick=()=>setView(true);
function el(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node}
function icon(name){const s=document.createElementNS('http://www.w3.org/2000/svg','svg');const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href','#'+name);s.append(u);s.setAttribute('aria-hidden','true');return s}
async function renderSettings(){const root=$('personSettings');root.replaceChildren(el('p','muted',t('Personen werden geladen …')));$('settingsMessage').textContent='';try{await loadPersons();if($('settingsPage').hidden)return;root.replaceChildren();if(!persons.length)root.append(el('p','muted',t('Noch keine Personen angelegt. Über „Person hinzufügen“ kannst du die erste Person erstellen.')));for(const p of persons){const card=el('article','panel person-setting');const title=el('h2','',p.name);const stage=el('div','setting-image');const img=el('img','car-image');img.alt=t('Fahrzeug von ')+p.name;setImage(img,p.image_url);stage.append(img);const note=el('p','small muted',p.image_url?t('Eigenes Bild hinterlegt'):t('Wallbox ohne Fahrzeug'));const input=el('input');input.type='file';input.accept='image/jpeg,image/png,image/webp';input.setAttribute('aria-label',t('Fahrzeugbild für ')+p.name);const actions=el('div','setting-actions');const save=el('button','primary',t('Speichern'));save.disabled=true;const remove=el('button','secondary',t('Bild entfernen'));remove.disabled=!p.image_url;const msg=el('p','small muted');msg.setAttribute('role','status');let preview=null;function revoke(){if(preview){URL.revokeObjectURL(preview);preview=null}}input.onchange=()=>{revoke();const file=input.files[0];save.disabled=!file;msg.textContent='';if(file){if(file.size>8*1024*1024){msg.textContent=t('Datei zu groß (maximal 8 MB).');save.disabled=true;return}preview=URL.createObjectURL(file);setImage(img,preview);note.textContent=t('Vorschau – noch nicht gespeichert')}else{setImage(img,p.image_url);note.textContent=p.image_url?t('Eigenes Bild hinterlegt'):t('Wallbox ohne Fahrzeug')}};async function changeImage(deleting){save.disabled=remove.disabled=input.disabled=deletePerson.disabled=true;msg.textContent=t('Wird gespeichert …');try{const form=new FormData();if(!deleting)form.append('image',input.files[0]);const result=await api('/person-image/'+encodeURIComponent(p.id),deleting?{method:'DELETE'}:{method:'POST',body:form});p.image_url=result.image_url;revoke();input.value='';setImage(img,p.image_url);note.textContent=p.image_url?t('Eigenes Bild hinterlegt'):t('Wallbox ohne Fahrzeug');msg.textContent=deleting?t('Bild entfernt.'):t('Bild gespeichert.');const item=persons.find(x=>x.id===p.id);if(item)item.image_url=p.image_url;updateHero();toast(msg.textContent)}catch(e){msg.textContent=e.message}finally{input.disabled=deletePerson.disabled=false;save.disabled=!input.files.length;remove.disabled=!p.image_url}}save.onclick=()=>changeImage(false);remove.onclick=()=>changeImage(true);actions.append(save,remove);const deletePerson=el('button','person-delete-btn',t('Person löschen'));deletePerson.type='button';deletePerson.setAttribute('aria-label',t('Person löschen: ')+p.name);deletePerson.onclick=()=>openDeletePerson(p,revoke);card.append(title,stage,note,input,actions,msg,deletePerson);root.append(card)}}catch(e){root.replaceChildren(el('p','muted',e.message))}}
let addingPerson=false;
function openAddPerson(){
  $('addPersonForm').reset();
  $('addPersonMessage').textContent='';
  $('addPersonModal').showModal();
  $('personName').focus();
}
function closeAddPerson(){if(!addingPerson)$('addPersonModal').close()}
$('addPersonBtn').onclick=openAddPerson;
$('closeAddPerson').onclick=closeAddPerson;
$('cancelAddPerson').onclick=closeAddPerson;
$('addPersonModal').addEventListener('cancel',e=>{if(addingPerson)e.preventDefault()});
$('addPersonFromStart').onclick=()=>{
  closeModal();
  settingsTab='persons';
  setView(true);
  openAddPerson();
};
$('addPersonForm').onsubmit=async e=>{
  e.preventDefault();
  if(addingPerson)return;
  const name=$('personName').value.trim();
  if(!name){$('addPersonMessage').textContent=t('Bitte einen Namen eingeben.');return}
  addingPerson=true;
  const controls=[$('personName'),$('savePerson'),$('cancelAddPerson'),$('closeAddPerson')];
  controls.forEach(c=>c.disabled=true);
  $('addPersonMessage').textContent=t('Wird gespeichert …');
  try{
    const person=await post('/persons',{name});
    $('addPersonModal').close();
    await renderSettings();
    toast(person.name+t(' wurde hinzugefügt.'));
  }catch(err){
    $('addPersonMessage').textContent=err.message;
  }finally{
    addingPerson=false;
    controls.forEach(c=>c.disabled=false);
    if($('addPersonModal').open)$('personName').focus();
  }
};
let deletingPerson=false,personToDelete=null,deleteImagePreview=null;
function openDeletePerson(person,revokePreview){
  personToDelete=person;
  deleteImagePreview=revokePreview;
  $('deletePersonName').textContent=person.name;
  $('deletePersonMessage').textContent='';
  $('deletePersonModal').showModal();
  $('cancelDeletePerson').focus();
}
function closeDeletePerson(){
  if(deletingPerson)return;
  $('deletePersonModal').close();
  personToDelete=null;
  deleteImagePreview=null;
}
$('closeDeletePerson').onclick=closeDeletePerson;
$('cancelDeletePerson').onclick=closeDeletePerson;
$('deletePersonModal').addEventListener('cancel',e=>{e.preventDefault();closeDeletePerson()});
$('confirmDeletePerson').onclick=async()=>{
  if(deletingPerson||!personToDelete)return;
  deletingPerson=true;
  const person=personToDelete;
  const controls=[$('closeDeletePerson'),$('cancelDeletePerson'),$('confirmDeletePerson')];
  controls.forEach(c=>c.disabled=true);
  $('deletePersonMessage').textContent=t('Wird gelöscht …');
  try{
    const result=await api('/persons/'+encodeURIComponent(person.id),{method:'DELETE'});
    if(deleteImagePreview)deleteImagePreview();
    persons=persons.filter(p=>p.id!==person.id);
    personToDelete=null;
    deleteImagePreview=null;
    $('deletePersonModal').close();
    updateHero();
    await renderSettings();
    await fetchData();
    toast(result.auto_reset?person.name+t(' gelöscht. Ladeautomatik deaktiviert.'):person.name+t(' wurde gelöscht.'));
    $('addPersonBtn').focus();
  }catch(err){
    $('deletePersonMessage').textContent=err.message;
  }finally{
    deletingPerson=false;
    controls.forEach(c=>c.disabled=false);
  }
};
let settingsTab='persons', autoHour=1, autoConfig=null, autoLoading=false;
function showSettingsTab(tab){settingsTab=tab;for(const [id,active] of [['tabPersons',tab==='persons'],['tabAuto',tab==='auto'],['tabCosts',tab==='costs']]){$(id).classList.toggle('active',active);$(id).setAttribute('aria-selected',String(active))}$('personsPanel').hidden=tab!=='persons';$('autoPanel').hidden=tab!=='auto';$('costsPanel').hidden=tab!=='costs';if(tab==='persons')renderSettings();else if(tab==='auto')loadAutoSettings();else loadCostSettings()}
$('tabPersons').onclick=()=>showSettingsTab('persons');$('tabAuto').onclick=()=>showSettingsTab('auto');$('tabCosts').onclick=()=>showSettingsTab('costs');
let costLoading=false,costLoaded=false;
function syncCostForm(){$('costPrice').disabled=costLoading||!costLoaded;$('costSave').disabled=costLoading||!costLoaded}
function renderCostSettings(cfg){costLoaded=true;$('currentCost').textContent=fmt(cfg.price_ct,2,'ct/kWh');$('costPrice').value=Number(cfg.price_ct).toLocaleString(I18N.locale,{useGrouping:false,minimumFractionDigits:2,maximumFractionDigits:2})}
async function loadCostSettings(){if(costLoading)return;costLoading=true;costLoaded=false;syncCostForm();$('costMessage').textContent='';try{renderCostSettings(await api('/cost-settings'))}catch(e){$('costMessage').textContent=e.message;$('currentCost').textContent='—'}finally{costLoading=false;syncCostForm()}}
$('costForm').onsubmit=async e=>{e.preventDefault();if(costLoading||!costLoaded)return;costLoading=true;syncCostForm();$('costMessage').textContent='';try{renderCostSettings(await post('/cost-settings',{price_ct:$('costPrice').value}));$('costMessage').textContent=t('Strompreis gespeichert.')}catch(err){$('costMessage').textContent=err.message}finally{costLoading=false;syncCostForm()}};
function syncAutoForm(){const enabled=$('autoEnabled').checked;$('autoFields').disabled=!enabled||autoLoading||!autoConfig;$('autoEnabled').disabled=autoLoading||!autoConfig;$('autoSave').disabled=autoLoading||!autoConfig||(enabled&&!$('autoPersonOptions').querySelector('input:checked'));$('autoHourLabel').textContent=String(autoHour).padStart(2,'0')+t(':00 Uhr');for(const button of $('autoHourGrid').children){const selected=Number(button.dataset.hour)===autoHour;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected))}}
$('autoEnabled').onchange=syncAutoForm;
function buildAutoForm(cfg){autoConfig=cfg;autoHour=cfg.hour;$('autoEnabled').checked=cfg.enabled;const grid=$('autoHourGrid');grid.replaceChildren();for(let h=0;h<24;h++){const button=el('button','hour-option',String(h).padStart(2,'0')+':00');button.type='button';button.dataset.hour=h;button.onclick=()=>{autoHour=h;syncAutoForm()};grid.append(button)}const root=$('autoPersonOptions');root.replaceChildren();for(const p of persons){const label=el('label','person-option');const radio=el('input');radio.type='radio';radio.name='autoPerson';radio.value=p.id;radio.checked=p.id===cfg.person_id;radio.onchange=syncAutoForm;label.append(icon('user'),el('span','',p.name),radio);root.append(label)}if(!persons.length)root.append(el('p','muted',t('Keine Personen vorhanden.')));if(cfg.person_id&&!persons.some(p=>p.id===cfg.person_id))$('autoMessage').textContent=t('Standardperson neu wählen.');syncAutoForm()}
async function loadAutoSettings(){if(autoLoading)return;autoLoading=true;autoConfig=null;$('autoMessage').textContent=t('Einstellungen werden geladen …');syncAutoForm();try{const [cfg]=await Promise.all([api('/auto-settings'),loadPersons()]);$('autoMessage').textContent='';buildAutoForm(cfg)}catch(e){$('autoMessage').textContent=e.message}finally{autoLoading=false;syncAutoForm();renderAutoState(live)}}
$('autoForm').onsubmit=async e=>{e.preventDefault();if(autoLoading||!autoConfig)return;const person=$('autoPersonOptions').querySelector('input:checked');const payload={enabled:$('autoEnabled').checked,hour:autoHour,person_id:person?.value||null};autoLoading=true;syncAutoForm();$('autoMessage').textContent=t('Wird gespeichert …');try{const cfg=await post('/auto-settings',payload);buildAutoForm(cfg);$('autoMessage').textContent=t('Automatik gespeichert.');toast(t('Automatik gespeichert.'));await fetchData()}catch(err){$('autoMessage').textContent=err.message}finally{autoLoading=false;syncAutoForm()}};
function renderAutoState(d){
  if(!d)return;
  const plan=d.auto_pending;
  $('autoState').textContent=!d.auto_enabled?t('Automatik aus'):!plan?t('Automatischer Ladestart aktiv'):(plan.skipped?t('Ladestart ausgesetzt: '):t('Nächster automatischer Ladestart: '))+I18N.formatSchedule(plan.due);
}
function renderAutoPending(d){
  const plan=d.auto_pending;
  const card=$('autoPendingCard');
  card.hidden=!plan;
  const skipped=!!plan?.skipped;
  card.classList.toggle('skipped',skipped);
  const remaining=plan?plan.due-(d.server_now??Date.now()/1000):0;
  const changeAllowed=!!plan&&remaining>0&&!d.auto_stale&&!busy;
  $('autoCancel').hidden=skipped;
  $('autoResume').hidden=!skipped;
  $('autoCancel').disabled=$('autoResume').disabled=!changeAllowed;
  if(plan){
    $('autoPendingDate').textContent=I18N.formatSchedule(plan.due);
    $('autoPendingPerson').textContent=t('Standardperson: ')+plan.person;
    const mins=Math.ceil(Math.max(0,remaining)/60);
    $('autoPendingCountdown').textContent=skipped?t('Dieser Ladestart wird ausgelassen'):mins===0?t('Zeitpunkt für automatischen Ladestart'):t('Ladestart in {hours} Std. {minutes} Min.',{hours:Math.floor(mins/60),minutes:String(mins%60).padStart(2,'0')});
    $('autoPendingHint').textContent=skipped?t('Nur dieser Termin entfällt. Die tägliche Automatik bleibt aktiv.'):t('Zur gewählten Uhrzeit wird geladen, wenn ein Fahrzeug angeschlossen ist und die Wallbox laden kann.');
  }
  renderAutoState(d);
}
async function changeAutoSkip(skipped){
  const plan=live?.auto_pending;
  if(busy||!plan||live.auto_stale)return;
  busy=true;
  renderAutoPending(live);
  try{
    const result=await post(skipped?'/auto-cancel':'/auto-resume',{due:plan.due});
    if(live?.auto_pending?.due===result.due){
      live.auto_pending.skipped=result.status==='skipped';
      renderAutoPending(live);
    }
    toast(skipped?t('Ladestart einmalig übersprungen.'):t('Automatischer Ladestart wieder aktiviert.'));
  }catch(e){toast(e.message)}
  finally{
    busy=false;
    await fetchData();
    if(live)renderAutoPending(live);
  }
}
$('autoCancel').onclick=()=>changeAutoSkip(true);
$('autoResume').onclick=()=>changeAutoSkip(false);
function selectPerson(p){chosen=p;$('confirmPerson').disabled=!p||busy;setImage($('modalImage'),p?.image_url);$('modalMessage').textContent=p?.image_url?t('Persönliches Fahrzeug'):p?t('Wallbox ohne Fahrzeug'):t('Bitte eine Person wählen.')}
$('startBtn').onclick=async()=>{if(busy)return;try{await loadPersons();const root=$('personOptions');root.replaceChildren();chosen=null;showPersonStep();for(const p of persons){const label=el('label','person-option');const radio=el('input');radio.type='radio';radio.name='person';radio.value=p.id;radio.onchange=()=>selectPerson(p);label.append(icon('user'),el('span','',p.name),radio);root.append(label)}selectPerson(null);$('personModal').showModal();$('addPersonFromStart').hidden=persons.length>0;if(!persons.length)$('modalMessage').textContent=t('Noch keine Personen vorhanden. Lege zuerst eine Person an.')}catch(e){toast(e.message)}};
function closeModal(){if(!busy)$('personModal').close()}
function showPersonStep(){step=1;$('personStep').hidden=false;$('timeStep').hidden=true;$('modalTitle').textContent=t('Person auswählen');$('cancelModal').textContent=t('Abbrechen');$('confirmPerson').textContent=t('Weiter');$('confirmPerson').disabled=!chosen||busy;if(chosen)selectPerson(chosen)}
function setMode(mode){startMode=mode;for(const [id,on] of [['modeNow',mode==='now'],['modeLater',mode==='scheduled']]){$(id).classList.toggle('selected',on);$(id).setAttribute('aria-pressed',String(on))}$('hourPicker').hidden=mode==='now';$('confirmPerson').textContent=mode==='now'?t('Jetzt starten'):t('Start planen');$('confirmPerson').disabled=busy||(mode==='scheduled'&&!selectedTime);$('modalMessage').textContent=''}
async function loadHours(){timeOptions=(await api('/charge-times')).options;selectedTime=null;const grid=$('hourGrid');grid.replaceChildren();for(const o of timeOptions){const button=el('button','hour-option');button.type='button';button.setAttribute('aria-pressed','false');button.append(el('strong','',String(o.hour).padStart(2,'0')+':00'),el('small','',t(o.day)));button.onclick=()=>{if(busy)return;selectedTime=o;for(const other of grid.children){other.classList.toggle('selected',other===button);other.setAttribute('aria-pressed',String(other===button))}$('hourPreview').textContent=t(o.day)+' · '+I18N.formatSchedule(o.due);$('confirmPerson').disabled=false;$('modalMessage').textContent=''};grid.append(button)}$('hourPreview').textContent=t('Wähle eine Uhrzeit.')}
function showTimeStep(){step=2;selectedTime=null;$('personStep').hidden=true;$('timeStep').hidden=false;$('modalTitle').textContent=t('Wann soll geladen werden?');$('planPerson').textContent=t('2 von 2 · ')+chosen.name;$('cancelModal').textContent=t('Zurück');$('modeLater').disabled=![4,6].includes(live?.raw_status);setMode('now');$('modalMessage').textContent=$('modeLater').disabled?t('Fahrzeug anschließen.'):''}
$('modeNow').onclick=()=>setMode('now');$('modeLater').onclick=async()=>{if(busy)return;selectedTime=null;$('hourGrid').replaceChildren();setMode('scheduled');try{await loadHours();if(startMode==='scheduled')$('confirmPerson').disabled=!selectedTime}catch(e){if(startMode==='scheduled')$('modalMessage').textContent=e.message}};
$('closeModal').onclick=closeModal;$('cancelModal').onclick=()=>{if(busy)return;step===2?showPersonStep():closeModal()};$('personModal').addEventListener('cancel',e=>{if(busy)e.preventDefault()});
$('confirmPerson').onclick=async()=>{if(!chosen||busy)return;if(step===1){showTimeStep();return}if(startMode==='scheduled'&&!selectedTime)return;const p=chosen;busy=true;const controls=[...$('personModal').querySelectorAll('button,input')];const disabled=controls.map(c=>c.disabled);controls.forEach(c=>c.disabled=true);$('modalMessage').textContent=startMode==='now'?t('Ladefreigabe wird angefordert …'):t('Startzeit wird gespeichert …');try{const result=await post('/select_person',{person:p.id,mode:startMode,...(startMode==='scheduled'?{due:selectedTime.due}:{})});$('personModal').close();toast(result.status==='scheduled'?t('Ladestart geplant.'):t('Ladefreigabe erteilt.'));}catch(e){$('modalMessage').textContent=e.message;if(startMode==='scheduled'){try{await loadHours()}catch{} }}finally{busy=false;controls.forEach((c,i)=>c.disabled=disabled[i]);$('confirmPerson').disabled=startMode==='scheduled'&&!selectedTime;await fetchData()}};
$('stopBtn').onclick=async()=>{if(busy)return;busy=true;$('stopBtn').disabled=true;try{const r=await post('/stop');toast(r.status==='cancelled'?t('Planung abgebrochen.'):t('Sperrbefehl gesendet.'))}catch(e){toast(e.message)}finally{busy=false;await fetchData()}};
function renderSchedule(d){const plan=d.scheduled_charge;$('scheduleCard').hidden=!plan;$('scheduleNotice').hidden=!d.schedule_notice||!!plan;$('scheduleNotice').textContent=d.schedule_notice?t(d.schedule_notice):'';if(plan){$('scheduleDate').textContent=I18N.formatSchedule(plan.due);$('schedulePerson').textContent=plan.person;const seconds=Math.max(0,Math.ceil(plan.due-(d.server_now||Date.now()/1000)));const minutes=Math.ceil(seconds/60);$('scheduleCountdown').textContent=seconds===0?d.raw_status==null?t('Keine Verbindung'):t('Warte auf Freigabe'):t('Start in {hours} Std. {minutes} Min.',{hours:Math.floor(minutes/60),minutes:String(minutes%60).padStart(2,'0')});$('stopBtn').lastChild.textContent=t(' Planung abbrechen')}else{$('stopBtn').lastChild.textContent=t(' Ladevorgang stoppen')}}
function setMetric(id,state){$(id).classList.toggle('good',state==='good');$(id).classList.toggle('bad',state==='bad')}
function renderVehicle(s){
  const connected=[4,5,6,7,8].includes(s);
  // Bei fehlenden oder nicht eindeutigen Messwerten keinen Anschlusszustand vortäuschen.
  $('vehicleStatus').textContent=connected?t('Verbunden'):[2,3].includes(s)?t('Kein Fahrzeug'):t('Unbekannt');
  setMetric('vehicleCard',connected?'good':'');
}
// Nur im Demo-Modus sichtbar: Wechsel zwischen Fahrzeug- und Leerbild.
let demoVehicleBusy=false;
function renderDemoVehicle(d){
  const button=$('demoVehicleBtn');
  if(!button)return;
  const known=d.demo_mode&&typeof d.demo_connected==='boolean';
  button.disabled=demoVehicleBusy||!known;
  if(known)$('demoVehicleLabel').textContent=d.demo_connected?t('Fahrzeug trennen'):t('Fahrzeug anschließen');
}
if($('demoVehicleBtn'))$('demoVehicleBtn').onclick=async()=>{
  if(demoVehicleBusy||typeof live?.demo_connected!=='boolean')return;
  demoVehicleBusy=true;
  renderDemoVehicle(live);
  try{
    const result=await post('/demo/vehicle',{connected:!live.demo_connected});
    // Bild direkt wechseln; die Messwerte folgen dem normalen Polling.
    await fetchData();
    toast(result.connected?t('Virtuelles Fahrzeug verbunden.'):t('Virtuelles Fahrzeug getrennt.'));
  }catch(err){toast(err.message)}
  finally{demoVehicleBusy=false;renderDemoVehicle(live||{})}
};
function renderLive(d){live=d;renderDemoVehicle(d);const s=d.raw_status,online=s!=null,charging=s===7,assigned=!!(d.scheduled_charge||d.current_person||d.charging_active||charging||[3,5,8].includes(s));const states={2:t('Gesperrt'),3:t('Bereit'),4:t('Gesperrt'),5:t('Bereit'),6:t('Gesperrt'),7:t('Lädt'),8:t('Begrenzt'),9:t('Fehler'),10:t('Fehler'),11:t('Fehler')};$('shortStatus').textContent=d.scheduled_charge?t('Geplant'):online?(states[s]||t('Unbekannt')):'—';$('statusCard').classList.toggle('planned',!!d.scheduled_charge);setMetric('statusCard',charging?'good':[9,10,11].includes(s)?'bad':'');$('online').textContent=online?t('Online'):t('Offline');setMetric('onlineCard',online?'good':'bad');$('connectionBadge').className='connection '+(online?'good':'bad');$('connectionLabel').textContent=online?t('Verbunden'):t('Keine Verbindung');renderVehicle(s);$('power_kw').textContent=fmt(d.power_kw,1,'kW');$('gaugeText').textContent=fmt(d.power_kw,1,'kW');$('energy_total').textContent=fmt(d.energy_total_kwh,2,'kWh');$('pcb_temp').textContent=fmt(d.pcb_temp,1,'°C');for(const l of ['L1','L2','L3']){$('current_'+l).textContent=fmt(d['current_'+l],1,'A');$('voltage_'+l).textContent=fmt(d['voltage_'+l],0,'V')};$('startBtn').hidden=assigned;$('startBtn').disabled=busy||assigned||![2,4,6].includes(s);$('stopBtn').hidden=!assigned;$('stopBtn').disabled=busy||!assigned;renderSchedule(d);renderAutoPending(d);const r=Math.max(0,Math.min(1,(d.power_kw||0)/11));$('gaugeArc').style.strokeDashoffset=252*(1-r);$('gaugeNeedle').style.transform=`rotate(${-90+r*180}deg)`;if(online&&!charging)selectedLevel=null;document.querySelectorAll('[data-level]').forEach(b=>{b.disabled=busy||!charging;b.classList.toggle('active',charging&&selectedLevel===b.dataset.level)});updateHero()}
async function fetchData(){if(pollBusy)return;pollBusy=true;try{renderLive(await api('/data'))}catch(e){renderLive({current_person:live?.current_person,current_person_id:live?.current_person_id,charging_active:live?.charging_active,scheduled_charge:live?.scheduled_charge,auto_pending:live?.auto_pending,auto_enabled:live?.auto_enabled,auto_blocked:live?.auto_blocked,auto_stale:true,schedule_notice:live?.schedule_notice,server_now:Date.now()/1000,raw_status:null,status_text:t('Webserver nicht erreichbar. Keine aktuellen Messwerte.')});$('stopBtn').disabled=true}finally{pollBusy=false}}
for(const b of document.querySelectorAll('[data-level]'))b.onclick=async()=>{if(busy)return;busy=true;document.querySelectorAll('[data-level]').forEach(btn=>btn.disabled=true);try{await post('/set_power',{level:b.dataset.level});selectedLevel=b.dataset.level;toast(t('Leistungsstufe eingestellt.'))}catch(e){toast(e.message)}finally{busy=false;await fetchData()}};
function monthName(key){const [y,m]=key.split('-').map(Number);return y&&m?new Date(y,m-1,1).toLocaleDateString(I18N.locale,{month:'long',year:'numeric'}):t('Unbekannter Monat')}
let historyBusy=false, historySignature=null, historyMonth=null;
const monthOverrides=new Map();
function dateTime(value){
  if(!value)return '—';
  const m=String(value).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
  if(!m)return String(value);
  const stamp=new Date(Date.UTC(Number(m[1]),Number(m[2])-1,Number(m[3]),Number(m[4]),Number(m[5])));
  return new Intl.DateTimeFormat(I18N.locale,{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'UTC'}).format(stamp);
}
function stat(label,value){const box=el('span','month-stat');box.append(el('span','month-stat-label',label),el('strong','',value));return box}
function renderMonth(key,rows,current){
  const details=el('details','history-month');details.dataset.month=key;details.classList.toggle('current-month',key===current);
  details.open=monthOverrides.has(key)?monthOverrides.get(key):key===current;
  const summary=el('summary','month-summary');
  const title=el('span','month-title');title.append(el('strong','',monthName(key)));if(key===current)title.append(el('span','month-current',t('Aktueller Monat')));
  const arrow=el('span','month-chevron');arrow.setAttribute('aria-hidden','true');
  const top=el('span','month-heading');top.append(title,arrow);
  const done=rows.filter(s=>s.end_time!=null);
  const sum=(field)=>done.reduce((n,s)=>n+(Number(s[field])||0),0);
  const stats=el('span','month-stats');stats.append(stat(t('Anz. Ladungen'),String(done.length)),stat(t('Verbrauch'),fmt(sum('verbrauch_total'),2,'kWh')),stat(t('Kosten'),fmt(sum('total_costs'),2,'€')));
  summary.append(top,stats);details.append(summary);
  if(!rows.length){details.append(el('p','history-empty muted',t('Keine Ladungen')))}
  else {
    const wrap=el('div','table-scroll history-table-wrap');const table=el('table','history-table');table.setAttribute('aria-label',t('Ladevorgänge ')+monthName(key));
    const headings=[t('Person'),t('Start'),t('Ende'),t('Verbrauch'),t('Kosten')];const thead=el('thead');const hr=el('tr');for(const label of headings){const th=el('th','',label);th.scope='col';hr.append(th)}thead.append(hr);
    const tbody=el('tbody');for(const s of rows){const tr=el('tr');const values=[s.person||'—',dateTime(s.start_time),s.end_time?dateTime(s.end_time):t('Aktiv'),fmt(s.verbrauch_total,3,'kWh'),fmt(s.total_costs,2,'€')];values.forEach((value,i)=>{const td=el('td','',value);td.dataset.label=headings[i];if(i===2&&!s.end_time)td.classList.add('session-active');tr.append(td)});tbody.append(tr)}table.append(thead,tbody);wrap.append(table);details.append(wrap);
  }
  // Nur tatsächliche Nutzeraktionen speichern, nicht programmatische Initialisierung.
  summary.addEventListener('click',()=>monthOverrides.set(key,!details.open));
  return details;
}
async function loadSessions(){
  if(historyBusy)return;historyBusy=true;
  try{
    const [sessions,month]=await Promise.all([api('/sessions'),api('/monthly_summary')]);
    const current=month.month_key;
    if(historyMonth!==current){monthOverrides.clear();historyMonth=current}
    const signature=JSON.stringify([current,sessions]);
    if(signature!==historySignature){
      const grouped=new Map([[current,[]]]);
      for(const s of sessions){const key=(s.start_time||'').slice(0,7);if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(s)}
      const keys=[...grouped.keys()].sort((a,b)=>b.localeCompare(a));
      $('sessionRows').replaceChildren(...keys.map(key=>renderMonth(key,grouped.get(key),current)));historySignature=signature;
    }
    $('historyMessage').hidden=true;
  }catch(e){$('historyMessage').textContent=t('Historie nicht verfügbar.');$('historyMessage').hidden=false;if(historySignature===null)$('sessionRows').replaceChildren()}
  finally{historyBusy=false}
}
$('languageSelect').onchange=()=>I18N.changeLanguage($('languageSelect').value,settingsTab);
if(['persons','auto','costs'].includes(I18N.resumeTab)){settingsTab=I18N.resumeTab;setView(true)}
loadPersons().catch(e=>toast(e.message));fetchData();loadSessions();setInterval(fetchData,2000);setInterval(loadSessions,5000);setInterval(()=>{if($('settingsPage').hidden&&!$('personModal').open)loadPersons().catch(()=>{})},15000);
