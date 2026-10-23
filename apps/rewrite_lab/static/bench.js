// Tab "🧪 Benchmark" — sets de preguntas por tema, componentes esperados, corridas
// juzgadas por el LLM y comparación entre corridas. Backend: /api/bench/* (bench.py).
// Usa los helpers globales de index.html ($, esc, readJur, renderChunks, window.__topics),
// que ya existen cuando se llama a cualquiera de estas funciones.
//
// Estructura: barra fija (tema · set · menú ⋯ · ayuda) + tres sub-pestañas:
//   ▶ Correr y resultados (default) · 📝 Preguntas · 🗂️ Prompts · 📊 Comparar
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
// ⏱ Segundos promedio por etapa (metrics.avg_timings; solo corridas desde 2026-10-19).
const ETAPAS = [['filtro','filtro por estado'], ['descomponer','descomponer'], ['por_delito','descomponer por delito'],
                ['remisiones','seguir remisiones'], ['busqueda','búsqueda (con HyDE, descomposiciones y remisiones)'], ['respuesta','respuesta de Gemma'], ['juez','juez']];
const tiempos = t => t ? ETAPAS.filter(([e])=>t[e]!=null).map(([e,l])=>`${l} ${t[e].toFixed(1)} s`).join(' · ') : '';
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
// 🧾 Verificación de citas (sin LLM, citations.py): cada artículo que cita la respuesta, contra el corpus y el contexto.
// [icono, nombre, explicación corta visible, explicación larga (tooltip)]
const CIT = {
  en_contexto: ['🟢', 'con respaldo', 'venía en los documentos que trajo el buscador',
                'El artículo que cita el LLM venía en los fragmentos que recuperó el buscador: la cita está respaldada por los documentos.'],
  memoria:     ['🟡', 'sin fundamento', 'existe, pero el buscador no lo trajo: el LLM lo sacó de lo que ya sabía',
                'El artículo existe en la base, pero NO venía en los fragmentos del buscador: el LLM lo citó de lo que aprendió antes. Puede estar bien, pero no se puede comprobar con los documentos y puede estar desactualizado.'],
  cruzada:     ['🟠', 'ley mal atribuida', 'el LLM le puso el nombre de otra ley (ej. dice CDMX, pero es del Edomex)',
                'El LLM le puso a un artículo el nombre de una ley que no es la suya: escribe «art. 269 del Código Penal de la CDMX», pero el 269 que trajo el buscador es del Estado de México.'],
  inexistente: ['🔴', 'inventado', 'el artículo no existe en la base',
                'La ley está en la base pero ese artículo no: el LLM lo inventó o lo numeró mal (alucinación clásica).'],
  sin_ley:     ['⚪', 'sin ley identificable', 'no se sabe de qué ley es: no se pudo revisar',
                'El LLM escribió el artículo suelto, sin que se pueda saber de qué ley es: no se clasifica.'],
};
// «Sin respaldo en los documentos» = inventados + sin fundamento + ley mal atribuida (sobre los artículos revisados).
const citSinRespaldo = m => m.cit_unsupported != null ? m.cit_unsupported
  : (m.cit_n ? (m.cit_memory||0) + (m.cit_cross||0) + (m.cit_missing||0)/m.cit_n : null);
function citTags(c){
  if(!c) return '';
  const k = c.counts||{}, out = [];
  if((c.other_states||[]).length) out.push(`<span class="tag ret-bad" title="${attr('Cita artículos de un código estatal que la pregunta no menciona: '+c.other_states.join(', '))}">🗺️ otro estado: ${esc(c.other_states.join(', '))}</span>`);
  if(k.inexistente) out.push(`<span class="tag ret-bad" title="${attr(CIT.inexistente[3])}">🔴 ${k.inexistente} inventado${k.inexistente>1?'s':''}</span>`);
  if(k.cruzada) out.push(`<span class="tag ret-part" title="${attr(CIT.cruzada[3])}">🟠 ${k.cruzada} ley mal atribuida</span>`);
  if(k.memoria) out.push(`<span class="tag ret-part" title="${attr(CIT.memoria[3])}">🟡 ${k.memoria} sin fundamento</span>`);
  return out.join(' ');
}
// Lista de citas de una respuesta (detalle expandido).
function citList(c){
  if(!c || !(c.items||[]).length) return '';
  const orden = Object.keys(CIT);
  const otro = new Set(c.other_states||[]), esOtro = i => otro.has(`${i.label} ${i.article}`);
  const items = [...c.items].sort((a,b)=>(esOtro(b)-esOtro(a)) || (orden.indexOf(b.clase)-orden.indexOf(a.clase)));
  return `<details ${items.some(i=>esOtro(i) || (i.clase!=='en_contexto'&&i.clase!=='sin_ley'))?'open':''}><summary>🧾 ¿De dónde salen los artículos que cita el LLM? (${items.length})</summary><ul style="margin:4px 0;padding-left:20px">${
    items.map(i=>`<li title="${attr(i.snippet||'')}">${CIT[i.clase][0]} <b>${esc(i.label||'¿?')} ${esc(i.article)}</b> — ${CIT[i.clase][1]} <span class="muted">(${CIT[i.clase][2]})</span>${esOtro(i)?' · <span style="color:#f87171">🗺️ de un estado que la pregunta no menciona</span>':''}${i.derogado?' · <span style="color:#fbbf24">derogado</span>':''}</li>`).join('')
  }</ul><p class="muted" style="font-size:11px;margin:2px 0">Pasa el ratón sobre una cita para ver dónde aparece en la respuesta.</p></details>`;
}
// Mismas métricas que citations.aggregate(), sobre un subconjunto de resultados.
function citAgg(rs){
  const ok = rs.filter(x=>!x.error && x.citations); if(!ok.length) return {};
  const t = Object.fromEntries(Object.keys(CIT).map(k=>[k, ok.reduce((a,x)=>a+((x.citations.counts||{})[k]||0),0)]));
  const n = t.en_contexto+t.memoria+t.cruzada+t.inexistente;
  const ap = ok.filter(x=>x.citations.other_states!=null);
  return {cit_n: n, cit_unknown: t.sin_ley, cit_context: n?t.en_contexto/n:null, cit_memory: n?t.memoria/n:null,
          cit_cross: n?t.cruzada/n:null, cit_missing: t.inexistente, cit_unsupported: n?(t.memoria+t.cruzada+t.inexistente)/n:null,
          other_state_n: ap.length, other_state_rate: ap.length ? ap.filter(x=>x.citations.other_states.length).length/ap.length : null};
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
const SUB_URL = {run: '', questions: 'preguntas', prompts: 'prompts', informes: 'informes', componentes: 'componentes', compare: 'comparar'};
function benchSub(name){
  BENCH.sub = name;
  document.querySelectorAll('.bsub button').forEach(b=>b.classList.toggle('active', b.dataset.sub===name));
  for(const s of ['run','questions','prompts','informes','componentes','compare']) $('bsub-'+s).hidden = (s!==name);
  if(name==='prompts') loadPrompts();
  if(name==='informes') loadInformes();
  if(name==='componentes') loadComponentes(); else clearTimeout(COMP.poll);
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
    // 🏷️ Etiqueta del system prompt
    $('bench-psel').addEventListener('change', ()=>{ const p = (BENCH.prompts||[]).find(x=>x.md5===$('bench-psel').value);
      if(p){ $('bench-system').value = p.text; promptStatus(); } });
    $('bench-system').addEventListener('input', ()=>{ clearTimeout(BENCH.ptimer); BENCH.ptimer = setTimeout(promptStatus, 400); });
    $('bench-pfilter').addEventListener('change', renderBenchRuns);
    $('bench-pdiff').addEventListener('click', diffPrompts);
    $('bench-preload').addEventListener('click', loadPrompts);
    $('bp-save').addEventListener('click', savePromptTag);
    $('bp-untag').addEventListener('click', untagPrompt);
    $('bp-cancel').addEventListener('click', ()=>closeModal('bench-prompt-modal'));
    $('bpt-close').addEventListener('click', ()=>closeModal('bench-ptext-modal'));
    $('bench-prompts').addEventListener('change', e=>{ if(e.target.classList.contains('bp-cmp')) $('bench-pdiff').disabled = checkedPrompts().length!==2; });
    document.querySelectorAll('.bss-diff').forEach(c=>c.addEventListener('change', ()=>subsetChanged()));
    $('bss-crit').addEventListener('change', ()=>subsetChanged());
    $('bss-run').addEventListener('change', ()=>subsetChanged());
    $('bss-all').addEventListener('click', ()=>{ BENCH.sub_manual = null; renderSubset(); });
    $('bss-none').addEventListener('click', ()=>{ BENCH.sub_manual = new Set(); renderSubset(); });
    $('bss-reset').addEventListener('click', resetSubset);
    $('bss-list').addEventListener('change', e=>{
      if(!e.target.classList.contains('bss-q')) return;
      BENCH.sub_manual = new Set([...document.querySelectorAll('.bss-q:checked')].map(c=>+c.value));
      renderSubset(false);
    });
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
  loadPrompts();
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
    const t = ts.find(x=>x.topic===BENCH.set.topic); if(t){ $('bench-system').value = t.system_prompt||''; promptStatus(); }
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
  promptStatus();
  renderQuestions();
  resetSubset(true);
  await loadBenchRuns();
  // Primera carga: aplica lo que pedía la URL (vista, corrida abierta, corridas comparadas).
  const w = BENCH.want; BENCH.want = null;
  // Sin ?set= en la URL (p. ej. /benchmark?vista=informes) se abre el set por omisión, y la vista pedida se aplica igual.
  if(w && (!w.set || String(w.set)===String(id))){
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
  $('bench-set-judge').value = s ? (s.judge_notes||'') : '';
  if(s) $('bench-set-topic').value = s.topic;
  else if($('bench-topic-filter').value) $('bench-set-topic').value = $('bench-topic-filter').value;
  $('bench-set-delete').style.display = s ? '' : 'none';
  openModal('bench-set-modal');
  $('bench-set-name').focus();
}
async function saveSet(thenEditJson){
  const body = {name:$('bench-set-name').value, topic:$('bench-set-topic').value, description:$('bench-set-desc').value,
                judge_notes:$('bench-set-judge').value};
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
  return `<span class="comp ${c.kind} ${cls}" title="${attr(title)}"><span class="k">${kindLabel(c.kind)}${w}</span>${esc(c.text)}</span>`;
}
// En la BD el tipo sigue siendo 'must_not'; en pantalla se llama «error» para que se redacte
// describiendo el error ("Omite…", "Confunde…") y no en negativo ("No omitir…").
const kindLabel = k => k==='must_not' ? '❌ error' : k;
function compCounts(comps){
  const n = k => comps.filter(c=>c.kind===k).length;
  return `<span class="cnt"><b>${n('must')}</b> must · <b>${n('should')}</b> should · <b>${n('must_not')}</b> error</span>`;
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
  row.innerHTML = `<select class="ck">${['must','should','must_not'].map(k=>`<option value="${k}" ${k===c.kind?'selected':''}>${kindLabel(k)}</option>`).join('')}</select>
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
  // «error» (must_not) en negativo = doble negación: "No omitir el artículo" aparece justo en las
  // respuestas correctas y el juez lo cuenta como error. El servidor rechaza los nuevos; aquí se
  // avisa antes. Los que ya estaban guardados así se dejan pasar (con aviso) para no trabar la edición.
  const old = new Set(((BENCH.editingQ||{}).components||[]).filter(c=>c.kind==='must_not').map(c=>c.text.trim()));
  const neg = components.filter(c=>c.kind==='must_not' && /^\s*(?:no|nunca|jamás|evitar|evita|sin)\b/i.test(c.text));
  const fresh = neg.filter(c=>!old.has(c.text));
  const negMsg = t => `El «error» describe lo que NO debe aparecer en la respuesta:\n\n«${t}»\n\nRedáctalo en positivo (p. ej. «Confunde robo con fraude» en vez de «No confundir robo con fraude»); así como está, una respuesta correcta contaría como error.`;
  if(fresh.length){ alert('❌ No se puede guardar. ' + negMsg(fresh[0].text)); return; }
  if(neg.length && !confirm('⚠️ ' + negMsg(neg[0].text) + '\n\n¿Guardar de todos modos?')) return;
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
  if(!(await ensurePromptTag())) return;
  const body = {set_id: BENCH.set.id, label: $('bench-label').value, setting: $('bench-setting').value,
    k: +$('bench-k').value, neighbors: $('bench-neighbors').checked, hyde: $('bench-hyde').checked,
    rerank: $('bench-rerank').checked, decompose: $('bench-decompose').value || false, route: $('bench-route').checked, gate: $('bench-gate').checked, remisiones: $('bench-remisiones').checked,
    system: $('bench-system').value, jurisdictions: readJur('bench-jur')};
  const sub = currentSubset();
  if(!sub.ids.length){ bmsg('No hay preguntas seleccionadas en «🎯 Qué preguntas correr».', false); return; }
  if(!sub.all){ body.question_ids = sub.ids; body.subset = sub.desc; }
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
  return [c.setting, 'k='+c.k, c.neighbors?'vecinos':'', c.hyde?'HyDE':'', c.rerank?'rerank':'', c.decompose?(c.decompose===true||c.decompose==='actual'?'descompone':'descompone ('+c.decompose+')'):'', c.route?'🧭 routing':'', c.gate?'🚧 filtro por estado':'', c.remisiones?'↪ remisiones':'', c.crimes?'⚖️ por delito'+(c.crime_extra_k!=null?` (+${c.crime_extra_k} chunks c/u)`:''):'',
          (c.jurisdictions||[]).length?'lugar='+c.jurisdictions.join('+'):'', c.judge_model?'juez '+c.judge_model:'', (c.judge_notes||'').trim()?'📋 criterios juez':'',
          (c.question_ids||[]).length ? `🎯 ${c.question_ids.length}${c.set_total?'/'+c.set_total:''} preg.${c.subset?' ('+c.subset+')':''}` : '']
    .filter(Boolean).join(' · ');
}
async function loadBenchRuns(){
  if(!BENCH.set) return;
  let runs; try{ runs = await bjson('/api/bench/runs?set_id='+BENCH.set.id); }catch(e){ return; }
  BENCH.runs = runs;
  fillPromptFilter();
  renderBenchRuns();
  fillSubsetRuns();
}
function renderBenchRuns(){
  const checked = new Set([...document.querySelectorAll('.bench-cmp:checked')].map(c=>+c.value));
  const all = BENCH.runs||[], pf = $('bench-pfilter').value;
  const runs = pf ? all.filter(r=>r.prompt_md5===pf) : all;
  const sel = BENCH.detail && BENCH.detail.id;
  $('bench-runs').innerHTML = runs.length ? `<table><tr><th title="marcar para comparar">☑</th><th>#</th><th>fecha</th><th>etiqueta / config</th><th title="Nombre del system prompt con que respondió el LLM (se pone en 🗂️ Prompts)">🏷️ prompt</th><th>estado</th>
    <th title="promedio del score por pregunta">score</th><th title="% de preguntas con todos los must y ningún must_not">pasan</th>
    <th title="% de componentes must presentes">must ✓</th><th title="must_not que aparecieron">viol.</th>
    <th title="% de los artículos necesarios (según los must de cita) que la búsqueda trajo al contexto — sin LLM, sin ruido">🔎 art.</th>
    <th title="🧾 Sin respaldo en los documentos: % de los artículos que cita el LLM que NO salen de los documentos del buscador = 🔴 inventados + 🟡 sin fundamento + 🟠 ley mal atribuida. Sin LLM.">🧾 sin respaldo</th>
    <th title="🔴 Artículos inventados: el LLM citó un artículo que no existe en la base (alucinación clásica). Con regex y la base de datos, sin LLM.">🔴 inventados</th>
    <th title="🗺️ % de respuestas que citan artículos de un código estatal que la pregunta no menciona (solo preguntas que mencionan un estado) — conteo con regex, sin LLM">🗺️ otro edo.</th><th>s/preg</th>
    <th title="Preguntas con revisión humana">✍️</th><th></th></tr>`+
    runs.map(r=>{ const m=r.metrics||{}; return `<tr class="clk ${r.id===sel?'sel':''}" onclick="showBenchRun(${r.id})">
      <td onclick="event.stopPropagation()"><input type="checkbox" class="bench-cmp" value="${r.id}" ${checked.has(r.id)?'checked':''}></td><td>${r.id}</td>
      <td style="white-space:nowrap">${esc((r.created_at||'').slice(5,16))}</td>
      <td>${esc(r.label||'—')}<div class="runcfg">${esc(cfgSummary(r.config))}</div></td>
      <td>${ptagChip(r)}</td>
      <td>${r.status==='running'?`⏳ ${r.done}/${r.n}`:esc(r.status)}${m.errors?` <span style="color:#f87171">(${m.errors} err)</span>`:''}</td>
      <td class="sc" style="background:${scoreColor(m.score)}">${pct(m.score)}</td>
      <td class="sc">${pct(m.pass_rate)}</td><td class="sc">${pct(m.must_coverage)}</td>
      <td class="sc">${m.violations??'—'}</td><td class="sc">${pct(m.retrieval_recall)}</td>
      <td class="sc">${m.cit_n!=null ? pct(citSinRespaldo(m)) : '<span class="muted">—</span>'}</td>
      <td class="sc"${m.cit_missing?' style="color:#f87171;font-weight:700"':''}>${m.cit_n!=null ? m.cit_missing : '<span class="muted">—</span>'}</td>
      <td class="sc">${m.other_state_rate!=null ? pct(m.other_state_rate) : '<span class="muted">—</span>'}</td><td class="sc">${m.avg_seconds??'—'}</td>
      <td class="sc">${r.reviewed ? `${r.reviewed}/${r.done}` : '<span class="muted">—</span>'}</td>
      <td onclick="event.stopPropagation()"><button class="danger" onclick="deleteBenchRun(${r.id}, ${r.reviewed||0})" title="Borrar corrida">🗑</button></td></tr>`; }).join('')+'</table>'
    : all.length ? '<p class="muted">Ninguna corrida de este set usó ese prompt.</p>'
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

// ── 🎯 Qué preguntas correr ─────────────────────────────────────────────────────
// Filtros (dificultad ∧ resultado en una corrida anterior) proponen una selección; las casillas
// de la lista permiten ajustarla a mano (BENCH.sub_manual). Cambiar un filtro descarta lo manual.
const SUB_CRITS = {
  fail: ['no pasaron', x=>!x.error && !x.passed],
  low: ['score < 70%', x=>!x.error && x.score < .7],
  viol: ['con violación', x=>x.violations>0],
  noret: ['🔎 no trajo el artículo', x=>!x.error && x.retrieval && x.retrieval.hit < x.retrieval.attainable],
  err: ['con error', x=>!!x.error],
};
BENCH.sub_runs = {};   // id → resultados de corridas usadas como filtro (caché)
function fillSubsetRuns(){
  const sel = $('bss-run'), prev = sel.value;
  const done = (BENCH.runs||[]).filter(r=>r.status!=='running' && r.done);
  sel.innerHTML = done.length ? done.map(r=>`<option value="${r.id}">#${r.id} ${esc(r.label||'')} · ${pct((r.metrics||{}).score)}${(r.config||{}).question_ids?' · parcial':''}</option>`).join('')
                              : '<option value="">(aún no hay corridas)</option>';
  if(prev && done.some(r=>String(r.id)===prev)) sel.value = prev;
  $('bss-crit').disabled = !done.length;
}
function resetSubset(quiet){
  document.querySelectorAll('.bss-diff').forEach(c=>{ c.checked = true; });
  $('bss-crit').value = ''; BENCH.sub_manual = null;
  if(!quiet) $('bench-subset').open = false;
  renderSubset();
}
async function subsetChanged(){
  BENCH.sub_manual = null;
  const rid = $('bss-run').value;
  if($('bss-crit').value && rid && !BENCH.sub_runs[rid]){
    $('bss-count').textContent = 'cargando la corrida…';
    try{ BENCH.sub_runs[rid] = (await bjson('/api/bench/runs/'+rid)).results; }
    catch(e){ bmsg(esc(e.message), false); return; }
  }
  renderSubset();
}
// Preguntas que proponen los filtros → [{q, res}] (res = su resultado en la corrida filtro).
function subsetCandidates(){
  if(!BENCH.set) return [];
  const diffs = new Set([...document.querySelectorAll('.bss-diff:checked')].map(c=>c.value));
  const crit = $('bss-crit').value, rid = $('bss-run').value, res = BENCH.sub_runs[rid];
  return BENCH.set.questions.filter(q=>q.components.length || q.expected_answer).map(q=>{
    const x = res ? res.find(y=>y.question_id===q.id) : null;
    return {q, x};
  }).filter(({q, x})=>{
    if(!diffs.has(q.difficulty||'')) return false;
    if(crit && res) return x && SUB_CRITS[crit][1](x);
    return true;
  });
}
function currentSubset(){
  const runnable = BENCH.set ? BENCH.set.questions.filter(q=>q.components.length || q.expected_answer) : [];
  const cand = subsetCandidates();
  const ids = BENCH.sub_manual ? runnable.map(q=>q.id).filter(id=>BENCH.sub_manual.has(id)) : cand.map(c=>c.q.id);
  const all = ids.length === runnable.length;
  const diffs = [...document.querySelectorAll('.bss-diff:checked')].map(c=>c.value);
  const crit = $('bss-crit').value;
  const parts = [];
  const dname = d => d ? diffLabel(d) : 'sin dificultad asignada';
  const excl = [...document.querySelectorAll('.bss-diff:not(:checked)')].map(c=>c.value);
  if(excl.length) parts.push(!diffs.length ? 'ninguna dificultad' : excl.length <= 2 ? 'sin ' + excl.map(dname).join(' ni ') : 'solo ' + diffs.map(dname).join('+'));
  if(crit && $('bss-run').value) parts.push(`${SUB_CRITS[crit][0]} en #${$('bss-run').value}`);
  if(BENCH.sub_manual) parts.push('elegidas a mano');
  return {ids, all, total: runnable.length, desc: parts.join(' · ')};
}
function renderSubset(rebuildList=true){
  if(!BENCH.set){ $('bss-list').innerHTML = ''; return; }
  const sub = currentSubset(), chosen = new Set(sub.ids);
  $('bench-subset-sum').textContent = sub.all ? `todas (${sub.total})` : `${sub.ids.length} de ${sub.total}${sub.desc?' · '+sub.desc:''}`;
  $('bench-subset-sum').style.color = sub.all ? '' : '#fbbf24';
  $('bss-count').textContent = `Se correrán ${sub.ids.length} de ${sub.total} preguntas` +
    (sub.ids.length && BENCH.runs && BENCH.runs[0] && (BENCH.runs[0].metrics||{}).avg_seconds ? ` · ~${Math.ceil(sub.ids.length*(BENCH.runs[0].metrics.avg_seconds)/60)} min` : '');
  $('bench-run').textContent = sub.all ? '▶ Correr benchmark' : `▶ Correr ${sub.ids.length} preguntas`;
  if(!rebuildList) return;
  // La lista muestra lo que proponen los filtros (y lo elegido a mano), con su score en la corrida filtro.
  const cand = subsetCandidates(), rid = $('bss-run').value, res = BENCH.sub_runs[rid];
  const shown = BENCH.sub_manual ? BENCH.set.questions.filter(q=>q.components.length || q.expected_answer).map(q=>({q, x: res && res.find(y=>y.question_id===q.id)}))
                                 : cand;
  const pos = new Map(BENCH.set.questions.map((q,i)=>[q.id, i+1]));
  $('bss-list').innerHTML = shown.length ? shown.map(({q, x})=>`<label><input type="checkbox" class="bss-q" value="${q.id}" ${chosen.has(q.id)?'checked':''}>
      <span class="muted">#${pos.get(q.id)}</span><span class="qt">${esc(q.question)} ${diffTag(q.difficulty)}</span>
      ${x ? `<span class="sc" style="background:${x.error?'#374151':scoreColor(x.score)}" title="score en #${rid}">${x.error?'err':pct(x.score)}</span>` : ''}</label>`).join('')
    : '<p class="muted" style="font-size:12px">Ninguna pregunta cumple estos filtros.</p>';
}
// Atajo desde el detalle de una corrida: deja preparado «solo las que no pasaron aquí».
async function rerunFailed(rid){
  document.querySelectorAll('.bss-diff').forEach(c=>{ c.checked = true; });
  $('bss-crit').value = 'fail'; $('bss-run').value = String(rid);
  await subsetChanged();
  const r = (BENCH.runs||[]).find(x=>x.id===rid);
  if(r && r.config){   // misma configuración que esa corrida, para que la comparación sea justa
    const c = r.config;
    if([...$('bench-setting').options].some(o=>o.value===c.setting)) $('bench-setting').value = c.setting;
    $('bench-k').value = String(c.k); $('bench-neighbors').checked = !!c.neighbors; $('bench-hyde').checked = !!c.hyde;
    $('bench-rerank').checked = !!c.rerank; $('bench-decompose').value = c.decompose === true ? 'actual' : (c.decompose || ''); $('bench-route').checked = !!c.route; $('bench-gate').checked = !!c.gate; $('bench-remisiones').checked = !!c.remisiones;
  }
  $('bench-subset').open = true;
  $('bench-subset').scrollIntoView({behavior:'smooth', block:'center'});
  bmsg(`Listo: ${currentSubset().ids.length} preguntas que no pasaron en #${rid}, con su misma configuración. Ajusta y pulsa ▶.`);
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
  ['otroedo', '🗺️ Cita otro estado', x=>!x.error && x.citations && (x.citations.other_states||[]).length>0],
  ['sinfuente', '🧾 Cita sin respaldo', x=>!x.error && x.citations && ['memoria','cruzada','inexistente'].some(k=>(x.citations.counts||{})[k])],
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
  $('bench-detail').innerHTML = `<h2 style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">Corrida #${r.id} ${esc(r.label||'')} ${ptagChip(r)}
      <span class="runcfg">${esc(cfgSummary(r.config))}</span>${r.status==='running'?`<span class="tag gap">en curso ${r.done}/${r.n}</span>`:''}
      <span style="flex:1"></span>${r.status!=='running' && r.results.some(x=>!x.passed)?`<button class="ghost" onclick="rerunFailed(${r.id})" title="Prepara una corrida solo con las preguntas que no pasaron aquí (no la arranca)">🎯 Re-correr las que no pasan</button>`:''}
      ${r.results.some(x=>!x.error)?`<button onclick="openReview()" title="Califica tú las respuestas, componente por componente">✍️ Revisar respuestas</button>`:''}</h2>
    <div class="cards">
      ${card('score medio', pct(m.score))}
      ${card('preguntas que pasan', pct(m.pass_rate), `${nPass} de ${r.results.length}`)}
      ${card('cobertura de must', pct(m.must_coverage))}
      ${card('violaciones must_not', m.violations??'—')}
      ${m.avg_timings ? card('⏱ segundos por pregunta', m.avg_seconds??'—', esc(tiempos(m.avg_timings))) : ''}
      ${m.retrieval_recall!=null ? card('artículos recuperados 🔎', pct(m.retrieval_recall), `${pct(m.retrieval_full)} de las preguntas con todos`) : ''}
      ${m.cit_n!=null ? (()=>{ const ln = (k, v, red) => `<div class="m" title="${attr(CIT[k][3])}"><span>${CIT[k][0]} ${CIT[k][1]}</span><b${red?' style="color:#f87171"':''}>${v}</b></div>
            <div class="muted" style="font-size:11px;margin:-2px 0 4px 22px">${CIT[k][2]}</div>`;
          return `<div class="card" style="min-width:300px"><h3>🧾 ¿De dónde salen los artículos que cita el LLM?</h3>
          <div class="muted" style="font-size:11px;margin-bottom:6px">Para cada artículo que cita el LLM (Gemma) se revisa con regex y la base de datos (sin otro LLM) si existe y si venía en los documentos que trajo el buscador.</div>
          <div class="m" title="Inventados + sin fundamento + ley mal atribuida"><span><b>🧾 sin respaldo en los documentos</b></span><b style="font-size:18px">${pct(citSinRespaldo(m))}</b></div>
          <div class="muted" style="font-size:11px;margin:-2px 0 6px 22px">el artículo no sale de los documentos: suma de los tres de abajo</div>
          ${ln('inexistente', m.cit_missing, m.cit_missing)}${ln('memoria', pct(m.cit_memory))}${ln('cruzada', pct(m.cit_cross))}
          <hr style="border:0;border-top:1px solid #374151;margin:6px 0">
          ${ln('en_contexto', pct(m.cit_context))}
          <div class="muted" style="font-size:11px;margin-top:4px">${m.cit_n} artículos revisados · ${m.cit_unknown} sin ley identificable (no se pudieron revisar)${m.cit_derogated?` · ${m.cit_derogated} a artículos derogados`:''}</div>
          <div class="muted" style="font-size:11px;margin-top:4px">⚠️ «Con respaldo» no significa «del estado correcto»: un artículo del Edomex que trajo el buscador cuenta aquí como respaldado aunque la pregunta sea de la CDMX. Eso se mide en 🗺️ cita otro estado.</div></div>`; })()
        : (r.status!=='running' && r.artifact_key ? `<div class="card"><h3>🧾 ¿De dónde salen los artículos que cita el LLM?</h3><p class="muted" style="font-size:12px;margin:4px 0">Corrida anterior a la verificación de citas.</p><button class="ghost" onclick="calcCitations(${r.id})">🧾 Calcular ahora</button></div>` : '')}
      ${m.other_state_rate!=null ? `<div class="card" title="Solo preguntas que mencionan al menos un estado"><h3>🗺️ cita otro estado</h3>
          <div style="font-size:22px;font-weight:700">${pct(m.other_state_rate)}</div>
          <div class="muted" style="font-size:12px">de ${m.other_state_n} respuestas · <b>conteo con regex</b> (sin LLM)</div>
          <div class="muted" style="font-size:11px;margin-top:4px">La pregunta dice un estado y el LLM cita artículos (reales, con su ley correcta) del código penal de OTRO estado.</div>
          ${m.other_state_judge_rate!=null ? `<div class="m" style="margin-top:4px"><span>según el juez (LLM)</span><b>${pct(m.other_state_judge_rate)}</b></div>
          <div class="muted" style="font-size:11px;margin:-2px 0 4px 0">el juez (otro LLM) solo lo cuenta si el artículo de otro estado se presenta como aplicable al caso</div>
          <div class="m"><span>acuerdo regex ↔ juez (LLM)</span><b>${pct(m.other_state_agreement)}</b></div>
          <div class="muted" style="font-size:11px;margin:-2px 0 0 0">% de preguntas donde el conteo con regex y el juez dicen lo mismo</div>` : ''}</div>` : ''}
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
      <td>${esc(x.question)} ${diffTag(qDiff(x.question_id))} ${retBadge(x.retrieval)} ${citTags(x.citations)}</td>
      <td class="sc" style="background:${x.error?'#374151':scoreColor(x.score)}">${x.error?'err':pct(x.score)}</td>
      <td class="sc">${x.error?'—':(x.passed?'✅':'❌')}</td>
      <td>${x.error?`<span style="color:#f87171">${esc(x.error)}</span>`
        : (miss.length || retMiss(x).length) ? `<ul class="miss" style="margin:0;padding-left:0;list-style:none">${miss.map(([ic,v])=>
            `<li title="${attr((v.verdict||'sin veredicto')+(v.evidence?' — «'+v.evidence+'»':''))}">${ic} ${esc(v.text)}</li>`).join('')}${retMiss(x).join('')}</ul>`
        : '<span class="muted" style="font-size:12px">todo presente</span>'}</td>
      <td class="sc" onclick="event.stopPropagation();${x.error?'':`openReview(${x.question_id})`}" title="Revisar esta respuesta">${revCell(x)}</td>
      <td class="sc">${x.seconds??''}</td></tr>`; }).join('') : '<tr><td colspan="7" class="muted">Ninguna pregunta en este filtro.</td></tr>')+'</table>';
}
async function calcCitations(rid){
  try{ await bjson(`/api/bench/runs/${rid}/citations`, {method:'POST'}); }
  catch(e){ bmsg(esc(e.message), false); return; }
  bmsg('🧾 Citas verificadas para la corrida #'+rid, true);
  await loadBenchRuns(); await showBenchRun(rid, true);
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
      ${(d.routes||[]).length?`<details open><summary>🧭 Routing por código</summary><ul style="margin:4px 0;padding-left:20px">${d.routes.map(r=>`<li>«${esc(r.match)}» → ${esc(r.source.replace(/\.md$/,''))}</li>`).join('')}</ul></details>`:''}
      ${(d.subqueries||[]).length>1?`<details open><summary>🧩 Buscó por partes (${d.subqueries.length} sub-búsquedas)</summary><ol style="margin:4px 0;padding-left:20px">${d.subqueries.map(q=>`<li>${esc(q)}</li>`).join('')}</ol></details>`:''}
      <details open><summary>💬 Respuesta del sistema</summary><div class="ans">${md(d.answer)}</div></details>
      ${citList(((BENCH.detail||{}).results||[]).find(y=>y.question_id===qid)?.citations || d.citations)}
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
        <p class="muted" style="font-size:11px;margin:0 0 6px">En <b>❌ error</b>, «Presente» = el error SÍ aparece (eso es malo).</p>
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
      <div><span class="comp ${c.kind}"><span class="k">${kindLabel(c.kind)}</span></span> ${esc(c.text)}</div>
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
// Mismas métricas que aggregate() de bench.py, sobre un subconjunto de resultados.
function metricsOver(rs){
  const ok = rs.filter(x=>!x.error), n = ok.length, mt = ok.reduce((a,x)=>a+(x.must_total||0),0);
  const rr = ok.map(x=>x.retrieval).filter(r=>r && r.attainable);
  const att = rr.reduce((a,r)=>a+r.attainable,0);
  return {score: n ? ok.reduce((a,x)=>a+x.score,0)/n : null, pass_rate: n ? ok.filter(x=>x.passed).length/n : null,
          must_coverage: mt ? ok.reduce((a,x)=>a+(x.must_ok||0),0)/mt : null,
          violations: ok.reduce((a,x)=>a+(x.violations||0),0),
          retrieval_recall: att ? rr.reduce((a,r)=>a+Math.min(r.hit,r.attainable),0)/att : null, ...citAgg(rs)};
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
  // Si alguna corrida es parcial (🎯), los promedios de cada una no se refieren a las mismas
  // preguntas: se recalculan solo sobre las preguntas que están en TODAS.
  const idSets = runs.map(r=>new Set(r.results.map(qkey)));
  const common = [...idSets[0]].filter(k=>idSets.every(st=>st.has(k)));
  const partial = idSets.some(st=>st.size !== common.length);
  const commonSet = new Set(common);
  let rows = qs;
  if(partial) rows = rows.filter(q=>commonSet.has(qkey(q)));   // las que no están en todas no se pueden comparar
  if(BENCH.cmpOnlyDiff) rows = rows.filter(q=>{ const vals = runs.map(r=>{ const x=get(r,q); return x ? (x.error?'e':x.passed+':'+x.score.toFixed(2)) : '-'; });
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
  const met = r => partial ? metricsOver(r.results.filter(x=>commonSet.has(qkey(x)))) : (r.metrics||{});
  const resOf = r => partial ? r.results.filter(x=>commonSet.has(qkey(x))) : r.results;
  const mrow = (label, fn) => `<tr><td><b>${label}</b></td>${runs.map(r=>`<td class="sc">${fn(met(r))}</td>`).join('')}${two?'<td></td>':''}</tr>`;
  $('bench-compare-out').innerHTML = `
    <div class="row" style="margin-top:0">
      <label class="chk"><input type="checkbox" ${BENCH.cmpOnlyDiff?'checked':''} onchange="BENCH.cmpOnlyDiff=this.checked;renderCompare()"> solo preguntas que cambian</label>
      ${two?`<select onchange="BENCH.cmpSort=this.value;renderCompare()">
        <option value="pos">orden del set</option><option value="delta" ${BENCH.cmpSort==='delta'?'selected':''}>más empeoradas primero</option></select>`:''}
      <span class="muted" style="font-size:12px">${rows.length} de ${qs.length} preguntas</span>
    </div>
    ${new Set(runs.map(r=>((r.config||{}).judge_notes||'').trim())).size > 1 ? `<p class="muted" style="font-size:12px;margin:4px 0;color:#fbbf24" title="${attr(runs.map(r=>'#'+r.id+': '+(((r.config||{}).judge_notes||'').trim()||'(sin criterios)')).join('\n\n'))}">📋 Las corridas se calificaron con <b>criterios para el juez distintos</b>: parte del Δ puede venir del juez y no del sistema (pasa el ratón para verlos).</p>` : ''}
    ${new Set(runs.map(r=>r.prompt_md5)).size > 1 ? `<p class="muted" style="font-size:12px;margin:4px 0">🏷️ Las corridas usan <b>system prompts distintos</b>: ${runs.map(r=>'#'+r.id+' '+ptagChip(r)).join(' · ')}</p>` : ''}
    ${partial ? `<p class="muted" style="font-size:12px;margin:4px 0;color:#fbbf24">🎯 Hay corridas parciales: se comparan solo las <b>${common.length}</b> preguntas que están en todas (promedios incluidos).</p>` : ''}
    <table><tr><th>pregunta</th>${runs.map(r=>`<th>#${r.id} ${esc(r.label||'')}<div>${ptagChip(r)}</div><div class="runcfg">${esc(cfgSummary(r.config))}</div></th>`).join('')}
      ${two?`<th title="diferencia de score (puntos) de #${runs[1].id} respecto a #${runs[0].id}">Δ</th>`:''}</tr>
    <tr><td><b>score medio</b>${partial?` <span class="muted" style="font-size:11px">(${common.length} comunes)</span>`:''}</td>${runs.map(r=>`<td class="sc" style="background:${scoreColor(met(r).score)}">${pct(met(r).score)}</td>`).join('')}${two?'<td></td>':''}</tr>
    ${mrow('pasan', m=>pct(m.pass_rate))}${mrow('cobertura de must', m=>pct(m.must_coverage))}${mrow('violaciones', m=>m.violations??'—')}${mrow('🔎 artículos recuperados', m=>pct(m.retrieval_recall))}
    ${runs.some(r=>(r.metrics||{}).avg_timings) ? mrow('⏱ s por pregunta (total)', m=>m.avg_seconds??'—')
      + ETAPAS.map(([e,l])=>runs.some(r=>((r.metrics||{}).avg_timings||{})[e]!=null) ? mrow('&nbsp;&nbsp;⏱ '+l, m=>(m.avg_timings||{})[e]!=null ? m.avg_timings[e].toFixed(1)+' s' : '—') : '').join('') : ''}
    ${runs.some(r=>(r.metrics||{}).cit_n!=null) ? mrow('🧾 sin respaldo en los documentos', m=>m.cit_n!=null?pct(citSinRespaldo(m)):'—')
      +mrow('&nbsp;&nbsp;🔴 inventados', m=>m.cit_n!=null?m.cit_missing:'—')+mrow('&nbsp;&nbsp;🟡 sin fundamento', m=>m.cit_n!=null?pct(m.cit_memory):'—')
      +mrow('&nbsp;&nbsp;🟠 ley mal atribuida', m=>m.cit_n!=null?pct(m.cit_cross):'—') : ''}
    ${runs.some(r=>(r.metrics||{}).other_state_rate!=null) ? mrow('🗺️ cita otro estado', m=>m.other_state_rate!=null?pct(m.other_state_rate):'—') : ''}
    ${DIFFS.map(([d,l])=>{ const st = runs.map(r=>diffStats(resOf(r))[d]); if(!st.some(Boolean)) return '';
      return `<tr><td><b>score ${diffTag(d)}</b></td>${st.map(x=>`<td class="sc" style="background:${scoreColor(x&&x.score)}">${x?pct(x.score):'—'}</td>`).join('')}${two?'<td></td>':''}</tr>`; }).join('')}`+
    rows.map(q=>`<tr><td>${esc(q.question)} ${diffTag(qDiff(q.question_id))}${changed(q)?' <span class="tag" style="border:1px solid #4b5563;color:#c7cdd6" title="Se editaron los componentes de esta pregunta entre las corridas comparadas">⚙ criterios distintos</span>':''}</td>${runs.map(r=>cell(r,q)).join('')}${two?dcell(q):''}</tr>`).join('')+'</table>';
}

// ── 🗂️ Prompts: nombre de cada system prompt ────────────────────────────────────
// La etiqueta va pegada al md5 del texto (bench_prompt_tags), no a la corrida: las corridas
// viejas con el mismo texto quedan etiquetadas solas. Backend: /api/bench/prompts (bench.py).
const short = md5 => (md5||'').slice(0,8);
function ptagChip(r){
  if(r.prompt_tag) return `<span class="ptag" title="system prompt · huella ${attr(short(r.prompt_md5))}">🏷️ ${esc(r.prompt_tag)}</span>`;
  return r.prompt_md5 ? `<span class="ptag none" title="Este system prompt aún no tiene nombre: ponlo en 🗂️ Prompts">sin etiqueta · ${esc(short(r.prompt_md5))}</span>` : '';
}
const checkedPrompts = () => [...document.querySelectorAll('.bp-cmp:checked')].map(c=>c.value);
// 🧩 Componentes: cada llamada al LLM contra su propio objetivo (componentes.py, /api/componentes).
const COMP = {sel: null, vista: null, corrida: null, poll: null, lista: []};
// Todo lo de «descomponer» va en una sola tarjeta con su propia sección: recall (¿ayuda al buscador?) y obediencia de
// cada versión del prompt (¿hace lo que dice su regla?).
const HYDE_IDS = ['hyde', 'hyde_recall'];
const DESC_IDS = ['division_recall', 'descomponer', 'desc_solo_lugar', 'desc_solo_pregunta', 'desc_lugar_y_pregunta', 'desc_libre',
                  'desc_libre_corto', 'desc_libre_max2'];
const DESC_OBED = [['descomponer', 'actual', 'Su prompt dice «solo por lugar» (el que se usa hoy)'],
  ['desc_solo_lugar', 'solo por lugar', 'Divide solo si compara estados, códigos o conceptos'],
  ['desc_solo_pregunta', 'solo por pregunta', 'Divide solo si el mensaje hace varias preguntas'],
  ['desc_lugar_y_pregunta', 'por lugar y por pregunta', 'Divide en los dos casos'],
  ['desc_libre', 'libre', 'El LLM decide; solo se revisan sus reglas (máx. 4 búsquedas, sin estados ajenos)'],
  ['desc_libre_corto', 'libre (prompt mínimo)', 'Como «libre», con un prompt de una línea'],
  ['desc_libre_max2', 'libre, máximo 2', 'Como «libre», pero con máximo 2 búsquedas']];
const cpct = x => x == null ? '—' : (x * 100).toFixed(0) + ' %';
// Tabla «Costo y efecto de cada opción» (componentes_efectos.json): cuánto cuesta y cuánto cambia los benchmarks.
async function compEfectos(){
  let d; try{ d = await bjson('/api/componentes/efectos'); }catch(e){ return; }
  COMP.efectos = d;
  const sig = x => x.ic && (x.ic[0] > 0 || x.ic[1] < 0);
  const f = v => (v > 0 ? '+' : '') + v.toFixed(1);
  const score = o => o.score.length ? o.score.map(x => `<span title="IC 95 %: ${x.ic[0]} a ${x.ic[1]}" style="white-space:nowrap;${sig(x) ? `color:${x.dif > 0 ? '#4ade80' : '#f87171'};font-weight:700` : ''}">set ${esc(x.set)}: ${f(x.dif)}${sig(x) ? '✱' : ''}</span>`).join('<br>') : '<span class="muted">no medido</span>';
  const recall = o => o.recall.length ? o.recall.map(x => `<span style="white-space:nowrap">set ${esc(x.set)}: ${x.de} → <b>${x.a}</b> %</span>`).join('<br>') : '<span class="muted">—</span>';
  const sets = (d.sets || []).map(x => `<tr><td style="white-space:nowrap"><b>${x.set === 'recall' ? '' : 'Set '}${esc(x.set === 'recall' ? '' : x.set)}</b> ${esc(x.nombre)}</td><td>${esc(x.prueba)}</td></tr>`).join('');
  $('comp-efectos').innerHTML = (sets ? `<div class="bcard" style="margin-bottom:10px"><h3 style="margin:0 0 4px;font-size:14px">Los sets de preguntas</h3>
    <div style="overflow-x:auto"><table class="comp-tab">${sets}</table></div></div>` : '') +
    `<div class="bcard" style="margin-bottom:10px"><h3 style="margin:0 0 4px;font-size:14px">Costo y efecto de cada opción</h3>
    <p class="muted" style="font-size:12px;margin:0 0 6px">${esc(d.nota || '')} Actualizado: ${esc(d.actualizado || '')}.</p>
    <div style="overflow-x:auto"><table class="comp-tab"><tr><th>Opción</th><th>Qué se compara</th><th>Costo</th><th>Recall</th><th>Score (puntos)</th><th>Veredicto</th></tr>
    ${d.opciones.map(o => `<tr><td><b>${esc(o.opcion)}</b></td><td class="muted">${esc(o.compara)}<div style="font-size:11px">${esc(o.fuente)}</div></td>
      <td>${esc(o.costo)}</td><td>${recall(o)}</td><td>${score(o)}${o.otro ? `<div class="muted" style="font-size:11px;margin-top:4px">${esc(o.otro)}</div>` : ''}</td>
      <td>${esc(o.veredicto)}</td></tr>`).join('')}</table></div></div>`;
}
async function loadComponentes(){
  clearTimeout(COMP.poll);
  if(!$('comp-efectos').innerHTML) await compEfectos();
  try{ COMP.lista = await bjson('/api/componentes'); }catch(e){ $('comp-cards').innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  const tarjetas = COMP.lista.filter(c => !DESC_IDS.includes(c.id) && !HYDE_IDS.includes(c.id)).map(c => {
    const m = (c.ultima || {}).metricas || {};
    const grupos = Object.entries(m.por_grupo || {}).map(([g, v]) => `${esc(g)} ${v.aciertos}/${v.n}`).join(' · ');
    const pv = m.por_version;
    const estado = c.corriendo ? '<span class="muted">⏳ corriendo…</span>'
      : (c.ultima && pv) ? `<div style="font-size:12px">${Object.entries(pv).map(([v, t]) =>
          `${esc(v)}: <b>${cpct((t.todas || {}).recall)}</b>`).join('<br>')}</div>`
      : c.ultima ? `<div class="muted" style="font-size:12px">Obedece (hace lo que dice su prompt):</div><span class="comp-tasa ${m.tasa >= 0.9 ? 'comp-ok' : m.tasa < 0.7 ? 'comp-mal' : ''}">${cpct(m.tasa)}</span>
          <span class="muted" style="font-size:12px"> ${m.aciertos ?? 0}/${(m.n ?? 0) - (m.errores ?? 0)} casos · prompt ${esc(c.ultima.prompt_md5.slice(0, 8))}${c.ultima.prompt_md5 !== c.prompt_md5 ? ' (el prompt cambió desde entonces)' : ''}</span>`
      : '<span class="muted">sin corridas todavía</span>';
    return `<div class="bcard comp-card ${COMP.sel === c.id ? 'on' : ''}" data-c="${c.id}">
      <div style="font-weight:700">${c.icono} ${esc(c.nombre)}</div>
      <div class="muted" style="font-size:12px;margin:4px 0 8px">${esc(c.objetivo)}</div>
      <div>${estado}</div>${grupos ? `<div class="muted" style="font-size:12px">${grupos}</div>` : ''}
      ${compEfectoCorto(c.id)}
      ${m.segundos_media != null ? `<div class="muted" style="font-size:12px;margin-top:6px">Tiempo de la llamada al LLM: <b>${m.segundos_media.toFixed(2)} s</b></div>` : ''}
      <div class="muted" style="font-size:12px;margin-top:6px">${c.casos} casos (${c.revisados} revisados)</div></div>`;
  });
  // Tarjeta de descomponer: el mejor recall y la obediencia del prompt actual.
  const rec = COMP.lista.find(c => c.id === 'division_recall'), act = COMP.lista.find(c => c.id === 'descomponer');
  const pv = ((rec || {}).ultima || {}).metricas?.por_version || {};
  const orden = Object.entries(pv).map(([v, t]) => [v, (t.todas || {}).recall]).sort((a, b) => (b[1] ?? -1) - (a[1] ?? -1));
  const sin = (pv['sin dividir'] || {}).todas || {};
  const corriendoDesc = COMP.lista.some(c => DESC_IDS.includes(c.id) && c.corriendo);
  tarjetas.splice(1, 0, `<div class="bcard comp-card ${COMP.vista === 'descomponer' ? 'on' : ''}" data-c="descomponer-grupo">
    <div style="font-weight:700">🧩 Descomponer</div>
    <div class="muted" style="font-size:12px;margin:4px 0 8px">Dividir la pregunta en varias búsquedas. Dos pruebas: si ayuda al buscador (recall) y si cada versión del prompt hace lo que dice su regla (obediencia).</div>
    ${corriendoDesc ? '<div class="muted">⏳ corriendo…</div>' : ''}
    ${orden.length ? `<div class="muted" style="font-size:12px">Recall (artículos esperados en los 10 primeros resultados):</div>
      <div><b>${esc(orden[0][0])}</b> <span class="comp-tasa comp-ok">${cpct(orden[0][1])}</span> <span class="muted" style="font-size:12px">· sin dividir ${cpct(sin.recall)}</span></div>` : ''}
    ${act && act.ultima ? `<div class="muted" style="font-size:12px;margin-top:4px">Obedece su prompt (versión actual): <b>${cpct(act.ultima.metricas?.tasa)}</b></div>` : ''}</div>`);
  // Tarjeta de HyDE: recall (con y sin HyDE) y sus reglas.
  const hr = COMP.lista.find(c => c.id === 'hyde_recall'), hy = COMP.lista.find(c => c.id === 'hyde');
  const hpv = ((hr || {}).ultima || {}).metricas?.por_version || {};
  tarjetas.splice(2, 0, `<div class="bcard comp-card ${COMP.vista === 'hyde' ? 'on' : ''}" data-c="hyde-grupo">
    <div style="font-weight:700">🧪 HyDE</div>
    <div class="muted" style="font-size:12px;margin:4px 0 8px">El LLM escribe un borrador del artículo que respondería y se busca con él. Dos pruebas: si ayuda al buscador (recall) y si el borrador cumple sus reglas.</div>
    ${(hr || {}).corriendo || (hy || {}).corriendo ? '<div class="muted">⏳ corriendo…</div>' : ''}
    ${hpv['con HyDE'] ? `<div class="muted" style="font-size:12px">Recall (10 primeros resultados):</div>
      <div>sin HyDE ${cpct((hpv['sin HyDE'].todas || {}).recall)} → <span class="comp-tasa comp-ok">${cpct((hpv['con HyDE'].todas || {}).recall)}</span></div>` : compEfectoCorto('hyde')}
    ${hy && hy.ultima ? `<div class="muted" style="font-size:12px;margin-top:4px">Cumple sus reglas: <b>${cpct(hy.ultima.metricas?.tasa)}</b></div>` : ''}</div>`);
  $('comp-cards').innerHTML = tarjetas.join('');
  document.querySelectorAll('.comp-card').forEach(el => el.addEventListener('click', () => compAbrir(el.dataset.c)));
  if(COMP.vista === 'descomponer') compDescomponer(); else if(COMP.vista === 'hyde') compHyde(); else if(COMP.sel) compDetalle();
  if(COMP.lista.some(c => c.corriendo)) COMP.poll = setTimeout(loadComponentes, 4000);
}
function compAbrir(id){
  if(id === 'descomponer-grupo'){ COMP.vista = 'descomponer'; COMP.sel = null; }
  else if(id === 'hyde-grupo'){ COMP.vista = 'hyde'; COMP.sel = null; }
  else { COMP.vista = null; COMP.sel = id; }
  COMP.corrida = null; loadComponentes();
}
// Efecto de una opción en una línea (de la tabla «Costo y efecto»): para que la obediencia nunca aparezca sola.
function compEfectoCorto(id){
  const o = ((COMP.efectos || {}).opciones || []).find(x => x.componente === id);
  if(!o) return '';
  const sig = x => x.ic && (x.ic[0] > 0 || x.ic[1] < 0);
  const sc = o.score.filter(sig).map(x => `set ${x.set} ${x.dif > 0 ? '+' : ''}${x.dif}✱`).join(', ');
  return `<div style="font-size:12px;margin-top:6px"><span class="muted">Efecto:</span> <b>${esc(o.veredicto)}</b>${sc ? ` <span class="muted">(score: ${sc})</span>` : ''}</div>`;
}
// Sección de HyDE: 1) recall con y sin HyDE; 2) reglas del borrador.
async function compHyde(){
  const L = id => COMP.lista.find(c => c.id === id) || {};
  const rec = L('hyde_recall'), m = (rec.ultima || {}).metricas || {}, hy = L('hyde'), mh = (hy.ultima || {}).metricas || {};
  $('comp-detalle').innerHTML = `<div class="bcard" style="margin-top:10px">
    <h3 style="margin:0 0 4px;font-size:15px">🧪 HyDE</h3>
    <h3 style="margin:14px 0 2px;font-size:14px">1 · Recall: ¿ayuda al buscador?</h3>
    <p class="muted" style="font-size:13px;margin:0">Para cada pregunta de los sets 3, 13 y 14 con artículos esperados, se busca con y sin HyDE (sin dividir la
      pregunta, sin respuesta ni juez) y se cuenta cuántos de esos artículos salen entre los 10 primeros resultados.</p>
    ${m.por_version ? compTablaRecall(m) : '<p class="muted">Sin corridas todavía en esta página (el 22-oct se midió con un script: sin → con HyDE, set 3: 76 → 84 %, set 13: 42 → 71 %, set 14: 52 → 65 %).</p>'}
    <div class="row" style="margin:6px 0"><button class="ghost" data-run="hyde_recall" ${rec.corriendo ? 'disabled' : ''}>▶ Correr recall (~10 min)</button>
      <button class="ghost" data-ver="hyde_recall">Historial y pregunta por pregunta</button></div>
    <h3 style="margin:18px 0 2px;font-size:14px">2 · Reglas: ¿el borrador cumple su prompt?</h3>
    <p class="muted" style="font-size:13px;margin:0">Sin números de artículo y sin nombrar estados que la pregunta no nombra.
      Cumple: <b>${cpct(mh.tasa)}</b>${mh.segundos_media != null ? ` · tiempo de la llamada: ${mh.segundos_media.toFixed(2)} s` : ''}</p>
    <div class="row" style="margin:6px 0"><button class="ghost" data-run="hyde" ${hy.corriendo ? 'disabled' : ''}>▶ Correr reglas</button>
      <button class="ghost" data-ver="hyde">Ver casos</button></div>
    <div id="comp-sub"></div></div>`;
  document.querySelectorAll('#comp-detalle [data-run]').forEach(b => b.onclick = async () => {
    try{ const r = await bpost(`/api/componentes/${b.dataset.run}/correr`); bmsg(`Corrida #${r.corrida} en marcha`, true); loadComponentes(); }
    catch(e){ bmsg(esc(e.message), false); }
  });
  document.querySelectorAll('#comp-detalle [data-ver]').forEach(b => b.onclick = () => { COMP.sel = b.dataset.ver; COMP.corrida = null; compDetalle('comp-sub'); });
  if(COMP.sel) compDetalle('comp-sub');
}
// Sección de descomponer: 1) recall de las 7 formas de dividir; 2) obediencia de cada versión del prompt.
async function compDescomponer(){
  const L = id => COMP.lista.find(c => c.id === id) || {};
  const rec = L('division_recall'), m = (rec.ultima || {}).metricas || {};
  const obed = DESC_OBED.map(([id, nombre, regla]) => {
    const c = L(id), mm = (c.ultima || {}).metricas || {}, g = mm.por_grupo || {};
    const debe = g['debe dividir'] || g['comparativas'], nodebe = g['no debe dividir'] || g['no comparativas'];
    const f = x => x ? `${x.aciertos}/${x.n}` : '—';
    return `<tr><td><b>${esc(nombre)}</b><div class="muted" style="font-size:12px">${esc(regla)}</div></td>
      <td>${c.corriendo ? '⏳' : `<b>${cpct(mm.tasa)}</b>`}</td><td>${f(debe)}</td><td>${f(nodebe)}</td><td>${mm.segundos_media != null ? mm.segundos_media.toFixed(2) + ' s' : '—'}</td>
      <td style="white-space:nowrap"><button class="ghost" data-run="${id}" ${c.corriendo ? 'disabled' : ''}>▶</button>
        <button class="ghost" data-ver="${id}">Ver casos</button></td></tr>`;
  }).join('');
  $('comp-detalle').innerHTML = `<div class="bcard" style="margin-top:10px">
    <h3 style="margin:0 0 4px;font-size:15px">🧩 Descomponer</h3>
    <h3 style="margin:14px 0 2px;font-size:14px">1 · Recall: ¿ayuda al buscador?</h3>
    <p class="muted" style="font-size:13px;margin:0">Para cada pregunta de los sets 3, 13 y 14 con artículos esperados, se busca con cada forma de dividir
      (sin respuesta ni juez) y se cuenta cuántos de esos artículos salen entre los 10 primeros resultados.
      ${rec.ultima ? `Última corrida: #${rec.ultima.id} (${esc((rec.ultima.fecha || '').slice(0, 16))}).` : ''}</p>
    ${m.por_version ? compTablaRecall(m) : '<p class="muted">Sin corridas todavía.</p>'}
    <div class="row" style="margin:6px 0"><button class="ghost" data-run="division_recall" ${rec.corriendo ? 'disabled' : ''}>▶ Correr recall (~35 min)</button>
      <button class="ghost" data-ver="division_recall">Historial y pregunta por pregunta</button></div>
    <h3 style="margin:18px 0 2px;font-size:14px">2 · Obediencia: ¿cada versión del prompt hace lo que dice su regla?</h3>
    <p class="muted" style="font-size:13px;margin:0">Solo se llama a «descomponer» con cada pregunta (sin búsqueda ni juez) y se revisa si dividió cuando su
      regla lo pide y si dejó entera la pregunta cuando no. Las etiquetas de «compara» y «varias preguntas» son automáticas (no revisadas).</p>
    <div style="overflow-x:auto"><table class="comp-tab"><tr><th>Versión del prompt</th><th>Obedece</th><th>Divide cuando debe</th><th>Deja entera cuando debe</th><th>Segundos por llamada</th><th></th></tr>${obed}</table></div>
    <div id="comp-sub"></div></div>`;
  document.querySelectorAll('#comp-detalle [data-run]').forEach(b => b.onclick = async () => {
    try{ const r = await bpost(`/api/componentes/${b.dataset.run}/correr`); bmsg(`Corrida #${r.corrida} en marcha`, true); loadComponentes(); }
    catch(e){ bmsg(esc(e.message), false); }
  });
  document.querySelectorAll('#comp-detalle [data-ver]').forEach(b => b.onclick = () => { COMP.sel = b.dataset.ver; COMP.corrida = null; compDetalle('comp-sub'); });
  if(COMP.sel) compDetalle('comp-sub');
}
async function compDetalle(destino = 'comp-detalle'){
  const c = COMP.lista.find(x => x.id === COMP.sel); if(!c) return;
  const corridas = await bjson(`/api/componentes/${c.id}/corridas`);
  if(COMP.corrida == null && corridas.length) COMP.corrida = corridas[0].id;
  const filas = corridas.map(r => {
    const m = r.metricas || {}, g = Object.entries(m.por_grupo || {}).map(([k, v]) => `${esc(k)} ${v.aciertos}/${v.n}`).join(' · ');
    return `<tr class="${r.id === COMP.corrida ? 'sel' : ''}" style="cursor:pointer" data-r="${r.id}"><td>#${r.id}</td><td>${esc((r.fecha || '').slice(0, 16))}</td>
      <td><code>${esc(r.prompt_md5.slice(0, 8))}</code>${r.prompt_md5 === c.prompt_md5 ? ' <span class="pill">actual</span>' : ''}</td>
      <td>${r.status === 'running' ? `⏳ ${r.done}/${r.n}` : m.por_version ? 'recall por versión ↓' : `<b>${cpct(m.tasa)}</b> (${m.aciertos ?? 0}/${(m.n ?? 0) - (m.errores ?? 0)})`}</td>
      <td class="muted">${g}${m.errores ? ` · ${m.errores} con error` : ''}</td><td class="muted">${m.segundos_media ?? '—'} s</td></tr>`;
  }).join('');
  $(destino).innerHTML = `<div class="bcard" style="margin-top:10px">
    <div class="row" style="margin:0"><b>${c.icono} ${esc(c.nombre)}</b><span style="flex:1"></span>
      <button class="ghost" id="comp-casos-btn">📝 Casos (JSON)</button>
      <button id="comp-correr" ${c.corriendo ? 'disabled' : ''}>▶ Correr prueba</button></div>
    <details style="margin-top:8px"><summary class="muted">Prompt actual · <code>${esc(c.prompt_md5.slice(0, 8))}</code></summary><pre class="comp-pre" style="white-space:pre-wrap;font:12px/1.4 ui-monospace,monospace">${esc(c.prompt)}</pre></details>
    <div id="comp-casos-edit"></div>
    <h3 style="margin:12px 0 4px;font-size:13px;color:#9aa4b2">Corridas</h3>
    ${corridas.length ? `<table class="comp-tab"><tr><th>#</th><th>Fecha</th><th>Prompt</th><th>Aciertos</th><th>Por grupo</th><th>s/caso</th></tr>${filas}</table>` : '<p class="muted">Todavía no hay corridas: ▶ Correr prueba.</p>'}
    <div id="comp-res"></div></div>`;
  $('comp-correr').onclick = compCorrer;
  $('comp-casos-btn').onclick = compCasos;
  document.querySelectorAll(`#${destino} tr[data-r]`).forEach(tr => tr.onclick = () => { COMP.corrida = +tr.dataset.r; compDetalle(destino); });
  if(COMP.corrida) compResultados(COMP.corrida);
}
// Cómo mostrar la salida de cada componente, en corto.
function compSalida(comp, s){
  if(s == null) return '—';
  if(comp === 'filtro') return (s.lugares || []).map(l => `${l.texto} → ${l.estado || '¿?'} (${l.rol})`).join('<br>') +
    `<div class="muted">tipo: ${esc(s.tipo || '—')}${s.teorica ? ' · teórica' : ''}${s.depende_del_estado ? ' · depende del estado' : ''}</div>`;
  if(Array.isArray(s)) return s.map((x, i) => `${i + 1}. ${esc(x)}`).join('<br>');
  return `<pre>${esc(String(s))}</pre>`;
}
function compTablaRecall(m){
  const pv = m.por_version || {}, x0 = Object.values(pv)[0] || {};
  const sets = Object.keys(x0).filter(t => t.startsWith('set ')).sort((a, b) => parseInt(a.slice(4)) - parseInt(b.slice(4)));
  const tiposP = ['comparativa', 'varias preguntas', 'varias conductas', 'otra'].filter(t => x0[t]);
  const seg = ts => ts.segundos ? `${ts.segundos.media.toFixed(1)} ± ${ts.segundos.de.toFixed(1)} s` : '<span class="muted">—</span>';
  const conPalabras = Object.values(pv).some(v => v.palabras);
  const pal = ts => ts.palabras ? `${Math.round(ts.palabras.media).toLocaleString('es-MX')} ± ${Math.round(ts.palabras.de).toLocaleString('es-MX')}` : '<span class="muted">—</span>';
  const mejor = t => Math.max(...Object.values(pv).map(v => (v[t] || {}).recall ?? -1));
  const orden = Object.entries(pv).sort((a, b) => ((b[1].todas || {}).recall ?? -1) - ((a[1].todas || {}).recall ?? -1));
  const tabla = (cols, conTiempo) => `<div style="overflow-x:auto"><table class="comp-tab"><tr><th>Versión</th>${cols.map(t => `<th>${esc(t)}<div class="muted" style="font-weight:normal">${x0[t] ? x0[t].preguntas + ' preg.' : ''}</div></th>`).join('')}${conTiempo ? '<th>Tiempo por pregunta<div class="muted" style="font-weight:normal">búsqueda completa</div></th>' : ''}${conTiempo && conPalabras ? '<th>Palabras del contexto<div class="muted" style="font-weight:normal">lo que lee el LLM</div></th>' : ''}</tr>
    ${orden.map(([v, ts]) => `<tr><td><b>${esc(v)}</b></td>${cols.map(t => { const c = ts[t];
      return c ? `<td${c.recall === mejor(t) ? ' class="comp-ok"' : ''}>${cpct(c.recall)} <span class="muted">${c.aciertos}/${c.gold}</span></td>` : '<td class="muted">—</td>'; }).join('')}${conTiempo ? `<td>${seg(ts)}</td>` : ''}${conTiempo && conPalabras ? `<td>${pal(ts)}</td>` : ''}</tr>`).join('')}
    </table></div>`;
  return `<h3 style="margin:12px 0 4px;font-size:13px;color:#9aa4b2">Recall por set: artículos esperados entre los 10 primeros resultados del buscador</h3>
    ${tabla(['todas', ...sets], true)}
    ${tiposP.length ? `<h3 style="margin:12px 0 4px;font-size:13px;color:#9aa4b2">Recall por tipo de pregunta</h3>${tabla(tiposP, false)}` : ''}
    <p class="muted" style="font-size:12px">En verde, la mejor versión de cada columna. Una pregunta puede ser de varios tipos.
    «Tiempo por pregunta» = HyDE + la división + todas las búsquedas, sin respuesta ni juez. Las corridas anteriores al 23 de octubre no separan por set ni guardan el tiempo.</p>`;
}
async function compResultados(rid){
  const res = await bjson(`/api/componentes/corridas/${rid}`), comp = COMP.sel;
  if(['division_recall', 'hyde_recall', 'rerank_recall', 'contexto_recall'].includes(comp)){
    const run = (await bjson(`/api/componentes/${comp}/corridas`)).find(r => r.id === rid) || {};
    $('comp-res').innerHTML = compTablaRecall(run.metricas || {}) + `<details><summary class="muted">Pregunta por pregunta (${res.length})</summary>
      <div style="overflow-x:auto"><table class="comp-tab"><tr><th>Pregunta</th><th>Tipos</th><th>Artículos esperados</th><th>Aciertos por versión</th></tr>
      ${res.map(r => { const s = r.salida || {}; return `<tr><td>${esc(r.entrada)}</td><td class="muted">${esc((s.tipos || []).join(', ') || 'otra')}</td><td>${s.gold ?? '—'}</td>
        <td>${r.error ? esc(r.error) : Object.entries(s.aciertos || {}).map(([v, h]) => `${esc(v)}: ${h}`).join('<br>')}</td></tr>`; }).join('')}
      </table></div></details>`;
    return;
  }
  const mal = res.filter(r => r.ok !== true).length;
  $('comp-res').innerHTML = `<h3 style="margin:12px 0 4px;font-size:13px;color:#9aa4b2">Corrida #${rid}: ${res.length} casos · ${mal} fallos (primero)</h3>
    <div style="overflow-x:auto"><table class="comp-tab"><tr><th></th><th>Entrada</th><th>Esperado</th><th>Salió</th><th>Por qué</th></tr>
    ${res.map(r => {
      const d = r.detalle || {}, por = r.error ? esc(r.error) : esc([].concat(d.falla || [], d.fallas || []).join(' · '))
        + (d.aviso ? `<div style="color:#fbbf24">⚠ ${esc(d.aviso)}</div>` : '');
      return `<tr><td>${r.ok === true ? '✅' : r.ok === false ? '❌' : '⚠️'}</td><td>${esc(r.entrada)}</td>
        <td><pre>${esc(JSON.stringify(r.esperado))}</pre></td><td>${compSalida(comp, r.salida)}</td><td class="muted">${por}</td></tr>`;
    }).join('')}</table></div>`;
}
async function compCorrer(){
  try{ const r = await bpost(`/api/componentes/${COMP.sel}/correr`); COMP.corrida = r.corrida; bmsg(`Corrida #${r.corrida} en marcha`, true); loadComponentes(); }
  catch(e){ bmsg(esc(e.message), false); }
}
async function compCasos(){
  const box = $('comp-casos-edit');
  if(box.innerHTML){ box.innerHTML = ''; return; }
  const casos = await bjson(`/api/componentes/${COMP.sel}/casos`);
  const limpio = casos.map(({id, ...k}) => k);
  box.innerHTML = `<p class="muted" style="font-size:12px;margin:8px 0 4px">Cada caso: <code>entrada</code>, <code>esperado</code> (objeto), y opcionales
    <code>fuente</code>, <code>nota</code>, <code>revisado</code>. Guardar reemplaza todos los casos; las corridas anteriores conservan su copia.</p>
    <textarea id="comp-json" style="min-height:260px">${esc(JSON.stringify(limpio, null, 1))}</textarea>
    <div class="row"><button id="comp-guardar">💾 Guardar casos</button></div>`;
  $('comp-guardar').onclick = async () => {
    let datos; try{ datos = JSON.parse($('comp-json').value); }catch(e){ bmsg('JSON inválido: ' + esc(e.message), false); return; }
    try{ const r = await bjson(`/api/componentes/${COMP.sel}/casos`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(datos)});
      bmsg(`${r.casos} casos guardados`, true); box.innerHTML = ''; loadComponentes(); }
    catch(e){ bmsg(esc(e.message), false); }
  };
}

// 📑 Informes: páginas fijas en static/informes/ (lista en index.json), una por informe.
async function loadInformes(){
  const box = $('bench-informes');
  const r = await fetch('/api/bench/informes');
  const list = r.ok ? await r.json() : [];
  box.innerHTML = list.length ? list.map(x => `<div class="bcard"><a href="/benchmark/informe/${esc(x.slug)}" style="font-weight:700;font-size:15px">${esc(x.titulo)} ↗</a>
      <div class="muted" style="font-size:13px;margin-top:4px">${esc(x.resumen || '')}</div></div>`).join('')
    : '<p class="muted">Todavía no hay informes.</p>';
}

async function loadPrompts(){
  try{ BENCH.prompts = await bjson('/api/bench/prompts'); }catch(e){ bmsg(esc(e.message), false); return; }
  const tagged = BENCH.prompts.filter(p=>p.tag);
  const prev = $('bench-psel').value;
  $('bench-psel').innerHTML = '<option value="">— elegir —</option>' +
    tagged.map(p=>`<option value="${p.md5}">${esc(p.tag)}${p.current_for.length?' · actual del tema':''} · ${p.n_runs} corridas</option>`).join('');
  if(prev) $('bench-psel').value = prev;
  renderPrompts();
  fillPromptFilter();
  promptStatus();
}
function renderPrompts(){
  const ps = BENCH.prompts||[], untagged = ps.filter(p=>!p.tag).length;
  $('bench-pcount').innerHTML = `${ps.length} prompts distintos` + (untagged ? ` · <span style="color:#fbbf24">⚠️ ${untagged} sin etiqueta</span>` : '');
  const was = new Set(checkedPrompts());
  const runsTxt = p => p.runs.length > 8 ? p.runs.slice(0,3).map(x=>'#'+x).join(', ')+' … '+p.runs.slice(-3).map(x=>'#'+x).join(', ') : p.runs.map(x=>'#'+x).join(', ');
  const who = e => esc((e||'').split('@')[0]);
  $('bench-prompts').innerHTML = ps.length ? `<table><tr><th title="Marca dos para comparar sus textos">☑</th><th>🏷️ etiqueta</th><th>nota</th>
      <th title="Huella del texto (md5): el mismo texto da siempre la misma huella">huella</th><th>tamaño</th><th>corridas</th><th>sets</th><th>usado</th><th></th></tr>` +
    ps.map(p=>`<tr class="${p.tag?'':'puntag'}">
      <td><input type="checkbox" class="bp-cmp" value="${p.md5}" ${was.has(p.md5)?'checked':''}></td>
      <td>${p.tag ? `<span class="ptag">🏷️ ${esc(p.tag)}</span>` : '<span class="ptag none">sin etiqueta</span>'}
        ${p.current_for.length ? `<div class="muted" style="font-size:11px" title="Es el system prompt actual de este tema: el que usa una corrida si no se cambia el texto">⭐ actual de: ${esc(p.current_for.map(topicLabel).join(', '))}</div>` : ''}
        <div class="muted" style="font-size:11px">${esc(p.text.slice(0,90).replace(/\s+/g,' '))}…</div></td>
      <td style="font-size:12px;max-width:260px">${esc(p.note||'')}${p.tag && p.updated_by ? `<div class="muted" style="font-size:11px">por ${who(p.updated_by)} · ${esc((p.updated_at||'').slice(0,10))}</div>` : ''}</td>
      <td><code>${short(p.md5)}</code></td><td class="sc">${p.text.length.toLocaleString()}</td>
      <td style="font-size:12px"><b>${p.n_runs}</b>${p.runs.length?` <span class="muted">(${runsTxt(p)})</span>`:''}</td>
      <td style="font-size:12px;max-width:220px" title="${attr(p.sets.join('\n'))}">${p.sets.length > 2 ? `${esc(p.sets[0])} <span class="muted">y ${p.sets.length-1} sets más</span>` : esc(p.sets.join(' · '))}</td>
      <td style="font-size:12px;white-space:nowrap">${p.first_run ? esc(p.first_run.slice(0,10))+(p.last_run.slice(0,10)!==p.first_run.slice(0,10)?' → '+esc(p.last_run.slice(0,10)):'') : '<span class="muted">sin corridas</span>'}
        ${p.run_by.length ? `<div class="muted" style="font-size:11px">${p.run_by.map(who).join(', ')}</div>` : ''}</td>
      <td style="white-space:nowrap"><button class="ghost" onclick="showPromptText('${p.md5}')" title="Ver el texto completo">👁</button>
        <button class="${p.tag?'ghost':''}" onclick="openPromptTag('${p.md5}')">${p.tag?'✏️':'🏷️ Ponerle nombre'}</button>
        <button class="ghost" onclick="usePrompt('${p.md5}')" title="Usarlo en la próxima corrida">▶</button></td></tr>`).join('') + '</table>'
    : '<p class="muted">Aún no hay corridas ni prompts etiquetados.</p>';
  $('bench-pdiff').disabled = checkedPrompts().length!==2;
}
// Filtro de la tabla de corridas: los prompts que usan las corridas de este set.
function fillPromptFilter(){
  const sel = $('bench-pfilter'), prev = sel.value, seen = new Map();
  for(const r of BENCH.runs||[]) if(r.prompt_md5) seen.set(r.prompt_md5, r.prompt_tag || 'sin etiqueta · '+short(r.prompt_md5));
  sel.innerHTML = '<option value="">🏷️ todos los prompts</option>' + [...seen].map(([m,t])=>`<option value="${m}">🏷️ ${esc(t)}</option>`).join('');
  sel.value = seen.has(prev) ? prev : '';
  sel.hidden = seen.size < 2 && !sel.value;
}
// Estado del prompt del formulario de corrida: ¿tiene nombre? Si no, pide uno antes de correr.
async function promptStatus(){
  if(!BENCH.set){ $('bench-psum').textContent = ''; return; }
  const text = $('bench-system').value;
  let lk; try{ lk = await bpost('/api/bench/prompts/lookup', {text, topic: BENCH.set.topic}); }catch(e){ return; }
  if(text !== $('bench-system').value) return;   // el texto cambió mientras se consultaba
  BENCH.plook = lk;
  $('bench-psel').value = (BENCH.prompts||[]).some(p=>p.md5===lk.md5 && p.tag) ? lk.md5 : '';
  if(lk.tag){
    $('bench-psum').innerHTML = `<span class="ptag">🏷️ ${esc(lk.tag)}</span>`;
    $('bench-pstatus').innerHTML = `<span class="muted">Huella <code>${short(lk.md5)}</code> · ${lk.length.toLocaleString()} caracteres · usado en ${lk.n_runs} corridas${lk.note?' · '+esc(lk.note):''}</span>`;
  }else{
    const keep = $('bench-pnew') ? [$('bench-pnew').value, $('bench-pnote').value] : ['', ''];
    $('bench-psum').innerHTML = `<span class="ptag none">⚠️ prompt sin etiqueta</span>`;
    $('bench-pstatus').innerHTML = `<span style="color:#fbbf24">⚠️ Este texto ${lk.n_runs ? `ya se usó en ${lk.n_runs} corridas pero` : 'es nuevo:'} no tiene nombre. Pónselo antes de correr:</span>
      <input type="text" id="bench-pnew" maxlength="60" placeholder="etiqueta, p. ej. penal-sencillo-v3" value="${attr(keep[0])}">
      <input type="text" id="bench-pnote" placeholder="nota (opcional): qué cambia" value="${attr(keep[1])}">
      <span class="muted" style="width:100%">Huella <code>${short(lk.md5)}</code> · ${lk.length.toLocaleString()} caracteres</span>`;
  }
}
// Antes de correr: si el prompt no tiene nombre, lo guarda con el que se escribió (o pide uno).
async function ensurePromptTag(){
  if(!$('bench-system').value.trim() && BENCH.set){   // vacío = el del tema: se muestra para que se vea qué se corre
    const t = (window.__topics||[]).find(x=>x.topic===BENCH.set.topic); if(t) $('bench-system').value = t.system_prompt||'';
  }
  await promptStatus();
  const lk = BENCH.plook; if(!lk || lk.tag) return true;
  const tag = ($('bench-pnew').value||'').trim();
  if(!tag){ $('bench-sys').open = true; $('bench-pnew').focus();
    bmsg('⚠️ El system prompt no tiene etiqueta: escribe un nombre en «⚙️ System prompt» antes de correr.', false); return false; }
  try{ await bjson('/api/bench/prompts/'+lk.md5, {method:'PUT', headers:{'Content-Type':'application/json'},
         body: JSON.stringify({tag, note: $('bench-pnote').value, text: $('bench-system').value})}); }
  catch(e){ $('bench-sys').open = true; bmsg(esc(e.message), false); return false; }
  await loadPrompts();
  return true;
}
function usePrompt(md5){
  const p = (BENCH.prompts||[]).find(x=>x.md5===md5); if(!p) return;
  $('bench-system').value = p.text; benchSub('run'); $('bench-sys').open = true; promptStatus();
  $('bench-sys').scrollIntoView({behavior:'smooth', block:'center'});
}
async function openPromptTag(md5){
  const p = (BENCH.prompts||[]).find(x=>x.md5===md5); if(!p) return;
  BENCH.ptagging = md5;
  $('bp-tag').value = p.tag||''; $('bp-note').value = p.note||'';
  $('bp-untag').hidden = !p.tag;
  $('bp-info').innerHTML = `Huella <code>${short(md5)}</code> · ${p.text.length.toLocaleString()} caracteres · ${p.n_runs} corridas · «${esc(p.text.slice(0,80).replace(/\s+/g,' '))}…»`;
  $('bp-history').innerHTML = '';
  openModal('bench-prompt-modal'); $('bp-tag').focus();
  try{ const h = await bjson(`/api/bench/prompts/${md5}/history`);
    const verb = {crear:'puso', editar:'cambió a', quitar:'quitó'};
    $('bp-history').innerHTML = h.length ? '<b>Historial</b><br>' + h.map(x=>`${esc((x.changed_at||'').slice(0,16))} · ${esc((x.changed_by||'?').split('@')[0])} ${verb[x.action]||x.action} «${esc(x.tag||'')}»${x.note?' — '+esc(x.note):''}`).join('<br>') : '';
  }catch(e){}
}
async function savePromptTag(){
  const md5 = BENCH.ptagging, p = (BENCH.prompts||[]).find(x=>x.md5===md5);
  try{ await bjson('/api/bench/prompts/'+md5, {method:'PUT', headers:{'Content-Type':'application/json'},
         body: JSON.stringify({tag: $('bp-tag').value, note: $('bp-note').value, text: p ? p.text : ''})}); }
  catch(e){ $('bp-info').innerHTML = `<span style="color:#f87171">${esc(e.message)}</span>`; return; }
  closeModal('bench-prompt-modal'); await loadPrompts(); loadBenchRuns();
}
async function untagPrompt(){
  const md5 = BENCH.ptagging;
  if(!confirm('¿Quitar la etiqueta? Las corridas no se tocan; este prompt volverá a «sin etiqueta».')) return;
  try{ await bjson('/api/bench/prompts/'+md5, {method:'DELETE'}); }catch(e){ bmsg(esc(e.message), false); return; }
  closeModal('bench-prompt-modal'); await loadPrompts(); loadBenchRuns();
}
const pname = p => p.tag || 'sin etiqueta · '+short(p.md5);
function showPromptText(md5){
  const p = (BENCH.prompts||[]).find(x=>x.md5===md5); if(!p) return;
  $('bpt-title').innerHTML = `🏷️ ${esc(pname(p))}`;
  $('bpt-legend').innerHTML = `Huella <code>${short(md5)}</code> · ${p.text.length.toLocaleString()} caracteres${p.note?' · '+esc(p.note):''}`;
  $('bpt-body').textContent = p.text;
  openModal('bench-ptext-modal');
}
// Diferencia por líneas entre dos prompts (LCS): verde = solo en B, rojo tachado = solo en A.
function lineDiff(a, b){
  const A = a.split('\n'), B = b.split('\n'), n = A.length, m = B.length;
  const L = Array.from({length: n+1}, ()=>new Uint16Array(m+1));
  for(let i=n-1;i>=0;i--) for(let j=m-1;j>=0;j--) L[i][j] = A[i]===B[j] ? L[i+1][j+1]+1 : Math.max(L[i+1][j], L[i][j+1]);
  const out = []; let i=0, j=0;
  while(i<n || j<m){
    if(i<n && j<m && A[i]===B[j]){ out.push([' ', A[i]]); i++; j++; }
    else if(j<m && (i>=n || L[i][j+1] >= L[i+1][j])) out.push(['+', B[j++]]);
    else out.push(['-', A[i++]]);
  }
  return out;
}
function diffPrompts(){
  const [ma, mb] = checkedPrompts(); const ps = BENCH.prompts||[];
  let a = ps.find(x=>x.md5===ma), b = ps.find(x=>x.md5===mb); if(!a || !b) return;
  if((a.first_run||'') > (b.first_run||'')) [a, b] = [b, a];   // A = el más antiguo
  const d = lineDiff(a.text, b.text);
  const add = d.filter(x=>x[0]==='+').length, del = d.filter(x=>x[0]==='-').length;
  $('bpt-title').innerHTML = `🔀 ${esc(pname(a))} → ${esc(pname(b))}`;
  $('bpt-legend').innerHTML = `A = <b>${esc(pname(a))}</b> · B = <b>${esc(pname(b))}</b> · <span style="color:#86efac">+${add} líneas solo en B</span> · <span style="color:#fca5a5">−${del} líneas solo en A</span> · las líneas iguales se muestran solo cerca de un cambio`;
  // Contexto: 2 líneas iguales alrededor de cada cambio; el resto se resume.
  const near = d.map((x,k)=>x[0]!==' ' ? 0 : Math.min(...d.map((y,q)=>y[0]!==' ' ? Math.abs(q-k) : 1e9)));
  let html = '', skipped = 0;
  d.forEach((x,k)=>{
    if(x[0]===' ' && near[k] > 2){ skipped++; return; }
    if(skipped){ html += `<span class="dl gap">… ${skipped} líneas iguales …</span>`; skipped = 0; }
    html += `<span class="dl ${x[0]==='+'?'add':x[0]==='-'?'del':''}">${x[0]===' '?'&nbsp;':x[0]} ${esc(x[1])||'&nbsp;'}</span>`;
  });
  if(skipped) html += `<span class="dl gap">… ${skipped} líneas iguales …</span>`;
  $('bpt-body').innerHTML = add || del ? html : '<span class="muted">Los textos son iguales línea por línea (difieren solo en espacios).</span>';
  openModal('bench-ptext-modal');
}
