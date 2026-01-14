# Monitor de Logs SSH con Diagnóstico Gemini

Microservicio en Python/FastAPI que monitorea logs de error remotos vía SSH y genera diagnósticos automáticos utilizando Gemini AI.

## 🎯 Características

- **Conexión SSH** segura a servidores remotos
- **Monitoreo periódico** de archivos de log
- **Parseo inteligente** de logs de Nginx/PHP
- **Diagnóstico con IA** usando Gemini
- **API REST** para control y consulta
- **Almacenamiento JSON** de diagnósticos

## 📋 Requisitos

- Python 3.10+
- Acceso SSH al servidor de logs
- API Key de Gemini

## 🚀 Instalación

```bash
# Clonar repositorio
git clone <url-repositorio>
cd error_logs

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## ⚙️ Configuración

Editar el archivo `.env` con tus credenciales:

```env
# SSH
SSH_HOST=tu-servidor.com
SSH_PORT=22
SSH_USER=usuario
SSH_PASSWORD=contraseña

# Ruta del log en el servidor remoto
LOG_PATH=/var/log/nginx/error.log

# Intervalo de verificación (segundos)
CHECK_INTERVAL_SECONDS=60

# Gemini
GEMINI_API_KEY=tu_api_key
```

## 🏃 Ejecución

```bash
# Iniciar servidor
uvicorn main:app --reload --port 8000

# O directamente
python main.py
```

## 📖 API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Estado del servicio |
| `GET` | `/status` | Estado del vigilante |
| `POST` | `/start` | Iniciar monitoreo |
| `POST` | `/stop` | Detener monitoreo |
| `POST` | `/diagnose-now` | Diagnóstico inmediato |
| `POST` | `/diagnose-manual` | ⚠️ **Solo pruebas** - Enviar log manual |
| `GET` | `/diagnoses` | Listar diagnósticos |
| `GET` | `/test-connection` | Probar conexión SSH |

### Documentación Interactiva

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📁 Estructura del Proyecto

```
error_logs/
├── main.py              # Aplicación FastAPI
├── config.py            # Configuración
├── models/
│   └── log_entry.py     # Modelos de datos
├── services/
│   ├── ssh_service.py   # Conexión SSH
│   ├── log_parser.py    # Parseo de logs
│   ├── gemini_service.py # Diagnóstico IA
│   ├── storage_service.py # Almacenamiento
│   └── log_watcher.py   # Monitoreo
├── tests/               # Tests unitarios
├── data/                # Datos generados
└── requirements.txt
```

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=.

# Tests específicos
pytest tests/test_log_parser.py -v
```

## 📊 Ejemplo de Diagnóstico

```json
{
  "id": "abc-123",
  "fecha_procesamiento": "2026-01-03T17:00:00",
  "log": {
    "timestamp": "2026-01-02T08:50:24",
    "nivel": "error",
    "mensaje": "PHP Fatal error: Call to a member function..."
  },
  "diagnostico": {
    "tipo_error": "PHP Fatal",
    "severidad": "alta",
    "resumen": "Error de referencia nula en método exists()",
    "causa_probable": "La variable no fue inicializada antes de llamar al método",
    "recomendacion": "Verificar que el objeto exista antes de llamar exists()",
    "requiere_atencion_inmediata": true
  }
}
```

## 🔒 Seguridad

- Las credenciales se almacenan en `.env` (no versionado)
- Soporta autenticación SSH por contraseña o llave
- Los diagnósticos se guardan localmente

## 📝 Licencia

MIT
