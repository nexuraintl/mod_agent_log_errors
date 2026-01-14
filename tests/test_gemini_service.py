"""
Tests del servicio Gemini.
Utiliza mocks para no consumir API real.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from models.log_entry import EntradaLog, TipoError, Severidad


@pytest.fixture
def entrada_log_ejemplo():
    """Entrada de log de ejemplo para tests."""
    return EntradaLog(
        timestamp=datetime(2026, 1, 2, 8, 50, 24),
        nivel="error",
        mensaje="PHP Fatal error: Call to a member function exists() on null",
        cliente_ip="35.191.73.170",
        servidor="www.yumbo.gov.co",
        request="GET /loader.php?lServicio=Tools2 HTTP/1.1",
        archivo="/home/portal/mod/Tools2/descargas.php",
        linea=233,
        raw="log completo original"
    )


class TestServicioGemini:
    """Tests para el servicio Gemini."""
    
    def test_diagnosticar_exitoso(self, entrada_log_ejemplo):
        """Verifica diagnóstico exitoso con respuesta válida."""
        respuesta_gemini = '''
        {
            "tipo_error": "PHP Fatal",
            "severidad": "alta",
            "resumen": "Error de referencia nula en método exists()",
            "causa_probable": "La variable no fue inicializada correctamente",
            "archivo_afectado": "/home/portal/mod/Tools2/descargas.php",
            "linea": 233,
            "recomendacion": "Verificar inicialización del objeto antes de llamar métodos",
            "requiere_atencion_inmediata": true
        }
        '''
        
        with patch('services.gemini_service.obtener_configuracion') as mock_config:
            mock_config.return_value.gemini_api_key = "fake-key"
            mock_config.return_value.gemini_model = "gemini-2.0-flash"
            
            with patch('services.gemini_service.genai') as mock_genai:
                # Configurar mock del modelo
                mock_modelo = MagicMock()
                mock_respuesta = MagicMock()
                mock_respuesta.text = respuesta_gemini
                mock_modelo.generate_content.return_value = mock_respuesta
                mock_genai.GenerativeModel.return_value = mock_modelo
                
                from services.gemini_service import ServicioGemini
                servicio = ServicioGemini()
                diagnostico = servicio.diagnosticar(entrada_log_ejemplo)
                
                assert diagnostico.tipo_error == TipoError.PHP_FATAL
                assert diagnostico.severidad == Severidad.ALTA
                assert "referencia nula" in diagnostico.resumen
                assert diagnostico.requiere_atencion_inmediata is True
    
    def test_diagnosticar_respuesta_con_markdown(self, entrada_log_ejemplo):
        """Verifica limpieza de respuesta con markdown."""
        respuesta_gemini = '''```json
{"tipo_error": "File Not Found", "severidad": "media", "resumen": "Archivo no encontrado", "causa_probable": "El archivo fue eliminado", "archivo_afectado": "/path/to/file", "linea": null, "recomendacion": "Restaurar archivo", "requiere_atencion_inmediata": false}
```'''
        
        with patch('services.gemini_service.obtener_configuracion') as mock_config:
            mock_config.return_value.gemini_api_key = "fake-key"
            mock_config.return_value.gemini_model = "gemini-2.0-flash"
            
            with patch('services.gemini_service.genai') as mock_genai:
                mock_modelo = MagicMock()
                mock_respuesta = MagicMock()
                mock_respuesta.text = respuesta_gemini
                mock_modelo.generate_content.return_value = mock_respuesta
                mock_genai.GenerativeModel.return_value = mock_modelo
                
                from services.gemini_service import ServicioGemini
                servicio = ServicioGemini()
                diagnostico = servicio.diagnosticar(entrada_log_ejemplo)
                
                assert diagnostico.tipo_error == TipoError.FILE_NOT_FOUND
                assert diagnostico.severidad == Severidad.MEDIA
    
    def test_diagnosticar_error_json_invalido(self, entrada_log_ejemplo):
        """Verifica manejo de respuesta JSON inválida."""
        respuesta_invalida = "esto no es JSON válido"
        
        with patch('services.gemini_service.obtener_configuracion') as mock_config:
            mock_config.return_value.gemini_api_key = "fake-key"
            mock_config.return_value.gemini_model = "gemini-2.0-flash"
            
            with patch('services.gemini_service.genai') as mock_genai:
                mock_modelo = MagicMock()
                mock_respuesta = MagicMock()
                mock_respuesta.text = respuesta_invalida
                mock_modelo.generate_content.return_value = mock_respuesta
                mock_genai.GenerativeModel.return_value = mock_modelo
                
                from services.gemini_service import ServicioGemini
                servicio = ServicioGemini()
                diagnostico = servicio.diagnosticar(entrada_log_ejemplo)
                
                # Debe retornar diagnóstico de error
                assert diagnostico.tipo_error == TipoError.OTRO
                assert "Error parseando" in diagnostico.causa_probable
    
    def test_diagnosticar_error_api(self, entrada_log_ejemplo):
        """Verifica manejo de error de API."""
        with patch('services.gemini_service.obtener_configuracion') as mock_config:
            mock_config.return_value.gemini_api_key = "fake-key"
            mock_config.return_value.gemini_model = "gemini-2.0-flash"
            
            with patch('services.gemini_service.genai') as mock_genai:
                mock_modelo = MagicMock()
                mock_modelo.generate_content.side_effect = Exception("API Error")
                mock_genai.GenerativeModel.return_value = mock_modelo
                
                from services.gemini_service import ServicioGemini
                servicio = ServicioGemini()
                diagnostico = servicio.diagnosticar(entrada_log_ejemplo)
                
                # Debe retornar diagnóstico de error
                assert diagnostico.tipo_error == TipoError.OTRO
                assert "Error en Gemini" in diagnostico.causa_probable
