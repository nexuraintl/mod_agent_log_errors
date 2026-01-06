"""
Parseador de logs de Nginx/PHP.
Extrae información estructurada de las líneas de log.
"""
import re
from datetime import datetime
from typing import List
from models.log_entry import EntradaLog


class ParseadorLogs:
    """
    Parsea logs de Nginx y extrae campos estructurados.
    Soporta logs de error estándar de Nginx con mensajes PHP.
    """
    
    # Patrón para logs de Nginx: YYYY/MM/DD HH:MM:SS [level] PID#PID: mensaje
    PATRON_NGINX = re.compile(
        r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+"  # Timestamp
        r"\[(\w+)\]\s+"                                 # Nivel
        r"\d+#\d+:\s+"                                  # PID
        r"(.+)"                                         # Mensaje
    )
    
    # Patrón para extraer IP del cliente
    PATRON_CLIENTE = re.compile(r"client:\s+([\d.]+)")
    
    # Patrón para extraer servidor
    PATRON_SERVIDOR = re.compile(r"server:\s+([\w.\-]+)")
    
    # Patrón para extraer request
    PATRON_REQUEST = re.compile(r'request:\s+"([^"]+)"')
    
    # Patrón para errores PHP con archivo y línea
    PATRON_PHP_ARCHIVO = re.compile(r"in\s+(/[^\s:]+):(\d+)")
    
    def parsear_linea(self, linea: str) -> EntradaLog | None:
        """
        Parsea una línea de log individual.
        
        Args:
            linea: Línea de log cruda.
            
        Returns:
            EntradaLog con los campos extraídos, o None si no es válida.
        """
        linea = linea.strip()
        if not linea:
            return None
        
        match = self.PATRON_NGINX.match(linea)
        if not match:
            return None
        
        timestamp_str, nivel, mensaje = match.groups()
        
        # Parsear timestamp
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S")
        except ValueError:
            timestamp = datetime.now()
        
        # Extraer campos opcionales del mensaje
        cliente_ip = self._extraer_patron(self.PATRON_CLIENTE, mensaje)
        servidor = self._extraer_patron(self.PATRON_SERVIDOR, mensaje)
        request = self._extraer_patron(self.PATRON_REQUEST, mensaje)
        
        # Extraer archivo y línea de errores PHP
        archivo, linea_num = self._extraer_archivo_php(mensaje)
        
        return EntradaLog(
            timestamp=timestamp,
            nivel=nivel,
            mensaje=mensaje,
            cliente_ip=cliente_ip,
            servidor=servidor,
            request=request,
            archivo=archivo,
            linea=linea_num,
            raw=linea
        )
    
    def parsear_multiples(self, contenido: str) -> List[EntradaLog]:
        """
        Parsea múltiples líneas de log.
        Maneja logs multilínea (stack traces) concatenándolos.
        
        Args:
            contenido: Contenido completo del archivo de log.
            
        Returns:
            Lista de EntradaLog parseados.
        """
        lineas = contenido.strip().split("\n")
        logs = []
        log_actual = ""
        
        for linea in lineas:
            # Si la línea empieza con timestamp, es un nuevo log
            if self.PATRON_NGINX.match(linea):
                if log_actual:
                    entrada = self.parsear_linea(log_actual)
                    if entrada:
                        logs.append(entrada)
                log_actual = linea
            else:
                # Es continuación del log anterior (stack trace)
                log_actual += " " + linea.strip()
        
        # Procesar último log
        if log_actual:
            entrada = self.parsear_linea(log_actual)
            if entrada:
                logs.append(entrada)
        
        return logs
    
    def _extraer_patron(self, patron: re.Pattern, texto: str) -> str | None:
        """Extrae el primer grupo de un patrón regex."""
        match = patron.search(texto)
        return match.group(1) if match else None
    
    def _extraer_archivo_php(self, mensaje: str) -> tuple[str | None, int | None]:
        """Extrae archivo y línea de errores PHP."""
        match = self.PATRON_PHP_ARCHIVO.search(mensaje)
        if match:
            return match.group(1), int(match.group(2))
        return None, None
