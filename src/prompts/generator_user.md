CONTEXTO DEL REPOSITORIO:
- Rama: {rama}
- Últimos commits:
{historial}
- Archivos modificados:
{archivos}
- Estadísticas: {estadisticas}

ANÁLISIS SEMÁNTICO:
- Tipo detectado: {tipo_detectado}
- Scope detectado: {scope_detectado}
- Intención del cambio: {intencion}
- Resumen: {resumen}

{contexto_rag}

INSTRUCCIÓN CRÍTICA SOBRE EL SCOPE:
Si "{scope_detectado}" no está vacío, ÚSALO SIEMPRE como scope —
"si aplica" significa que ya se evaluó que aplica al calcularlo, no es
una invitación a omitirlo. Nunca dejes el scope vacío "()" cuando
{scope_detectado} sí tiene un valor.
NUNCA uses rutas completas como scope (ej: conversion/crypto_utils.py).
El scope debe ser solo el nombre del módulo: conversion, auth, api, etc.
Solo omite el scope (usa "tipo:" sin paréntesis, sin "()") cuando
{scope_detectado} está literalmente vacío.

INSTRUCCIÓN CRÍTICA SOBRE EL TIPO:
"{tipo_detectado}" es una pista heurística (basada en nombres de archivo y
palabras clave), no una clasificación confiable — puede estar mal, sobre
todo cuando el diff mezcla código de producción con sus tests. Tomá el
DIFF de abajo como fuente de verdad: el tipo debe reflejar el cambio de
mayor peso semántico (qué problema resuelve o qué capacidad agrega),
no el archivo que más aparece. Si el diff modifica tanto lógica de
producción como sus tests, clasificá por la lógica de producción
(feat/fix/perf/refactor), nunca "test" — "test" es solo para diffs que
únicamente tocan archivos de prueba.

DIFF:
{diff}