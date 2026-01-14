"""
Tests del servicio SSH.
Utiliza mocks para no requerir conexión real.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestServicioSSH:
    """Tests para el servicio SSH usando mocks."""
    
    def test_conectar_con_password(self):
        """Verifica conexión SSH con contraseña."""
        with patch('services.ssh_service.obtener_configuracion') as mock_config:
            mock_config.return_value.ssh_host = "test.host"
            mock_config.return_value.ssh_port = 22
            mock_config.return_value.ssh_user = "testuser"
            mock_config.return_value.ssh_password = "testpass"
            mock_config.return_value.ssh_key_path = None
            mock_config.return_value.log_path = "/var/log/test.log"
            
            with patch('services.ssh_service.paramiko.SSHClient') as mock_client:
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance
                
                from services.ssh_service import ServicioSSH
                servicio = ServicioSSH()
                servicio.conectar()
                
                # Verificar que se llamó connect con los parámetros correctos
                mock_instance.connect.assert_called_once()
                args = mock_instance.connect.call_args
                assert args.kwargs['hostname'] == "test.host"
                assert args.kwargs['username'] == "testuser"
                assert args.kwargs['password'] == "testpass"
    
    def test_conectar_con_llave(self):
        """Verifica conexión SSH con llave."""
        with patch('services.ssh_service.obtener_configuracion') as mock_config:
            mock_config.return_value.ssh_host = "test.host"
            mock_config.return_value.ssh_port = 22
            mock_config.return_value.ssh_user = "testuser"
            mock_config.return_value.ssh_password = None
            mock_config.return_value.ssh_key_path = "/path/to/key.pem"
            mock_config.return_value.log_path = "/var/log/test.log"
            
            with patch('services.ssh_service.paramiko.SSHClient') as mock_client:
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance
                
                from services.ssh_service import ServicioSSH
                servicio = ServicioSSH()
                servicio.conectar()
                
                args = mock_instance.connect.call_args
                assert args.kwargs['key_filename'] == "/path/to/key.pem"
                assert 'password' not in args.kwargs
    
    def test_ejecutar_comando(self):
        """Verifica ejecución de comando remoto."""
        with patch('services.ssh_service.obtener_configuracion') as mock_config:
            mock_config.return_value.ssh_host = "test.host"
            mock_config.return_value.ssh_port = 22
            mock_config.return_value.ssh_user = "testuser"
            mock_config.return_value.ssh_password = "testpass"
            mock_config.return_value.ssh_key_path = None
            mock_config.return_value.log_path = "/var/log/test.log"
            
            with patch('services.ssh_service.paramiko.SSHClient') as mock_client:
                # Configurar mock de exec_command
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance
                
                mock_stdout = MagicMock()
                mock_stdout.read.return_value = b"hostname-test"
                mock_stderr = MagicMock()
                mock_stderr.read.return_value = b""
                
                mock_instance.exec_command.return_value = (None, mock_stdout, mock_stderr)
                
                from services.ssh_service import ServicioSSH
                servicio = ServicioSSH()
                servicio.conectar()
                resultado = servicio.ejecutar_comando("hostname")
                
                assert resultado == "hostname-test"
    
    def test_ejecutar_comando_sin_conexion(self):
        """Verifica que falle si no hay conexión."""
        with patch('services.ssh_service.obtener_configuracion') as mock_config:
            mock_config.return_value.ssh_host = "test.host"
            mock_config.return_value.ssh_port = 22
            mock_config.return_value.ssh_user = "testuser"
            mock_config.return_value.ssh_password = "testpass"
            mock_config.return_value.ssh_key_path = None
            mock_config.return_value.log_path = "/var/log/test.log"
            
            from services.ssh_service import ServicioSSH
            servicio = ServicioSSH()
            
            with pytest.raises(RuntimeError, match="No hay conexión SSH activa"):
                servicio.ejecutar_comando("hostname")
    
    def test_context_manager(self):
        """Verifica uso como context manager."""
        with patch('services.ssh_service.obtener_configuracion') as mock_config:
            mock_config.return_value.ssh_host = "test.host"
            mock_config.return_value.ssh_port = 22
            mock_config.return_value.ssh_user = "testuser"
            mock_config.return_value.ssh_password = "testpass"
            mock_config.return_value.ssh_key_path = None
            mock_config.return_value.log_path = "/var/log/test.log"
            
            with patch('services.ssh_service.paramiko.SSHClient') as mock_client:
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance
                
                from services.ssh_service import ServicioSSH
                
                with ServicioSSH() as servicio:
                    pass
                
                # Verificar que se llamó connect y close
                mock_instance.connect.assert_called_once()
                mock_instance.close.assert_called_once()
