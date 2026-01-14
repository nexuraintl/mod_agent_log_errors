"""
Tests del parseador de logs.
Verifica el parseo correcto de logs de Nginx/PHP.
"""
import pytest
from datetime import datetime
from services.log_parser import ParseadorLogs


@pytest.fixture
def parseador():
    """Fixture que retorna una instancia del parseador."""
    return ParseadorLogs()


class TestParsearLinea:
    """Tests para el método parsear_linea."""
    
    def test_parsear_log_php_fatal(self, parseador):
        """Verifica el parseo de un error fatal de PHP."""
        linea = (
            '2026/01/02 08:50:24 [error] 1641#1641: *13100 FastCGI sent in stderr: '
            '"PHP message: PHP Fatal error: Uncaught Error: Call to a member function '
            'exists() on null in /home/portal/mod/Tools2/descargas.php:233'
        )
        
        resultado = parseador.parsear_linea(linea)
        
        assert resultado is not None
        assert resultado.timestamp == datetime(2026, 1, 2, 8, 50, 24)
        assert resultado.nivel == "error"
        assert "PHP Fatal error" in resultado.mensaje
        assert resultado.archivo == "/home/portal/mod/Tools2/descargas.php"
        assert resultado.linea == 233
    
    def test_parsear_log_file_not_found(self, parseador):
        """Verifica el parseo de un error de archivo no encontrado."""
        linea = (
            '2026/01/02 08:53:06 [error] 1641#1641: *15604 open() '
            '"/home/portal/public_html/info/yumbo_se/media/galeria.jpg" failed '
            '(2: No such file or directory), client: 35.191.74.121, '
            'server: www.yumbo.gov.co, request: "GET /info/yumbo_se/media/galeria.jpg HTTP/1.1"'
        )
        
        resultado = parseador.parsear_linea(linea)
        
        assert resultado is not None
        assert resultado.timestamp == datetime(2026, 1, 2, 8, 53, 6)
        assert resultado.nivel == "error"
        assert resultado.cliente_ip == "35.191.74.121"
        assert resultado.servidor == "www.yumbo.gov.co"
        assert "GET /info/yumbo_se/media/galeria.jpg" in resultado.request
    
    def test_parsear_linea_vacia(self, parseador):
        """Verifica que líneas vacías retornen None."""
        assert parseador.parsear_linea("") is None
        assert parseador.parsear_linea("   ") is None
    
    def test_parsear_linea_invalida(self, parseador):
        """Verifica que líneas sin formato Nginx retornen None."""
        assert parseador.parsear_linea("esto no es un log válido") is None
        assert parseador.parsear_linea("2026-01-02 error algo") is None


class TestParsearMultiples:
    """Tests para el método parsear_multiples."""
    
    def test_parsear_multiples_logs(self, parseador):
        """Verifica el parseo de múltiples logs."""
        contenido = """2026/01/02 08:50:24 [error] 1641#1641: *13100 Error uno
2026/01/02 08:51:24 [error] 1641#1641: *13101 Error dos
2026/01/02 08:52:24 [warning] 1641#1641: *13102 Warning uno"""
        
        resultados = parseador.parsear_multiples(contenido)
        
        assert len(resultados) == 3
        assert "Error uno" in resultados[0].mensaje
        assert "Error dos" in resultados[1].mensaje
        assert resultados[2].nivel == "warning"
    
    def test_parsear_contenido_vacio(self, parseador):
        """Verifica que contenido vacío retorne lista vacía."""
        assert parseador.parsear_multiples("") == []
        assert parseador.parsear_multiples("   \n   ") == []
    
    def test_parsear_log_multilinea(self, parseador):
        """Verifica el parseo de logs con stack traces multilínea."""
        contenido = """2026/01/02 08:50:24 [error] 1641#1641: *13100 PHP Fatal error: Something
    #0 /path/to/file.php(10): function()
    #1 /path/to/other.php(20): another()
2026/01/02 08:51:24 [error] 1641#1641: *13101 Otro error"""
        
        resultados = parseador.parsear_multiples(contenido)
        
        assert len(resultados) == 2
        # El stack trace debe unirse al primer log
        assert "#0 /path/to/file.php" in resultados[0].mensaje
