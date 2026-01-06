"""
Servicio de almacenamiento de diagnósticos.
Guarda y recupera diagnósticos en formato JSON.
"""
import json
import os
from datetime import datetime
from typing import List
from models.log_entry import RegistroDiagnostico
from config import obtener_configuracion


class ServicioAlmacenamiento:
    """
    Gestiona el almacenamiento persistente de diagnósticos.
    Utiliza archivos JSON para guardar los registros.
    """
    
    def __init__(self):
        """Inicializa el servicio y crea el directorio si no existe."""
        self._config = obtener_configuracion()
        self._ruta_archivo = self._config.diagnoses_file
        self._asegurar_directorio()
    
    def _asegurar_directorio(self) -> None:
        """Crea el directorio de datos si no existe."""
        directorio = os.path.dirname(self._ruta_archivo)
        if directorio and not os.path.exists(directorio):
            os.makedirs(directorio)
    
    def guardar(self, registro: RegistroDiagnostico) -> None:
        """
        Guarda un nuevo diagnóstico en el archivo JSON.
        
        Args:
            registro: Registro de diagnóstico a guardar.
        """
        registros = self.obtener_todos()
        registros.append(registro)
        self._escribir_archivo(registros)
    
    def guardar_multiples(self, registros_nuevos: List[RegistroDiagnostico]) -> None:
        """
        Guarda múltiples diagnósticos de una vez.
        
        Args:
            registros_nuevos: Lista de registros a guardar.
        """
        registros = self.obtener_todos()
        registros.extend(registros_nuevos)
        self._escribir_archivo(registros)
    
    def obtener_todos(self) -> List[RegistroDiagnostico]:
        """
        Obtiene todos los diagnósticos guardados.
        
        Returns:
            Lista de registros de diagnóstico.
        """
        if not os.path.exists(self._ruta_archivo):
            return []
        
        try:
            with open(self._ruta_archivo, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
                return [RegistroDiagnostico(**r) for r in datos]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def obtener_por_severidad(self, severidad: str) -> List[RegistroDiagnostico]:
        """
        Filtra diagnósticos por severidad.
        
        Args:
            severidad: Nivel de severidad a filtrar.
            
        Returns:
            Lista de registros con esa severidad.
        """
        todos = self.obtener_todos()
        return [r for r in todos if r.diagnostico.severidad.value == severidad]
    
    def obtener_recientes(self, limite: int = 10) -> List[RegistroDiagnostico]:
        """
        Obtiene los diagnósticos más recientes.
        
        Args:
            limite: Cantidad máxima de registros a retornar.
            
        Returns:
            Lista de los registros más recientes.
        """
        todos = self.obtener_todos()
        ordenados = sorted(todos, key=lambda r: r.fecha_procesamiento, reverse=True)
        return ordenados[:limite]
    
    def contar(self) -> int:
        """
        Cuenta el total de diagnósticos guardados.
        
        Returns:
            Número total de registros.
        """
        return len(self.obtener_todos())
    
    def limpiar(self) -> None:
        """Elimina todos los diagnósticos guardados."""
        self._escribir_archivo([])
    
    def _escribir_archivo(self, registros: List[RegistroDiagnostico]) -> None:
        """
        Escribe la lista de registros al archivo JSON.
        
        Args:
            registros: Lista de registros a escribir.
        """
        datos = [r.model_dump(mode="json") for r in registros]
        
        with open(self._ruta_archivo, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2, default=str)
