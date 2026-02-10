
import unittest
from unittest.mock import MagicMock, patch
import sys
from app.core.dependency_verifier import DependencyVerifier, DependencyStatus

class TestDependencyVerifier(unittest.TestCase):
    def test_verify_installed_dependency(self):
        with patch('importlib.util.find_spec') as mock_find_spec, \
             patch('importlib.import_module') as mock_import:
            
            # Setup mock for find_spec
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec
            
            # Setup mock for module
            mock_module = MagicMock()
            mock_module.__version__ = "1.0.0"
            mock_module.__file__ = "/tmp/test.py"
            mock_import.return_value = mock_module
            
            # Mock os.access and stat
            with patch('os.access', return_value=True), \
                 patch('pathlib.Path.exists', return_value=True), \
                 patch('pathlib.Path.stat') as mock_stat:
                
                mock_stat.return_value.st_mode = 0o644
                
                verifier = DependencyVerifier(["test_pkg"])
                report = verifier.verify()
                
                self.assertTrue(report.success)
                self.assertEqual(report.missing_count, 0)
                status = report.dependencies["test_pkg"]
                self.assertTrue(status.installed)
                self.assertEqual(status.version, "1.0.0")

    def test_verify_missing_dependency(self):
        with patch('importlib.util.find_spec', return_value=None):
            verifier = DependencyVerifier(["missing_pkg"])
            report = verifier.verify()
            
            self.assertFalse(report.success)
            self.assertEqual(report.missing_count, 1)
            status = report.dependencies["missing_pkg"]
            self.assertFalse(status.installed)
            self.assertEqual(status.error, "Module not found in sys.path")

    def test_verify_import_error(self):
        with patch('importlib.util.find_spec') as mock_find_spec, \
             patch('importlib.import_module', side_effect=ImportError("Broken install")):
            
            mock_find_spec.return_value = MagicMock()
            
            verifier = DependencyVerifier(["broken_pkg"])
            report = verifier.verify()
            
            self.assertFalse(report.success)
            status = report.dependencies["broken_pkg"]
            self.assertFalse(status.installed)
            self.assertIn("ImportError", status.error)

if __name__ == '__main__':
    unittest.main()
