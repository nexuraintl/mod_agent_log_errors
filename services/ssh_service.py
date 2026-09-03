"""
Servicio de conexión SSH.
Gestiona la conexión al servidor remoto y la lectura de archivos de log.
"""
import logging
import unicodedata
import paramiko
from typing import Optional
from config import obtener_configuracion

logger = logging.getLogger(__name__)


class ServicioSSH:
    """
    Gestiona conexiones SSH y ejecución de comandos remotos.
    Utiliza paramiko para la comunicación segura.
    """
    
    def __init__(self):
        """Inicializa el servicio con la configuración del sistema."""
        self._config = obtener_configuracion()
        self._cliente: Optional[paramiko.SSHClient] = None
    
    def conectar(self) -> None:
        """
        Establece conexión SSH con el servidor remoto.
        Soporta autenticación por contraseña o llave SSH.
        """
        self._cliente = paramiko.SSHClient()
        self._cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Preparar argumentos de conexión
        kwargs_conexion = {
            "hostname": self._config.ssh_host,
            "port": self._config.ssh_port,
            "username": self._config.ssh_user,
        }
        
        # Usar llave SSH si está configurada, sino usar contraseña
        if self._config.ssh_key_path:
            kwargs_conexion["key_filename"] = self._config.ssh_key_path
        else:
            kwargs_conexion["password"] = self._config.ssh_password
        
        self._cliente.connect(**kwargs_conexion)
    
    def desconectar(self) -> None:
        """Cierra la conexión SSH si está activa."""
        if self._cliente:
            self._cliente.close()
            self._cliente = None
    
    def ejecutar_comando(self, comando: str) -> str:
        """
        Ejecuta un comando en el servidor remoto.
        
        Args:
            comando: Comando a ejecutar en el servidor.
            
        Returns:
            Salida del comando como string.
            
        Raises:
            RuntimeError: Si no hay conexión activa.
            Exception: Si el comando falla.
        """
        if not self._cliente:
            raise RuntimeError("No hay conexión SSH activa. Llame a conectar() primero.")
        
        stdin, stdout, stderr = self._cliente.exec_command(comando)
        error = stderr.read().decode("utf-8")
        
        if error:
            raise Exception(f"Error ejecutando comando: {error}")
        
        return stdout.read().decode("utf-8")
    
    def obtener_archivo_mas_reciente(self) -> str:
        """
        Encuentra el archivo de log más reciente en el directorio configurado.
        
        Returns:
            Ruta completa del archivo más reciente.
        """
        directorio = self._config.log_path.rstrip("/")

        # Buscar el archivo modificado más recientemente. Los logs por cliente
        # se llaman *.error.log.<nodo>, no terminan en .log.
        comando = f"ls -t {directorio}/*error.log* 2>/dev/null | head -1"
        resultado = self.ejecutar_comando(comando).strip()
        
        if not resultado:
            # Si no hay .log, buscar cualquier archivo
            comando = f"ls -t {directorio}/* 2>/dev/null | head -1"
            resultado = self.ejecutar_comando(comando).strip()
        
        if not resultado:
            raise Exception(f"No se encontraron archivos en {directorio}")
        
        return resultado
    
    def leer_archivo_log(self, desde_linea: int = 0) -> tuple[str, int]:
        """
        Lee el archivo de log más reciente desde una línea específica.
        
        Args:
            desde_linea: Número de línea desde donde empezar (0 = inicio).
            
        Returns:
            Tupla con (contenido_nuevo, ultima_linea_leida).
        """
        # Obtener el archivo más reciente del directorio
        ruta_log = self.obtener_archivo_mas_reciente()
        logger.info("Leyendo archivo: %s", ruta_log)
        
        if desde_linea > 0:
            comando = f"tail -n +{desde_linea + 1} {ruta_log}"
        else:
            comando = f"cat {ruta_log}"
        
        contenido = self.ejecutar_comando(comando)
        lineas = contenido.strip().split("\n") if contenido.strip() else []
        total_lineas = desde_linea + len(lineas)
        
        return contenido, total_lineas
    
    def obtener_total_lineas(self) -> int:
        """
        Obtiene el número total de líneas del archivo de log más reciente.
        
        Returns:
            Número total de líneas.
        """
        ruta_log = self.obtener_archivo_mas_reciente()
        comando = f"wc -l < {ruta_log}"
        resultado = self.ejecutar_comando(comando)
        return int(resultado.strip())
    
    def buscar_fatal_errors(self, entidad: str, horas: int = 2) -> list[str]:
        """
        Busca errores fatales (PHP Fatal error) de una entidad en las últimas N horas.
        
        Args:
            entidad: Keyword/entidad a buscar (ej: 'floridablanca', 'yumbo')
            horas: Ventana de tiempo hacia atrás en horas (default: 2)
            
        Returns:
            Lista de líneas de log que contienen PHP Fatal error.
        """
        # LOG_PATH es el directorio con los error logs por cliente
        # (ej: /home/logs/error_log). Los archivos se llaman
        # www.<token>.gov.co.error.log.<nodo>
        directorio = self._config.log_path.rstrip("/")

        # Normalizar la entidad al token que aparece en el nombre del archivo:
        # sin acentos, en minúscula, quedándonos con la última palabra
        # ("Alcaldía de Floridablanca" -> "floridablanca").
        token = (
            unicodedata.normalize("NFKD", entidad or "")
            .encode("ascii", "ignore")
            .decode()
            .lower()
            .strip()
        )
        token = token.split()[-1] if token else ""
        if not token:
            logger.warning("buscar_fatal_errors: entidad vacía o no normalizable: %r", entidad)
            return []

        # 1. cd al directorio de logs por cliente
        # 2. MATCH POR ENTIDAD: archivos que contengan el token en su nombre
        # 3. MATCH TIPO ARCHIVO: *error.log*
        # 4. MATCH TIEMPO: modificados en las últimas N horas
        # 5. EXCLUSIÓN: ignora preproduccion
        # 6. CONTENIDO: "PHP Fatal error" (regex extendida) en los archivos hallados
        comando = f'''
        cd "{directorio}" 2>/dev/null && \
        find . -maxdepth 2 -type f -newermt "$(date -d '{horas} hour ago')" \
            -iname "*{token}*" \
            -iname "*error.log*" \
            -not -path "*preprod*" \
            -print0 2>/dev/null | \
        xargs -0 -r grep -aEH "PHP Fatal error" 2>/dev/null | tail -n 400 || true
        '''

        resultado = self.ejecutar_comando(comando)

        # Filtrar líneas vacías y retornar lista
        lineas = [linea.strip() for linea in resultado.split('\n') if linea.strip()]
        return lineas
    
    def probar_conexion(self) -> dict:
        """
        Prueba la conexión SSH y devuelve información del servidor.
        
        Returns:
            Diccionario con estado de la conexión y datos del servidor.
        """
        try:
            self.conectar()
            hostname = self.ejecutar_comando("hostname").strip()
            uptime = self.ejecutar_comando("uptime").strip()
            self.desconectar()
            
            return {
                "exitoso": True,
                "hostname": hostname,
                "uptime": uptime,
                "mensaje": "Conexión exitosa"
            }
        except Exception as e:
            return {
                "exitoso": False,
                "hostname": None,
                "uptime": None,
                "mensaje": f"Error de conexión: {str(e)}"
            }
    
    def __enter__(self):
        """Permite usar el servicio como context manager."""
        self.conectar()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra la conexión al salir del context manager."""
        self.desconectar()
