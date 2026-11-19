"""Run the real packaged executable without a Python dependency or Ollama server."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from version import VERSION

ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--build-dir',type=Path,default=Path(tempfile.gettempdir())/'AuditAssistant-build');p.add_argument('--executable',type=Path);args=p.parse_args()
    executable=args.executable or (args.build_dir/'dist'/'AuditAssistant.app'/'Contents'/'MacOS'/'AuditAssistant' if sys.platform=='darwin' else args.build_dir/'dist'/'AuditAssistant.exe')
    if not executable.is_file():raise SystemExit('Build the native app first.')
    env=dict(os.environ);env['QT_QPA_PLATFORM']='offscreen'
    # The frozen application must not rely on the developer's Python paths.
    for k in ['PYTHONPATH','PYTHONHOME','VIRTUAL_ENV']:env.pop(k,None)
    with tempfile.TemporaryDirectory(prefix='audit-assistant-verify-') as td:
        result=Path(td)/'result.json'
        process=subprocess.run([str(executable.resolve()),'--self-test','--output',str(result)],env=env,cwd=td,capture_output=True,text=True,timeout=120)
        if not result.exists():raise SystemExit(f'Packaged self-test did not report a result: {process.stderr}')
        data=json.loads(result.read_text())
        if process.returncode or data.get('status')!='passed' or data.get('version')!=VERSION:raise SystemExit(json.dumps(data))
        print(json.dumps(data,indent=2))
    for checksum in (ROOT/'dist').glob('*.sha256'):
        digest,name=checksum.read_text().strip().split('  ',1);file=checksum.parent/name
        with file.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=digest:raise SystemExit('Package checksum does not match: '+name)
    print('Packaged GUI, demo PDFs, rule editing and source highlighting passed.')

if __name__=='__main__':main()
