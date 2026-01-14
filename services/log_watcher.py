"""
Vigilante de logs.
Monitorea periódicamente el archivo de logs y procesa nuevas entradas.
"""
import uuid
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from models.log_entry import EntradaLog, RegistroDiagnostico
from services.ssh_service import ServicioSSH
from services.log_parser import ParseadorLogs
from services.gemini_service import ServicioGemini
from services.storage_service import ServicioAlmacenamiento
from config import obtener_configuracion


class VigilanteLogs:
    """
    Monitorea logs remotos periódicamente y genera diagnósticos.
    Coordina los servicios de SSH, parseo, Gemini y almacenamiento.
    """
    
    def __init__(
        self,
        servicio_ssh: Optional[ServicioSSH] = None,
        parseador: Optional[ParseadorLogs] = None,
        servicio_gemini: Optional[ServicioGemini] = None,
        almacenamiento: Optional[ServicioAlmacenamiento] = None
    ):
        """
        Inicializa el vigilante con los servicios necesarios.
        Permite inyección de dependencias para testing.
        """
        self._config = obtener_configuracion()
        
        # Servicios (inyectables para testing)
        self._ssh = servicio_ssh or ServicioSSH()
        self._parseador = parseador or ParseadorLogs()
        self._gemini = servicio_gemini or ServicioGemini()
        self._almacenamiento = almacenamiento or ServicioAlmacenamiento()
        
        # Estado del vigilante
        self._scheduler: Optional[BackgroundScheduler] = None
        self._ultima_linea: int = 0
        self._activo: bool = False
        self._ultimo_check: Optional[datetime] = None
        self._logs_procesados: int = 0
        
        # Callback opcional para notificaciones
        self._on_nuevo_diagnostico: Optional[Callable[[RegistroDiagnostico], None]] = None
    
    def iniciar(self) -> None:
        """
        Inicia el monitoreo periódico de logs.
        Ignora logs existentes y solo procesa los nuevos.
        """
        if self._activo:
            return
        
        # Obtener posición actual del archivo para ignorar logs existentes
        try:
            with self._ssh:
                self._ultima_linea = self._ssh.obtener_total_lineas()
                print(f"Iniciando monitoreo desde línea {self._ultima_linea} (ignorando logs existentes)")
        except Exception as e:
            print(f"Advertencia: No se pudo obtener posición inicial: {e}")
            self._ultima_linea = 0
        
        intervalo = self._config.check_interval_seconds
        
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self._verificar_logs,
            trigger=IntervalTrigger(seconds=intervalo),
            id="verificar_logs",
            replace_existing=True
        )
        self._scheduler.start()
        self._activo = True
    
    def detener(self) -> None:
        """Detiene el monitoreo periódico."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self._activo = False
    
    def verificar_ahora(self) -> list[RegistroDiagnostico]:
        """
        Ejecuta una verificación inmediata de logs.
        
        Returns:
            Lista de diagnósticos generados.
        """
        return self._verificar_logs()
    
    def obtener_estado(self) -> dict:
        """
        Obtiene el estado actual del vigilante.
        
        Returns:
            Diccionario con información del estado.
        """
        return {
            "activo": self._activo,
            "ultima_linea_leida": self._ultima_linea,
            "ultimo_check": self._ultimo_check.isoformat() if self._ultimo_check else None,
            "logs_procesados_total": self._logs_procesados,
            "intervalo_segundos": self._config.check_interval_seconds
        }
    
    def configurar_callback(self, callback: Callable[[RegistroDiagnostico], None]) -> None:
        """
        Configura un callback para nuevos diagnósticos.
        
        Args:
            callback: Función a llamar cuando se genera un diagnóstico.
        """
        self._on_nuevo_diagnostico = callback
    
    def _verificar_logs(self) -> list[RegistroDiagnostico]:
        """
        Verifica nuevos logs y genera diagnósticos.
        Método interno llamado por el scheduler.
        """
        diagnosticos = []
        self._ultimo_check = datetime.now()
        
        try:
            with self._ssh:
                # Leer nuevas líneas del log
                contenido, nueva_ultima_linea = self._ssh.leer_archivo_log(self._ultima_linea)
                
                if not contenido.strip():
                    return diagnosticos
                
                # Parsear logs
                entradas = self._parseador.parsear_multiples(contenido)
                
                if not entradas:
                    self._ultima_linea = nueva_ultima_linea
                    return diagnosticos
                
                # Procesar cada entrada
                for entrada in entradas:
                    registro = self._procesar_entrada(entrada)
                    diagnosticos.append(registro)
                    
                    if self._on_nuevo_diagnostico:
                        self._on_nuevo_diagnostico(registro)
                
                # Guardar todos los diagnósticos
                if diagnosticos:
                    self._almacenamiento.guardar_multiples(diagnosticos)
                    self._logs_procesados += len(diagnosticos)
                
                self._ultima_linea = nueva_ultima_linea
                
        except Exception as e:
            # Log del error pero no detener el vigilante
            print(f"Error verificando logs: {e}")
        
        return diagnosticos
    
    def _procesar_entrada(self, entrada: EntradaLog) -> RegistroDiagnostico:
        """
        Procesa una entrada de log y genera su diagnóstico.
        
        Args:
            entrada: Log parseado.
            
        Returns:
            Registro completo con log y diagnóstico.
        """
        diagnostico = self._gemini.diagnosticar(entrada)
        
        return RegistroDiagnostico(
            id=str(uuid.uuid4()),
            fecha_procesamiento=datetime.now(),
            log=entrada,
            diagnostico=diagnostico
        )
