"""Native PyInstaller configuration; no developer cache or interpreter paths."""
import os
from pathlib import Path
import runpy
import sys
import sysconfig
from PyInstaller.utils.hooks import copy_metadata

root=Path(SPECPATH)
version=runpy.run_path(str(root/'version.py'))['VERSION']
datas=[(str(root/'pilot'/'inputs'/name),'pilot/inputs') for name in ['Procurement_Dossier.pdf','Procurement_Dossier_Mixed.pdf','Procurement_Procedure.pdf','Payment_Checklist.pdf']]
datas += [(str(root/name),'.') for name in ['THIRD_PARTY_NOTICES.md','RELEASE_NOTES.md']]
for candidate in [Path(sysconfig.get_path('stdlib'))/'LICENSE.txt',Path(sys.base_prefix)/'LICENSE.txt']:
    if candidate.is_file():
        datas.append((str(candidate),'licenses/Python'));break
for package in ['PyQt6','PyQt6-Qt6','PyQt6-sip','pypdf','pypdfium2','Pillow']:
    datas.extend(copy_metadata(package))
a=Analysis([str(root/'launcher.py')],pathex=[str(root)],datas=datas,
           hiddenimports=['package_selftest'],excludes=['tkinter','PyQt5','PySide2','PySide6','pytest','IPython','matplotlib','numpy','pandas'],noarchive=False)
pyz=PYZ(a.pure)
signing=os.environ.get('AUDIT_ASSISTANT_CODESIGN_IDENTITY') or None
if sys.platform=='win32':
    exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='AuditAssistant',console=False,upx=False)
else:
    exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='AuditAssistant',console=False,upx=False,codesign_identity=signing)
    collection=COLLECT(exe,a.binaries,a.datas,name='AuditAssistant',upx=False)
    if sys.platform=='darwin':
        app=BUNDLE(collection,name='AuditAssistant.app',bundle_identifier='org.auditassistant.desktop',version=version,
                   codesign_identity=signing,info_plist={'CFBundleDisplayName':'Audit Assistant',
                   'CFBundleShortVersionString':version,'NSHighResolutionCapable':True,'LSMinimumSystemVersion':'14.0'})
