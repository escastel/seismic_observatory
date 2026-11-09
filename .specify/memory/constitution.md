<!--
Sync Impact Report
- Version change: unratified scaffold → 1.0.0
- Modified principles: placeholders → Arquitectura local reproducible; placeholders →
  Entrega de eventos idempotente y transaccional; placeholders → Consumidor como WAF y
  cuarentena auditable; placeholders → Integración espacial verificable; placeholders →
  Calidad y viabilidad financiera medibles
- Added sections: Stack Tecnológico y Límites; Flujo de Desarrollo y Calidad
- Removed sections: none
- Follow-up TODOs: confirmar la fecha histórica de ratificación del proyecto
-->

# Observatorio Sísmico Constitution

## Core Principles

### I. Arquitectura local reproducible
El stack obligatorio es Python con `aiokafka`, GeoPandas y `requests`; Apache Kafka;
PostgreSQL; FastAPI; Docker Compose; y un frontend Angular con Leaflet. Docker Compose
debe orquestar exactamente los cinco servicios locales definidos por el sistema. El
backend unificado debe ejecutarse exclusivamente con `docker compose up --build -d`.
El frontend publicado en Netlify se conectará al backend mediante un túnel ngrok.
Esta restricción garantiza una ejecución reproducible y evita divergencias entre
entornos de desarrollo y demostración.

### II. Entrega de eventos idempotente y transaccional
El Consumidor debe procesar eventos con semántica at-least-once. El offset de Kafka
solo puede confirmarse después de que el commit correspondiente en PostgreSQL haya
terminado exitosamente. La persistencia debe evitar duplicidades mediante la
comparación conjunta de `id` y `updated`, aplicando un upsert únicamente cuando el
evento recibido tenga la fecha de actualización más reciente. Ningún fallo de
persistencia puede producir una confirmación prematura del offset.

### III. Consumidor como WAF y cuarentena auditable
El Consumidor debe actuar como un WAF/Filtro de calidad, inspirado en la Sesión 6.
Todo evento inválido o anómalo, incluidas coordenadas falsas, debe insertarse en una
tabla de Cuarentena junto con el motivo concreto de rechazo. Está prohibido descartar
silenciosamente eventos o convertir errores de validación en éxitos. La cuarentena
debe permitir auditar qué se rechazó, por qué y cuándo.

### IV. Integración espacial verificable
GeoPandas debe cruzar cada coordenada con datos de Natural Earth mediante Point in
Polygon para extraer país, continente y subregión, habilitando filtros avanzados.
Los sismos marítimos deben clasificarse estrictamente como `Sin país asignado`;
está prohibido imputarles el país más cercano. Las reglas espaciales y sus datos de
referencia deben mantenerse reproducibles y ser verificables mediante pruebas o
evidencia equivalente.

### V. Calidad y viabilidad financiera medibles
La memoria técnica solo puede declarar viable una alternativa cuando `NPV > 0` e
`IRR > WACC`, conforme a la Sesión 7. Está prohibido usar ROI simple como criterio
para proyecciones largas. Las decisiones de calidad deben aplicar la regla de costes
1-10-100, priorizando la prevención y detección temprana frente al coste de corregir
fallos en producción. Los informes de calidad automáticos están fuera de alcance:
la evidencia y las conclusiones de calidad deben documentarse manualmente.

## Stack Tecnológico y Límites

El sistema debe usar únicamente el stack especificado en esta constitución para sus
componentes principales: Python (`aiokafka`, GeoPandas, `requests`), Apache Kafka,
PostgreSQL, FastAPI, Docker Compose, Angular y Leaflet. Netlify y ngrok se permiten
únicamente para publicar el frontend y establecer su túnel de conexión,
respectivamente. Queda prohibido usar Spark, Flink, Kubernetes, cualquier servicio
Cloud adicional o Streamlit. Estas exclusiones son límites estrictos de alcance y
no pueden sortearse mediante equivalentes que introduzcan la misma complejidad o
dependencia.

## Flujo de Desarrollo y Calidad

Todo cambio debe preservar la semántica at-least-once, el commit coordinado entre
PostgreSQL y el offset de Kafka, la cuarentena auditable y la clasificación espacial
marítima. Las revisiones deben comprobar la ejecución del backend con
`docker compose up --build -d`, la integración entre servicios, la idempotencia del
upsert por `id` y `updated`, y los casos de eventos inválidos y coordenadas marítimas.
Las decisiones económicas deben incluir NPV, IRR y WACC cuando aplique. La calidad
se revisa manualmente y sus resultados deben quedar documentados; no se generarán
informes automáticos de calidad.

## Governance

Esta constitución prevalece sobre prácticas locales que la contradigan. Toda
enmienda debe modificar este archivo mediante una propuesta revisable que describa
el impacto en principios, stack, límites, datos, operación y pruebas. La aprobación
debe verificar que no se debilitan la transaccionalidad, la idempotencia, la
cuarentena, la integración espacial ni los criterios financieros; cualquier
excepción debe quedar justificada explícitamente y aprobada por los responsables
del proyecto.

La versión usa Semantic Versioning: MAJOR para eliminar o redefinir de forma
incompatible un principio o límite; MINOR para añadir un principio, sección o
requisito material; PATCH para aclaraciones y correcciones no semánticas. Toda
revisión de código, especificación o despliegue debe incluir una comprobación de
cumplimiento constitucional. La revisión de cumplimiento es obligatoria antes de
aceptar cambios que afecten al consumidor, los contratos de datos, la topología de
servicios, la clasificación espacial o la evaluación financiera.

**Version**: 1.0.0 | **Ratified**: TODO(RATIFICATION_DATE): confirmar la fecha histórica de adopción | **Last Amended**: 2026-11-09
