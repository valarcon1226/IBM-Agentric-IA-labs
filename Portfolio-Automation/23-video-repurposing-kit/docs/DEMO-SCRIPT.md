# Guion de Demostración: Kit de Reutilización de Video (1 minuto)

**Objetivo del video:** Demostrar cómo un podcaster o agencia puede convertir un video largo en 10 clips verticales para Reels/TikTok y un paquete completo para YouTube en minutos, de manera 100% local y gratis.

**Duración objetivo:** 60 segundos.

---

### [0:00 - 0:10] El Problema y la Promesa
- **Visual:** Grabación de pantalla mostrando un video horizontal de podcast de 1 hora en Premiere o DaVinci con una línea de tiempo abrumadora.
- **Voz en off:**
  > *"Editar 10 reels a mano a partir de un podcast suele tomar 4 horas: buscar momentos, recortar a 9:16, transcribir y subtitular palabra por palabra. Hoy te muestro cómo automatizarlo todo en tu propia computadora, 100% gratis y en minutos."*

---

### [0:10 - 0:25] Ejecución y Transcripción Local
- **Visual:** Terminal o interfaz web. Se ejecuta el comando:
  `python -m kit run podcast_episodio.mp4`
  Se ve la extracción del audio y la transcripción ultrarrápida con `faster-whisper` en CPU generando marcas de tiempo exactas por palabra.
- **Voz en off:**
  > *"El kit extrae el audio y transcribe localmente con faster-whisper. Detecta cada palabra y genera tanto el archivo JSON como los subtítulos SRT sin pagar un solo centavo de API."*

---

### [0:25 - 0:40] Detección Inteligente de Momentos y Edición
- **Visual:** Se abre la interfaz web (`http://localhost:8000`). Se muestra la tabla con los 5 a 10 momentos seleccionados, mostrando el segundo inicial, final, el gancho (hook) y el score de viralidad. El cursor ajusta un momento en 2 segundos.
- **Voz en off:**
  > *"Un modelo local (Ollama) o nuestra heurística identifica los 10 momentos de 20 a 60 segundos con mayor retención y gancho inicial. Puedes editarlos en la interfaz web si quieres ajustar algún detalle antes del render."*

---

### [0:40 - 0:50] Render Vertical 9:16 y Subtítulos Dinámicos
- **Visual:** Clic en 'Renderizar'. Se muestran los clips generados reproduciéndose en formato vertical 1080x1920 con la palabra activa iluminada en amarillo sobre subtítulos grandes con borde negro y audio con volumen perfecto.
- **Voz en off:**
  > *"Con un solo clic, ffmpeg recorta el video a 9:16 centrado, quema subtítulos dinámicos estilo TikTok con palabra resaltada y normaliza el audio a nivel profesional."*

---

### [0:50 - 1:00] Paquete de YouTube y Llamado a la Acción
- **Visual:** Se muestra el archivo `youtube_package.md` generado con 3 títulos virales, capítulos con tiempos listos para YouTube y 10 tags SEO.
- **Voz en off:**
  > *"Además, recibes el paquete completo para YouTube con capítulos y tags. De 4 horas a 30 minutos. Automatiza la presencia de tu marca hoy mismo."*

---

## Recursos necesarios para grabar la demo
1. Video de prueba en `23-video-repurposing-kit/test_video_2min.mp4`.
2. Servidor web iniciado con `python -m kit serve`.
3. Navegador Microsoft Edge en `http://localhost:8000`.
