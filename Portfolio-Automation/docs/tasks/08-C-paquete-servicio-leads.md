# 08-C · Paquete de servicio de lead generation (para vender el 08)

Carpeta: `Portfolio-Automation/08-lead-generator/service/` (nueva, solo esta; puedes LEER el resto del 08).
En el Trend Spotter, lead generation tiene la mejor relación del mercado: 205 avisos, 15 propuestas promedio, pago
mediano $190. El motor (08) ya existe; falta empaquetarlo como servicio.

1. `OFERTA.md` (español) y `OFFER.md` (inglés): una página para un cliente: qué recibe, en cuánto tiempo, 3 paquetes
   con precio sugerido (100, 300 y 500 leads) y qué NO incluye. Precios basados en los datos de arriba.
2. `secuencias/`: 3 secuencias de cold email (restaurantes, clínicas, inmobiliarias), 3 correos cada una, en español
   e inglés, cortas y personalizables con variables (`{{empresa}}`, `{{ciudad}}`), con línea de baja.
3. `entregable-plantilla.xlsx`: generado con el código del 08 desde `demo-directory` (datos ficticios), con las
   hojas que ya produce + una hoja "Seguimiento" (estado, fecha de contacto, respuesta). Script que la regenera.
4. `ENTREGABILIDAD.md`: checklist corto (dominio aparte, SPF, DKIM, DMARC, calentamiento, límites diarios,
   verificación de correos) y las normas que aplican: Ley 1581 de 2012 (Colombia), CAN-SPAM, GDPR para Europa.
5. `PROPUESTA-PLANTILLA.md`: texto de propuesta para Freelancer/Workana que enlaza el 08 y el entregable de ejemplo.

Sin datos personales reales en ningún archivo. Verificación (salida real): el script que regenera la plantilla y
`python -c` que abre el xlsx y lista sus hojas y número de filas.

Reglas: ponytail, sin commit ni push, sin secretos, no toques otras carpetas.
Al terminar escribe `docs/reviews/T-08-C.md` (español) con la salida real de cada comando.
