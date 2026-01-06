"""
Configuración centralizada del microservicio.
Carga las variables de entorno y las expone como un objeto tipado.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Configuracion(BaseSettings):
    """
    Configuración del microservicio cargada desde variables de entorno.
    Utiliza pydantic-settings para validación automática de tipos.
    """
    
    # Configuración SSH
    ssh_host: str = Field(..., alias="SSH_HOST")
    ssh_port: int = Field(22, alias="SSH_PORT")
    ssh_user: str = Field(..., alias="SSH_USER")
    ssh_password: str | None = Field(None, alias="SSH_PASSWORD")
    ssh_key_path: str | None = Field(None, alias="SSH_KEY_PATH")
    
    # Ruta del log remoto
    log_path: str = Field("/var/log/nginx/error.log", alias="LOG_PATH")
    
    # Intervalo de verificación en segundos
    check_interval_seconds: int = Field(60, alias="CHECK_INTERVAL_SECONDS")
    
    # Gemini
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.0-flash", alias="GEMINI_MODEL")
    
    # Almacenamiento
    diagnoses_file: str = Field("data/diagnoses.json", alias="DIAGNOSES_FILE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def obtener_configuracion() -> Configuracion:
    """
    Obtiene la configuración del sistema.
    Usa caché para evitar recargar el archivo .env en cada llamada.
    """
    return Configuracion()
