"""
Las leyes del corpus que el catálogo de casos puede citar. Lo usan catalogo.py y expediente.py.
"""

# Ley → (documento del corpus, materia, jurisdicción). La jurisdicción es el estado donde vale la ley (la clave de
# su código penal), 'federal' o 'general' (leyes generales y nacionales: valen en todos los estados).
LEYES = {
    'cdmx': ('Código Penal de la Ciudad de México.md', 'penal', 'cdmx'),
    'queretaro': ('Código Penal del Estado de Querétaro.md', 'penal', 'queretaro'),
    'edomex': ('Código Penal del Estado de México.md', 'penal', 'edomex'),
    'morelos': ('Código PENALEM.md', 'penal', 'morelos'),
    'federal': ('Código Penal Federal.md', 'penal', 'federal'),
    'cnpp': ('Código Nacional de Procedimientos Penales.md', 'penal', 'general'),
    'ley_victimas': ('Ley General de Víctimas.md', 'penal', 'general'),
    'ley_extorsion': ('Ley General para Prevenir, Investigar y Sancionar Delitos en Materia de Extorsión.md', 'penal',
                      'general'),
    'ley_secuestro': ('Ley General para Delitos en Materia de Secuestro.md', 'penal', 'general'),
    'lgamvlv': ('Ley General de Acceso de las Mujeres a una Vida Libre de Violencias.md', 'penal', 'general'),
    'lfcdo': ('Ley Federal Contra la Delincuencia Organizada.md', 'penal', 'federal'),
    'lfra': ('Ley Federal de Responsabilidad Ambiental.md', 'penal', 'federal'),
    'lgeepa': ('LEY GENERAL DEL EQUILIBRIO ECOLÓGICO Y LA PROTECCIÓN AL AMBIENTE.md', 'penal', 'general'),
    'cc_cdmx': ('Código Civil para el Distrito Federal.md', 'familiar', 'cdmx'),
    'cpc_cdmx': ('Código de Procedimientos Civiles para el Distrito Federal (Texto vigente).md', 'familiar', 'cdmx'),
    'cnpcf': ('Código Nacional de Procedimientos Civiles y Familiares.md', 'familiar', 'general'),
}
CODIGOS = {k: v[0] for k, v in LEYES.items()}       # ley → documento (las llaves de `articulos` en cada regla)
JURISDICCION = {k: v[2] for k, v in LEYES.items()}
NOMBRES = {'cdmx': 'CDMX', 'queretaro': 'Querétaro', 'edomex': 'Edomex', 'morelos': 'Morelos', 'federal': 'Federal',
           'cnpp': 'CNPP', 'ley_victimas': 'Ley de Víctimas', 'ley_extorsion': 'Ley de Extorsión',
           'ley_secuestro': 'Ley de Secuestro', 'lgamvlv': 'Ley de Acceso de las Mujeres', 'lfcdo': 'LFCDO',
           'lfra': 'Ley de Resp. Ambiental', 'lgeepa': 'LGEEPA', 'cc_cdmx': 'Código Civil CDMX',
           'cpc_cdmx': 'Proc. Civiles CDMX', 'cnpcf': 'CNPCF'}
MATERIAS = ('penal', 'familiar')
