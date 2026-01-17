"""
Tests de los endpoints de la API.
Utiliza TestClient de FastAPI para testing.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

from app import app
from models.log_entry import (
    EntradaLog,
    Diagnostico,
    RegistroDiagnostico,
    TipoError,
    Severidad
)


@pytest.fixture
def cliente():
    """Cliente de prueba para la API."""
    return TestClient(app)


@pytest.fixture
def registro_mock():
    """Registro de diagnóstico mock."""
    return RegistroDiagnostico(
        id="mock-123",
        fecha_procesamiento=datetime.now(),
        log=EntradaLog(
            timestamp=datetime.now(),
            nivel="error",
            mensaje="Test error",
            raw="log original"
        ),
        diagnostico=Diagnostico(
            tipo_error=TipoError.PHP_FATAL,
            severidad=Severidad.ALTA,
            resumen="Error de prueba",
            causa_probable="Test",
            recomendacion="Test rec",
            requiere_atencion_inmediata=True
        )
    )


class TestEndpointsSistema:
    """Tests para endpoints del sistema."""
    
    def test_health_check(self, cliente):
        """Verifica endpoint de salud."""
        response = cliente.get("/health")
        
        assert response.status_code == 200
        datos = response.json()
        assert datos["estado"] == "saludable"
        assert datos["servicio"] == "Monitor de Logs SSH"


class TestEndpointsVigilante:
    """Tests para endpoints del vigilante."""
    
    def test_obtener_estado(self, cliente):
        """Verifica endpoint de estado del vigilante."""
        with patch('app.vigilante') as mock_vigilante:
            mock_vigilante.obtener_estado.return_value = {
                "activo": False,
                "ultima_linea_leida": 0,
                "ultimo_check": None,
                "logs_procesados_total": 0,
                "intervalo_segundos": 60
            }
            
            response = cliente.get("/status")
            
            assert response.status_code == 200
            datos = response.json()
            assert "activo" in datos
            assert "intervalo_segundos" in datos
    
    def test_iniciar_monitoreo(self, cliente):
        """Verifica endpoint para iniciar monitoreo."""
        with patch('app.vigilante') as mock_vigilante:
            with patch('app.obtener_configuracion') as mock_config:
                mock_config.return_value.check_interval_seconds = 60
                
                response = cliente.post("/start")
                
                assert response.status_code == 200
                datos = response.json()
                assert "Monitoreo iniciado" in datos["mensaje"]
    
    def test_detener_monitoreo(self, cliente):
        """Verifica endpoint para detener monitoreo."""
        with patch('app.vigilante') as mock_vigilante:
            response = cliente.post("/stop")
            
            assert response.status_code == 200
            datos = response.json()
            assert "Monitoreo detenido" in datos["mensaje"]


class TestEndpointsDiagnostico:
    """Tests para endpoints de diagnósticos."""
    
    def test_listar_diagnosticos_vacio(self, cliente):
        """Verifica listado vacío de diagnósticos."""
        with patch('app.ServicioAlmacenamiento') as mock_storage:
            mock_storage.return_value.obtener_recientes.return_value = []
            
            response = cliente.get("/diagnoses")
            
            assert response.status_code == 200
            assert response.json() == []
    
    def test_listar_diagnosticos_con_datos(self, cliente, registro_mock):
        """Verifica listado con diagnósticos."""
        with patch('app.ServicioAlmacenamiento') as mock_storage:
            mock_storage.return_value.obtener_recientes.return_value = [registro_mock]
            
            response = cliente.get("/diagnoses")
            
            assert response.status_code == 200
            datos = response.json()
            assert len(datos) == 1
            assert datos[0]["id"] == "mock-123"
    
    def test_contar_diagnosticos(self, cliente):
        """Verifica conteo de diagnósticos."""
        with patch('app.ServicioAlmacenamiento') as mock_storage:
            mock_storage.return_value.contar.return_value = 5
            
            response = cliente.get("/diagnoses/count")
            
            assert response.status_code == 200
            assert response.json()["total"] == 5
    
    def test_limpiar_diagnosticos(self, cliente):
        """Verifica limpieza de diagnósticos."""
        with patch('app.ServicioAlmacenamiento') as mock_storage:
            response = cliente.delete("/diagnoses")
            
            assert response.status_code == 200
            mock_storage.return_value.limpiar.assert_called_once()


class TestEndpointConexion:
    """Tests para endpoint de prueba de conexión."""
    
    def test_probar_conexion_exitosa(self, cliente):
        """Verifica prueba de conexión exitosa."""
        with patch('app.ServicioSSH') as mock_ssh:
            mock_ssh.return_value.probar_conexion.return_value = {
                "exitoso": True,
                "hostname": "test-server",
                "uptime": "10 days",
                "mensaje": "Conexión exitosa"
            }
            
            response = cliente.get("/test-connection")
            
            assert response.status_code == 200
            datos = response.json()
            assert datos["exitoso"] is True
            assert datos["hostname"] == "test-server"
    
    def test_probar_conexion_fallida(self, cliente):
        """Verifica prueba de conexión fallida."""
        with patch('app.ServicioSSH') as mock_ssh:
            mock_ssh.return_value.probar_conexion.return_value = {
                "exitoso": False,
                "hostname": None,
                "uptime": None,
                "mensaje": "Error de conexión: timeout"
            }
            
            response = cliente.get("/test-connection")
            
            assert response.status_code == 200
            datos = response.json()
            assert datos["exitoso"] is False
