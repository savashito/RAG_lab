# Diseño: máquina de estados con expediente de la consulta (ronda 3)

*10 de noviembre de 2026. Plan de implementación del punto C6 de `06_evaluation/trabajo_futuro.md`. Todavía no hay código.*

## Términos

- **Estado:** Siempre hay exactamente uno, y el siguiente depende solo del estado actual, la memoria (expediente de consulta) y del evento.
- **Evento:** un mensaje de la persona o un botón que presiona.
- **Transición:** la regla «estando en el estado X, si llega el evento E, pasa al estado Y».
- **Expediente de la consulta:** los datos del caso que el programa va anotando. Es la memoria
- **Dato del expediente:** cada dato que el programa anota en el expediente de la consulta, porque de él depende qué ley aplica (por ejemplo, el lugar de los hechos, la edad de la víctima, si piden dinero). La lista completa está en el catálogo de casos.
- **Catálogo de casos:** el archivo, escrito por Karen, con tres partes: (1) los datos del expediente, con el texto con que se pregunta cada uno; (2) los tipos de caso, cada uno con los datos del expediente que necesita; (3) las reglas: qué valores de los datos llevan a qué delito, con el artículo de cada código.

  --> pregunta a claud: las leyes aplican diferente si eres funcionario publico, servidor publico, mujer, hombre, de la tercera edad, menor de edad, donde estas, cuales otros hoy? 
  
  --> respuesta: sí. En derecho penal mexicano cambian qué ley aplica, el delito o la pena, sobre todo:
    (1) el **lugar de los hechos** (qué código penal estatal) y si la **materia es federal**;
    (2) la **edad**: si la víctima es menor de edad cambian delitos y agravantes, y si la persona señalada es menor de 18 no se le aplica el código penal sino la Ley Nacional del Sistema Integral de Justicia Penal para Adolescentes;
    (3) ser **mujer** (feminicidio, Ley General de Acceso de las Mujeres a una Vida Libre de Violencia, agravantes por razón de género);
    (4) ser **persona adulta mayor** o **con discapacidad** (agravantes y leyes de protección);
    (5) ser **servidor público** (delitos propios de servidores públicos y agravantes);
    (6) la **relación entre las partes**: pareja, familia (violencia familiar; algunos delitos entre familiares se persiguen por querella), relación de trabajo o jerárquica (hostigamiento);
    (7) pertenecer a un **pueblo o comunidad indígena** (derechos procesales, como intérprete);
    (8) ser **militar** (puede aplicar el fuero militar);
    (9) ser **persona extranjera** (aviso consular).

  También importa el **papel de quien consulta**: víctima, persona señalada o familiar. «Servidor público» y «funcionario público» se usan casi como sinónimos; Karen debe confirmar la lista y decir cuáles aplican a las tres situaciones del estudio.

  --> pregunta a claud: Tambien en que casos necesitamos que informacion? osea por que tendriamos que identificar el tipo de caso y saber antes que datos se ocupan para ese caso especifico no?
  
  --> respuesta: sí, por eso hay que identificar el tipo de caso primero: los datos del expediente dependen del caso (en extorsión importa si hubo dinero de por medio; en hostigamiento, si quien manda los mensajes es superior). Rediseño: hay dos niveles de datos del expediente. **Generales**, que se piden en todos los casos: lugar de los hechos, papel de quien consulta y si alguna persona involucrada es menor de edad. **Del tipo de caso**, que salen del catálogo una vez identificado el caso. El tipo de caso es, entonces, el primer dato del expediente.

  --> pregunta a claud: se va identificar el tipo de caso? el LLM lo va identificar? se va guardar en la memoria que es para ese caso especifico?
  
  --> respuesta: sí a las tres. El LLM elige el tipo de caso de la **lista cerrada** del catálogo (temperatura 0, respuesta en JSON, con la opción «ninguno»), igual que `elegir_formulario` en trámites; Python revisa que el tipo exista y lo guarda en el expediente (`tipos_caso`). Puede ser más de uno: «Las fotos» es extorsión y también amenaza de difundir imágenes íntimas; entonces los datos del expediente son la unión de los dos. Si el LLM elige «ninguno», el asistente le pide a la persona que cuente qué pasó con otras palabras (sigue en LLENAR_EXPEDIENTE). En el estudio, además, Python conoce la situación, así que guardamos las dos cosas: lo que eligió el LLM y lo esperado por la situación, para medir cuántas veces el LLM clasifica bien.

  --> pregunta a claud: El yml va tener esa informacion de los casos?
  
  --> respuesta: sí. El catálogo es un archivo YAML con una entrada por tipo de caso: cómo se describe (para que el LLM lo reconozca), sus datos del expediente, por qué importa cada uno y el texto con que se pregunta. Los datos del expediente generales van al inicio del mismo archivo. Ejemplo en la sección 7.
  
- **Programa:** el código en Python de `apps/rewrite_lab`. «Código penal» siempre se escribe completo.

## 1. Principios

1. **La máquina de estados es una función pura.** Recibe el estado, el expediente, el evento y el catálogo; devuelve el nuevo estado, el nuevo expediente, lo que se le muestra a la persona y un registro. No toca la base de datos ni llama al LLM directamente: recibe esos servicios como parámetros. Así se prueba sin servidor, igual que `forms/asistente.py` con `tests/test_asistente.py`.
2. **Python decide las transiciones,** El LLM solo extrae datos, escribe la orientación y revisa la aplicabilidad, python recibe los datos extraidos por la LLM, actualiza la memoria (expediente)
3. **Todo se registra en cada mensaje:** estado antes y después, transición, expediente y el md5 de cada prompt usado. Así no hay que reconstruir decisiones después, como pasó con el filtro en la ronda 2.

   --> pregunta a claud: como lo vas a implementar? osea te refieres a un historial de toda la conversacion, agregando el estado actual por mensaje, y asi haras seguimiento?
   
   --> respuesta: sí. La tabla `estudio_turnos` ya guarda una fila por mensaje de la persona (su mensaje y la respuesta del asistente), en orden; esa es la historia de la conversación. A cada fila se le agregan el estado antes y después, una copia del expediente después del mensaje y las llamadas al LLM con el md5 de su prompt. Para no recorrer toda la historia en cada mensaje, el estado y el expediente actuales también se guardan en `estudio_intentos` (una fila por persona y situación). Con eso se puede reconstruir, mensaje por mensaje, qué sabía el asistente y por qué preguntó o respondió.
4. **(Rediseñado) Una sola fuente de verdad, congelada al abrir el estudio.** El catálogo de casos y los prompts viven en archivos del repo (git guarda su historia). Al abrir la ronda 3, la definición del estudio queda **congelada**: el programa no deja editarla mientras el estudio esté abierto; un cambio exige un estudio nuevo con otro id. Cada mensaje registra el md5 del catálogo y de cada prompt, y la página de administración del estudio muestra en grande el commit y los md5 en uso.

  --> pregunta a claud: a que te refieres con catalogo? catalogo de que? sigues siendo ambigo, te refieres a lo que se define como crrecto? por que tener versiones, por que no mejor solo fijar una cosa. lo de los promps concuerdo, y que sea muy evidente que version se usa para el estudio
  
  --> respuesta: el **catálogo de casos** es la lista de tipos de caso (por ejemplo «extorsión con imágenes íntimas», «hostigamiento sexual en el trabajo», «lesiones en una riña») con, para cada uno, sus datos del expediente y cómo se pregunta cada dato. **No es la clave de respuestas** (lo que se califica como correcto en el cuestionario), que sigue en la definición del estudio. Sobre las versiones: tienes razón, no hacen falta. El problema de la ronda 2 no fue que faltaran versiones, sino que la definición se podía editar con el estudio abierto y que copié una copia vieja. Con un solo archivo como fuente de verdad, congelado al abrir el estudio y con su md5 en cada mensaje, se resuelve más simple. Quité las tablas de versiones (sección 4).


## 2. Módulos nuevos

Una carpeta nueva, `apps/rewrite_lab/consulta/`, con la misma forma que `forms/`:

| Archivo | Qué contiene | ¿Llama al LLM o a la base? |
|---|---|---|
| `maquina.py` | Los estados, la tabla `TRANSICIONES` y la función `turno()` | No |
| `expediente.py` | La forma del expediente, cómo se combinan datos nuevos y la función `datos_faltantes()` | No |
| `catalogo.py` | Cargar y validar el catálogo de casos (`catalogo_casos.yaml`) y calcular su md5 | No |
| `catalogo_casos.yaml` | El catálogo de casos (lo escribe Karen; ejemplo en la sección 7) | — |
| `ia.py` | Las tareas del LLM: `clasificar_caso`, `extraer_hechos`, `revisar_aplicabilidad`. Cada una con su prompt fijo y salida JSON | Sí, el LLM |
| `busqueda.py` | Convierte el expediente en filtros para el buscador (código penal del lugar de los hechos, leyes nacionales, leyes según a quién protegen) y llama al chat existente | Sí, el buscador y el LLM |

(Rediseño: se quitaron `store.py` y `api.py`. Para la ronda 3 el catálogo es un archivo del repo, sin tablas ni página de edición.)

--> pregunta a claud: que es faltan_decisivos? es como requiero_mas_informacion? que regresa? que recibe? 

--> respuesta: es parecida, pero no regresa sí o no: regresa **cuáles** datos faltan, en orden, para que Python sepa qué preguntar primero. La renombro a `datos_faltantes()`:

```python
def datos_faltantes(expediente: dict, catalogo: dict) -> list[dict]:
    """Los datos del expediente sin valor en el expediente, en el orden en que se preguntan: primero los generales,
    luego los de cada tipo de caso del expediente. Cada elemento trae el id del dato, por qué importa y la pregunta.
    Lista vacía = ya están todos → transición a ORIENTACIÓN."""
```

Recibe el expediente y el catálogo; no llama al LLM ni a la base. Mientras el tipo de caso no esté identificado, regresa solo los generales más «tipo de caso».

`turno()` quedaría así:

```python
def turno(estado, expediente, evento, catalogo, ia, buscar) -> tuple[str, dict, dict, dict]:
    """Devuelve (estado nuevo, expediente nuevo, salida para la persona, registro del mensaje)."""
```

- `ia` es el objeto de `consulta/ia.py`; en las pruebas se usa uno falso.
- `buscar(expediente, mensajes)` es el puente de `busqueda.py` hacia el chat actual; en las pruebas también es falso.

## 3. Conexión con el código actual

**Con el estudio (`study/`).** El estudio ya asigna una condición a cada persona y la guarda en `estudio_participantes.condicion`.

- La definición del estudio (YAML) gana un campo por condición: `asistente.modo: actual | expediente`. Así la ronda 3 compara las dos condiciones con la asignación aleatoria que ya existe.
- En `study/api.py`, `p_preguntar_stream` revisa el modo. Con `actual`, sigue igual. Con `expediente`, llama a `consulta.maquina.turno()`.
- La respuesta sigue llegando al navegador por el mismo streaming: la página del estudio no cambia. En LLENAR_EXPEDIENTE la salida es la pregunta del catálogo, sin streaming del LLM; en ORIENTACIÓN, se transmite la respuesta del LLM.

**Con el buscador (`main.py`).**
- `chat_event_dicts` ya acepta `jurisdicciones`. `busqueda.py` se lo pasa desde el expediente (lugar de los hechos) y apaga el filtro por estado actual (`gate=False`), porque el expediente ya decidió el lugar.
- Hay que agregar un parámetro para excluir leyes según la persona, usando las etiquetas que ya existen en `documento_categorias` (por ejemplo, la ley de violencia contra las mujeres solo si la víctima es mujer). Es la fase 2 que `categorias.py` ya anticipa.

**Con el filtro por estado (`jurisdiction_gate.py`).** `extraer_lugares` ya separa el lugar de los hechos de otros lugares. `consulta/ia.py` lo reutiliza dentro de `extraer_hechos` en vez de reescribirlo.

**Con trámites (`forms/`), para REDACTAR_DOCUMENTO.**
- Se reutiliza `forms/asistente.turno()` como submáquina, empezando en ENTREVISTA, con el expediente copiado a `borrador['respuestas']`.
- Las plantillas de los escritos van en la tabla `formularios`, que ya existe.
- **No entra en la ronda 3** (ver `trabajo_futuro.md`, C6).

## 4. Base de datos

**Tablas que se reutilizan sin cambios:** `estudio_estudios`, `estudio_codigos`, `estudio_participantes`, `estudio_prompts` (texto de cada prompt por md5), `categorias_persona`, `documento_categorias` y `formularios`.

**Columnas nuevas:**

| Tabla | Columna | Para qué |
|---|---|---|
| `estudio_intentos` | `estado text` | El estado actual de la conversación de esa situación |
| `estudio_intentos` | `expediente jsonb` | El expediente actual |
| `estudio_turnos` | `estado_antes text`, `estado_despues text` | La transición de cada mensaje |
| `estudio_turnos` | `expediente jsonb` | Copia del expediente después del mensaje; no se modifica después |
| `estudio_turnos` | `llamadas jsonb` | Cada llamada al LLM: tarea, md5 del prompt, respuesta cruda y segundos |
| `estudio_turnos` | `catalogo_md5 text` | Qué catálogo se usó (md5 del archivo) |

El estado y el expediente actuales viven en `estudio_intentos`, en el servidor. En trámites viajan con el navegador; en el estudio no conviene, porque son datos de medición y el navegador los podría alterar.

**Tablas nuevas:** ninguna (rediseño).

--> pregunta a claud:porque versionar los casos de consulta? por que no simplificarlo y solo tener un source of truth? que ganamos con versionarlo? vale la pena?

--> respuesta: no vale la pena para la ronda 3. Una tabla de versiones solo ganaría poder editar el catálogo desde una página y ver cada versión en la base; git ya da la historia del archivo. Lo que sí hace falta es una sola fuente de verdad que no cambie durante el estudio: el archivo `catalogo_casos.yaml`, congelado al abrir el estudio, con su md5 guardado en cada mensaje. Quité `consulta_casos` y `consulta_casos_versiones`. Si más adelante Karen necesita editar el catálogo seguido desde una página, se agregan.

**Cambio en el estudio, en vez de una tabla de versiones:** que `estudio_estudios` no permita editar la definición mientras el estado sea `abierto` (hoy sí lo permite; así se editó la ronda 1 a la v9). Para cambiar algo, se cierra el estudio y se abre uno nuevo con otro id.

## 5. ¿Qué va en la base y qué en el código?

**Criterio (rediseñado):** lo que define el estudio y no debe cambiar mientras está abierto va en archivos del repo o en la definición del estudio congelada. En la base van los datos que produce el estudio (mensajes, expedientes, respuestas de las personas). Cada mensaje registra el md5 de cada prompt y del catálogo usados.

| Qué | Dónde | Por qué |
|---|---|---|
| Prompt de la orientación legal de cada condición | Base: definición del estudio (YAML), como hoy, congelada al abrir | Lo edita Karen; cambia entre condiciones |
| Catálogo de casos: tipos de caso, datos del expediente, por qué importan y texto de cada pregunta | Repo: `consulta/catalogo_casos.yaml` | Lo escribe Karen; git guarda la historia |
| Plantillas de los escritos | Base: `formularios`, como hoy | Las escribe Karen |
| A quién protege cada ley | Base: `documento_categorias`, como hoy | Lo etiquetan las expertas |
| Prompts de las tareas internas (`extraer_hechos`, `clasificar_caso`, `revisar_aplicabilidad`) | Código: `consulta/ia.py` | El programa lee su JSON; si cambian, cambian las pruebas |
| Estados, transiciones y reglas para decidir el evento | Código: `consulta/maquina.py` | Es la lógica del programa |
| Configuración de la búsqueda (k, reranker, HyDE) | Base: definición del estudio, como hoy | Se fija por estudio |
| Texto exacto de cada prompt usado | Base: `estudio_prompts`, por md5, como hoy | Para saber después qué prompt respondió cada mensaje |

## 6. Orden de construcción

1. `expediente.py` y `maquina.py` con sus pruebas (sin LLM ni base).
2. `catalogo.py` y el catálogo de las tres situaciones del estudio, validado con Karen.
3. `ia.py`, probado con las conversaciones reales de las rondas 1 y 2: ¿extrae bien el lugar y los datos del expediente? Ahí se miden las 7 fallas que tuvo el filtro.
4. `busqueda.py` y el parámetro para excluir leyes por persona en `main.py`.
5. Conexión con `study/api.py` (modo `expediente`) y las columnas nuevas.
6. Repetición de las conversaciones de la ronda 1 con el modo `expediente`, igual que se hizo con el filtro, antes de abrir la ronda 3.
7. Bloquear la edición de un estudio abierto en `study/store.py`.

## 7. Ejemplo del catálogo de casos (`consulta/catalogo_casos.yaml`)

Karen debe revisar y completar los datos y las preguntas.

```yaml
# Datos del expediente que se piden en todos los casos, antes que los del tipo de caso.
generales:
  - id: lugar_hechos
    por_que: Cada estado tiene su propio código penal.
    pregunta: ¿En qué estado pasó? Lo necesito porque cada estado tiene su propio código penal.
  - id: papel
    valores: [victima, persona_senalada, familiar_o_tercero]
    por_que: Los derechos y los pasos cambian si eres la víctima o la persona señalada.
    pregunta: ¿Esto te pasó a ti, te acusan a ti, o le pasó a otra persona?
  - id: menor_de_edad
    por_que: Si alguna persona involucrada es menor de 18 años cambian el delito, las penas o la ley.
    pregunta: ¿Alguna de las personas involucradas es menor de 18 años?

casos:
  - id: extorsion_imagenes
    titulo: Te piden dinero a cambio de no publicar fotos o videos íntimos
    descripcion: Alguien amenaza con difundir imágenes íntimas si no se le paga.   # la usa el LLM para clasificar
    datos:
      - id: pide_dinero
        por_que: Si hay dinero de por medio es extorsión (Ley General en materia de Extorsión).
        pregunta: ¿Te pidieron dinero o algo a cambio?
  - id: hostigamiento_laboral
    titulo: Mensajes sexuales de alguien del trabajo
    descripcion: Insinuaciones o propuestas sexuales de alguien del trabajo.
    datos:
      - id: es_superior
        por_que: Si es tu superior es hostigamiento sexual y la pena es mayor.
        pregunta: ¿Esa persona es tu jefe o supervisa tu trabajo?
  - id: lesiones_rina
    titulo: Una pelea y un citatorio
    descripcion: Pelea o golpes, y un citatorio de la Fiscalía.
    datos: []     # basta con los generales
```

## Decisiones pendientes

- **Clasificar el caso en el estudio:** propongo que lo clasifique el LLM, como lo haría con cualquier persona, y que Python guarde también el tipo esperado por la situación, para medir cuántas veces acierta. La alternativa es fijarlo por situación, que quita esa fuente de error pero ya no prueba lo que pasaría fuera del estudio.
- **Lista de características de la persona:** Karen debe confirmar cuáles de las de la sección «Términos» entran en los datos generales y cuáles solo en ciertos tipos de caso.
