"""
Modelos de datos para logs y diagnósticos.
Define las estructuras utilizadas en todo el microservicio.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class TipoError(str, Enum):
    """Tipos de errores detectables en los logs."""
    PHP_FATAL = "PHP Fatal"
    FILE_NOT_FOUND = "File Not Found"
    DATABASE = "Database"
    TIMEOUT = "Timeout"
    PERMISSION = "Permission"
    OTRO = "Otro"


class Severidad(str, Enum):
    """Niveles de severidad del error."""
    CRITICA = "crítica"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class EntradaLog(BaseModel):
    """
    Representa una entrada de log parseada.
    Contiene los campos extraídos del log de Nginx/PHP.
    """
    timestamp: datetime = Field(..., description="Fecha y hora del error")
    nivel: str = Field(..., description="Nivel del log (error, warning, etc)")
    mensaje: str = Field(..., description="Mensaje completo del error")
    cliente_ip: str | None = Field(None, description="IP del cliente")
    servidor: str | None = Field(None, description="Nombre del servidor")
    request: str | None = Field(None, description="Request HTTP que causó el error")
    archivo: str | None = Field(None, description="Archivo donde ocurrió el error")
    linea: int | None = Field(None, description="Línea del error")
    raw: str = Field(..., description="Log original sin procesar")


class Diagnostico(BaseModel):
    """
    Diagnóstico generado por Gemini para un log de error.
    Estructura la respuesta del modelo de IA.
    """
    tipo_error: TipoError = Field(..., description="Clasificación del tipo de error")
    severidad: Severidad = Field(..., description="Nivel de severidad")
    resumen: str = Field(..., description="Descripción breve del error")
    causa_probable: str = Field(..., description="Explicación técnica de la causa")
    archivo_afectado: str | None = Field(None, description="Archivo involucrado")
    linea: int | None = Field(None, description="Línea del código")
    recomendacion: str = Field(..., description="Acción sugerida para resolver")
    requiere_atencion_inmediata: bool = Field(..., description="Si necesita atención urgente")


class RegistroDiagnostico(BaseModel):
    """
    Combina un log con su diagnóstico para almacenamiento.
    Es la estructura que se guarda en el archivo JSON.
    """
    id: str = Field(..., description="Identificador único del registro")
    fecha_procesamiento: datetime = Field(..., description="Cuándo se procesó el log")
    log: EntradaLog = Field(..., description="Log original parseado")
    diagnostico: Diagnostico = Field(..., description="Diagnóstico de Gemini")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
