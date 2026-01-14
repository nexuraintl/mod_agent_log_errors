"""
Tests del servicio de almacenamiento.
Verifica guardado y recuperación de diagnósticos.
"""
import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

from services.storage_service import ServicioAlmacenamiento
from models.log_entry import (
    EntradaLog, 
    Diagnostico, 
    RegistroDiagnostico,
    TipoError,
    Severidad
)


@pytest.fixture
def archivo_temporal():
    """Crea un archivo temporal para los tests."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        archivo = f.name
    yield archivo
    # Limpiar después del test
    if os.path.exists(archivo):
        os.remove(archivo)


@pytest.fixture
def registro_ejemplo():
    """Crea un registro de diagnóstico de ejemplo."""
    entrada = EntradaLog(
        timestamp=datetime(2026, 1, 2, 8, 50, 24),
        nivel="error",
        mensaje="PHP Fatal error: Test",
        cliente_ip="192.168.1.1",
        servidor="test.com",
        request="GET /test HTTP/1.1",
        archivo="/path/to/file.php",
        linea=100,
        raw="log original completo"
    )
    
    diagnostico = Diagnostico(
        tipo_error=TipoError.PHP_FATAL,
        severidad=Severidad.ALTA,
        resumen="Error de prueba",
        causa_probable="Variable nula",
        archivo_afectado="/path/to/file.php",
        linea=100,
        recomendacion="Verificar inicialización",
        requiere_atencion_inmediata=True
    )
    
    return RegistroDiagnostico(
        id="test-123",
        fecha_procesamiento=datetime.now(),
        log=entrada,
        diagnostico=diagnostico
    )


class TestGuardarYRecuperar:
    """Tests para guardar y recuperar diagnósticos."""
    
    def test_guardar_y_obtener(self, archivo_temporal, registro_ejemplo):
        """Verifica que se pueda guardar y recuperar un registro."""
        # Mock de la configuración para usar archivo temporal
        with patch('services.storage_service.obtener_configuracion') as mock_config:
            mock_config.return_value.diagnoses_file = archivo_temporal
            
            almacenamiento = ServicioAlmacenamiento()
            almacenamiento.guardar(registro_ejemplo)
            
            registros = almacenamiento.obtener_todos()
            
            assert len(registros) == 1
            assert registros[0].id == "test-123"
            assert registros[0].diagnostico.severidad == Severidad.ALTA
    
    def test_guardar_multiples(self, archivo_temporal, registro_ejemplo):
        """Verifica guardado de múltiples registros."""
        with patch('services.storage_service.obtener_configuracion') as mock_config:
            mock_config.return_value.diagnoses_file = archivo_temporal
            
            almacenamiento = ServicioAlmacenamiento()
            
            # Crear segundo registro
            registro2 = registro_ejemplo.model_copy(update={"id": "test-456"})
            
            almacenamiento.guardar_multiples([registro_ejemplo, registro2])
            
            registros = almacenamiento.obtener_todos()
            assert len(registros) == 2
    
    def test_obtener_archivo_inexistente(self, archivo_temporal):
        """Verifica que archivo inexistente retorne lista vacía."""
        import tempfile
        ruta_inexistente = os.path.join(tempfile.gettempdir(), "test_inexistente", "archivo.json")
        
        with patch('services.storage_service.obtener_configuracion') as mock_config:
            mock_config.return_value.diagnoses_file = ruta_inexistente
            
            almacenamiento = ServicioAlmacenamiento()
            registros = almacenamiento.obtener_todos()
            
            assert registros == []
            
            # Limpiar directorio temporal creado
            directorio = os.path.dirname(ruta_inexistente)
            if os.path.exists(directorio):
                os.rmdir(directorio)


class TestFiltros:
    """Tests para métodos de filtrado."""
    
    def test_obtener_por_severidad(self, archivo_temporal, registro_ejemplo):
        """Verifica filtrado por severidad."""
        with patch('services.storage_service.obtener_configuracion') as mock_config:
            mock_config.return_value.diagnoses_file = archivo_temporal
            
            almacenamiento = ServicioAlmacenamiento()
            almacenamiento.guardar(registro_ejemplo)
            
            # Buscar por severidad alta
            altos = almacenamiento.obtener_por_severidad("alta")
            assert len(altos) == 1
            
            # Buscar severidad que no existe
            criticos = almacenamiento.obtener_por_severidad("crítica")
            assert len(criticos) == 0
    
    def test_contar(self, archivo_temporal, registro_ejemplo):
        """Verifica el conteo de registros."""
        with patch('services.storage_service.obtener_configuracion') as mock_config:
            mock_config.return_value.diagnoses_file = archivo_temporal
            
            almacenamiento = ServicioAlmacenamiento()
            
            assert almacenamiento.contar() == 0
            
            almacenamiento.guardar(registro_ejemplo)
            assert almacenamiento.contar() == 1
    
    def test_limpiar(self, archivo_temporal, registro_ejemplo):
        """Verifica limpieza de todos los registros."""
        with patch('services.storage_service.obtener_configuracion') as mock_config:
            mock_config.return_value.diagnoses_file = archivo_temporal
            
            almacenamiento = ServicioAlmacenamiento()
            almacenamiento.guardar(registro_ejemplo)
            
            almacenamiento.limpiar()
            
            assert almacenamiento.contar() == 0
