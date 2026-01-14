"""
Microservicio Monitor de Logs SSH.
API REST para monitorear logs remotos y generar diagnósticos con Gemini.
"""
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from config import obtener_configuracion
from services.ssh_service import ServicioSSH
from services.storage_service import ServicioAlmacenamiento
from services.log_watcher import VigilanteLogs
from models.log_entry import RegistroDiagnostico


# Instancia global del vigilante
vigilante: Optional[VigilanteLogs] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global vigilante
    vigilante = VigilanteLogs()
    yield
    if vigilante:
        vigilante.detener()


app = FastAPI(
    title="Monitor de Logs SSH",
    description="Microservicio para monitorear logs remotos vía SSH y diagnosticarlos con Gemini AI",
    version="1.0.0",
    lifespan=lifespan
)


# ==================== Modelos de Respuesta ====================

class RespuestaEstado(BaseModel):
    """Respuesta del endpoint de estado."""
    servicio: str
    version: str
    estado: str


class RespuestaVigilante(BaseModel):
    """Estado del vigilante de logs."""
    activo: bool
    ultima_linea_leida: int
    ultimo_check: Optional[str]
    logs_procesados_total: int
    intervalo_segundos: int


class RespuestaConexion(BaseModel):
    """Respuesta de prueba de conexión SSH."""
    exitoso: bool
    hostname: Optional[str]
    uptime: Optional[str]
    mensaje: str


class RespuestaDiagnostico(BaseModel):
    """Respuesta de diagnóstico inmediato."""
    procesados: int
    diagnosticos: list[RegistroDiagnostico]


# ==================== Endpoints ====================

@app.get("/health", response_model=RespuestaEstado, tags=["Sistema"])
async def verificar_salud():
    """
    Verifica que el servicio esté funcionando.
    Útil para health checks de contenedores/kubernetes.
    """
    return RespuestaEstado(
        servicio="Monitor de Logs SSH",
        version="1.0.0",
        estado="saludable"
    )


@app.get("/status", response_model=RespuestaVigilante, tags=["Vigilante"])
async def obtener_estado():
    """
    Obtiene el estado actual del vigilante de logs.
    Incluye información sobre monitoreo activo y estadísticas.
    """
    if not vigilante:
        raise HTTPException(status_code=500, detail="Vigilante no inicializado")
    
    estado = vigilante.obtener_estado()
    return RespuestaVigilante(**estado)


@app.post("/start", response_model=dict, tags=["Vigilante"])
async def iniciar_monitoreo():
    """
    Inicia el monitoreo periódico de logs.
    El vigilante revisará logs cada N segundos según configuración.
    """
    if not vigilante:
        raise HTTPException(status_code=500, detail="Vigilante no inicializado")
    
    vigilante.iniciar()
    config = obtener_configuracion()
    
    return {
        "mensaje": "Monitoreo iniciado",
        "intervalo_segundos": config.check_interval_seconds
    }


@app.post("/stop", response_model=dict, tags=["Vigilante"])
async def detener_monitoreo():
    """
    Detiene el monitoreo periódico de logs.
    Los diagnósticos existentes se mantienen guardados.
    """
    if not vigilante:
        raise HTTPException(status_code=500, detail="Vigilante no inicializado")
    
    vigilante.detener()
    
    return {"mensaje": "Monitoreo detenido"}


@app.post("/diagnose-now", response_model=RespuestaDiagnostico, tags=["Diagnóstico"])
async def diagnosticar_ahora():
    """
    Ejecuta un diagnóstico inmediato.
    Lee logs nuevos y genera diagnósticos sin esperar al scheduler.
    """
    if not vigilante:
        raise HTTPException(status_code=500, detail="Vigilante no inicializado")
    
    try:
        diagnosticos = vigilante.verificar_ahora()
        return RespuestaDiagnostico(
            procesados=len(diagnosticos),
            diagnosticos=diagnosticos
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en diagnóstico: {str(e)}")


@app.get("/diagnoses", response_model=list[RegistroDiagnostico], tags=["Diagnóstico"])
async def listar_diagnosticos(
    limite: int = Query(default=50, ge=1, le=500, description="Cantidad máxima de registros"),
    severidad: Optional[str] = Query(default=None, description="Filtrar por severidad")
):
    """
    Lista los diagnósticos guardados.
    Soporta paginación y filtrado por severidad.
    """
    almacenamiento = ServicioAlmacenamiento()
    
    if severidad:
        return almacenamiento.obtener_por_severidad(severidad)[:limite]
    
    return almacenamiento.obtener_recientes(limite)


@app.get("/diagnoses/count", response_model=dict, tags=["Diagnóstico"])
async def contar_diagnosticos():
    """
    Cuenta el total de diagnósticos guardados.
    """
    almacenamiento = ServicioAlmacenamiento()
    return {"total": almacenamiento.contar()}


@app.delete("/diagnoses", response_model=dict, tags=["Diagnóstico"])
async def limpiar_diagnosticos():
    """
    Elimina todos los diagnósticos guardados.
    ⚠️ Esta acción no se puede deshacer.
    """
    almacenamiento = ServicioAlmacenamiento()
    almacenamiento.limpiar()
    return {"mensaje": "Todos los diagnósticos han sido eliminados"}


class LogManual(BaseModel):
    """Log enviado manualmente para diagnóstico."""
    log: str


@app.post("/diagnose-manual", response_model=RegistroDiagnostico, tags=["Diagnóstico"])
async def diagnosticar_manual(datos: LogManual):
    """
    ⚠️ SOLO PARA PRUEBAS - NO USAR EN PRODUCCIÓN
    
    Envía un log manualmente y obtiene el diagnóstico de Gemini.
    Útil para probar sin conexión SSH.
    
    Ejemplo de log:
    2026/01/02 08:50:24 [error] 1641#1641: *13100 PHP Fatal error: ...
    """
    from datetime import datetime
    from uuid import uuid4
    from services.log_parser import ParseadorLogs
    from services.gemini_service import ServicioGemini
    
    parseador = ParseadorLogs()
    gemini = ServicioGemini()
    almacenamiento = ServicioAlmacenamiento()
    
    # Parsear el log
    entrada = parseador.parsear_linea(datos.log)
    
    if not entrada:
        raise HTTPException(status_code=400, detail="Log inválido. Formato esperado: YYYY/MM/DD HH:MM:SS [level] ...")
    
    # Diagnosticar con Gemini
    diagnostico = gemini.diagnosticar(entrada)
    
    # Crear registro
    registro = RegistroDiagnostico(
        id=str(uuid4()),
        fecha_procesamiento=datetime.now(),
        log=entrada,
        diagnostico=diagnostico
    )
    
    # Guardar
    almacenamiento.guardar(registro)
    
    return registro


@app.get("/test-connection", response_model=RespuestaConexion, tags=["Sistema"])
async def probar_conexion():
    """
    Prueba la conexión SSH al servidor remoto.
    Útil para verificar credenciales y conectividad.
    """
    servicio = ServicioSSH()
    resultado = servicio.probar_conexion()
    return RespuestaConexion(**resultado)


# ==================== Punto de Entrada ====================

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

