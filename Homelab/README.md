# Mi Homelab - Guía Inicial

Bienvenida a tu servidor personal. Este documento es un resumen del sistema construido sobre Debian, con las IPs, puertos y una explicación de cómo interactúa todo.

## Datos del Servidor
- **Sistema Operativo:** Debian Linux (Modo Servidor, sin suspensión).
- **Dirección IP Local:** `192.168.2.12`
- **Usuario SSH:** `valentina`
- **Carpeta Maestra:** `~/homelab/` (Aquí vive el archivo `docker-compose.yml` que controla todo).

## Servicios Instalados (Puertos)

| Servicio | Puerto | URL de Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| **Homepage** | `3000` | http://192.168.2.12:3000 | **El Panel Principal.** |
| **Portainer** | `9000` | http://192.168.2.12:9000 | **El Cuarto de Máquinas.** |
| **Jellyfin** | `8096` | http://192.168.2.12:8096 | **Tu Netflix Personal.** |
| **Nextcloud** | `8443` | https://192.168.2.12:8443 | **Tu Google Drive Privado.** |
| **qBittorrent**| `8080` | http://192.168.2.12:8080 | **El Descargador.** |
| **Prowlarr** | `9696` | http://192.168.2.12:9696 | **El Buscador.** |
| **Radarr** | `7878` | http://192.168.2.12:7878 | **El Gestor de Películas.** |
| **Sonarr** | `8989` | http://192.168.2.12:8989 | **El Gestor de Series.** |

## ¿Cómo funciona el ecosistema de medios? (El Flujo)

Montamos un ecosistema automatizado de entretenimiento conocido como la **"Pila *arr" (*arr stack)**.

1. **La Petición:** Entras a Radarr (o Sonarr) y añades la película que quieres ver.
2. **La Búsqueda:** Radarr le pregunta a **Prowlarr** dónde está.
3. **La Descarga:** Prowlarr le devuelve el mejor archivo a Radarr, y Radarr envía la orden a **qBittorrent**.
4. **La Organización:** Cuando qBittorrent termina al 100%, Radarr mueve el archivo a su carpeta definitiva (`/data/media/movies`).
5. **La Reproducción:** **Jellyfin** detecta la nueva película y la pone disponible en tu televisor.

## Estructura de Carpetas

Todo tu servidor vive dentro de la carpeta `~/homelab/`.
- `docker-compose.yml`: El archivo maestro.
- `config/`: Guarda las configuraciones, usuarios y bases de datos de cada aplicación.
- `data/`: La carpeta de datos pesados compartida.
  - `data/media/movies/`: Aquí terminan las películas ordenadas.
  - `data/media/tv/`: Aquí terminan las series ordenadas.

## Comandos de Supervivencia Básicos

- `cd ~/homelab` - Ir a la carpeta del servidor
- `docker compose up -d` - Encender todo
- `docker compose down` - Apagar todo el servidor
- `docker ps` - Ver qué programas están encendidos
- `docker restart nextcloud` - Reiniciar un programa específico
