import sys, re, collections
exec(open('/tmp/prueba_respuesta.py').read().split("PROMPTS = {")[0])
ART = re.compile(r'(?i)\bart[íi]culos?\s+\d+|\bart\.\s*\d+')
PREG = re.compile(r'¿[^?]{5,300}\?')
FUND = re.compile(r'(?im)^\W*fundamento')
for nombre, rs in (('penal-original-v1', (157, 173)), ('tlacua-v1-penas', (161, 177))):
    c = collections.Counter()
    for r in rs:
        for x in art(r):
            ans = x.get('answer') or ''
            falla = [v for v in x.get('verdicts') or [] if v['kind'] == 'must' and re.match(r'(?i)\s*cita', v['text'])]
            if not falla: continue
            no_cita = any(v.get('verdict') != 'presente' for v in falla)
            g = 'falla_cita' if no_cita else 'cumple_cita'
            c[g] += 1
            c[g + '_preguntas'] += len(PREG.findall(ans)) >= 1
            c[g + '_2preguntas'] += len(PREG.findall(ans)) >= 2
            c[g + '_sin_articulo'] += not ART.search(ans)
            c[g + '_fundamento'] += bool(FUND.search(ans))
            c[g + '_palabras'] += len(ans.split())
    for g in ('falla_cita', 'cumple_cita'):
        n = c[g] or 1
        print(f"{nombre} · {g}: {c[g]} respuestas · con ≥1 pregunta a la persona {100*c[g+'_preguntas']/n:.0f} % · con ≥2 {100*c[g+'_2preguntas']/n:.0f} % · "
              f"sin ningún número de artículo {100*c[g+'_sin_articulo']/n:.0f} % · con sección «Fundamento» {100*c[g+'_fundamento']/n:.0f} % · palabras {c[g+'_palabras']/n:.0f}")
