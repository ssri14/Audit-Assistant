from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import AuditJob,parse,title
from pdf_tools import calculate,windows,inspect_pdf

ROOT=Path(__file__).resolve().parents[1]
CONFIG={'AUDIT_REASONING_MODEL':'test-model','AUDIT_REASONING_BASE_URL':'http://localhost:8000/v1',
 'AUDIT_REASONING_API_KEY':'not-a-real-key','AUDIT_VISION_MODEL':'test-vision','AUDIT_VISION_BASE_URL':'http://localhost:8002/v1','AUDIT_VISION_API_KEY':''}

class Workflow(unittest.TestCase):
    def job(self,folder):
        p=ROOT/'pilot/inputs';return AuditJob(p/'Procurement_Dossier.pdf',[p/'Procurement_Procedure.pdf',p/'Payment_Checklist.pdf'],CONFIG,folder)
    def test_dynamic_task_title_comes_from_document(self):
        self.assertEqual(title('Sales data for ABC Inc.\nRevenue details'),'Sales data for ABC Inc.')
        self.assertIn('P004',title('```json\n{"record":"P004", "amount":"55000"}\n```'))
        self.assertNotIn('```',title('```json\n{"record":"P004"}\n```'))
    def test_fragment_windows_preserve_full_text_and_overlap(self):
        text='A'*17000;parts=list(windows(text));covered=set()
        for p in parts:
            self.assertEqual(text[p['start_offset']:p['end_offset']],p['text']);covered.update(range(p['start_offset'],p['end_offset']))
        self.assertEqual(len(covered),len(text));self.assertLess(parts[1]['start_offset'],parts[0]['end_offset'])
    def test_calculator_is_numeric_only(self):
        self.assertEqual(calculate('100 * 450'),'45000');self.assertEqual(calculate('(55000-45000)/2'),'5000')
        for expression in ['__import__("os")','2**1000000','True+1','a+1','[1,2]']:
            with self.assertRaises((ValueError,SyntaxError)):calculate(expression)
    def test_single_json_and_explicit_context_requests(self):
        self.assertEqual(parse('```json\n{"rules":[]}\n```'),{'rules':[]})
        raw='{"action":"request_context","requests":[{"tool":"calculate","expression":"2+2"}]}\n{"action":"finish","result":{}}'
        result=parse(raw);self.assertEqual(result['action'],'request_context');self.assertEqual(len(result['requests']),1);self.assertIn('_normalization',result)
    def test_conflicting_final_answers_are_never_silently_chosen(self):
        with self.assertRaises(ValueError):parse('{"action":"finish","result":{"a":1}}\n{"action":"finish","result":{"a":2}}')
    def test_mixed_demo_uses_both_document_routes(self):
        pages=inspect_pdf(ROOT/'pilot/inputs/Procurement_Dossier_Mixed.pdf');self.assertEqual([p['needs_vision'] for p in pages],[False,False,True,False])
    def test_checkpoint_redacts_api_keys(self):
        with tempfile.TemporaryDirectory() as td:
            job=self.job(td);job.checkpoint();content=(Path(td)/'job.json').read_text();self.assertNotIn('not-a-real-key',content);self.assertIn('[configured]',content)
    def test_call_budget_stops_before_inference(self):
        with tempfile.TemporaryDirectory() as td:
            job=self.job(td);job.calls=80;job.client.chat=Mock()
            with self.assertRaises(ValueError):job.call('x','test','label')
            job.client.chat.assert_not_called()
    def test_context_budget_stops_before_inference(self):
        with tempfile.TemporaryDirectory() as td:
            job=self.job(td);job.client.chat=Mock()
            with self.assertRaises(ValueError):job.call('x','x'*50000,'label')
            job.client.chat.assert_not_called()
    def test_partial_intake_cannot_be_mistaken_for_all_references(self):
        import shutil
        with tempfile.TemporaryDirectory() as td:
            job=self.job(td);job.client.models=Mock(return_value=[{'id':'test-model','max_model_len':32768}]);copy=shutil.copyfile
            def fail_last(src,dst):
                if Path(src).name=='Payment_Checklist.pdf':raise InterruptedError('simulate cancellation')
                return copy(src,dst)
            with patch('engine.shutil.copyfile',side_effect=fail_last):
                with self.assertRaises(InterruptedError):job.intake()
            self.assertFalse(job.intake_complete);self.assertEqual(len(job.sources),2)
            job.intake();self.assertTrue(job.intake_complete);self.assertEqual(len(job.sources),3)
    def test_page_tool_stays_within_uploaded_sources(self):
        with tempfile.TemporaryDirectory() as td:
            job=self.job(td);job.sources=[{'id':'TARGET','pages':[{'page':1,'text':'hello'}]}]
            with self.assertRaises(ValueError):job.page('OTHER',1)
            with self.assertRaises(ValueError):job.page('TARGET',2)
            self.assertFalse(job.verify_quote('TARGET',1,None));self.assertTrue(job.verify_quote('TARGET',1,'hello'))
    def rule_job(self,folder):
        job=self.job(folder);job.completed=[1]
        job.sources=[{'id':'TARGET','name':'target.pdf','path':'unused','pages':[{'page':1,'text':'Purchase P001.','route':'native','title':'Purchase P001'}]},
            {'id':'REF01','name':'rules.pdf','pages':[{'page':1,'text':'Obtain three quotations.','route':'native'}]}]
        job.book={'rules':[{'id':'R0001','clause':'C1','requirement':'Obtain quotations.','conditions':'Ordinary purchase','exceptions':'None',
            'source_id':'REF01','page':1,'quote':'Obtain three quotations.','quote_verified':True,'reading_route':'native'}],'scope_notes':[]}
        return job
    def test_rule_changes_keep_originals_ids_and_history(self):
        with tempfile.TemporaryDirectory() as td:
            job=self.rule_job(td);original=dict(job.book['rules'][0]);edited={**original,'requirement':'Obtain three quotations.'}
            job.change_rule('edit',edited,'R0001');self.assertEqual(job.book['rules'][0]['id'],'R0001')
            self.assertEqual(job.book['original_model_rules'],[original]);self.assertTrue(job.book['rules'][0]['user_modified'])
            manual={**edited,'source_id':None,'page':None,'quote':'','requirement':'Inspect the acceptance date.'}
            added=job.change_rule('add',manual);self.assertEqual(added['id'],'R0002');self.assertFalse(added['quote_verified'])
            job.change_rule('remove',rule_id='R0002');self.assertEqual(job.change_rule('add',manual)['id'],'R0003')
            saved=json.loads((Path(td)/'job.json').read_text());self.assertEqual(len(saved['book']['rule_changes']),4)
            self.assertEqual(saved['book']['rule_changes'][0]['before'],original)
    def test_rule_edit_validation_and_phase_lock(self):
        with tempfile.TemporaryDirectory() as td:
            job=self.rule_job(td);values=dict(job.book['rules'][0])
            for change in [{'requirement':' '},{'source_id':'TARGET'},{'page':9}]:
                with self.assertRaises(ValueError):job.change_rule('edit',{**values,**change},'R0001')
            self.assertNotIn('rule_changes',job.book)
            job.completed.append(2)
            with self.assertRaises(ValueError):job.change_rule('remove',rule_id='R0001')
    def test_screening_uses_revised_rules_and_clears_partial_results(self):
        with tempfile.TemporaryDirectory() as td:
            job=self.rule_job(td);job.candidates=[{'stale':True}];job.highlight_file='stale.pdf'
            job.change_rule('edit',{**job.book['rules'][0],'requirement':'Revised requirement for this audit.'},'R0001')
            self.assertEqual(job.candidates,[]);self.assertIsNone(job.highlight_file)
            job.call=Mock(return_value={'parsed':{'candidates':[],'rules_considered':['R0001']}});job.phase2()
            prompt=job.call.call_args.args[1];self.assertIn('Revised requirement for this audit.',prompt);self.assertNotIn('Obtain quotations.',prompt)
    def test_empty_rule_book_cannot_be_screened(self):
        with tempfile.TemporaryDirectory() as td:
            job=self.rule_job(td);job.change_rule('remove',rule_id='R0001');job.call=Mock()
            with self.assertRaises(ValueError):job.phase2()
            job.call.assert_not_called()
    def test_export_preserves_rule_changes_without_stale_highlights(self):
        import zipfile
        with tempfile.TemporaryDirectory() as td:
            job=self.rule_job(td);path=Path(td)/'review.zip';job.export(path)
            (Path(td)/'export/Highlighted_Target.pdf').write_text('stale')
            job.change_rule('edit',{**job.book['rules'][0],'requirement':'User revised requirement.'},'R0001');job.export(path)
            with zipfile.ZipFile(path) as archive:
                self.assertNotIn('Highlighted_Target.pdf',archive.namelist())
                book=json.loads(archive.read('compliance_book.json'));self.assertEqual(book['rules'][0]['requirement'],'User revised requirement.')
                self.assertEqual(book['original_model_rules'][0]['requirement'],'Obtain quotations.')
                self.assertEqual(book['rule_changes'][0]['action'],'edit')

if __name__=='__main__':unittest.main()
