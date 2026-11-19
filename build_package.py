"""Build an AuditAssistant EXE on Windows or an Apple Silicon/Intel DMG on macOS."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from version import VERSION

ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir',type=Path,default=Path(tempfile.gettempdir())/'AuditAssistant-build')
    p.add_argument('--skip-build',action='store_true');args=p.parse_args()
    if sys.platform not in ['darwin','win32']:raise SystemExit('Build natively on macOS or Windows.')
    if os.environ.get('GITHUB_REF_TYPE')=='tag' and os.environ.get('GITHUB_REF_NAME')!='v'+VERSION:
        raise SystemExit('Release tag must match VERSION in version.py.')
    scratch=args.build_dir.resolve();scratch.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ);env.setdefault('PYINSTALLER_CONFIG_DIR',str(scratch/'cache'))
    native=scratch/'dist'
    if not args.skip_build:
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--workpath',str(scratch/'work'),
                        '--distpath',str(native),str(ROOT/'AuditAssistant.spec')],cwd=ROOT,env=env,check=True)
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    name=f'AuditAssistant-{VERSION}-macOS-{platform.machine()}.dmg' if sys.platform=='darwin' else f'AuditAssistant-{VERSION}-Windows-x64.exe'
    destination=out/name
    if destination.exists():raise SystemExit(f'Existing package preserved: {destination}. Move it before rebuilding.')
    if sys.platform=='darwin':
        with tempfile.TemporaryDirectory(prefix='audit-assistant-dmg-') as td:
            volume=Path(td)/'volume';volume.mkdir()
            shutil.copytree(native/'AuditAssistant.app',volume/'AuditAssistant.app',symlinks=True)
            (volume/'Applications').symlink_to('/Applications')
            image=Path(td)/name
            subprocess.run(['hdiutil','create','-volname','AuditAssistant','-srcfolder',str(volume),'-format','UDZO',str(image)],check=True)
            shutil.copy2(image,destination)
    else:shutil.copy2(native/'AuditAssistant.exe',destination)
    digest=hashlib.sha256()
    with destination.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    destination.with_name(name+'.sha256').write_text(digest.hexdigest()+'  '+name+'\n',encoding='utf-8')
    print('Package:',destination);print('Native build:',native)

if __name__=='__main__':main()
