# Diseño: máquina de estados con expediente de la consulta (ronda 3)

*10 de noviembre de 2026. Plan de implementación del punto C6 de `06_evaluation/trabajo_futuro.md`. Todavía no hay
código.*

## Términos

- **Estado:** uno de una lista finita y fija de situaciones de la conversación. Siempre hay exactamente uno, y el
  siguiente depende solo del estado actual y del evento.
- **Evento:** un mensaje de la persona o un botón que presiona.
- **Transición:** la regla «estando en el estado X, si llega el evento E, pasa al estado Y».
- **Expediente de la consulta:** los datos del caso que el programa va anotando. No es un estado.
- **Dato decisivo:** un dato del expediente del que depende qué ley aplica.
- **Catálogo de casos:** la lista, escrita por Karen, de tipos de caso con sus datos decisivos y el texto con que se
  pregunta cada uno.
- **Programa:** el código en Python de `apps/rewrite_lab`. «Código penal» siempre se escribe completo.

## 1. Principios

1. **La máquina de estados es una función pura.** Recibe el estado, el expediente, el evento y el catálogo; devuelve el
   nuevo estado, el nuevo expediente, lo que se le muestra a la persona y un registro. No toca la base de datos ni
   llama al LLM directamente: recibe esos servicios como parámetros. Así se prueba sin servidor, igual que
   `forms/asistente.py` con `tests/test_asistente.py`.
2. **El programa decide las transiciones; el LLM no.** El LLM solo extrae datos, escribe la orientación y revisa la
   aplicabilidad.
3. **Todo se registra en cada mensaje:** estado antes y después, transición, expediente y el md5 de cada prompt usado.
   Así no hay que reconstruir decisiones después, como pasó con el filtro en la ronda 2.
4. **Todo lo que edita una experta se versiona y se fija por versión.** El estudio guarda qué versión del catálogo y de
   cada prompt usó. Es la lección de la clave de «Las fotos» (v7 contra v9).

## 2. Módulos nuevos

Una carpeta nueva, `apps/rewrite_lab/consulta/`, con la misma forma que `forms/`:

| Archivo | Qué contiene | ¿Llama al LLM o a la base? |
|---|---|---|
| `maquina.py` | Los estados, la tabla `TRANSICIONES` y la función `turno()` | No |
| `expediente.py` | La forma del expediente, cómo se combinan datos nuevos y la función `faltan_decisivos()` | No |
| `catalogo.py` | Cargar y validar el catálogo de casos (YAML) | No |
| `ia.py` | Las tareas del LLM: `extraer_hechos`, `clasificar_caso`, `revisar_aplicabilidad`. Cada una con su prompt fijo y salida JSON | Sí, el LLM |
| `busqueda.py` | Convierte el expediente en filtros para el buscador (código penal del lugar de los hechos, leyes nacionales, leyes según a quién protegen) y llama al chat existente | Sí, el buscador y el LLM |
| `store.py` | Leer y guardar el catálogo y sus versiones | Sí, la base |
| `api.py` | Las rutas para editar el catálogo desde una página de administración | Sí |

`turno()` quedaría así:

```python
def turno(estado, expediente, evento, catalogo, ia, buscar) -> tuple[str, dict, dict, dict]:
    """Devuelve (estado nuevo, expediente nuevo, salida para la persona, registro del mensaje)."""
```

- `ia` es el objeto de `consulta/ia.py`; en las pruebas se usa uno falso.
- `buscar(expediente, mensajes)` es el puente de `busqueda.py` hacia el chat actual; en las pruebas también es falso.

## 3. Conexión con el código actual

**Con el estudio (`study/`).** El estudio ya asigna una condición a cada persona y la guarda en
`estudio_participantes.condicion`.

- La definición del estudio (YAML) gana un campo por condición: `asistente.modo: actual | expediente`. Así la ronda 3
  compara las dos condiciones con la asignación aleatoria que ya existe.
- En `study/api.py`, `p_preguntar_stream` revisa el modo. Con `actual`, sigue igual. Con `expediente`, llama a
  `consulta.maquina.turno()`.
- La respuesta sigue llegando al navegador por el mismo streaming: la página del estudio no cambia. En LLENAR_EXPEDIENTE
  la salida es la pregunta del catálogo, sin streaming del LLM; en ORIENTACIÓN, se transmite la respuesta del LLM.

**Con el buscador (`main.py`).**
- `chat_event_dicts` ya acepta `jurisdicciones`. `busqueda.py` se lo pasa desde el expediente (lugar de los hechos) y
  apaga el filtro por estado actual (`gate=False`), porque el expediente ya decidió el lugar.
- Hay que agregar un parámetro para excluir leyes según la persona, usando las etiquetas que ya existen en
  `documento_categorias` (por ejemplo, la ley de violencia contra las mujeres solo si la víctima es mujer). Es la fase 2
  que `categorias.py` ya anticipa.

**Con el filtro por estado (`jurisdiction_gate.py`).** `extraer_lugares` ya separa el lugar de los hechos de otros
lugares. `consulta/ia.py` lo reutiliza dentro de `extraer_hechos` en vez de reescribirlo.

**Con trámites (`forms/`), para REDACTAR_DOCUMENTO.**
- Se reutiliza `forms/asistente.turno()` como submáquina, empezando en ENTREVISTA, con el expediente copiado a
  `borrador['respuestas']`.
- Las plantillas de los escritos van en la tabla `formularios`, que ya existe.
- **No entra en la ronda 3** (ver `trabajo_futuro.md`, C6).

## 4. Base de datos

**Tablas que se reutilizan sin cambios:** `estudio_estudios`, `estudio_codigos`, `estudio_participantes`,
`estudio_prompts` (texto de cada prompt por md5), `categorias_persona`, `documento_categorias` y `formularios`.

**Columnas nuevas:**

| Tabla | Columna | Para qué |
|---|---|---|
| `estudio_intentos` | `estado text` | El estado actual de la conversación de esa situación |
| `estudio_intentos` | `expediente jsonb` | El expediente actual |
| `estudio_turnos` | `estado_antes text`, `estado_despues text` | La transición de cada mensaje |
| `estudio_turnos` | `expediente jsonb` | Copia del expediente después del mensaje; no se modifica después |
| `estudio_turnos` | `llamadas jsonb` | Cada llamada al LLM: tarea, md5 del prompt, respuesta cruda y segundos |
| `estudio_turnos` | `catalogo_version int` | Qué versión del catálogo se usó |

El estado y el expediente actuales viven en `estudio_intentos`, en el servidor. En trámites viajan con el navegador; en
el estudio no conviene, porque son datos de medición y el navegador los podría alterar.

**Tablas nuevas:**

```sql
-- El catálogo de casos que edita Karen (una fila por tipo de caso).
CREATE TABLE consulta_casos (
    id text PRIMARY KEY,               -- p. ej. 'extorsion_imagenes'
    titulo text NOT NULL,
    version int NOT NULL DEFAULT 1,
    spec_yaml text NOT NULL,           -- datos decisivos, por qué importan, texto de cada pregunta
    estado text NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'revisado', 'publicado')),
    updated_by text, updated_at timestamptz DEFAULT now());

-- Cada versión guardada, sin borrar nunca: así se sabe qué vio cada participante.
CREATE TABLE consulta_casos_versiones (
    caso_id text NOT NULL REFERENCES consulta_casos(id),
    version int NOT NULL,
    spec_yaml text NOT NULL,
    guardado_por text, guardado_at timestamptz DEFAULT now(),
    PRIMARY KEY (caso_id, version));
```

**Una tabla de versiones también para la definición del estudio** (`estudio_estudios_versiones`, con la misma forma).
Hoy `estudio_estudios` guarda solo la última versión; por eso no pudimos ver la v7 en la base y yo copié la versión
equivocada al armar la ronda 2.

## 5. ¿Qué va en la base y qué en el código?

**Criterio:** lo que edita una experta va en la base, con versiones. Lo que depende de la forma del código (cómo se lee
el JSON, qué campos existen) va en el código, en git y con pruebas. En los dos casos, cada mensaje registra el md5 del
prompt usado.

| Qué | Dónde | Por qué |
|---|---|---|
| Prompt de la orientación legal de cada condición | Base: definición del estudio (YAML), como hoy | Lo edita Karen; cambia entre condiciones |
| Catálogo de casos: datos decisivos, por qué importan y texto de cada pregunta | Base: `consulta_casos`, con versiones | Lo escribe Karen |
| Plantillas de los escritos | Base: `formularios`, como hoy | Las escribe Karen |
| A quién protege cada ley | Base: `documento_categorias`, como hoy | Lo etiquetan las expertas |
| Prompts de las tareas internas (`extraer_hechos`, `clasificar_caso`, `revisar_aplicabilidad`) | Código: `consulta/ia.py` | El programa lee su JSON; si cambian, cambian las pruebas |
| Estados, transiciones y reglas para decidir el evento | Código: `consulta/maquina.py` | Es la lógica del programa |
| Configuración de la búsqueda (k, reranker, HyDE) | Base: definición del estudio, como hoy | Se fija por estudio |
| Texto exacto de cada prompt usado | Base: `estudio_prompts`, por md5, como hoy | Para saber después qué prompt respondió cada mensaje |

## 6. Orden de construcción

1. `expediente.py` y `maquina.py` con sus pruebas (sin LLM ni base).
2. `catalogo.py` y el catálogo de las tres situaciones del estudio, validado con Karen.
3. `ia.py`, probado con las conversaciones reales de las rondas 1 y 2: ¿extrae bien el lugar y los datos decisivos?
   Ahí se miden las 7 fallas que tuvo el filtro.
4. `busqueda.py` y el parámetro para excluir leyes por persona en `main.py`.
5. Conexión con `study/api.py` (modo `expediente`) y las columnas nuevas.
6. Repetición de las conversaciones de la ronda 1 con el modo `expediente`, igual que se hizo con el filtro, antes de
   abrir la ronda 3.
7. Página para que Karen edite el catálogo, con versiones.

## Decisiones pendientes

- **Página del catálogo:** ¿Karen lo edita desde una página (como trámites) o basta con un YAML en el repo para la
  ronda 3? El YAML es más rápido de construir; la página es necesaria si lo va a cambiar seguido.
- **Clasificar el caso:** ¿el LLM elige el tipo de caso del catálogo (como `elegir_formulario` en trámites) o en el
  estudio se fija por situación? En el estudio se puede fijar por situación, lo que quita una fuente de error.
