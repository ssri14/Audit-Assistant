import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server_client import dotenv_path

class RuntimePaths(unittest.TestCase):
    def test_windows_frozen_env_is_next_to_executable(self):
        with patch('sys.frozen',True,create=True),patch('sys.platform','win32'),patch('sys.executable','/portable/AuditAssistant.exe'):
            self.assertEqual(dotenv_path(),Path('/portable/.env').resolve())
    def test_mac_frozen_env_is_outside_bundle(self):
        with patch('sys.frozen',True,create=True),patch('sys.platform','darwin'),patch('sys.executable','/Applications/AuditAssistant.app/Contents/MacOS/AuditAssistant'):
            self.assertEqual(dotenv_path(),Path('/Applications/.env').resolve())
    def test_package_smoke_test_from_source(self):
        from package_selftest import main
        with tempfile.TemporaryDirectory() as td:
            report=Path(td)/'report.json';code=main(['--output',str(report)])
            result=json.loads(report.read_text());self.assertEqual(code,0,result);self.assertEqual(result['server_calls'],0)

if __name__=='__main__':unittest.main()
