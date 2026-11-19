import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from PyQt6.QtWidgets import QApplication
    from app import AuditAssistant
    HAS_QT=True
except ImportError:HAS_QT=False

@unittest.skipUnless(HAS_QT,'PyQt6 unavailable')
class ActivityFeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):self.window=AuditAssistant()
    def tearDown(self):self.window.close();self.app.processEvents()
    def test_real_task_labels_and_multiple_active_tasks(self):
        w=self.window
        w.activity({'id':'a','state':'active','label':'Reading sales data for ABC Inc.','role':'vision'})
        w.activity({'id':'b','state':'active','label':'Checking receipt PQR against rule R0001','role':'reasoning'})
        self.assertIn('ABC Inc.',w.current.text());self.assertIn('receipt PQR',w.current.text());self.assertEqual(w.feed.count(),2)
        w.activity({'id':'a','state':'complete','label':'Reading sales data for ABC Inc.','role':'vision'})
        self.assertNotIn('ABC Inc.',w.current.text());self.assertIn('receipt PQR',w.current.text());self.assertIn('Done',w.tasks['a']['item'].text())
    def test_demo_requires_one_target_and_two_references(self):
        w=self.window;w.load_demo();self.assertTrue(Path(w.target).exists());self.assertEqual(len(w.references),2);self.assertTrue(w.next_button.isEnabled())
    def test_task_events_do_not_create_fabricated_timer_tasks(self):
        w=self.window;w.activity({'id':'x','state':'active','label':'Reviewing Appendix A for P003','role':'reasoning'})
        for _ in range(5):w.tick()
        self.assertEqual(w.feed.count(),1);self.assertEqual(len(w.tasks),1)
    def test_background_task_delivers_context_and_result(self):
        from PyQt6.QtTest import QTest
        w=self.window;results=[]
        def work(emit):
            emit({'id':'worker-record','state':'active','label':'Checking invoice INV-104 for safety gloves','role':'reasoning'})
            emit({'id':'worker-record','state':'complete','label':'Checking invoice INV-104 for safety gloves','role':'reasoning'})
            return 'finished'
        w.start_task(work,results.append)
        for _ in range(100):
            QTest.qWait(10)
            if w.worker is None:break
        self.assertIsNone(w.worker);self.assertEqual(results,['finished'])
        self.assertIn('INV-104',w.feed.item(0).text());self.assertIn('Done',w.feed.item(0).text())
    def setup_book(self):
        from test_engine import Workflow
        w=self.window;w.job=Workflow().rule_job(w.temp.name);w.phase=1;w.target='target.pdf';w.references=['rules.pdf']
        # No PDF rendering is needed for control/evidence tests.
        w.preview.load=lambda sources:None;w.preview.locate=lambda sid,page:None
        w.refresh_results();w.update_controls();return w
    def test_rule_editor_controls_and_readable_evidence(self):
        w=self.setup_book();self.assertTrue(w.add_rule_button.isEnabled());self.assertFalse(w.edit_rule_button.isEnabled())
        w.rules.selectRow(0);w.rule_clicked(0,0);self.assertTrue(w.edit_rule_button.isEnabled())
        self.assertIn('Supporting excerpt',w.details.toPlainText());self.assertFalse(w.details.toPlainText().startswith('{'))
        self.assertIn('Source documents',w.coverage.toPlainText());self.assertNotIn('"scope_notes"',w.coverage.toPlainText())
        self.assertIs(w.feed.parentWidget(),w.tabs.parentWidget());self.assertIs(w.details.parentWidget(),w.preview.parentWidget())
        w.phase=2;w.update_controls();self.assertFalse(w.add_rule_button.isEnabled());self.assertFalse(w.remove_rule_button.isEnabled())
    def test_removing_last_rule_disables_screening(self):
        w=self.setup_book();w.rules.selectRow(0);w.remove_rule()
        self.assertEqual(w.rules.rowCount(),0);self.assertFalse(w.next_button.isEnabled());self.assertTrue(w.add_rule_button.isEnabled())
    def test_rule_dialog_accepts_a_user_rule(self):
        from app import RuleDialog
        d=RuleDialog([]);d.validate();self.assertIn('Enter a requirement',d.error.text());self.assertEqual(d.result(),0)
        d.fields['requirement'].setPlainText('Inspect invoice dates.');d.validate()
        self.assertEqual(d.result(),d.DialogCode.Accepted);self.assertIsNone(d.values()['source_id']);self.assertIsNone(d.values()['page']);d.close()

if __name__=='__main__':unittest.main()
