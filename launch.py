"""Use the current interpreter, or this Mac's configured runtime, without a venv."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
def main():
    config=ROOT/'.local-runtime.json'
    if config.exists():
        data=json.loads(config.read_text());env=os.environ.copy()
        env['PYTHONPATH']=str(data['dependencies'])+os.pathsep+env.get('PYTHONPATH','')
        return subprocess.call([data['python'],str(ROOT/'app.py')],cwd=ROOT,env=env)
    from app import main as run
    return run()
if __name__=='__main__':raise SystemExit(main())
