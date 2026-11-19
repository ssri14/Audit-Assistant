"""Exercise the frozen GUI and bundled PDF tools without any server requests."""
import argparse
import json
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args(argv)
    try:
        from PyQt6.QtWidgets import QApplication
        import app as desktop
        from engine import AuditJob
        from pdf_tools import inspect_pdf,render,annotate,calculate
        from version import VERSION
        expected={'Procurement_Dossier.pdf','Procurement_Dossier_Mixed.pdf','Procurement_Procedure.pdf','Payment_Checklist.pdf'}
        folder=desktop.ROOT/'pilot/inputs'
        assert {p.name for p in folder.glob('*.pdf')}==expected,'Demo PDF bundle is incomplete'
        if getattr(sys,'frozen',False):
            assert {p.name for p in folder.iterdir()}==expected,'Unexpected files in packaged demo'
            assert not (desktop.ROOT/'.env').exists(),'Developer .env must not be bundled'
            assert not (desktop.ROOT/'.git-token').exists(),'Local token must not be bundled'
        app=QApplication.instance() or QApplication([]);app.setStyle('Fusion');app.setStyleSheet(desktop.STYLE)
        defaults={'AUDIT_REASONING_BASE_URL':'','AUDIT_REASONING_MODEL':'openai/gpt-oss-120b','AUDIT_REASONING_API_KEY':'',
                  'AUDIT_VISION_BASE_URL':'','AUDIT_VISION_MODEL':'nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16','AUDIT_VISION_API_KEY':''}
        with patch('http.client.HTTPConnection.connect',side_effect=AssertionError('Network is forbidden during package verification')),patch('http.client.HTTPSConnection.connect',side_effect=AssertionError('Network is forbidden during package verification')),patch('app.configuration',return_value=defaults):
            w=desktop.AuditAssistant();w.show();w.load_demo();app.processEvents()
            pages=inspect_pdf(w.target);assert [p['needs_vision'] for p in pages]==[False,False,True,False]
            image,count=render(w.target,3);assert count==4 and image.width>2000
            with tempfile.TemporaryDirectory(prefix='audit-assistant-selftest-') as td:
                j=AuditJob(w.target,w.references,defaults,td);j.completed=[1]
                j.sources=[{'id':'TARGET','name':'Demo target','path':str(folder/'Procurement_Dossier.pdf'),'sha256':'self-test',
                            'pages':[{'page':p['page'],'text':p['native_text'],'route':'native','title':'Demo page'} for p in inspect_pdf(folder/'Procurement_Dossier.pdf')]},
                           {'id':'REF01','name':'Demo reference','path':w.references[0],'sha256':'self-test',
                            'pages':[{'page':1,'text':'Obtain three quotations.','route':'native','title':'Demo rule'}]}]
                j.book={'rules':[],'scope_notes':[]}
                rule=j.change_rule('add',{'clause':'Package test','requirement':'Check supplied evidence.','conditions':'Test only',
                         'exceptions':'None','source_id':'REF01','page':1,'quote':'Obtain three quotations.'})
                assert rule['quote_verified']
                w.job=j;w.phase=1;w.refresh_results();w.update_controls();w.rules.selectRow(0);w.rule_clicked(0,0)
                assert w.edit_rule_button.isEnabled() and not w.details.toPlainText().startswith('{')
                dialog=desktop.RuleDialog(j.sources[1:],rule,w);dialog.fields['requirement'].setPlainText('Revised test requirement.')
                w.apply_rule_change('edit',dialog.values(),rule['id']);dialog.close();assert j.book['rules'][0]['requirement']=='Revised test requirement.'
                assert j.book['rule_changes'][-1]['action']=='edit'
                label='Checking invoice INV-104 for safety gloves'
                w.activity({'id':'smoke','state':'active','label':label,'role':'reasoning'});assert label in w.current.text()
                w.activity({'id':'smoke','state':'complete','label':label,'role':'reasoning'});assert 'Done' in w.feed.item(0).text()
                quote='Exactly one written quotation was obtained before the order; no other quotations were obtained.'
                mapping=annotate(j.sources[0]['path'],[{'id':'C0001','page':1,'quote':quote,'quote_verified':True,'reading_route':'native','possible_concern':'Packaging smoke test passage'}],[],Path(td)/'highlight.pdf')
                assert mapping[0]['status']=='highlighted'
                j.export(Path(td)/'review.zip');assert (Path(td)/'review.zip').is_file()
                assert calculate('100 * 450')=='45000'
            w.close();app.processEvents()
        args.output.write_text(json.dumps({'status':'passed','version':VERSION,'demo_pdfs':4,'gui':True,'pdf_rendering':True,
            'native_and_scanned_routes':True,'rule_editor':True,'activity_feed':True,'source_highlighting':True,'export':True,'server_calls':0},indent=2)+'\n',encoding='utf-8');return 0
    except Exception:
        import traceback
        args.output.write_text(json.dumps({'status':'failed','error':traceback.format_exc()},indent=2)+'\n',encoding='utf-8');return 1
