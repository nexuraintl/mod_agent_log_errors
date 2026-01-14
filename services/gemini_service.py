"""
Servicio de diagnóstico con Gemini.
Utiliza la API de Gemini para analizar logs y generar diagnósticos.
"""
import json
import google.generativeai as genai
from models.log_entry import EntradaLog, Diagnostico, TipoError, Severidad
from config import obtener_configuracion


class ServicioGemini:
    """
    Genera diagnósticos de errores utilizando Gemini AI.
    Procesa logs y retorna análisis estructurados.
    """
    
    PROMPT_DIAGNOSTICO = """
Eres un experto en sistemas web (Nginx, PHP, FastCGI, Linux).
Analiza el siguiente log de error y proporciona un diagnóstico técnico.

LOG DE ERROR:
{log}

INFORMACIÓN ADICIONAL:
- Timestamp: {timestamp}
- Nivel: {nivel}
- Cliente IP: {cliente_ip}
- Servidor: {servidor}
- Request: {request}
- Archivo: {archivo}
- Línea: {linea}

Responde ÚNICAMENTE con un JSON válido (sin markdown ni texto adicional) con esta estructura exacta:
{{
    "tipo_error": "PHP Fatal" | "File Not Found" | "Database" | "Timeout" | "Permission" | "Otro",
    "severidad": "crítica" | "alta" | "media" | "baja",
    "resumen": "descripción breve en español del problema",
    "causa_probable": "explicación técnica detallada de la causa raíz",
    "archivo_afectado": "ruta del archivo o null",
    "linea": número o null,
    "recomendacion": "pasos específicos para resolver el problema",
    "requiere_atencion_inmediata": true | false
}}
"""
    
    def __init__(self):
        """Inicializa el servicio configurando la API de Gemini."""
        self._config = obtener_configuracion()
        genai.configure(api_key=self._config.gemini_api_key)
        self._modelo = genai.GenerativeModel(self._config.gemini_model)
    
    def diagnosticar(self, entrada: EntradaLog) -> Diagnostico:
        """
        Genera un diagnóstico para una entrada de log.
        
        Args:
            entrada: Log parseado a diagnosticar.
            
        Returns:
            Diagnostico con el análisis de Gemini.
        """
        prompt = self.PROMPT_DIAGNOSTICO.format(
            log=entrada.raw,
            timestamp=entrada.timestamp.isoformat(),
            nivel=entrada.nivel,
            cliente_ip=entrada.cliente_ip or "N/A",
            servidor=entrada.servidor or "N/A",
            request=entrada.request or "N/A",
            archivo=entrada.archivo or "N/A",
            linea=entrada.linea or "N/A"
        )
        
        try:
            respuesta = self._modelo.generate_content(prompt)
            texto_respuesta = respuesta.text.strip()
            
            # Limpiar respuesta si viene con markdown
            texto_respuesta = self._limpiar_respuesta_json(texto_respuesta)
            
            datos = json.loads(texto_respuesta)
            return self._crear_diagnostico(datos)
            
        except json.JSONDecodeError as e:
            return self._diagnostico_error(f"Error parseando respuesta de Gemini: {e}")
        except Exception as e:
            return self._diagnostico_error(f"Error en Gemini: {e}")
    
    def _limpiar_respuesta_json(self, texto: str) -> str:
        """
        Limpia la respuesta de Gemini eliminando markdown si existe.
        
        Args:
            texto: Respuesta cruda de Gemini.
            
        Returns:
            JSON limpio.
        """
        # Remover bloques de código markdown
        if texto.startswith("```"):
            lineas = texto.split("\n")
            # Eliminar primera y última línea (```json y ```)
            lineas = [l for l in lineas if not l.startswith("```")]
            texto = "\n".join(lineas)
        
        return texto.strip()
    
    def _crear_diagnostico(self, datos: dict) -> Diagnostico:
        """
        Crea un objeto Diagnostico desde el diccionario de Gemini.
        
        Args:
            datos: Diccionario con la respuesta de Gemini.
            
        Returns:
            Diagnostico validado.
        """
        # Mapear tipo de error
        tipo_mapa = {
            "PHP Fatal": TipoError.PHP_FATAL,
            "File Not Found": TipoError.FILE_NOT_FOUND,
            "Database": TipoError.DATABASE,
            "Timeout": TipoError.TIMEOUT,
            "Permission": TipoError.PERMISSION,
        }
        tipo = tipo_mapa.get(datos.get("tipo_error", ""), TipoError.OTRO)
        
        # Mapear severidad
        severidad_mapa = {
            "crítica": Severidad.CRITICA,
            "alta": Severidad.ALTA,
            "media": Severidad.MEDIA,
            "baja": Severidad.BAJA,
        }
        severidad = severidad_mapa.get(datos.get("severidad", ""), Severidad.MEDIA)
        
        return Diagnostico(
            tipo_error=tipo,
            severidad=severidad,
            resumen=datos.get("resumen", "Sin resumen disponible"),
            causa_probable=datos.get("causa_probable", "Causa no determinada"),
            archivo_afectado=datos.get("archivo_afectado"),
            linea=datos.get("linea"),
            recomendacion=datos.get("recomendacion", "Revisar logs manualmente"),
            requiere_atencion_inmediata=datos.get("requiere_atencion_inmediata", False)
        )
    
    def _diagnostico_error(self, mensaje: str) -> Diagnostico:
        """
        Crea un diagnóstico de error cuando Gemini falla.
        
        Args:
            mensaje: Mensaje de error.
            
        Returns:
            Diagnostico indicando el error.
        """
        return Diagnostico(
            tipo_error=TipoError.OTRO,
            severidad=Severidad.MEDIA,
            resumen="Error al generar diagnóstico",
            causa_probable=mensaje,
            archivo_afectado=None,
            linea=None,
            recomendacion="Revisar la conexión con Gemini y reintentar",
            requiere_atencion_inmediata=False
        )
