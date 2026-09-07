"""
Microservicio Monitor de Logs SSH.
API REST para monitorear logs remotos y generar diagnósticos con Gemini.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional, Union, Dict
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from config import obtener_configuracion
from services.ssh_service import ServicioSSH
from services.storage_service import ServicioAlmacenamiento
from services.log_watcher import VigilanteLogs
from models.log_entry import RegistroDiagnostico


# Sin basicConfig el root logger queda en WARNING y todo logger.info() del
# servicio se descarta antes de llegar a Cloud Logging.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)


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


class DatosIncidente(BaseModel):
    """Datos del incidente recibidos desde mod_agents."""
    ticket_id: Union[str, int]
    ticket_number: Optional[str] = None
    title: str
    ticket_text: str  # Contenido completo del artículo del ticket
    diagnostico: Optional[str] = None  # Diagnóstico previo de mod_agents
    entity: Optional[str] = None  # <--- CAMBIO: Se agregó el campo entity
    cliente_real: Optional[dict] = None
    cliente_znuny: Optional[dict] = None
    queue: Optional[str] = None
    state: Optional[str] = None
    priority: Optional[str] = None
    created: Optional[str] = None
    type_id: Optional[int] = None


class RespuestaIncidente(BaseModel):
    """Respuesta estructurada para mod_agents."""
    ticket_id: str
    entity: str
    logs_encontrados: int
    diagnosticos: list[RegistroDiagnostico]
    mensaje_resumen: str  # Resumen consolidado para Znuny
    logs_consultados: list[str] = []  # Líneas crudas usadas como soporte (verbatim)

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


@app.get("/test-connection", response_model=RespuestaConexion, tags=["Sistema"])
async def probar_conexion():
    """
    Prueba la conexión SSH al servidor remoto.
    Útil para verificar credenciales y conectividad.
    """
    servicio = ServicioSSH()
    resultado = servicio.probar_conexion()
    return RespuestaConexion(**resultado)


@app.post("/analyze-incident", response_model=RespuestaIncidente, tags=["Incidentes"])
async def analizar_incidente(datos: DatosIncidente):
    """
    Analiza un incidente buscando fatal errors relacionados con la entidad.
    
    Endpoint llamado por mod_agents cuando detecta un ticket tipo incidente.
    Busca logs fatales en el servidor SSH, los diagnostica con Gemini,
    y devuelve respuesta estructurada para actualizar Znuny.
    
    ⚠️ Esta operación puede tomar varios segundos debido a:
    - Conexión SSH al servidor remoto
    - Búsqueda de logs (grep)
    - Diagnóstico con Gemini de cada log encontrado
    """
    import re
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    from services.log_parser import ParseadorLogs
    from services.gemini_service import ServicioGemini
    
    servicio_ssh = ServicioSSH()
    parseador = ParseadorLogs()
    gemini = ServicioGemini()
    diagnosticos_resultado = []
    
    try:
        # CAMBIO: Extraer entidad verificando los dos posibles campos
        entidad = datos.entity
        if not entidad or entidad == "No identificado":
            if datos.cliente_real and isinstance(datos.cliente_real, dict):
                entidad = datos.cliente_real.get("entidad", "No identificado")

        with servicio_ssh:
            # Buscar fatal errors de la entidad en las últimas 2 horas
            logs_fatales = servicio_ssh.buscar_fatal_errors(entidad, horas=2)
        
        if not logs_fatales:
            return RespuestaIncidente(
                ticket_id=str(datos.ticket_id),
                entity=entidad,
                logs_encontrados=0,
                diagnosticos=[],
                mensaje_resumen=f"No se encontraron errores fatales relacionados con '{entidad}' en las últimas 2 horas."
            )
        
        # Parsear todos los logs primero
        logs_procesados = []
        for log_linea in logs_fatales:
            # grep puede anteponer "archivo:" cuando hay varios ficheros;
            # nos quedamos desde el timestamp del log en adelante.
            m = re.search(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} .*", log_linea)
            if m:
                log_linea = m.group(0)

            entrada = parseador.parsear_linea(log_linea)
            if entrada:
                logs_procesados.append(entrada)

        # La ventana de N horas del find aplica a la fecha de modificación del
        # archivo, no a cada línea: los archivos se escriben de forma continua y
        # el grep devuelve también errores viejos. Filtrar por el timestamp real
        # de cada entrada.
        # El parser produce timestamps naive en la hora local del server de logs
        # (America/Bogota), mientras el contenedor corre en UTC: el corte se
        # calcula en esa misma zona para no descartar líneas por el desfase.
        # Si falta la base de zonas horarias se usa un offset fijo (Colombia no
        # tiene horario de verano).
        cfg = obtener_configuracion()
        try:
            from zoneinfo import ZoneInfo
            ahora_local = datetime.now(ZoneInfo(getattr(cfg, "tz_logs", "America/Bogota")))
        except Exception:
            ahora_local = datetime.now(timezone.utc) + timedelta(hours=-5)
        umbral = ahora_local.replace(tzinfo=None) - timedelta(hours=2)
        parseados_total = len(logs_procesados)
        logs_procesados = [e for e in logs_procesados if e.timestamp and e.timestamp >= umbral]

        logger.info(
            "analyze-incident entidad=%r logs_crudos=%d parseados=%d en_ventana=%d",
            entidad, len(logs_fatales), parseados_total, len(logs_procesados),
        )

        if not logs_procesados:
            return RespuestaIncidente(
                ticket_id=str(datos.ticket_id),
                entity=entidad,
                logs_encontrados=0,
                diagnosticos=[],
                mensaje_resumen=f"No se encontraron errores fatales relacionados con '{entidad}' en las últimas 2 horas."
            )

        # Estrategia de Diagnóstico
        if len(logs_procesados) > 10:
            # ESTRATEGIA MASIVA: Diagnóstico consolidado
            logger.info(
                "Modo Masivo: %d logs encontrados. Generando resumen consolidado.",
                len(logs_procesados),
            )
            diagnostico_consolidado = gemini.analizar_incidente_completo(
                ticket_titulo=datos.title,
                ticket_texto=datos.ticket_text,
                diagnostico_inicial=datos.diagnostico,
                logs=logs_procesados
            )
            
            registro = RegistroDiagnostico(
                id=str(uuid4()),
                fecha_procesamiento=datetime.now(),
                log=logs_procesados[0], # Usamos el primero de muestra para el campo log
                diagnostico=diagnostico_consolidado
            )
            registro.diagnostico.resumen = f"[CONSOLIDADO {len(logs_procesados)} ERRORES] " + registro.diagnostico.resumen
            diagnosticos_resultado.append(registro)
            
        else:
            # ESTRATEGIA INDIVIDUAL: Diagnosticar 1 a 1 (max 10)
            for entrada in logs_procesados:
                diagnostico = gemini.diagnosticar(entrada)
                registro = RegistroDiagnostico(
                    id=str(uuid4()),
                    fecha_procesamiento=datetime.now(),
                    log=entrada,
                    diagnostico=diagnostico
                )
                diagnosticos_resultado.append(registro)
        
        # Generar mensaje resumen para Znuny
        if diagnosticos_resultado:
            resumen_partes = [f"Se encontraron {len(diagnosticos_resultado)} errores fatales de '{entidad}':"]
            for i, diag in enumerate(diagnosticos_resultado[:5], 1):  # Limitar a 5 en resumen
                resumen_partes.append(f"\n{i}. {diag.diagnostico.tipo_error}: {diag.diagnostico.resumen}")
            
            if len(diagnosticos_resultado) > 5:
                resumen_partes.append(f"\n... y {len(diagnosticos_resultado) - 5} más.")
            
            resumen_partes.append(f"\n\nRecomendación principal: {diagnosticos_resultado[0].diagnostico.recomendacion}")
            mensaje_resumen = "".join(resumen_partes)
        else:
            mensaje_resumen = f"Se encontraron {len(logs_procesados)} logs pero no pudieron ser parseados correctamente."

        # Líneas crudas que respaldan el diagnóstico (verbatim, dedup, las 5 más
        # recientes; logs_procesados viene en orden cronológico ascendente).
        logs_consultados = []
        vistos = set()
        for e in reversed(logs_procesados):
            linea = (e.raw or "").strip()
            if not linea:
                continue
            clave = linea[:200]
            if clave in vistos:
                continue
            vistos.add(clave)
            logs_consultados.append(linea if len(linea) <= 800 else linea[:800] + " […]")
            if len(logs_consultados) >= 5:
                break
        logs_consultados.reverse()  # de vuelta a orden cronológico

        return RespuestaIncidente(
            ticket_id=str(datos.ticket_id),
            entity=entidad,
            logs_encontrados=len(logs_procesados),
            diagnosticos=diagnosticos_resultado,
            mensaje_resumen=mensaje_resumen,
            logs_consultados=logs_consultados
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analizando incidente: {str(e)}"
        )


# ==================== Punto de Entrada ====================


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
