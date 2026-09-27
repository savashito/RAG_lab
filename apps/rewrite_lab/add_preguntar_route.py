"""Parche idempotente: agrega la ruta GET /preguntar a main.py sin tocar nada más.
Se corre EN el directorio apps/rewrite_lab (donde está main.py). Seguro de re-ejecutar."""
import pathlib

f = pathlib.Path("main.py")
s = f.read_text(encoding="utf-8")

ANCHOR = "    return FileResponse(STATIC / 'index.html', headers={'Cache-Control': 'no-store'})"
ROUTE = """


# Página simplificada para usuarios finales: solo campo de pregunta + respuesta. Sin
# controles (tema/vecinos/HyDE/método). Los defaults salen de la URL, p. ej.
#   /preguntar?tema=psicologia_conductual&vecinos=true&HyDE=true
@app.get('/preguntar')
def preguntar():
    return FileResponse(STATIC / 'preguntar.html', headers={'Cache-Control': 'no-store'})"""

if "'/preguntar'" in s:
    print("La ruta /preguntar ya existe: no hago nada.")
elif ANCHOR not in s:
    raise SystemExit("No encontré el ancla de la ruta index(); revisa main.py a mano.")
else:
    f.write_text(s.replace(ANCHOR, ANCHOR + ROUTE, 1), encoding="utf-8")
    print("Ruta /preguntar agregada.")
