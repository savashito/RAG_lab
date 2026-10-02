// Tab "🧪 Benchmark" — sets de preguntas por tema, componentes esperados, corridas
// juzgadas por el LLM y comparación entre corridas. Backend: /api/bench/* (bench.py).
// Usa los helpers globales de index.html ($, esc, readJur, renderChunks, window.__topics),
// que ya existen cuando se llama a cualquiera de estas funciones.
//
// Estructura: barra fija (tema · set · menú ⋯ · ayuda) + tres sub-pestañas:
//   ▶ Correr y resultados (default) · 📝 Preguntas · 📊 Comparar
// Los formularios de set y de pregunta son ventanas emergentes (no hay que hacer scroll).
// ✍️ Revisión humana: desde el detalle de una corrida, una persona marca cada componente de
// cada respuesta (como el juez, que queda oculto tras un 👁) y la califica de 1 a 5.

let BENCH = {sets: [], set: null, runs: [], editingQ: null, editingSet: null, poll: null, inited: false,
             sub: 'run', detail: null, dfilter: 'all', dsort: 'pos', open: new Set(), cmp: null, cmpOnlyDiff: false};

async function bjson(url, opts){
  const r = await fetch(url, opts);
  let body = null; try{ body = await r.json(); }catch(e){}
  if(!r.ok || (body && body.error)) throw new Error((body && body.error) || `HTTP ${r.status}`);
  return body;
}
const bpost = (url, obj) => bjson(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(obj||{})});
function bmsg(html, ok){
  $('bench-msg').innerHTML = html ? `<span style="color:${ok===false?'#f87171':'#4ade80'}">${html}</span>` : '';
  clearTimeout(BENCH.msgT); if(html && ok!==false) BENCH.msgT = setTimeout(()=>bmsg(''), 6000);
}
const attr = s => esc(s).replace(/"/g,'&quot;');
const pct = v => v==null ? '—' : (100*v).toFixed(0)+'%';
function scoreColor(v){ if(v==null) return '#374151'; if(v>=.85) return '#166534'; if(v>=.6) return '#3f6212'; if(v>=.35) return '#854d0e'; return '#7f1d1d'; }
const topicLabel = t => ((window.__topics||[]).find(x=>x.topic===t)||{}).label || t;
// Dificultad (criterio en la ayuda «¿Cómo se califica?»).
const DIFFS = [['facil','Fácil'], ['mediano','Mediano'], ['dificil','Difícil']];
const diffLabel = d => (DIFFS.find(x=>x[0]===d)||[])[1] || '';
const diffTag = d => d ? `<span class="tag d-${d}" title="Dificultad">${diffLabel(d)}</span>` : '';
const qDiff = qid => ((BENCH.set && BENCH.set.questions.find(q=>q.id===qid)) || {}).difficulty || '';
// Recuperación: ¿llegaron al contexto los artículos que piden los must de cita? (sin LLM)
function retBadge(r){
  if(!r || !r.attainable) return r && r.total ? '<span class="tag gap" title="Los artículos de esta pregunta no están en el corpus">🔎 hueco</span>' : '';
  const h = Math.min(r.hit, r.attainable), cls = h>=r.attainable ? 'ret-ok' : h ? 'ret-part' : 'ret-bad';
  return `<span class="tag ${cls}" title="Artículos necesarios que la búsqueda trajo al contexto del LLM">🔎 ${h}/${r.attainable}</span>`;
}
// Score medio y % que pasa por dificultad, sobre los resultados sin error.
function diffStats(results){
  const out = {};
  for(const [d] of DIFFS){
    const rs = results.filter(x=>!x.error && qDiff(x.question_id)===d);
    out[d] = rs.length ? {n: rs.length, score: rs.reduce((a,x)=>a+x.score,0)/rs.length, pass: rs.filter(x=>x.passed).length/rs.length} : null;
  }
  return out;
}

// ── Navegación ──────────────────────────────────────────────────────────────────
// La URL refleja lo que se ve, para recargar o compartir el enlace:
//   /benchmark?set=3&vista=preguntas · ?set=3&corrida=12 · ?set=3&vista=comparar&comparar=11,12
const SUB_URL = {run: '', questions: 'preguntas', compare: 'comparar'};
function benchSub(name){
  BENCH.sub = name;
  document.querySelectorAll('.bsub button').forEach(b=>b.classList.toggle('active', b.dataset.sub===name));
  for(const s of ['run','questions','compare']) $('bsub-'+s).hidden = (s!==name);
  benchUrlSync();
}
function benchUrlSync(){
  if(location.pathname !== '/benchmark') return;
  const p = new URLSearchParams();
  if(BENCH.set) p.set('set', BENCH.set.id);
  if(SUB_URL[BENCH.sub]) p.set('vista', SUB_URL[BENCH.sub]);
  if(BENCH.sub==='run' && BENCH.detail) p.set('corrida', BENCH.detail.id);
  if(BENCH.sub==='compare' && BENCH.cmp) p.set('comparar', BENCH.cmp.map(r=>r.id).join(','));
  const url = '/benchmark' + (p.toString() ? '?' + p.toString().replace(/%2C/g, ',') : '');
  if(location.pathname + location.search !== url) history.replaceState(history.state, '', url);
}
// Lo que pide la URL al abrir la página (se aplica una vez, cuando carga ese set).
function benchUrlWanted(){
  const p = new URLSearchParams(location.search);
  const sub = Object.keys(SUB_URL).find(k=>SUB_URL[k] && SUB_URL[k]===p.get('vista')) || 'run';
  return {set: p.get('set'), sub, run: +p.get('corrida') || null,
          cmp: (p.get('comparar')||'').split(',').map(Number).filter(Boolean)};
}
// El sub-tab «Comparar» solo aparece con ☑ dos o más corridas marcadas.
const checkedRuns = () => [...document.querySelectorAll('.bench-cmp:checked')].map(c=>+c.value).sort((a,b)=>a-b);
function syncCompareTab(){
  const n = checkedRuns().length, btn = document.querySelector('.bsub button[data-sub="compare"]');
  btn.hidden = n < 2 && !(BENCH.sub==='compare' && BENCH.cmp);
  $('bench-ccount').textContent = n; $('bench-ccount').hidden = n < 2;
  $('bench-compare').hidden = n < 2;
  $('bench-compare').textContent = `📊 Comparar ${n} corridas`;
}
function openModal(id){ $(id).hidden = false; }
function closeModal(id){ $(id).hidden = true; }

async function benchInit(){
  if(!BENCH.inited){
    BENCH.inited = true;
    document.querySelectorAll('.bsub button').forEach(b=>b.addEventListener('click', ()=>
      b.dataset.sub==='compare' ? compareBenchRuns() : benchSub(b.dataset.sub)));
    $('bench-runs').addEventListener('change', e=>{ if(e.target.classList.contains('bench-cmp')) syncCompareTab(); });
    BENCH.want = benchUrlWanted();
    $('bench-set').addEventListener('change', ()=>loadBenchSet($('bench-set').value));
    $('bench-topic-filter').addEventListener('change', ()=>renderSetOptions());
    // Menú ⋯: cada acción cierra el menú.
    const menu = (id, fn) => $(id).addEventListener('click', ()=>{ $('bench-menu').open = false; fn(); });
    $('bench-new-set').addEventListener('click', ()=>openSetForm(null));
    menu('bench-edit-set', ()=>BENCH.set && openSetForm(BENCH.set));
    menu('bench-export', exportSet);
    menu('bench-import-btn', ()=>$('bench-import').click());
    menu('bench-backup', backupSet);
    const openEditor = () => { if(BENCH.set) location.href = '/benchmark/editor?set=' + BENCH.set.id; };
    $('bench-json-editor').addEventListener('click', openEditor);
    $('bench-json-editor2').addEventListener('click', openEditor);
    $('bench-import').addEventListener('change', importSet);
    $('bench-set-cancel').addEventListener('click', ()=>closeModal('bench-set-modal'));
    $('bench-set-save').addEventListener('click', ()=>saveSet(false));
    $('bench-set-save-json').addEventListener('click', ()=>saveSet(true));
    $('bench-set-delete').addEventListener('click', deleteSet);
    $('bench-help-btn').addEventListener('click', ()=>openModal('bench-help'));
    $('bench-help-close').addEventListener('click', ()=>closeModal('bench-help'));
    // Preguntas
    $('bench-add-q').addEventListener('click', ()=>openQForm(null));
    $('bench-qsearch').addEventListener('input', renderQuestions);
    $('bench-qfilter').addEventListener('change', renderQuestions);
    $('bench-expand-all').addEventListener('click', toggleExpandAll);
    $('bq-add-comp').addEventListener('click', ()=>addCompRow());
    $('bq-cancel').addEventListener('click', closeQForm);
    $('bq-save').addEventListener('click', saveQ);
    // Corridas
    $('bench-run').addEventListener('click', startBenchRun);
    $('bench-cancel').addEventListener('click', cancelBenchRun);
    $('bench-refresh').addEventListener('click', loadBenchRuns);
    $('bench-compare').addEventListener('click', compareBenchRuns);
    // Modales: clic en el fondo o Esc cierran; el menú ⋯ se cierra al hacer clic fuera.
    document.querySelectorAll('.bmodal').forEach(m=>m.addEventListener('click', e=>{ if(e.target===m){ if(m.id==='bench-review') rvClose(); else m.hidden = true; } }));
    document.addEventListener('keydown', e=>{ if(e.key==='Escape') document.querySelectorAll('.bmodal').forEach(m=>m.hidden = true); });
    document.addEventListener('click', e=>{ const m=$('bench-menu'); if(m.open && !m.contains(e.target)) m.open = false; });
  }
  try{
    const info = await bjson('/api/bench/info');
    const st = info.storage||{};
    $('bench-storage').textContent = `Detalle de cada corrida → ${st.backend==='minio' ? 'MinIO '+st.where : 'carpeta local '+st.where+' (MinIO no configurado)'}`;
    $('bench-judge').textContent = 'LLM en '+(info.judge_url||'?');
    if(info.running) watchBenchRun(info.running);
  }catch(e){}
  benchFillTopics();
  await loadBenchSets(BENCH.want && BENCH.want.set);
}
// Selectores de tema del tab. Se llama también desde loadTopics() (index.html), porque
// /api/topics puede llegar DESPUÉS de abrir el tab en la carga inicial.
function benchFillTopics(){
  const ts = window.__topics||[];
  // Tema del formulario de set: solo los temas en los que el usuario puede escribir.
  const prevT = $('bench-set-topic').value;
  $('bench-set-topic').innerHTML = ts.filter(t=>canIngestTopic(t.topic))
    .map(t=>`<option value="${esc(t.topic)}">${esc(t.label)}</option>`).join('');
  if(prevT) $('bench-set-topic').value = prevT;
  const prevF = $('bench-topic-filter').value;
  $('bench-topic-filter').innerHTML = '<option value="">todos</option>' +
    ts.map(t=>`<option value="${esc(t.topic)}">${esc(t.label)}</option>`).join('');
  $('bench-topic-filter').value = prevF;
  if(BENCH.set && !$('bench-system').value){
    const t = ts.find(x=>x.topic===BENCH.set.topic); if(t) $('bench-system').value = t.system_prompt||'';
  }
}

// ── Sets ────────────────────────────────────────────────────────────────────────
async function loadBenchSets(selectId){
  try{ BENCH.sets = await bjson('/api/bench/sets'); }catch(e){ bmsg(esc(e.message), false); return; }
  renderSetOptions(selectId);
}
function renderSetOptions(selectId){
  const f = $('bench-topic-filter').value;
  const list = BENCH.sets.filter(s=>!f || s.topic===f);
  const want = String(selectId || (BENCH.set && BENCH.set.id) || '');
  $('bench-set').innerHTML = list.length
    ? list.map(s=>`<option value="${s.id}">${esc(s.name)} · ${s.n_questions} preg.${f?'':' · '+esc(s.topic_label)}</option>`).join('')
    : '<option value="">— no hay sets; crea uno en ⋯ Set —</option>';
  if(want && list.some(s=>String(s.id)===want)) $('bench-set').value = want;
  loadBenchSet($('bench-set').value);
}
async function loadBenchSet(id){
  closeQForm();
  BENCH.detail = null; BENCH.open.clear();
  $('bench-detail').innerHTML = '';
  $('bench-compare-out').innerHTML = '';
  BENCH.cmp = null;
  $('bench-json-editor').disabled = !id;
  if(BENCH.sub==='compare') benchSub('run');
  if(!id){ BENCH.set=null; $('bench-questions').innerHTML='<p class="muted">Crea un set para empezar (menú ⋯ Set).</p>';
    $('bench-qcount').textContent=''; $('bench-runs').innerHTML=''; syncCompareTab(); benchUrlSync(); return; }
  try{ BENCH.set = await bjson('/api/bench/sets/'+id); }catch(e){ bmsg(esc(e.message), false); return; }
  const t = (window.__topics||[]).find(x=>x.topic===BENCH.set.topic);
  $('bench-system').value = (t && t.system_prompt) || '';
  renderQuestions();
  await loadBenchRuns();
  // Primera carga: aplica lo que pedía la URL (vista, corrida abierta, corridas comparadas).
  const w = BENCH.want; BENCH.want = null;
  if(w && String(w.set)===String(id)){
    if(w.cmp.length >= 2){
      document.querySelectorAll('.bench-cmp').forEach(c=>{ c.checked = w.cmp.includes(+c.value); });
      syncCompareTab();
    }
    if(w.sub==='compare' && checkedRuns().length >= 2){ await compareBenchRuns(); return; }
    if(w.run) await showBenchRun(w.run, true);
    if(w.sub!=='run') benchSub(w.sub);
  }
  benchUrlSync();
}
function openSetForm(s){
  BENCH.editingSet = s;
  $('bench-set-title').textContent = s ? `Editar set «${s.name}»` : 'Nuevo set';
  $('bench-set-name').value = s ? s.name : '';
  $('bench-set-desc').value = s ? (s.description||'') : '';
  if(s) $('bench-set-topic').value = s.topic;
  else if($('bench-topic-filter').value) $('bench-set-topic').value = $('bench-topic-filter').value;
  $('bench-set-delete').style.display = s ? '' : 'none';
  openModal('bench-set-modal');
  $('bench-set-name').focus();
}
async function saveSet(thenEditJson){
  const body = {name:$('bench-set-name').value, topic:$('bench-set-topic').value, description:$('bench-set-desc').value};
  try{
    let id;
    if(BENCH.editingSet){ id = BENCH.editingSet.id; await bpost('/api/bench/sets/'+id, body); }
    else id = (await bpost('/api/bench/sets', body)).id;
    closeModal('bench-set-modal');
    if(thenEditJson){ location.href = '/benchmark/editor?set=' + id; return; }
    bmsg('Set guardado.');
    await loadBenchSets(id);
  }catch(e){ bmsg(esc(e.message), false); }
}
async function deleteSet(){
  const s = BENCH.editingSet; if(!s) return;
  if(!confirm(`¿Borrar el set «${s.name}» con sus ${s.questions.length} preguntas? Las corridas se conservan.`)) return;
  try{ await bjson('/api/bench/sets/'+s.id, {method:'DELETE'}); BENCH.set=null;
    closeModal('bench-set-modal'); bmsg('Set borrado.'); await loadBenchSets(); }
  catch(e){ bmsg(esc(e.message), false); }
}
async function exportSet(){
  if(!BENCH.set) return;
  try{
    const data = await bjson(`/api/bench/sets/${BENCH.set.id}/export`);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}));
    a.download = (BENCH.set.name||'set').replace(/[^\w\-]+/g,'_')+'.json';
    a.click(); URL.revokeObjectURL(a.href);
  }catch(e){ bmsg(esc(e.message), false); }
}
async function importSet(ev){
  const f = ev.target.files[0]; ev.target.value = ''; if(!f) return;
  try{
    const data = JSON.parse(await f.text());
    if(!data.topic) data.topic = $('bench-topic-filter').value || $('bench-set-topic').value;
    if(!data.name) data.name = f.name.replace(/\.json$/i,'');
    const r = await bpost('/api/bench/sets/import', data);
    bmsg(`Importado: ${r.questions} preguntas en «${esc(data.name)}» (${esc(topicLabel(data.topic))}).`);
    await loadBenchSets(r.id);
  }catch(e){ bmsg('No pude importar: '+esc(e.message), false); }
}
async function backupSet(){
  if(!BENCH.set) return;
  try{ const r = await bpost(`/api/bench/sets/${BENCH.set.id}/backup`);
    bmsg(`Respaldado en ${esc(r.backend)}: ${esc(r.key)}`); }
  catch(e){ bmsg(esc(e.message), false); }
}

// ── Preguntas ───────────────────────────────────────────────────────────────────
function compChip(c, verdict){
  // Con veredicto: verde = bien, rojo = mal (invertido para must_not).
  let cls = '';
  if(verdict !== undefined){
    const v = verdict || null;
    if(v==null) cls = 'unk';
    else if(c.kind==='must_not') cls = v==='presente' ? 'bad' : v==='parcial' ? 'half' : 'good';
    else cls = v==='presente' ? 'good' : v==='parcial' ? 'half' : 'bad';
  }
  const w = (c.weight!=null && +c.weight!==1) ? ` ×${+c.weight}` : '';
  const title = verdict!==undefined ? `${verdict||'sin veredicto'}${c.evidence?' — «'+c.evidence+'»':''}` : '';
  return `<span class="comp ${c.kind} ${cls}" title="${attr(title)}"><span class="k">${c.kind.replace('_',' ')}${w}</span>${esc(c.text)}</span>`;
}
function compCounts(comps){
  const n = k => comps.filter(c=>c.kind===k).length;
  return `<span class="cnt"><b>${n('must')}</b> must · <b>${n('should')}</b> should · <b>${n('must_not')}</b> must not</span>`;
}
function renderQuestions(){
  if(!BENCH.set) return;
  const all = BENCH.set.questions;
  $('bench-qcount').textContent = all.length;
  const term = $('bench-qsearch').value.trim().toLowerCase(), f = $('bench-qfilter').value;
  const shown = all.map((q,i)=>({q,i})).filter(({q})=>{
    if(f==='nocomp' && q.components.length) return false;
    if(f.startsWith('dif:') && (q.difficulty||'') !== f.slice(4)) return false;
    if(!term) return true;
    return [q.question, q.expected_answer, q.notes, ...q.components.map(c=>c.text)].join(' ').toLowerCase().includes(term);
  });
  $('bench-questions').innerHTML = (shown.length!==all.length ? `<p class="muted" style="font-size:12px">${shown.length} de ${all.length}</p>` : '') +
    (shown.length ? shown.map(({q,i})=>`
    <details class="bq" data-qid="${q.id}" ${BENCH.open.has(q.id)?'open':''} ontoggle="benchQToggle(this)">
      <summary><span class="muted">#${i+1}</span><span class="qt">${esc(q.question)}</span>
        ${diffTag(q.difficulty)}
        ${q.components.length ? compCounts(q.components)
          : (q.expected_answer ? '<span class="cnt">vs. referencia</span>' : '<span class="cnt" style="color:#f87171">sin criterios</span>')}
        <button class="ghost" onclick="event.preventDefault();openQForm(${q.id})" title="Editar">✏️</button>
        <button class="danger" onclick="event.preventDefault();deleteQ(${q.id})" title="Borrar">🗑</button></summary>
      <div class="qbody">
        ${q.expected_answer?`<div class="ref"><b style="color:#c7cdd6">Respuesta esperada:</b> ${esc(q.expected_answer)}</div>`:''}
        <div class="comps">${q.components.map(c=>compChip(c)).join('') ||
          (q.expected_answer ? '<span class="muted" style="font-size:12px">sin componentes: se compara contra la referencia</span>'
                             : '<span style="color:#f87171;font-size:12px">sin componentes ni referencia: no se evalúa</span>')}</div>
        ${q.notes?`<div class="muted" style="font-size:12px;margin-top:6px">📝 ${esc(q.notes)}</div>`:''}
      </div>
    </details>`).join('') : '<p class="muted">Ninguna pregunta coincide.</p>');
  $('bench-expand-all').textContent = BENCH.open.size ? '↕ Colapsar todo' : '↕ Expandir todo';
}
function benchQToggle(el){ const id=+el.dataset.qid; if(el.open) BENCH.open.add(id); else BENCH.open.delete(id);
  $('bench-expand-all').textContent = BENCH.open.size ? '↕ Colapsar todo' : '↕ Expandir todo'; }
function toggleExpandAll(){
  const els = [...document.querySelectorAll('#bench-questions details.bq')];
  const open = !BENCH.open.size;
  els.forEach(d=>{ d.open = open; });   // ontoggle actualiza BENCH.open
  if(!open) BENCH.open.clear();
}
function addCompRow(c){
  c = c || {kind:'must', text:'', weight:1};
  const row = document.createElement('div'); row.className = 'cedit';
  row.innerHTML = `<select class="ck">${['must','should','must_not'].map(k=>`<option ${k===c.kind?'selected':''}>${k}</option>`).join('')}</select>
    <input type="text" class="ct" placeholder="p. ej. «Cita el art. 146 del CNPP»" value="${attr(c.text)}">
    <input type="number" class="cw" min="0" step="0.5" value="${c.weight??1}" title="peso">
    <button class="danger" title="quitar">✕</button>`;
  row.querySelector('button').onclick = ()=>row.remove();
  $('bq-comps').appendChild(row);
  return row;
}
function openQForm(qid){
  if(!BENCH.set){ bmsg('Primero crea o elige un set.', false); return; }
  const q = qid ? BENCH.set.questions.find(x=>x.id===qid) : null;
  BENCH.editingQ = q;
  $('bq-title').textContent = q ? `Editar pregunta #${BENCH.set.questions.indexOf(q)+1}` : 'Nueva pregunta';
  $('bq-question').value = q ? q.question : '';
  $('bq-expected').value = q ? (q.expected_answer||'') : '';
  $('bq-notes').value = q ? (q.notes||'') : '';
  $('bq-difficulty').value = q ? (q.difficulty||'') : '';
  $('bq-comps').innerHTML = '';
  (q && q.components.length ? q.components : [null]).forEach(c=>addCompRow(c));
  openModal('bench-q-modal');
  $('bq-question').focus();
}
function closeQForm(){ BENCH.editingQ = null; closeModal('bench-q-modal'); }
async function saveQ(){
  const components = [...$('bq-comps').querySelectorAll('.cedit')].map(r=>({
    kind: r.querySelector('.ck').value, text: r.querySelector('.ct').value.trim(),
    weight: parseFloat(r.querySelector('.cw').value)||1})).filter(c=>c.text);
  const body = {question:$('bq-question').value, expected_answer:$('bq-expected').value,
                notes:$('bq-notes').value, difficulty:$('bq-difficulty').value, components};
  try{
    if(BENCH.editingQ) await bpost('/api/bench/questions/'+BENCH.editingQ.id, body);
    else await bpost(`/api/bench/sets/${BENCH.set.id}/questions`, body);
    closeQForm();
    BENCH.set = await bjson('/api/bench/sets/'+BENCH.set.id);
    renderQuestions(); bmsg('Pregunta guardada.');
    const s = BENCH.sets.find(x=>x.id===BENCH.set.id); if(s) s.n_questions = BENCH.set.questions.length;
  }catch(e){ bmsg(esc(e.message), false); }
}
async function deleteQ(qid){
  if(!confirm('¿Borrar esta pregunta?')) return;
  try{ await bjson('/api/bench/questions/'+qid, {method:'DELETE'});
    BENCH.open.delete(qid);
    BENCH.set = await bjson('/api/bench/sets/'+BENCH.set.id); renderQuestions(); }
  catch(e){ bmsg(esc(e.message), false); }
}

// ── Corridas ────────────────────────────────────────────────────────────────────
async function startBenchRun(){
  if(!BENCH.set) return;
  const body = {set_id: BENCH.set.id, label: $('bench-label').value, setting: $('bench-setting').value,
    k: +$('bench-k').value, neighbors: $('bench-neighbors').checked, hyde: $('bench-hyde').checked,
    rerank: $('bench-rerank').checked, decompose: $('bench-decompose').checked,
    system: $('bench-system').value, jurisdictions: readJur('bench-jur')};
  try{ const r = await bpost('/api/bench/run', body); watchBenchRun(r.run_id); loadBenchRuns(); }
  catch(e){ bmsg(esc(e.message), false); }
}
async function cancelBenchRun(){
  const rid = BENCH.running; if(!rid) return;
  try{ await bpost(`/api/bench/runs/${rid}/cancel`); $('bench-cancel').disabled = true; }catch(e){ bmsg(esc(e.message), false); }
}
function watchBenchRun(rid){
  BENCH.running = rid; BENCH.shownDone = 0;
  clearInterval(BENCH.poll);
  $('bench-run').disabled = true; $('bench-cancel').style.display = ''; $('bench-cancel').disabled = false;
  const tick = async ()=>{
    let r; try{ r = await bjson('/api/bench/runs/'+rid); }catch(e){ return; }
    const p = r.n ? Math.round(100*r.done/r.n) : 0, m = r.metrics||{};
    const running = r.status==='running';
    const eta = running && m.avg_seconds ? ` · faltan ~${Math.ceil((r.n-r.done)*m.avg_seconds/60)} min` : '';
    $('bench-progress').innerHTML = `<div class="phead"><span>Corrida <b>#${r.id}</b> ${esc(r.label||'')} · ${esc(r.set_name||'')}</span>
      <span><b>${r.done}/${r.n}</b> preguntas · ${esc(r.status)}${m.score!=null?` · score ${pct(m.score)} · pasan ${pct(m.pass_rate)}`:''}${eta}</span></div>
      <div class="pbar ${running?'busy':(r.status==='done'?'done':'err')}"><i style="width:${Math.max(p,3)}%"></i></div>
      ${r.error?`<div style="color:#f87171;font-size:12px">${esc(r.error)}</div>`:''}`;
    const mine = BENCH.set && r.set_id===BENCH.set.id;
    if(!running){
      clearInterval(BENCH.poll); BENCH.running = null;
      $('bench-run').disabled = false; $('bench-cancel').style.display = 'none';
      if(mine){ loadBenchRuns(); if(!BENCH.detail || BENCH.detail.id===rid) showBenchRun(rid, true); }
    }else if(mine && r.done && r.done!==BENCH.shownDone){
      BENCH.shownDone = r.done;   // solo si llegó un resultado nuevo (no colapsa filas abiertas en cada tick)
      loadBenchRuns();
      if(!BENCH.detail || BENCH.detail.id===rid) showBenchRun(rid, true);
    }
  };
  tick(); BENCH.poll = setInterval(tick, 3000);
}
function cfgSummary(c){
  c = c||{};
  return [c.setting, 'k='+c.k, c.neighbors?'vecinos':'', c.hyde?'HyDE':'', c.rerank?'rerank':'', c.decompose?'descompone':'',
          (c.jurisdictions||[]).length?'lugar='+c.jurisdictions.join('+'):'', c.judge_model?'juez '+c.judge_model:'']
    .filter(Boolean).join(' · ');
}
async function loadBenchRuns(){
  if(!BENCH.set) return;
  let runs; try{ runs = await bjson('/api/bench/runs?set_id='+BENCH.set.id); }catch(e){ return; }
  const checked = new Set([...document.querySelectorAll('.bench-cmp:checked')].map(c=>+c.value));
  BENCH.runs = runs;
  const sel = BENCH.detail && BENCH.detail.id;
  $('bench-runs').innerHTML = runs.length ? `<table><tr><th title="marcar para comparar">☑</th><th>#</th><th>fecha</th><th>etiqueta / config</th><th>estado</th>
    <th title="promedio del score por pregunta">score</th><th title="% de preguntas con todos los must y ningún must_not">pasan</th>
    <th title="% de componentes must presentes">must ✓</th><th title="must_not que aparecieron">viol.</th>
    <th title="% de los artículos necesarios (según los must de cita) que la búsqueda trajo al contexto — sin LLM, sin ruido">🔎 art.</th><th>s/preg</th>
    <th title="Preguntas con revisión humana">✍️</th><th></th></tr>`+
    runs.map(r=>{ const m=r.metrics||{}; return `<tr class="clk ${r.id===sel?'sel':''}" onclick="showBenchRun(${r.id})">
      <td onclick="event.stopPropagation()"><input type="checkbox" class="bench-cmp" value="${r.id}" ${checked.has(r.id)?'checked':''}></td><td>${r.id}</td>
      <td style="white-space:nowrap">${esc((r.created_at||'').slice(5,16))}</td>
      <td>${esc(r.label||'—')}<div class="runcfg">${esc(cfgSummary(r.config))}</div></td>
      <td>${r.status==='running'?`⏳ ${r.done}/${r.n}`:esc(r.status)}${m.errors?` <span style="color:#f87171">(${m.errors} err)</span>`:''}</td>
      <td class="sc" style="background:${scoreColor(m.score)}">${pct(m.score)}</td>
      <td class="sc">${pct(m.pass_rate)}</td><td class="sc">${pct(m.must_coverage)}</td>
      <td class="sc">${m.violations??'—'}</td><td class="sc">${pct(m.retrieval_recall)}</td><td class="sc">${m.avg_seconds??'—'}</td>
      <td class="sc">${r.reviewed ? `${r.reviewed}/${r.done}` : '<span class="muted">—</span>'}</td>
      <td onclick="event.stopPropagation()"><button class="danger" onclick="deleteBenchRun(${r.id}, ${r.reviewed||0})" title="Borrar corrida">🗑</button></td></tr>`; }).join('')+'</table>'
    : '<p class="muted">Aún no hay corridas de este set. Configura arriba y pulsa ▶ Correr benchmark.</p>';
  syncCompareTab();
}
async function deleteBenchRun(rid, reviewed){
  if(!confirm(`¿Borrar la corrida #${rid} (y su artefacto)?` + (reviewed ? `\n\n⚠️ Tiene ${reviewed} preguntas con revisión humana: también se borrarán.` : ''))) return;
  try{ await bjson('/api/bench/runs/'+rid, {method:'DELETE'});
    if(BENCH.detail && BENCH.detail.id===rid){ BENCH.detail=null; $('bench-detail').innerHTML=''; benchUrlSync(); }
    loadBenchRuns(); }
  catch(e){ bmsg(esc(e.message), false); }
}

// ── Detalle de una corrida ──────────────────────────────────────────────────────
const DFILTERS = [
  ['all', 'Todas', ()=>true],
  ['fail', '❌ No pasan', x=>!x.error && !x.passed],
  ['pass', '✅ Pasan', x=>!x.error && x.passed],
  ['viol', '⚠️ Con violación', x=>x.violations>0],
  ['gap', '🔎 Ley fuera del corpus', x=>!x.error && x.retrieval && x.retrieval.attainable < x.retrieval.total],
  ['noret', '🔎 No trajo el artículo', x=>!x.error && x.retrieval && x.retrieval.hit < x.retrieval.attainable],
  ['retfail', '🔎✓ pero no pasa', x=>!x.error && !x.passed && x.retrieval && x.retrieval.attainable && x.retrieval.hit >= x.retrieval.attainable],
  ['facil', 'Fácil', x=>qDiff(x.question_id)==='facil'],
  ['mediano', 'Mediano', x=>qDiff(x.question_id)==='mediano'],
  ['dificil', 'Difícil', x=>qDiff(x.question_id)==='dificil'],
  ['err', 'Errores', x=>!!x.error],
  ['rv_no', '✍️ Sin revisar', x=>!x.error && !myReview(x.question_id)],
  ['rv_yes', '✍️ Revisadas', x=>!x.error && revsOf(x.question_id).length>0],
  ['rv_diff', '✍️ ≠ juez (pasa/no pasa)', x=>!x.error && revsOf(x.question_id).some(v=>v.passed!==x.passed)],
];
// Revisiones humanas de la corrida en pantalla (BENCH.reviews = {me, reviews, stats}).
const revsOf = qid => ((BENCH.reviews||{}).reviews||[]).filter(v=>v.question_id===qid);
const myReview = qid => revsOf(qid).find(v=>v.reviewer===(BENCH.reviews||{}).me);
async function loadReviews(rid){
  try{ BENCH.reviews = await bjson(`/api/bench/runs/${rid}/reviews`); }
  catch(e){ BENCH.reviews = {me:null, reviews:[], stats:{}}; }
}
// Celda ✍️ de la tabla de resultados: veredicto humano (pasa/no pasa) y calificación.
function revCell(x){
  if(x.error) return '';
  const vs = revsOf(x.question_id); if(!vs.length) return '<span class="muted">—</span>';
  return vs.map(v=>{ const diff = v.passed!==x.passed;
    return `<span class="tag ${diff?'rv-diff':'rv-ok'}" title="${attr(v.reviewer+(diff?' · NO coincide con el juez':' · coincide con el juez')+(v.comment?'\n«'+v.comment+'»':''))}">${v.passed?'✅':'❌'}${v.rating?' '+v.rating+'★':''}${v.comment?' 💬':''}</span>`; }).join(' ');
}
async function showBenchRun(rid, quiet){
  let r; try{ r = await bjson('/api/bench/runs/'+rid); }catch(e){ bmsg(esc(e.message), false); return; }
  if(!BENCH.detail || BENCH.detail.id!==rid){ BENCH.dfilter = 'all'; }
  BENCH.detail = r;
  await loadReviews(rid);
  document.querySelectorAll('#bench-runs tr.clk').forEach(tr=>tr.classList.toggle('sel', tr.getAttribute('onclick')===`showBenchRun(${rid})`));
  renderBenchDetail();
  benchUrlSync();
  if(!quiet) $('bench-detail').scrollIntoView({behavior:'smooth', block:'start'});
}
// Lo que falló de una pregunta: must/should no presentes y must_not que aparecieron.
function missesOf(x){
  const out = [];
  for(const v of (x.verdicts||[])){
    if(v.kind==='must_not'){ if(v.verdict==='presente' || v.verdict==='parcial') out.push(['⚠️', v]); }
    else if(v.verdict!=='presente') out.push([v.kind==='must' ? (v.verdict==='parcial'?'◐':'✗') : '·', v]);
  }
  return out;
}
// Artículos que la búsqueda NO trajo (o que no existen en el corpus), para "qué faltó".
function retMiss(x){
  const r = x.retrieval; if(!r) return [];
  return r.groups.filter(g=>g.rank==null).map(g=> g.in_corpus
    ? `<li style="color:#fbbf24" title="La búsqueda no trajo este artículo al contexto: el LLM nunca lo vio">🔎✗ no llegó al contexto: ${esc(g.labels.join(' o '))}</li>`
    : `<li style="color:#fcd34d" title="Este artículo no está en el corpus (hueco)">🔎 no está en el corpus: ${esc(g.labels.join(' o '))}</li>`);
}
function renderBenchDetail(){
  const r = BENCH.detail; if(!r) return;
  const m = r.metrics||{};
  const f = DFILTERS.find(d=>d[0]===BENCH.dfilter) || DFILTERS[0];
  let rows = r.results.filter(f[2]);
  if(BENCH.dsort==='worst') rows = [...rows].sort((a,b)=>(a.error?-1:a.score)-(b.error?-1:b.score));
  const card = (t, v, sub) => `<div class="card"><h3>${t}</h3><div style="font-size:22px;font-weight:700">${v}</div>${sub?`<div class="muted" style="font-size:12px">${sub}</div>`:''}</div>`;
  const nPass = r.results.filter(x=>!x.error && x.passed).length;
  $('bench-detail').innerHTML = `<h2 style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">Corrida #${r.id} ${esc(r.label||'')}
      <span class="runcfg">${esc(cfgSummary(r.config))}</span>${r.status==='running'?`<span class="tag gap">en curso ${r.done}/${r.n}</span>`:''}
      <span style="flex:1"></span>${r.results.some(x=>!x.error)?`<button onclick="openReview()" title="Califica tú las respuestas, componente por componente">✍️ Revisar respuestas</button>`:''}</h2>
    <div class="cards">
      ${card('score medio', pct(m.score))}
      ${card('preguntas que pasan', pct(m.pass_rate), `${nPass} de ${r.results.length}`)}
      ${card('cobertura de must', pct(m.must_coverage))}
      ${card('violaciones must_not', m.violations??'—')}
      ${m.retrieval_recall!=null ? card('artículos recuperados 🔎', pct(m.retrieval_recall), `${pct(m.retrieval_full)} de las preguntas con todos`) : ''}
      ${(()=>{ const st = (BENCH.reviews||{}).stats||{}; if(!st.n_reviews) return '';
        return `<div class="card" title="Comparado en las mismas preguntas revisadas"><h3>✍️ revisión humana</h3>
          <div class="m"><span>revisadas</span><b>${st.n_questions} de ${r.results.filter(x=>!x.error).length}</b></div>
          <div class="m"><span>score humano / juez</span><b>${pct(st.human_score)} / ${pct(st.judge_score)}</b></div>
          <div class="m"><span>pasan humano / juez</span><b>${pct(st.human_pass_rate)} / ${pct(st.judge_pass_rate)}</b></div>
          <div class="m" title="% de componentes donde el juez marcó lo mismo que la persona"><span>acuerdo por componente</span><b>${pct(st.comp_agreement)}</b></div>
          <div class="m" title="% de preguntas donde juez y persona coinciden en si pasa"><span>acuerdo pasa/no pasa</span><b>${pct(st.pass_agreement)}</b></div>
          ${st.avg_rating!=null?`<div class="m"><span>calificación media</span><b>${st.avg_rating}★</b></div>`:''}</div>`; })()}
      ${(()=>{ const ds = diffStats(r.results); if(!DIFFS.some(([d])=>ds[d])) return '';
        return `<div class="card"><h3>score por dificultad</h3>${DIFFS.map(([d,l])=>ds[d]
          ? `<div class="m"><span>${diffTag(d)} <span class="muted" style="font-size:11px">${ds[d].n}</span></span><b>${pct(ds[d].score)}</b></div>` : '').join('')}</div>`; })()}
    </div>
    <div class="fchips">${DFILTERS.map(([k,label,fn])=>{ const n = r.results.filter(fn).length;
        return (k==='all'||n) ? `<button class="${k===BENCH.dfilter?'active':''}" onclick="BENCH.dfilter='${k}';renderBenchDetail()">${label} <span class="pill">${n}</span></button>` : ''; }).join('')}
      <span style="flex:1"></span>
      <select onchange="BENCH.dsort=this.value;renderBenchDetail()">
        <option value="pos" ${BENCH.dsort==='pos'?'selected':''}>orden del set</option>
        <option value="worst" ${BENCH.dsort==='worst'?'selected':''}>peor score primero</option></select>
    </div>
    <p class="muted" style="font-size:12px;margin:4px 0">Clic en una fila → respuesta completa, todos los veredictos con evidencia, fuentes y salida cruda del juez.</p>
    <table><tr><th>#</th><th>pregunta</th><th>score</th><th>pasa</th><th title="must/should no presentes (✗ ausente · ◐ parcial · · should) y must_not que aparecieron (⚠️)">qué faltó / qué sobró</th>
      <th title="Revisión humana: ✅/❌ según la persona, ★ calificación; en rojo si no coincide con el juez">✍️</th><th>s</th></tr>`+
    (rows.length ? rows.map(x=>{ const miss = missesOf(x); return `<tr class="clk" onclick="toggleBenchAnswer(${r.id}, ${x.question_id}, this)">
      <td>${x.position+1}</td>
      <td>${esc(x.question)} ${diffTag(qDiff(x.question_id))} ${retBadge(x.retrieval)}</td>
      <td class="sc" style="background:${x.error?'#374151':scoreColor(x.score)}">${x.error?'err':pct(x.score)}</td>
      <td class="sc">${x.error?'—':(x.passed?'✅':'❌')}</td>
      <td>${x.error?`<span style="color:#f87171">${esc(x.error)}</span>`
        : (miss.length || retMiss(x).length) ? `<ul class="miss" style="margin:0;padding-left:0;list-style:none">${miss.map(([ic,v])=>
            `<li title="${attr((v.verdict||'sin veredicto')+(v.evidence?' — «'+v.evidence+'»':''))}">${ic} ${esc(v.text)}</li>`).join('')}${retMiss(x).join('')}</ul>`
        : '<span class="muted" style="font-size:12px">todo presente</span>'}</td>
      <td class="sc" onclick="event.stopPropagation();${x.error?'':`openReview(${x.question_id})`}" title="Revisar esta respuesta">${revCell(x)}</td>
      <td class="sc">${x.seconds??''}</td></tr>`; }).join('') : '<tr><td colspan="7" class="muted">Ninguna pregunta en este filtro.</td></tr>')+'</table>';
}
async function toggleBenchAnswer(rid, qid, tr){
  const next = tr.nextElementSibling;
  if(next && next.classList.contains('bench-ans')){ next.remove(); return; }
  const row = document.createElement('tr'); row.className = 'bench-ans';
  row.innerHTML = `<td colspan="7" class="muted">cargando…</td>`;
  tr.after(row);
  try{
    const d = await bjson(`/api/bench/runs/${rid}/artifact?question_id=${qid}`);
    const md = s => (window.marked ? marked.parse(s||'') : `<pre>${esc(s)}</pre>`);
    row.innerHTML = `<td colspan="7">
      <div class="comps" style="margin:4px 0 8px">${(d.verdicts||[]).map(v=>compChip(v, v.verdict)).join('')}</div>
      ${(d.subqueries||[]).length>1?`<details open><summary>🧩 Buscó por partes (${d.subqueries.length} sub-búsquedas)</summary><ol style="margin:4px 0;padding-left:20px">${d.subqueries.map(q=>`<li>${esc(q)}</li>`).join('')}</ol></details>`:''}
      <details open><summary>💬 Respuesta del sistema</summary><div class="ans">${md(d.answer)}</div></details>
      ${d.expected_answer?`<details><summary>🎯 Respuesta esperada</summary><div class="ref">${esc(d.expected_answer)}</div></details>`:''}
      <details><summary>⚖️ Veredictos con evidencia</summary><ul>${(d.verdicts||[]).map(v=>
        `<li>${compChip(v, v.verdict)} → <b>${esc(v.verdict||'sin veredicto')}</b>${v.evidence?` — «${esc(v.evidence)}»`:''}</li>`).join('')}</ul></details>
      ${d.chunks?renderChunks(d.chunks, d.score_kind||'score').replace('<details open>','<details>'):''}
      <details><summary>🧾 Salida cruda del juez</summary><pre class="hyde-p">${esc(d.judge_raw)}</pre></details>
      ${d.hyde_passage?`<details><summary>🧪 Borrador HyDE</summary><div class="hyde-p">${esc(d.hyde_passage)}</div></details>`:''}
    </td>`;
  }catch(e){ row.innerHTML = `<td colspan="7" style="color:#f87171">${esc(e.message)}</td>`; }
}

// ── ✍️ Revisión humana ──────────────────────────────────────────────────────────
// Una pregunta a la vez. El veredicto del juez está OCULTO por default (👁 para verlo) para
// no sesgar a quien revisa; se vuelve a ocultar al cambiar de pregunta.
const RV_OPTS = [['presente','Presente'], ['parcial','Parcial'], ['ausente','Ausente']];
function rvList(){ return BENCH.detail.results.filter(x=>!x.error); }
async function openReview(qid){
  const list = rvList(); if(!list.length) return;
  let i = qid!=null ? list.findIndex(x=>x.question_id===qid) : list.findIndex(x=>!myReview(x.question_id));
  BENCH.rv = {i: Math.max(i,0), dirty: false};
  openModal('bench-review');
  await rvShow(BENCH.rv.i);
}
async function rvShow(i){
  const list = rvList(), x = list[i]; if(!x) return;
  const rv = BENCH.rv; rv.i = i; rv.dirty = false; rv.eye = false;
  const mine = myReview(x.question_id);
  rv.verdicts = mine ? [...mine.verdicts] : (x.verdicts||[]).map(()=>null);
  rv.rating = mine ? mine.rating : null;
  const done = list.filter(y=>myReview(y.question_id)).length;
  $('rv-head').innerHTML = `<b>Pregunta ${i+1} de ${list.length}</b> <span class="muted">· corrida #${BENCH.detail.id} · revisadas por ti: ${done}/${list.length}</span>
    ${mine?'<span class="tag rv-ok">ya la revisaste</span>':''}`;
  $('rv-prev').disabled = i===0; $('rv-next').disabled = i===list.length-1;
  $('rv-body').innerHTML = '<p class="muted">cargando…</p>';
  let d; try{ d = await bjson(`/api/bench/runs/${BENCH.detail.id}/artifact?question_id=${x.question_id}`); }
  catch(e){ $('rv-body').innerHTML = `<p style="color:#f87171">${esc(e.message)}</p>`; return; }
  if(BENCH.rv.i!==i) return;   // se navegó a otra mientras cargaba
  rv.d = d;
  const md = s => (window.marked ? marked.parse(s||'') : `<pre>${esc(s)}</pre>`);
  const others = revsOf(x.question_id).filter(v=>v!==mine);
  $('rv-body').innerHTML = `
    <div class="rv-q">${esc(x.question)} ${diffTag(qDiff(x.question_id))}</div>
    <div class="rv-cols">
      <div class="rv-ans"><div class="muted" style="font-size:12px;margin-bottom:4px">💬 Respuesta del sistema</div><div class="ans">${md(d.answer)}</div>
        ${d.expected_answer?`<details><summary>🎯 Respuesta esperada</summary><div class="ref">${esc(d.expected_answer)}</div></details>`:''}
        ${d.chunks?renderChunks(d.chunks, d.score_kind||'score').replace('<details open>','<details>'):''}
      </div>
      <div class="rv-side">
        <div class="row" style="margin:0 0 6px;justify-content:space-between"><b>¿Qué contiene la respuesta?</b>
          <button class="ghost" id="rv-eye" onclick="rvToggleEye()" title="Mostrar u ocultar lo que marcó el juez (Gemma)">👁 ver juez</button></div>
        <p class="muted" style="font-size:11px;margin:0 0 6px">En <b>must not</b>, «Presente» = el error SÍ aparece (eso es malo).</p>
        <div id="rv-comps"></div>
        <label class="f">Calificación global de la respuesta</label>
        <div class="rv-stars" id="rv-stars"></div>
        <label class="f">Comentario (qué está mal, qué falta, qué sobra)</label>
        <textarea id="rv-comment" style="min-height:80px">${esc(mine ? (mine.comment||'') : '')}</textarea>
        ${others.length?`<details style="margin-top:8px"><summary>Otras revisiones (${others.length})</summary>${others.map(v=>`<div class="muted" style="font-size:12px;margin:4px 0">${esc(v.reviewer)}: ${v.passed?'✅':'❌'} ${v.rating?v.rating+'★':''} ${v.comment?'— «'+esc(v.comment)+'»':''}</div>`).join('')}</details>`:''}
      </div>
    </div>`;
  $('rv-comment').addEventListener('input', ()=>{ BENCH.rv.dirty = true; });
  rvRenderComps(); rvRenderStars(); rvStatus();
  $('rv-del').hidden = !mine;
}
function rvRenderComps(){
  const rv = BENCH.rv, x = rvList()[rv.i], jv = (rv.d && rv.d.verdicts) || x.verdicts || [];
  $('rv-comps').innerHTML = jv.map((c,k)=>{
    const h = rv.verdicts[k], j = c.verdict || 'ausente';
    const judge = rv.eye ? `<div class="rv-judge ${h && h!==j ? 'diff':''}">🤖 juez: <b>${esc(j)}</b>${c.evidence?` — «${esc(c.evidence)}»`:''}</div>` : '';
    return `<div class="rv-comp ${c.kind}">
      <div><span class="comp ${c.kind}"><span class="k">${c.kind.replace('_',' ')}</span></span> ${esc(c.text)}</div>
      <div class="rv-seg">${RV_OPTS.map(([v,l])=>`<button class="${h===v?'on '+v:''}" onclick="rvSet(${k},'${v}')">${l}</button>`).join('')}</div>
      ${judge}</div>`; }).join('');
  $('rv-eye').textContent = rv.eye ? '🙈 ocultar juez' : '👁 ver juez';
}
function rvRenderStars(){
  const r = BENCH.rv.rating;
  $('rv-stars').innerHTML = [1,2,3,4,5].map(n=>`<button class="${r&&n<=r?'on':''}" onclick="rvRate(${n})" title="${['','Muy mala','Mala','Aceptable','Buena','Excelente'][n]}">★</button>`).join('') +
    `<span class="muted" style="font-size:12px;margin-left:8px">${r?['','Muy mala','Mala','Aceptable','Buena','Excelente'][r]:'sin calificar (opcional)'}</span>`;
}
function rvSet(k, v){ BENCH.rv.verdicts[k] = v; BENCH.rv.dirty = true; rvRenderComps(); rvStatus(); }
function rvRate(n){ BENCH.rv.rating = BENCH.rv.rating===n ? null : n; BENCH.rv.dirty = true; rvRenderStars(); }
function rvToggleEye(){ BENCH.rv.eye = !BENCH.rv.eye; rvRenderComps(); }
function rvStatus(msg, ok){
  const left = BENCH.rv.verdicts.filter(v=>!v).length;
  $('rv-status').innerHTML = msg ? `<span style="color:${ok===false?'#f87171':'#4ade80'}">${msg}</span>`
    : left ? `<span class="muted">faltan ${left} componente${left>1?'s':''} por marcar</span>` : '<span class="muted">listo para guardar</span>';
  $('rv-save').disabled = $('rv-save-next').disabled = left>0;
}
async function rvSave(next){
  const rv = BENCH.rv, x = rvList()[rv.i];
  try{
    const r = await bpost(`/api/bench/runs/${BENCH.detail.id}/reviews/${x.question_id}`,
                          {verdicts: rv.verdicts, rating: rv.rating, comment: $('rv-comment').value});
    rv.dirty = false;
    await loadReviews(BENCH.detail.id);
    const same = r.passed===x.passed;
    if(next && rv.i < rvList().length-1){ await rvGo(+1, true); return; }
    rvStatus(`Guardada · score ${pct(r.score)} ${r.passed?'✅ pasa':'❌ no pasa'}${same?'':' (el juez dijo lo contrario)'}`);
    $('rv-del').hidden = false;
  }catch(e){ rvStatus(esc(e.message), false); }
}
async function rvDelete(){
  const x = rvList()[BENCH.rv.i];
  if(!confirm('¿Borrar tu revisión de esta pregunta?')) return;
  try{ await bjson(`/api/bench/runs/${BENCH.detail.id}/reviews/${x.question_id}`, {method:'DELETE'});
    await loadReviews(BENCH.detail.id); await rvShow(BENCH.rv.i); }
  catch(e){ rvStatus(esc(e.message), false); }
}
async function rvGo(step, force){
  if(!force && BENCH.rv.dirty && !confirm('Tienes cambios sin guardar en esta pregunta. ¿Descartarlos?')) return;
  const n = rvList().length; let i = BENCH.rv.i + step;
  if(step===0){   // siguiente sin revisar (después de la actual, y si no, desde el inicio)
    const list = rvList(), pend = k => !myReview(list[k].question_id);
    i = -1; for(let k=1; k<=n; k++){ const j=(BENCH.rv.i+k)%n; if(pend(j)){ i=j; break; } }
    if(i<0){ rvStatus('¡Ya revisaste todas las preguntas de esta corrida! 🎉'); return; }
  }
  if(i<0 || i>=n) return;
  await rvShow(i);
}
function rvClose(){
  if(BENCH.rv && BENCH.rv.dirty && !confirm('Tienes cambios sin guardar. ¿Cerrar de todos modos?')) return;
  closeModal('bench-review');
  renderBenchDetail(); loadBenchRuns();
}
document.addEventListener('keydown', e=>{
  if($('bench-review').hidden) return;
  const typing = /^(TEXTAREA|INPUT|SELECT)$/.test(e.target.tagName);
  if(e.key==='Escape'){ e.preventDefault(); e.stopImmediatePropagation(); rvClose(); }
  else if((e.metaKey||e.ctrlKey) && e.key==='Enter'){ e.preventDefault(); if(!$('rv-save-next').disabled) rvSave(true); }
  else if(!typing && e.key==='ArrowLeft') rvGo(-1);
  else if(!typing && e.key==='ArrowRight') rvGo(+1);
}, true);

// ── Comparación ─────────────────────────────────────────────────────────────────
async function compareBenchRuns(){
  const ids = checkedRuns();
  if(ids.length < 2){ bmsg('Marca ☑ al menos 2 corridas en la tabla para comparar.', false); return; }
  try{ BENCH.cmp = await Promise.all(ids.map(id=>bjson('/api/bench/runs/'+id))); }
  catch(e){ bmsg(esc(e.message), false); return; }
  renderCompare();
  benchSub('compare');
}
function renderCompare(){
  const runs = BENCH.cmp; if(!runs) return;
  // Filas = preguntas (por id, así una pregunta editada sigue alineada entre corridas y
  // dos preguntas con el mismo texto no se funden); columnas = corridas.
  const qkey = x => x.question_id ?? x.question;
  const qs = []; const seen = new Set();
  runs.forEach(r=>r.results.forEach(x=>{ if(!seen.has(qkey(x))){ seen.add(qkey(x)); qs.push(x); } }));
  const get = (r,q) => r.results.find(y=>qkey(y)===qkey(q));
  const two = runs.length===2;
  const delta = q => { const a=get(runs[0],q), b=get(runs[1],q); return (a&&b&&!a.error&&!b.error) ? b.score-a.score : null; };
  let rows = qs;
  if(BENCH.cmpOnlyDiff) rows = qs.filter(q=>{ const vals = runs.map(r=>{ const x=get(r,q); return x ? (x.error?'e':x.passed+':'+x.score.toFixed(2)) : '-'; });
    return new Set(vals).size>1; });
  if(two && BENCH.cmpSort==='delta') rows = [...rows].sort((a,b)=>(delta(a)??0)-(delta(b)??0));
  const cell = (r,q) => { const x = get(r,q);
    if(!x) return '<td class="sc muted">—</td>';
    if(x.error) return '<td class="sc" style="background:#374151">err</td>';
    return `<td class="sc" style="background:${scoreColor(x.score)}">${pct(x.score)}${x.passed?' ✓':''}</td>`; };
  // Si la pregunta se editó entre corridas, sus criterios (componentes) no son los mismos y el
  // cambio de score no significa que el sistema mejoró o empeoró: se marca ⚙.
  const crit = x => (x && !x.error) ? (x.verdicts||[]).map(v=>v.kind+':'+v.text).join('|') : null;   // con error no hay criterios que comparar
  const changed = q => new Set(runs.map(r=>crit(get(r,q))).filter(v=>v!=null)).size > 1;
  const dcell = q => { const d = delta(q), ch = changed(q);
    const mark = ch ? ' <span title="Los criterios de esta pregunta cambiaron entre corridas: el Δ no es comparable">⚙</span>' : '';
    if(d==null) return `<td class="sc muted">—${mark}</td>`;
    const s = Math.round(100*d); return `<td class="sc delta ${ch?'':s>0?'up':s<0?'down':''}">${s>0?'+':''}${s}${mark}</td>`; };
  const mrow = (label, fn) => `<tr><td><b>${label}</b></td>${runs.map(r=>`<td class="sc">${fn(r.metrics||{})}</td>`).join('')}${two?'<td></td>':''}</tr>`;
  $('bench-compare-out').innerHTML = `
    <div class="row" style="margin-top:0">
      <label class="chk"><input type="checkbox" ${BENCH.cmpOnlyDiff?'checked':''} onchange="BENCH.cmpOnlyDiff=this.checked;renderCompare()"> solo preguntas que cambian</label>
      ${two?`<select onchange="BENCH.cmpSort=this.value;renderCompare()">
        <option value="pos">orden del set</option><option value="delta" ${BENCH.cmpSort==='delta'?'selected':''}>más empeoradas primero</option></select>`:''}
      <span class="muted" style="font-size:12px">${rows.length} de ${qs.length} preguntas</span>
    </div>
    <table><tr><th>pregunta</th>${runs.map(r=>`<th>#${r.id} ${esc(r.label||'')}<div class="runcfg">${esc(cfgSummary(r.config))}</div></th>`).join('')}
      ${two?`<th title="diferencia de score (puntos) de #${runs[1].id} respecto a #${runs[0].id}">Δ</th>`:''}</tr>
    <tr><td><b>score medio</b></td>${runs.map(r=>`<td class="sc" style="background:${scoreColor((r.metrics||{}).score)}">${pct((r.metrics||{}).score)}</td>`).join('')}${two?'<td></td>':''}</tr>
    ${mrow('pasan', m=>pct(m.pass_rate))}${mrow('cobertura de must', m=>pct(m.must_coverage))}${mrow('violaciones', m=>m.violations??'—')}${mrow('🔎 artículos recuperados', m=>pct(m.retrieval_recall))}
    ${DIFFS.map(([d,l])=>{ const st = runs.map(r=>diffStats(r.results)[d]); if(!st.some(Boolean)) return '';
      return `<tr><td><b>score ${diffTag(d)}</b></td>${st.map(x=>`<td class="sc" style="background:${scoreColor(x&&x.score)}">${x?pct(x.score):'—'}</td>`).join('')}${two?'<td></td>':''}</tr>`; }).join('')}`+
    rows.map(q=>`<tr><td>${esc(q.question)} ${diffTag(qDiff(q.question_id))}${changed(q)?' <span class="tag" style="border:1px solid #4b5563;color:#c7cdd6" title="Se editaron los componentes de esta pregunta entre las corridas comparadas">⚙ criterios distintos</span>':''}</td>${runs.map(r=>cell(r,q)).join('')}${two?dcell(q):''}</tr>`).join('')+'</table>';
}
