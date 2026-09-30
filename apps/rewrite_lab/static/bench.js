// Tab "🧪 Benchmark" — sets de preguntas por tema, componentes esperados, corridas
// juzgadas por el LLM y comparación entre corridas. Backend: /api/bench/* (bench.py).
// Usa los helpers globales de index.html ($, esc, readJur, window.__topics), que ya
// existen cuando se llama a cualquiera de estas funciones.

let BENCH = {sets: [], set: null, editingQ: null, editingSet: null, poll: null, inited: false};

async function bjson(url, opts){
  const r = await fetch(url, opts);
  let body = null; try{ body = await r.json(); }catch(e){}
  if(!r.ok || (body && body.error)) throw new Error((body && body.error) || `HTTP ${r.status}`);
  return body;
}
const bpost = (url, obj) => bjson(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(obj||{})});
function bmsg(html, ok){ $('bench-msg').innerHTML = html ? `<span style="color:${ok===false?'#f87171':'#4ade80'}">${html}</span>` : ''; }
const attr = s => esc(s).replace(/"/g,'&quot;');
const pct = v => v==null ? '—' : (100*v).toFixed(0)+'%';
function scoreColor(v){ if(v==null) return '#374151'; if(v>=.85) return '#166534'; if(v>=.6) return '#3f6212'; if(v>=.35) return '#854d0e'; return '#7f1d1d'; }
const topicLabel = t => ((window.__topics||[]).find(x=>x.topic===t)||{}).label || t;

async function benchInit(){
  if(!BENCH.inited){
    BENCH.inited = true;
    $('bench-set').addEventListener('change', ()=>loadBenchSet($('bench-set').value));
    $('bench-topic-filter').addEventListener('change', renderSetOptions);
    $('bench-new-set').addEventListener('click', ()=>openSetForm(null));
    $('bench-edit-set').addEventListener('click', ()=>BENCH.set && openSetForm(BENCH.set));
    $('bench-set-cancel').addEventListener('click', ()=>$('bench-set-form').style.display='none');
    $('bench-set-save').addEventListener('click', saveSet);
    $('bench-set-delete').addEventListener('click', deleteSet);
    $('bench-export').addEventListener('click', exportSet);
    $('bench-import-btn').addEventListener('click', ()=>$('bench-import').click());
    $('bench-import').addEventListener('change', importSet);
    $('bench-backup').addEventListener('click', backupSet);
    $('bench-add-q').addEventListener('click', ()=>openQForm(null));
    $('bq-add-comp').addEventListener('click', ()=>addCompRow());
    $('bq-cancel').addEventListener('click', closeQForm);
    $('bq-save').addEventListener('click', saveQ);
    $('bench-run').addEventListener('click', startBenchRun);
    $('bench-cancel').addEventListener('click', cancelBenchRun);
    $('bench-refresh').addEventListener('click', loadBenchRuns);
    $('bench-compare').addEventListener('click', compareBenchRuns);
  }
  try{
    const info = await bjson('/api/bench/info');
    const st = info.storage||{};
    $('bench-storage').textContent = `artefactos → ${st.backend==='minio' ? 'MinIO '+st.where : 'carpeta local '+st.where+' (MinIO no configurado)'}`;
    $('bench-judge').textContent = 'LLM en '+(info.judge_url||'?');
    if(info.running) watchBenchRun(info.running);
  }catch(e){}
  benchFillTopics();
  await loadBenchSets();
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
    ? list.map(s=>`<option value="${s.id}">${esc(s.name)} · ${esc(s.topic_label)} · ${s.n_questions} preg.</option>`).join('')
    : '<option value="">— no hay sets; crea uno —</option>';
  if(want && list.some(s=>String(s.id)===want)) $('bench-set').value = want;
  loadBenchSet($('bench-set').value);
}
async function loadBenchSet(id){
  closeQForm();
  $('bench-detail').innerHTML = '';
  if(!id){ BENCH.set=null; $('bench-questions').innerHTML='<p class="muted">Crea un set para empezar.</p>';
    $('bench-qcount').textContent=''; $('bench-runs').innerHTML=''; return; }
  try{ BENCH.set = await bjson('/api/bench/sets/'+id); }catch(e){ bmsg(esc(e.message), false); return; }
  const t = (window.__topics||[]).find(x=>x.topic===BENCH.set.topic);
  $('bench-system').value = (t && t.system_prompt) || '';
  renderQuestions();
  loadBenchRuns();
}
function openSetForm(s){
  BENCH.editingSet = s;
  $('bench-set-form').style.display = 'block';
  $('bench-set-name').value = s ? s.name : '';
  $('bench-set-desc').value = s ? (s.description||'') : '';
  if(s) $('bench-set-topic').value = s.topic;
  else if($('bench-topic-filter').value) $('bench-set-topic').value = $('bench-topic-filter').value;
  $('bench-set-delete').style.display = s ? '' : 'none';
  $('bench-set-name').focus();
}
async function saveSet(){
  const body = {name:$('bench-set-name').value, topic:$('bench-set-topic').value, description:$('bench-set-desc').value};
  try{
    let id;
    if(BENCH.editingSet){ id = BENCH.editingSet.id; await bpost('/api/bench/sets/'+id, body); }
    else id = (await bpost('/api/bench/sets', body)).id;
    $('bench-set-form').style.display = 'none';
    bmsg('Set guardado.');
    await loadBenchSets(id);
  }catch(e){ bmsg(esc(e.message), false); }
}
async function deleteSet(){
  const s = BENCH.editingSet; if(!s) return;
  if(!confirm(`¿Borrar el set «${s.name}» con sus ${s.questions.length} preguntas? Las corridas se conservan.`)) return;
  try{ await bjson('/api/bench/sets/'+s.id, {method:'DELETE'}); BENCH.set=null;
    $('bench-set-form').style.display='none'; bmsg('Set borrado.'); await loadBenchSets(); }
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
function renderQuestions(){
  const qs = BENCH.set.questions;
  $('bench-qcount').textContent = `(${qs.length})`;
  $('bench-questions').innerHTML = qs.length ? qs.map((q,i)=>`
    <div class="bq"><div class="qh"><span class="muted">#${i+1}</span><span class="qt">${esc(q.question)}</span>
      <button class="ghost" onclick="openQForm(${q.id})">✏️</button>
      <button class="danger" onclick="deleteQ(${q.id})">🗑</button></div>
      ${q.expected_answer?`<details><summary>respuesta de referencia</summary><div class="ref">${esc(q.expected_answer)}</div></details>`:''}
      <div class="comps">${q.components.length ? q.components.map(c=>compChip(c)).join('')
        : (q.expected_answer ? '<span class="muted" style="font-size:12px">sin componentes: se compara contra la referencia</span>'
                             : '<span style="color:#f87171;font-size:12px">sin componentes ni referencia: no se evalúa</span>')}</div>
      ${q.notes?`<div class="muted" style="font-size:12px;margin-top:4px">📝 ${esc(q.notes)}</div>`:''}
    </div>`).join('') : '<p class="muted">Este set aún no tiene preguntas.</p>';
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
  const q = qid ? BENCH.set.questions.find(x=>x.id===qid) : null;
  if(!BENCH.set){ bmsg('Primero crea o elige un set.', false); return; }
  BENCH.editingQ = q;
  $('bench-q-form').style.display = 'block';
  $('bq-question').value = q ? q.question : '';
  $('bq-expected').value = q ? (q.expected_answer||'') : '';
  $('bq-notes').value = q ? (q.notes||'') : '';
  $('bq-comps').innerHTML = '';
  (q && q.components.length ? q.components : [null]).forEach(c=>addCompRow(c));
  $('bench-q-form').scrollIntoView({behavior:'smooth', block:'center'});
  $('bq-question').focus();
}
function closeQForm(){ BENCH.editingQ = null; $('bench-q-form').style.display = 'none'; }
async function saveQ(){
  const components = [...$('bq-comps').querySelectorAll('.cedit')].map(r=>({
    kind: r.querySelector('.ck').value, text: r.querySelector('.ct').value.trim(),
    weight: parseFloat(r.querySelector('.cw').value)||1})).filter(c=>c.text);
  const body = {question:$('bq-question').value, expected_answer:$('bq-expected').value,
                notes:$('bq-notes').value, components};
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
    BENCH.set = await bjson('/api/bench/sets/'+BENCH.set.id); renderQuestions(); }
  catch(e){ bmsg(esc(e.message), false); }
}

// ── Corridas ────────────────────────────────────────────────────────────────────
async function startBenchRun(){
  if(!BENCH.set) return;
  const body = {set_id: BENCH.set.id, label: $('bench-label').value, setting: $('bench-setting').value,
    k: +$('bench-k').value, neighbors: $('bench-neighbors').checked, hyde: $('bench-hyde').checked,
    rerank: $('bench-rerank').checked, system: $('bench-system').value, jurisdictions: readJur('bench-jur')};
  try{ const r = await bpost('/api/bench/run', body); watchBenchRun(r.run_id); }
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
    $('bench-progress').innerHTML = `<div class="phead"><span>Corrida <b>#${r.id}</b> ${esc(r.label||'')} · ${esc(r.set_name||'')}</span>
      <span><b>${r.done}/${r.n}</b> preguntas · ${esc(r.status)}${m.score!=null?` · score ${pct(m.score)} · pasan ${pct(m.pass_rate)}`:''}</span></div>
      <div class="pbar ${running?'busy':(r.status==='done'?'done':'err')}"><i style="width:${Math.max(p,3)}%"></i></div>
      ${r.error?`<div style="color:#f87171;font-size:12px">${esc(r.error)}</div>`:''}`;
    if(!running){
      clearInterval(BENCH.poll); BENCH.running = null;
      $('bench-run').disabled = false; $('bench-cancel').style.display = 'none';
      if(BENCH.set && r.set_id===BENCH.set.id){ loadBenchRuns(); showBenchRun(rid); }
    }else if(BENCH.set && r.set_id===BENCH.set.id && r.done && r.done!==BENCH.shownDone){
      BENCH.shownDone = r.done; showBenchRun(rid, true);   // solo si llegó un resultado nuevo
    }
  };
  tick(); BENCH.poll = setInterval(tick, 3000);
}
function cfgSummary(c){
  c = c||{};
  return [c.setting, 'k='+c.k, c.neighbors?'vecinos':'', c.hyde?'HyDE':'', c.rerank?'rerank':'',
          (c.jurisdictions||[]).length?'lugar='+c.jurisdictions.join('+'):'', c.judge_model?'juez '+c.judge_model:'']
    .filter(Boolean).join(' · ');
}
async function loadBenchRuns(){
  if(!BENCH.set) return;
  let runs; try{ runs = await bjson('/api/bench/runs?set_id='+BENCH.set.id); }catch(e){ return; }
  BENCH.runs = runs;
  $('bench-runs').innerHTML = runs.length ? `<table><tr><th></th><th>#</th><th>fecha</th><th>etiqueta / config</th><th>estado</th>
    <th title="promedio del score por pregunta">score</th><th title="% de preguntas con todos los must y ningún must_not">pasan</th>
    <th title="% de componentes must presentes">must ✓</th><th title="must_not que aparecieron">viol.</th><th>s/preg</th><th></th></tr>`+
    runs.map(r=>{ const m=r.metrics||{}; return `<tr>
      <td><input type="checkbox" class="bench-cmp" value="${r.id}"></td><td>${r.id}</td>
      <td style="white-space:nowrap">${esc((r.created_at||'').slice(0,16))}</td>
      <td>${esc(r.label||'')}<div class="runcfg">${esc(cfgSummary(r.config))}</div></td>
      <td>${esc(r.status)}${r.status==='running'?` ${r.done}/${r.n}`:''}${m.errors?` <span style="color:#f87171">(${m.errors} err)</span>`:''}</td>
      <td class="sc" style="background:${scoreColor(m.score)}">${pct(m.score)}</td>
      <td class="sc">${pct(m.pass_rate)}</td><td class="sc">${pct(m.must_coverage)}</td>
      <td class="sc">${m.violations??'—'}</td><td class="sc">${m.avg_seconds??'—'}</td>
      <td style="white-space:nowrap"><button class="ghost" style="padding:3px 9px;font-size:12px" onclick="showBenchRun(${r.id})">ver</button>
        <button class="danger" onclick="deleteBenchRun(${r.id})">🗑</button></td></tr>`; }).join('')+'</table>'
    : '<p class="muted">Aún no hay corridas de este set.</p>';
}
async function deleteBenchRun(rid){
  if(!confirm(`¿Borrar la corrida #${rid} (y su artefacto)?`)) return;
  try{ await bjson('/api/bench/runs/'+rid, {method:'DELETE'}); $('bench-detail').innerHTML=''; loadBenchRuns(); }
  catch(e){ bmsg(esc(e.message), false); }
}
async function showBenchRun(rid, quiet){
  let r; try{ r = await bjson('/api/bench/runs/'+rid); }catch(e){ bmsg(esc(e.message), false); return; }
  const m = r.metrics||{};
  $('bench-detail').innerHTML = `<h2>Corrida #${r.id} ${esc(r.label||'')} <span class="muted">${esc(cfgSummary(r.config))}</span></h2>
    <div class="cards">
      <div class="card"><h3>score medio</h3><div style="font-size:22px;font-weight:700">${pct(m.score)}</div></div>
      <div class="card"><h3>preguntas que pasan</h3><div style="font-size:22px;font-weight:700">${pct(m.pass_rate)}</div></div>
      <div class="card"><h3>cobertura de must</h3><div style="font-size:22px;font-weight:700">${pct(m.must_coverage)}</div></div>
      <div class="card"><h3>violaciones must_not</h3><div style="font-size:22px;font-weight:700">${m.violations??'—'}</div></div>
    </div>
    <p class="muted" style="font-size:12px">Clic en una fila para ver la respuesta completa, las fuentes y la salida cruda del juez (desde el object store).
      Pasa el cursor sobre un componente para ver la evidencia que citó el juez.</p>
    <table><tr><th>#</th><th>pregunta</th><th>score</th><th>pasa</th><th>componentes (veredicto del juez)</th><th>s</th></tr>`+
    r.results.map(x=>`<tr class="clk" onclick="toggleBenchAnswer(${r.id}, ${x.question_id}, this)">
      <td>${x.position+1}</td><td>${esc(x.question)}</td>
      <td class="sc" style="background:${x.error?'#374151':scoreColor(x.score)}">${x.error?'err':pct(x.score)}</td>
      <td class="sc">${x.error?'—':(x.passed?'✅':'❌')}</td>
      <td>${x.error?`<span style="color:#f87171">${esc(x.error)}</span>`:`<div class="comps" style="margin:0">${(x.verdicts||[]).map(v=>compChip(v, v.verdict)).join('')}</div>`}</td>
      <td class="sc">${x.seconds??''}</td></tr>`).join('')+'</table>';
  if(!quiet) $('bench-detail').scrollIntoView({behavior:'smooth'});
}
async function toggleBenchAnswer(rid, qid, tr){
  const next = tr.nextElementSibling;
  if(next && next.classList.contains('bench-ans')){ next.remove(); return; }
  const row = document.createElement('tr'); row.className = 'bench-ans';
  row.innerHTML = `<td colspan="6" class="muted">cargando…</td>`;
  tr.after(row);
  try{
    const d = await bjson(`/api/bench/runs/${rid}/artifact?question_id=${qid}`);
    const md = s => (window.marked ? marked.parse(s||'') : `<pre>${esc(s)}</pre>`);
    row.innerHTML = `<td colspan="6">
      <div class="ans">${md(d.answer)}</div>
      ${d.expected_answer?`<details><summary>respuesta de referencia</summary><div class="ref">${esc(d.expected_answer)}</div></details>`:''}
      <details><summary>veredictos con evidencia</summary><ul>${(d.verdicts||[]).map(v=>
        `<li>${compChip(v, v.verdict)} → <b>${esc(v.verdict||'sin veredicto')}</b>${v.evidence?` — «${esc(v.evidence)}»`:''}</li>`).join('')}</ul></details>
      ${d.chunks?renderChunks(d.chunks, d.score_kind||'score').replace('<details open>','<details>'):''}
      <details><summary>salida cruda del juez</summary><pre class="hyde-p">${esc(d.judge_raw)}</pre></details>
      ${d.hyde_passage?`<details><summary>borrador HyDE</summary><div class="hyde-p">${esc(d.hyde_passage)}</div></details>`:''}
    </td>`;
  }catch(e){ row.innerHTML = `<td colspan="6" style="color:#f87171">${esc(e.message)}</td>`; }
}
async function compareBenchRuns(){
  const ids = [...document.querySelectorAll('.bench-cmp:checked')].map(c=>+c.value).sort((a,b)=>a-b);
  if(ids.length < 2){ bmsg('Marca al menos 2 corridas para comparar.', false); return; }
  const runs = await Promise.all(ids.map(id=>bjson('/api/bench/runs/'+id)));
  // Filas = preguntas (por id, así una pregunta editada sigue alineada entre corridas y
  // dos preguntas con el mismo texto no se funden); columnas = corridas.
  const qkey = x => x.question_id ?? x.question;
  const qs = []; const seen = new Set();
  runs.forEach(r=>r.results.forEach(x=>{ if(!seen.has(qkey(x))){ seen.add(qkey(x)); qs.push(x); } }));
  const cellOf = (r,q) => { const x = r.results.find(y=>qkey(y)===qkey(q));
    if(!x) return '<td class="sc muted">—</td>';
    if(x.error) return '<td class="sc" style="background:#374151">err</td>';
    return `<td class="sc" style="background:${scoreColor(x.score)}">${pct(x.score)}${x.passed?' ✓':''}</td>`; };
  $('bench-detail').innerHTML = `<h2>Comparación</h2><table><tr><th>pregunta</th>${runs.map(r=>
      `<th>#${r.id} ${esc(r.label||'')}<div class="runcfg">${esc(cfgSummary(r.config))}</div></th>`).join('')}</tr>
    <tr><td><b>score medio</b></td>${runs.map(r=>`<td class="sc" style="background:${scoreColor((r.metrics||{}).score)}">${pct((r.metrics||{}).score)}</td>`).join('')}</tr>
    <tr><td><b>pasan</b></td>${runs.map(r=>`<td class="sc">${pct((r.metrics||{}).pass_rate)}</td>`).join('')}</tr>`+
    qs.map(q=>`<tr><td>${esc(q.question)}</td>${runs.map(r=>cellOf(r,q)).join('')}</tr>`).join('')+'</table>';
  $('bench-detail').scrollIntoView({behavior:'smooth'});
}
