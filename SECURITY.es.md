<p align="center">
  <a href="SECURITY.md">English</a> |
  <a href="SECURITY.fr.md">Français</a> |
  <a href="SECURITY.zh-CN.md">中文</a> |
  <a href="SECURITY.es.md">Español</a> |
  <a href="SECURITY.ja.md">日本語</a> |
  <a href="SECURITY.pt.md">Português</a> |
  <a href="SECURITY.de.md">Deutsch</a> |
  <a href="SECURITY.ko.md">한국어</a>
</p>

# Politica de Seguridad

## Versiones Soportadas

| Version | Soportada |
|---------|----------|
| 2.2.x   | Si       |
| 2.1.x   | Si       |
| < 2.1   | No        |

## Reportar una Vulnerabilidad

Si descubre una vulnerabilidad de seguridad, reportela de manera responsable:

1. **No** abra una issue publica en GitHub
2. Envie un correo a **security@macaron-software.com**
3. Incluya:
   - Descripcion de la vulnerabilidad
   - Pasos para reproducir
   - Impacto potencial
   - Correccion sugerida (si la hay)

Acusaremos recibo en 48 horas y proporcionaremos una respuesta detallada en 7 dias.

## Medidas de Seguridad

### Autenticacion y Autorizacion

- Autenticacion JWT con renovacion de token
- Control de acceso basado en roles (RBAC): admin, project_manager, developer, viewer
- Integracion OAuth 2.0 (GitHub, Azure AD)
- Gestion de sesiones con cookies seguras

### Validacion de Entradas

- Proteccion contra inyeccion de prompt en todas las entradas LLM
- Saneamiento de entradas en todos los endpoints API
- Consultas SQL parametrizadas (sin interpolacion SQL directa)
- Proteccion contra recorrido de rutas de archivos

### Proteccion de Datos

- Limpieza de secretos en salidas de agentes (claves API, contrasenas, tokens)
- Sin secretos almacenados en codigo fuente o logs
- Configuracion basada en entorno para valores sensibles
- Modo WAL de SQLite para integridad de datos

### Seguridad de Red

- Cabeceras Content Security Policy (CSP)
- Configuracion CORS para endpoints API
- Limitacion de tasa por usuario/IP
- HTTPS obligatorio en produccion (via Nginx)

### Gestion de Dependencias

- Auditorias regulares de dependencias via `pip-audit`
- Analisis SAST con bandit y semgrep
- Misiones de seguridad automatizadas por proyecto (escaneos semanales)

## Politica de Divulgacion

Seguimos la divulgacion coordinada. Despues de publicar una correccion:
1. Credito al reportero (a menos que se solicite anonimato)
2. Publicacion de un aviso de seguridad en GitHub
3. Actualizacion del changelog con correcciones de seguridad
