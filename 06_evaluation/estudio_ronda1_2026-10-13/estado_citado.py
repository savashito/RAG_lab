# Solo lectura: lo que cada persona dijo sobre «¿de qué estado era la ley que te citó el asistente?» (última
# situación) frente a lo que el asistente citó de verdad en esa conversación.
import sys
sys.path[:0] = ['apps/rewrite_lab', '.']
from dotenv import load_dotenv; load_dotenv('apps/rewrite_lab/.env')
from shared.db import connect
from shared.code_routes import codes_in
CAT = {'Querétaro': 'qro', 'CDMX': 'cdmx', 'Morelos': 'otro:Morelos', 'CPEM': 'otro:Edomex', 'CPF': 'nacional:CPF', 'CNPP': 'nacional:CNPP',
       'LGExtorsión': 'nacional:LGExtorsión', 'LGSecuestro': 'nacional:LGSecuestro', 'LGV': 'nacional:LGV', 'LFCDO': 'nacional:LFCDO'}
ESPERADO = {'mensajes_trabajo/qro': 'qro', 'mensajes_trabajo/cdmx': 'cdmx', 'fotos': 'nacional (y Querétaro)', 'citatorio': 'qro (y CNPP)'}
filas = []
with connect() as c, c.cursor() as cur:
    cur.execute("""select i.id, p.codigo, p.condicion, i.escenario, i.variante, i.respuestas->>'_estado_citado', i.confianza, i.detecto, (i.comprension->>'aciertos'), (i.comprension->>'total')
                   from estudio_intentos i join estudio_participantes p using (codigo)
                   where p.fase='principal' and i.fin is not null and i.respuestas ? '_estado_citado' order by i.fin""")
    for iid, cod, cond, esc, var, dijo, conf, det, ac, tot in cur.fetchall():
        cur.execute("select pregunta, respuesta from estudio_turnos where intento_id=%s and respuesta is not null order by n", (iid,))
        turnos = cur.fetchall()
        orden = []
        for _, r in turnos:
            for h in codes_in(r):
                k = CAT.get(h['label'])
                if k and k not in orden: orden.append(k)
        estados = [k for k in orden if not k.startswith('nacional')]            # códigos de un estado
        tipos = {k.split(':')[0] for k in estados}
        if len(estados) >= 2: real = 'varios'
        elif len(estados) == 1: real = estados[0].split(':')[0]
        elif orden: real = 'nacional'
        else: real = '(ninguna)'
        dijo_lugar = any(CAT.get(h['label'], '').split(':')[0] in ('qro', 'cdmx') for q, _ in turnos for h in codes_in(q))
        filas.append(dict(cod=cod, cond=cond, esc=esc + (f'/{var}' if var else ''), dijo=dijo, real=real, cito=orden, ok=(dijo == real),
                          conf=conf, det=det, ac=f'{ac}/{tot}', lugar=dijo_lugar))
for f in filas:
    print(f"{f['cod']} {f['cond']:8} {f['esc']:22} dijo={f['dijo']:10} real={f['real']:8} {'✔' if f['ok'] else '✘'} | usuario dijo el lugar: {'sí' if f['lugar'] else 'no'} | citó: {', '.join(f['cito'])} | conf {f['conf']} aciertos {f['ac']}")
n = len(filas); ok = sum(f['ok'] for f in filas)
print(f"\nacertaron qué estado(s) citó el asistente: {ok}/{n}")
varios = [f for f in filas if f['real'] == 'varios']
print(f"el asistente citó códigos de VARIOS estados en {len(varios)}/{n}; de esos, lo notaron (dijeron «varios»): {sum(f['dijo']=='varios' for f in varios)}; dijeron UN solo estado: {sum(f['dijo'] in ('qro','cdmx','otro') for f in varios)}; «no me fijé»: {sum(f['dijo']=='no_me_fije' for f in varios)}; «nacional»: {sum(f['dijo']=='nacional' for f in varios)}")
esc_estado = lambda f: 'qro' if ('qro' in f['esc'] or f['esc'] in ('fotos', 'citatorio')) else 'cdmx'
print('respondieron el estado DE LA SITUACIÓN aunque el asistente citó varios:', sum(f['dijo'] == esc_estado(f) for f in varios), 'de', len(varios))
for cnd in ('actual', 'sencillo'):
    fs = [f for f in filas if f['cond'] == cnd]; print(f"  {cnd}: acertaron {sum(f['ok'] for f in fs)}/{len(fs)} · asistente citó varios estados en {sum(f['real']=='varios' for f in fs)}/{len(fs)}")
