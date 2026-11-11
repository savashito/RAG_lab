// 📚 Preguntar (Catálogo): tab de index.html. La consulta de la ronda 3 (consulta/maquina.py): clasifica el caso, pide
// los datos del expediente y llega a reglas y artículos del catálogo; con «orientar», el LLM redacta la respuesta con
// esos artículos (consulta/orientar.py). El estado y el expediente viven en esta página: no se guarda nada en la base.
(() => {
  const g = id => document.getElementById(id);
  const e = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const PROMPT_POR_OMISION = 'ronda2:intermedio';
  let C = {cat:null, nombres:{}, md5:''}, S = nuevo(), iniciado = false;
  function nuevo(){ return {estado:null, expediente:null, historial:[], ultima:null, orientacion:null, registros:[]}; }

  async function catInit(){
    if (iniciado) return;
    iniciado = true;
    const j = await (await fetch('/api/catalogo')).json();
    C = {cat:j.catalogo, nombres:j.nombres || {}, md5:j.md5};
    try {
      const ps = await (await fetch('/api/consulta/prompts')).json();
      g('cat-prompt').innerHTML = ps.map(p => `<option value="${e(p.id)}" ${p.id === PROMPT_POR_OMISION ? 'selected' : ''}>${e(p.nombre)}${p.id === PROMPT_POR_OMISION ? ' (el mejor de la ronda 2)' : ''}</option>`).join('');
    } catch (_) {}
    g('cat-txt').addEventListener('keydown', ev => { if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); enviar(); } });
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
          historial:S.historial, contexto:g('cat-modo').value, tope_tokens:+g('cat-tope').value || null, prompt:g('cat-prompt').value})});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      await readSSE(r, ev => {
        if (ev.stage === 'turno') {
          Object.assign(S, {estado:ev.estado, expediente:ev.expediente, ultima:ev.salida, orientacion:null});
          S.registros.push(ev.registro);
          quitarEspera(); responder(ev.salida); panel();
          if (ev.salida.tipo === 'orientar' && !ev.salida.sin_reglas && g('cat-modo').value !== 'ninguno') espera = burbuja('assistant', 'Leyendo los artículos del catálogo…');
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
        } else if (ev.stage === 'error') {     // readSSE se traga lo que lance este callback: se muestra aquí
          quitarEspera(); burbuja('assistant', '').innerHTML = `<span class="bad">Error: ${e(ev.error)}</span>`;
        }
      });
      quitarEspera();
    } catch (err) { quitarEspera(); burbuja('assistant', '').innerHTML = `<span class="bad">Error: ${e(err.message)}</span>`; }
    g('cat-run').disabled = false; g('cat-txt').focus();
  }

  function decir(texto, extra){ burbuja('assistant', texto, extra); S.historial.push({role:'assistant', content:texto}); }
  function responder(s){
    if (s.aviso) decir(s.aviso);
    if (s.tipo === 'pregunta') decir(s.texto);
    else if (s.tipo === 'elegir_tipo')
      decir(s.texto, `<div class="cat-btns">${s.opciones.map(x => `<button class="ghost" onclick="catElegir('${e(x.id)}', this)">${e(x.titulo)}</button>`).join('')}</div>`);
    else if (s.tipo === 'orientar' && s.sin_reglas) decir('Con los datos que diste no encontré reglas del catálogo para tu caso.');
    else if (s.tipo === 'orientar' && g('cat-modo').value === 'ninguno')
      decir(`Tengo lo necesario para orientarte: ${s.reglas.length} regla(s) del catálogo y ${Object.values(s.articulos).flat().length} artículo(s). Míralos en el panel.`);
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
      ${(r.faltan || []).length ? `<div>Faltan: ${e(r.faltan.join(', '))}</div>` : ''}`;
    if (s.tipo === 'orientar') {
      h += `<h3>Reglas que aplican (${s.reglas.length})</h3>` + (s.reglas.length ? `<table>${s.reglas.map(id => { const q = regla(id);
          return `<tr><td>${e(id)}</td><td>${e(q.delito)}${s.inciertas.includes(id) ? ' <span class="warn">(incierta: falta un dato)</span>' : ''}
            <div class="muted">${e(tipo(q.tipo_caso))}${q.condicion ? ' · ' + e(q.condicion) : ''} · ${e(q.estado)}</div></td></tr>`; }).join('')}</table>` : '<span class="muted">ninguna</span>');
      h += `<h3>Artículos por ley (${Object.values(s.articulos).flat().length})</h3>` + (Object.keys(s.articulos).length ? Object.entries(s.articulos).map(([k, arts]) =>
          `<div><b>${e(C.nombres[k] || k)}</b> ${arts.map(a => `<span class="cat-chip" onclick="catLeer('${e(k)}','${e(a)}')">${e(a)}</span>`).join('')}</div>`).join('')
          : '<span class="muted">ninguno</span>');
      const o = S.orientacion;
      if (o) {
        const entra = o.contexto.filter(a => a.entra).length, emb = o.modo_contexto === 'embedding';
        h += `<h3>Contexto de la respuesta: ${e(o.modo_contexto)} · prompt ${e(o.prompt || '')} · ${entra} de ${o.contexto.length} artículos · ~${o.tokens_contexto} tokens (tope ${o.tope_tokens}) · contexto ${o.segundos.contexto} s${o.segundos.respuesta != null ? ` · respuesta ${o.segundos.respuesta} s` : ' · escribiendo…'}</h3>
          <table><tr><th>Artículo</th><th>Entra</th><th>Orden</th>${emb ? '<th>Distancia</th>' : ''}<th>Tokens</th></tr>
          ${[...o.contexto].sort((a, b) => (a.orden || 999) - (b.orden || 999)).map(a => `<tr><td><span class="cat-chip" onclick="catLeer('${e(a.codigo)}','${e(a.num)}')">${e(C.nombres[a.codigo] || a.codigo)} ${e(a.num)}</span></td>
            <td>${a.entra ? '✓' : '<span class="muted">✗</span>'}</td><td>${a.orden || ''}</td>${emb ? `<td>${a.distancia ?? ''}</td>` : ''}<td>${a.tokens}</td></tr>`).join('')}</table>
          ${o.no_encontrados.length ? `<div class="warn">No están en el corpus: ${e(o.no_encontrados.join(', '))}</div>` : ''}`;
      }
      h += '<div id="cat-texto"></div>';
      if ((s.tipos_quitados || []).length) h += `<div class="warn">Tipos que ya no aplican: ${e(s.tipos_quitados.map(tipo).join(', '))}</div>`;
    }
    const llamada = l => l.partes ? l.partes.map(llamada).join('')
      : `<details><summary>${e(l.tarea)}${l.segundos != null ? ` · ${l.segundos} s` : ''}</summary><pre>${e(l.raw)}</pre></details>`;
    h += '<h3>Llamadas al LLM en este mensaje</h3>' + ((r.llamadas || []).length ? r.llamadas.map(llamada).join('') : '<span class="muted">ninguna</span>');
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
