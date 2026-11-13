// 📚 Preguntar (Catálogo): tab de index.html. La consulta de la ronda 3 (consulta/maquina.py): clasifica el caso, pide
// los datos del expediente y llega a reglas y artículos del catálogo; con «orientar», el LLM redacta la respuesta con
// esos artículos (consulta/orientar.py). El estado y el expediente viven en esta página: no se guarda nada en la base.
(() => {
  const g = id => document.getElementById(id);
  const e = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const PROMPT_POR_OMISION = 'ronda2:intermedio';
  let C = {cat:null, nombres:{}, md5:''}, S = nuevo(), iniciado = false;
  function nuevo(){ return {estado:null, expediente:null, historial:[], ultima:null, orientacion:null, buscador:null, extra:[], registros:[]}; }

  async function catInit(){
    if (iniciado) return;
    iniciado = true;
    const j = await (await fetch('/api/catalogo')).json();
    C = {cat:j.catalogo, nombres:j.nombres || {}, md5:j.md5};
    try {
      const ps = await (await fetch('/api/consulta/prompts')).json();
      g('cat-prompt').innerHTML = ps.map(p => `<option value="${e(p.id)}" ${p.id === PROMPT_POR_OMISION ? 'selected' : ''}>${e(p.nombre)}${p.id === PROMPT_POR_OMISION ? ' (el mejor de la ronda 2)' : ''}</option>`).join('');
    } catch (_) {}
    cargarPrompt();
    g('cat-preset').onclick = () => { g('cat-psys').value = P.guardado; resumenPrompt(); };
    g('cat-psys').addEventListener('input', resumenPrompt);
    g('cat-psave').onclick = guardarPrompt;
    g('cat-pvers').onchange = async ev => { if (!ev.target.value) return;
      const v = await (await fetch(`/api/consulta/prompt_preguntas/${ev.target.value}`)).json(); if (v.texto) { g('cat-psys').value = v.texto; resumenPrompt(); } };
    g('cat-txt').addEventListener('keydown', ev => { if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); enviar(); } });
  }
  // El prompt de las preguntas: el guardado en la base; lo editado en el cuadro solo vale para esta página.
  const P = {guardado:''};
  async function cargarPrompt(){
    try {
      const j = await (await fetch('/api/consulta/prompt_preguntas')).json();
      P.guardado = j.texto; P.info = j.por ? `guardado por ${j.por} · ${j.creado.slice(0, 16).replace('T', ' ')}` : 'versión inicial (del código)';
      if (!g('cat-psys').value || g('cat-psys').dataset.limpio === '1') g('cat-psys').value = j.texto;
      g('cat-psys').dataset.limpio = '1';
      g('cat-pvers').innerHTML = '<option value="">— elegir —</option>' + j.historial.map(v => `<option value="${v.id}">#${v.id} · ${e(v.por || '')} · ${e(v.creado.slice(0, 16).replace('T', ' '))}</option>`).join('');
      resumenPrompt();
    } catch (_) {}
  }
  function resumenPrompt(){
    const cambiado = g('cat-psys').value !== P.guardado;
    g('cat-psys').dataset.limpio = cambiado ? '0' : '1';
    g('cat-psum').innerHTML = cambiado ? '<span class="warn">· editado (solo en esta página)</span>' : `· ${e(P.info || '')}`;
  }
  async function guardarPrompt(){
    try {
      const r = await fetch('/api/consulta/prompt_preguntas', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({texto:g('cat-psys').value})});
      const j = await r.json(); if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status);
      g('cat-pmsg').textContent = 'Guardado ✓'; setTimeout(() => g('cat-pmsg').textContent = '', 2500);
      await cargarPrompt();
    } catch (err) { g('cat-pmsg').textContent = '⚠ ' + err.message; }
  }
  const tipo = id => ((C.cat.tipos_caso || []).find(t => t.id === id) || {titulo:id}).titulo;
  const regla = id => (C.cat.reglas || []).find(r => r.id === id) || {id, delito:id};

  function burbuja(rol, texto, extra){
    const d = document.createElement('div'); d.className = 'cat-msg' + (rol === 'user' ? ' user' : '');
    d.innerHTML = `<span class="quien">${rol === 'user' ? 'Persona' : 'Asistente'}</span>${e(texto)}${extra || ''}`;
    g('cat-msgs').appendChild(d); g('cat-msgs').scrollTop = 1e9; return d;
  }

  // Un mensaje → /api/consulta/turno/stream (SSE, lo lee readSSE de index.html): 'turno' trae el estado y la salida;
  // si toca orientar, 'contexto' dice qué artículos entraron y 'token' va escribiendo la respuesta.
  async function turno(evento){
    g('cat-run').disabled = true;
    let espera = burbuja('assistant', '…'), viva = null, respuesta = '';
    const quitarEspera = () => { if (espera) { espera.remove(); espera = null; } };
    try {
      const r = await fetch('/api/consulta/turno/stream', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({estado:S.estado, expediente:S.expediente, evento, solo_confirmadas:g('cat-conf').checked,
          historial:S.historial, contexto:g('cat-modo').value, tope_tokens:+g('cat-tope').value || null, prompt:g('cat-prompt').value,
          preguntas_llm:g('cat-preg-llm').checked, prompt_preguntas:g('cat-psys').value !== P.guardado ? g('cat-psys').value : null})});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      await readSSE(r, ev => {
        if (ev.stage === 'turno') {
          Object.assign(S, {estado:ev.estado, expediente:ev.expediente, ultima:ev.salida, orientacion:null, buscador:ev.buscador ? [] : null, extra:[]});
          S.registros.push(ev.registro);
          quitarEspera(); responder(ev.salida, g('cat-preg-llm').checked, ev.buscador); panel();
          if (ev.buscador) espera = burbuja('assistant', 'El catálogo no tiene reglas para este caso: buscando en las leyes…');
          if (ev.salida.tipo === 'pregunta' && g('cat-preg-llm').checked) espera = burbuja('assistant', '…');
          if (ev.salida.tipo === 'orientar' && !ev.salida.sin_reglas && g('cat-modo').value !== 'ninguno') espera = burbuja('assistant', 'Leyendo los artículos del catálogo…');
        } else if (ev.stage === 'llm_entrada') {    // lo que recibe el LLM al redactar la pregunta o la orientación
          S.extra.push({tarea:ev.tarea, system:ev.system, user:ev.user, raw:''}); panel();
        } else if (ev.stage === 'buscador') {
          S.buscador = ev.chunks || []; panel();
        } else if (ev.stage === 'contexto') {
          S.orientacion = ev.orientacion; panel();
        } else if (ev.stage === 'token') {
          quitarEspera();
          if (!viva) { viva = burbuja('assistant', ''); viva.classList.add('md'); }
          respuesta += ev.text || '';
          viva.innerHTML = '<span class="quien">Asistente</span>' + marked.parse(respuesta);
          g('cat-msgs').scrollTop = 1e9;
        } else if (ev.stage === 'done') {
          if (S.orientacion) { S.orientacion.respuesta = respuesta; S.orientacion.segundos.respuesta = ev.segundos_respuesta; panel(); }
          if (respuesta) S.historial.push({role:'assistant', content:respuesta});
          if (S.extra.length) { S.extra[S.extra.length - 1].raw = respuesta; S.extra[S.extra.length - 1].segundos = ev.segundos_respuesta; panel(); }
        } else if (ev.stage === 'error') {     // readSSE se traga lo que lance este callback: se muestra aquí
          quitarEspera(); burbuja('assistant', '').innerHTML = `<span class="bad">Error: ${e(ev.error)}</span>`;
          if (S.ultima && S.ultima.tipo === 'pregunta' && !respuesta) decir(S.ultima.texto);   // la pregunta fija del catálogo
        }
      });
      quitarEspera();
    } catch (err) { quitarEspera(); burbuja('assistant', '').innerHTML = `<span class="bad">Error: ${e(err.message)}</span>`; }
    g('cat-run').disabled = false; g('cat-txt').focus();
  }

  function decir(texto, extra){ burbuja('assistant', texto, extra); S.historial.push({role:'assistant', content:texto}); }
  // `llm`: la pregunta (y el aviso) los redacta el LLM y llegan como tokens; aquí no se escriben.
  // `buscador`: el catálogo no tiene reglas y la respuesta la escribe el buscador (llega como tokens).
  function responder(s, llm, buscador){
    if (s.tipo === 'pregunta' && llm) return;
    if (s.tipo === 'orientar' && buscador) return;
    if (s.aviso) decir(s.aviso);
    if (s.tipo === 'pregunta') decir(s.texto);
    else if (s.tipo === 'elegir_tipo')
      decir(s.texto, `<div class="cat-btns">${s.opciones.map(x => `<button class="ghost" onclick="catElegir('${e(x.id)}', this)">${e(x.titulo)}</button>`).join('')}</div>`);
    else if (s.tipo === 'orientar' && s.sin_reglas) decir('Con los datos que diste no encontré reglas del catálogo para tu caso.');
    else if (s.tipo === 'orientar' && g('cat-modo').value === 'ninguno')
      decir(`Tengo lo necesario para orientarte: ${s.reglas.length} regla(s) del catálogo y ${Object.values(s.articulos).flat().length} artículo(s). Míralos en el panel.`);
    // Sin orientación del LLM, el dato complementario se escribe aquí; con ella, el servidor lo manda al final.
    if (s.tipo === 'orientar' && (s.sin_reglas || g('cat-modo').value === 'ninguno') && !buscador) {
      (s.avisos_ley || []).forEach(decir);
      if (s.pregunta) decir(s.pregunta.texto);
    }
  }

  function enviar(){
    const texto = g('cat-txt').value.trim(); if (!texto) return;
    g('cat-txt').value = ''; burbuja('user', texto);
    const evento = {tipo:'mensaje', texto, historial:[...S.historial]};
    S.historial.push({role:'user', content:texto});
    turno(evento);
  }
  function elegir(id, btn){
    btn.parentElement.querySelectorAll('button').forEach(b => b.disabled = true);
    burbuja('user', '▸ ' + (id === 'otro' ? 'Ninguna de estas' : tipo(id)));
    turno({tipo:'elegir_tipo', valor:id});
  }
  function reiniciar(){ S = nuevo(); g('cat-msgs').innerHTML = ''; g('cat-panel').innerHTML = '<span class="muted">Escribe un caso para ver qué hace la consulta.</span>'; }

  function panel(){
    const x = S.expediente || {}, s = S.ultima || {}, r = S.registros[S.registros.length - 1] || {};
    const datos = Object.entries(x.datos || {});
    let h = `<h3>Estado</h3><span class="cat-est">${e(S.estado)}</span> <span class="muted">antes: ${e(r.estado_antes)} · catálogo ${e((C.md5 || '').slice(0, 8))}</span>
      <h3>Tipos de caso</h3>${(x.tipos_caso || []).map(t => `<span class="cat-chip">${e(tipo(t))} <span class="muted">${e(t)}</span></span>`).join('') || '<span class="muted">ninguno todavía</span>'}
      ${r.por_que ? `<div class="muted">Por qué (LLM): ${e(r.por_que)}</div>` : ''}
      <h3>Expediente</h3>${datos.length ? `<table>${datos.map(([k, v]) => `<tr><td>${e(k)}</td><td>${e(v)}${(x.supuestos || []).includes(k) ? ' <span class="warn">(supuesto: es donde vive)</span>' : ''}</td></tr>`).join('')}</table>` : '<span class="muted">sin datos</span>'}
      ${(x.no_sabe || []).length ? `<div class="warn">No sabe: ${e(x.no_sabe.join(', '))}</div>` : ''}
      ${(x.hechos || []).length ? `<h3>Hechos (no caben en ningún dato)</h3><ul>${x.hechos.map(h => `<li>${e(h)}</li>`).join('')}</ul>` : ''}
      ${(r.faltan || []).length ? `<div>Faltan: ${e(r.faltan.join(', '))}</div>` : ''}
      ${(x.por_actualizar || []).length ? `<div class="muted">Complementarios (después de orientar): ${e(x.por_actualizar.join(', '))}</div>` : ''}
      ${s.actualizacion ? `<div class="muted">Actualización corta con: ${e(Object.entries(s.actualizacion).map(([k, v]) => k + ' = ' + v).join(', '))}</div>` : ''}`;
    if (s.tipo === 'orientar') {
      h += `<h3>Reglas que aplican (${s.reglas.length})</h3>` + (s.reglas.length ? `<table>${s.reglas.map(id => { const q = regla(id);
          return `<tr><td>${e(id)}</td><td>${e(q.delito)}${s.inciertas.includes(id) ? ' <span class="warn">(incierta: falta un dato)</span>' : ''}
            <div class="muted">${e(tipo(q.tipo_caso))}${q.condicion ? ' · ' + e(q.condicion) : ''} · ${e(q.estado)}</div></td></tr>`; }).join('')}</table>` : '<span class="muted">ninguna</span>');
      h += `<h3>Artículos por ley (${Object.values(s.articulos).flat().length})</h3>` + (Object.keys(s.articulos).length ? Object.entries(s.articulos).map(([k, arts]) =>
          `<div><b>${e(C.nombres[k] || k)}</b> ${arts.map(a => `<span class="cat-chip" onclick="catLeer('${e(k)}','${e(a)}')">${e(a)}</span>`).join('')}</div>`).join('')
          : '<span class="muted">ninguno</span>');
      if ((s.leyes_quitadas || []).length) h += `<div class="warn">No entran (condición de ley no cumplida o desconocida): ${e(s.leyes_quitadas.map(k => C.nombres[k] || k).join(', '))}${(s.avisos_ley || []).length ? ' · se dice el aviso fijo' : ''}</div>`;
      const o = S.orientacion;
      if (o) {
        const entra = o.contexto.filter(a => a.entra).length, emb = o.modo_contexto === 'embedding';
        h += `<h3>Contexto de la respuesta: ${e(o.modo_contexto)} · prompt ${e(o.prompt || '')} · ${entra} de ${o.contexto.length} artículos · ~${o.tokens_contexto} tokens (tope ${o.tope_tokens}) · contexto ${o.segundos.contexto} s${o.segundos.respuesta != null ? ` · respuesta ${o.segundos.respuesta} s` : ' · escribiendo…'}</h3>
          <table><tr><th>Artículo</th><th>Entra</th><th>Orden</th>${emb ? '<th>Distancia</th>' : ''}<th>Tokens</th></tr>
          ${[...o.contexto].sort((a, b) => (a.orden || 999) - (b.orden || 999)).map(a => `<tr><td><span class="cat-chip" onclick="catLeer('${e(a.codigo)}','${e(a.num)}')">${e(C.nombres[a.codigo] || a.codigo)} ${e(a.num)}</span></td>
            <td>${a.entra ? '✓' : '<span class="muted">✗</span>'}</td><td>${a.orden || ''}</td>${emb ? `<td>${a.distancia ?? ''}</td>` : ''}<td>${a.tokens}</td></tr>`).join('')}</table>
          ${o.no_encontrados.length ? `<div class="warn">No están en el corpus: ${e(o.no_encontrados.join(', '))}</div>` : ''}
          ${(o.valores || []).length ? `<h3>Multas en pesos (valores de referencia)</h3><ul>${o.valores.map(v => `<li>${e(v)}</li>`).join('')}</ul>` : ''}`;
      }
      h += '<div id="cat-texto"></div>';
      if ((s.tipos_quitados || []).length) h += `<div class="warn">Tipos que ya no aplican: ${e(s.tipos_quitados.map(tipo).join(', '))}</div>`;
    }
    if (S.buscador) h += `<h3>Respuesta del buscador (el catálogo no tiene reglas para este caso) · ${S.buscador.length} fragmentos</h3>`
      + (S.buscador.length ? `<table>${S.buscador.map(c => `<tr><td>${e(c.rank)}</td><td>${e(c.citation || '')}<div class="muted">${e(c.hierarchy || '')}</div></td></tr>`).join('')}</table>` : '<span class="muted">buscando…</span>');
    // Cada llamada al LLM: lo que recibió (mensaje de sistema y mensaje con el caso) y lo que respondió.
    const NOMBRE = {clasificar_caso:'clasificar el caso', extraer_lugares:'extraer los lugares', extraer_expediente:'extraer los datos del expediente',
                    redactar_pregunta:'redactar la pregunta', orientar:'redactar la orientación'};
    const llamada = l => l.partes ? l.partes.map(llamada).join('')
      : `<details><summary>${e(NOMBRE[l.tarea] || l.tarea)}${l.segundos != null ? ` · ${l.segundos} s` : ''}</summary>
          ${l.system != null ? `<details><summary class="muted">mensaje de sistema (${l.system.length} caracteres)</summary><pre>${e(l.system)}</pre></details>
          <div class="muted">mensaje con el caso:</div><pre>${e(l.user)}</pre>` : ''}
          <div class="muted">respuesta:</div><pre>${e(l.raw || '…')}</pre></details>`;
    const todas = [...(r.llamadas || []), ...(S.extra || [])];
    h += `<h3>Llamadas al LLM en este mensaje (estado ${e(r.estado_antes || '')})</h3>` + (todas.length ? todas.map(llamada).join('') : '<span class="muted">ninguna</span>');
    g('cat-panel').innerHTML = h;
  }
  async function leer(codigo, num){
    g('cat-texto').innerHTML = '<div class="cat-texto muted">Cargando…</div>';
    const j = await (await fetch(`/api/catalogo/articulo?codigo=${encodeURIComponent(codigo)}&num=${encodeURIComponent(num)}`)).json();
    g('cat-texto').innerHTML = j.encontrado ? `<div class="cat-texto"><b>${e(C.nombres[codigo] || codigo)} · ${e(j.ruta)}</b>\n\n${e(j.texto)}</div>`
      : `<div class="cat-texto bad">No encontré el artículo ${e(num)} en ${e(C.nombres[codigo] || codigo)}.</div>`;
    g('cat-texto').scrollIntoView({block:'nearest'});
  }
  Object.assign(window, {catInit, catEnviar:enviar, catElegir:elegir, catReiniciar:reiniciar, catLeer:leer});
})();
