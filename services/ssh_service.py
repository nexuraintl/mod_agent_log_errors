"""
Servicio de conexión SSH.
Gestiona la conexión al servidor remoto y la lectura de archivos de log.
"""
import paramiko
from typing import Optional
from config import obtener_configuracion


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
        directorio = self._config.log_path
        
        # Buscar el archivo modificado más recientemente
        comando = f"ls -t {directorio}/*.log 2>/dev/null | head -1"
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
        print(f"Leyendo archivo: {ruta_log}")
        
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
