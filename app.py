"""Audit Assistant desktop pre-release with grounded live activity feedback."""
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import time
from PyQt6.QtCore import Qt,QThread,QTimer,pyqtSignal,QEvent,QRect,QSize
from PyQt6.QtGui import QImage,QPixmap,QColor
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QPushButton,QFileDialog,QMessageBox,QTabWidget,QTableWidget,QTableWidgetItem,
    QHeaderView,QSplitter,QListWidget,QListWidgetItem,QScrollArea,QComboBox,QDialog,
    QDialogButtonBox,QFormLayout,QLineEdit,QPlainTextEdit,QProgressBar,QSpinBox,QAbstractItemView)
from server_client import configuration,ServerClient
from engine import AuditJob
from pdf_tools import render
from version import VERSION

ROOT=Path(__file__).resolve().parent
STYLE='''QWidget {font-size:12px;color:#21354d;}
QMainWindow,QWidget#root {background:#f4f7fb;}
QLabel#brand {font-size:25px;font-weight:700;color:#123756;}
QLabel#subheading {font-size:14px;font-weight:600;color:#496582;}
QPushButton {padding:8px 11px;background:white;border:1px solid #cbd7e5;border-radius:6px;font-weight:600;}
QPushButton:hover {background:#eaf2fa;}
QPushButton:disabled {color:#8493a3;background:#e9eef4;}
QPushButton#primary {background:#1263a3;color:white;}
QPushButton#primary:disabled {background:#dce6f0;color:#8493a3;}
QComboBox,QLineEdit,QPlainTextEdit,QTableWidget,QListWidget,QScrollArea {background:white;border:1px solid #d0dce8;}
QComboBox,QLineEdit {padding:6px;}
QHeaderView::section {background:#e6eef7;padding:7px;border:none;font-weight:600;}
QTabBar::tab {padding:9px 13px;background:#e7eef6;}
QTabBar::tab:selected {background:white;color:#1263a3;}
QStatusBar {background:#e8eff6;}
'''

def button(label,fn,primary=False):
    b=QPushButton(label);b.clicked.connect(fn)
    if primary:b.setObjectName('primary')
    return b

class Task(QThread):
    activity_event=pyqtSignal(object);success=pyqtSignal(object);error=pyqtSignal(str)
    def __init__(self,fn,parent):super().__init__(parent);self.fn=fn
    def run(self):
        try:self.success.emit(self.fn(self.activity_event.emit))
        except Exception as exc:self.error.emit(str(exc))

class ServerSettings(QDialog):
    def __init__(self,config,parent):
        super().__init__(parent);self.setWindowTitle('In-house GPU servers');self.resize(760,380);self.fields={}
        layout=QVBoxLayout(self);hint=QLabel('Configure each role using an OpenAI-compatible base URL, ending in /v1. A /v1/models URL is also accepted.');hint.setWordWrap(True);layout.addWidget(hint)
        form=QFormLayout();layout.addLayout(form)
        for role,title in [('REASONING','Rule extraction / screening / review'),('VISION','Scanned-page reading')]:
            form.addRow(QLabel(title))
            for suffix,label in [('BASE_URL','Server URL'),('MODEL','Model ID'),('API_KEY','API key (optional)')]:
                key='AUDIT_'+role+'_'+suffix;field=QLineEdit(config.get(key,''))
                if suffix=='API_KEY':field.setEchoMode(QLineEdit.EchoMode.Password)
                self.fields[key]=field;form.addRow(label,field)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);controls.accepted.connect(self.accept);controls.rejected.connect(self.reject);layout.addWidget(controls)
    def values(self):return {k:f.text().strip() for k,f in self.fields.items()}

class RuleDialog(QDialog):
    def __init__(self,sources,rule=None,parent=None):
        super().__init__(parent);self.setWindowTitle('Edit rule' if rule else 'Add rule');self.resize(720,650)
        self.sources=sources;rule=rule or {};layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.fields={}
        for key,label in [('clause','Title / clause'),('requirement','Requirement'),('conditions','When it applies'),('exceptions','Exceptions / qualifications')]:
            field=QLineEdit() if key=='clause' else QPlainTextEdit()
            if key=='clause':field.setText(rule.get(key,''))
            else:field.setPlainText(rule.get(key,''));field.setMaximumHeight(78)
            self.fields[key]=field;form.addRow(label,field)
        self.source=QComboBox();self.source.addItem('User-added rule · no reference linked',None)
        for s in sources:self.source.addItem(s['name'],s['id'])
        form.addRow('Reference document',self.source);self.page=QSpinBox();self.page.setMinimum(1);form.addRow('PDF page',self.page)
        self.source.currentIndexChanged.connect(self.source_changed);self.source.setCurrentIndex(max(0,self.source.findData(rule.get('source_id'))));self.source_changed();self.page.setValue(rule.get('page') or 1)
        self.quote=QPlainTextEdit();self.quote.setPlainText(rule.get('quote',''));self.quote.setMaximumHeight(110);form.addRow('Supporting source excerpt',self.quote)
        hint=QLabel('The requirement is mandatory. A reference and exact excerpt help trace the rule to its source. Added and edited rules are recorded as user changes.');hint.setWordWrap(True);layout.addWidget(hint)
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);controls.accepted.connect(self.validate);controls.rejected.connect(self.reject);layout.addWidget(controls)
    def source_changed(self):
        s=next((s for s in self.sources if s['id']==self.source.currentData()),None);self.page.setEnabled(s is not None);self.page.setMaximum(len(s['pages']) if s else 1)
    def values(self):
        return {**{k:(f.text() if isinstance(f,QLineEdit) else f.toPlainText()) for k,f in self.fields.items()},
                'source_id':self.source.currentData(),'page':self.page.value() if self.source.currentData() else None,'quote':self.quote.toPlainText()}
    def validate(self):
        if not self.values()['requirement'].strip():self.error.setText('Enter a requirement before saving.');return
        self.accept()

def source_label(rule):
    return f'{rule["source_id"]} · PDF page {rule["page"]}' if rule.get('source_id') else 'User-added · no reference linked'

def readable(value):
    if value is None:return 'None specified'
    if isinstance(value,dict):return '\n'.join(k.replace('_',' ').capitalize()+': '+readable(v) for k,v in value.items())
    if isinstance(value,list):return '\n'.join(readable(v) for v in value) or 'None specified'
    return str(value)

def rule_details(rule):
    return '\n\n'.join([rule.get('clause') or rule['id'],'Requirement\n'+rule['requirement'],
        'When it applies\n'+(rule['conditions'] or 'Not specified'), 'Exceptions / qualifications\n'+(rule['exceptions'] or 'Not specified'),
        'Reference\n'+source_label(rule),'Supporting excerpt\n'+(rule['quote'] or 'No excerpt supplied'),
        'User-edited rule' if rule.get('user_modified') else 'Extracted by the model'])

class SourcePreview(QWidget):
    def __init__(self):
        super().__init__();self.sources=[];self.image=None;self.points=595
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);bar=QHBoxLayout()
        self.document=QComboBox();self.document.currentIndexChanged.connect(self.changed_document);bar.addWidget(self.document,1)
        self.page=QComboBox();self.page.currentIndexChanged.connect(self.show_page);bar.addWidget(self.page)
        self.zoom=QComboBox();self.zoom.addItems(['Fit width','100%','150%','200%']);self.zoom.currentTextChanged.connect(self.scale);bar.addWidget(self.zoom);layout.addLayout(bar)
        self.scroll=QScrollArea();self.label=QLabel('Source PDF preview');self.label.setAlignment(Qt.AlignmentFlag.AlignCenter);self.scroll.setWidget(self.label);self.scroll.setWidgetResizable(True);self.scroll.viewport().installEventFilter(self);layout.addWidget(self.scroll)
    def load(self,sources):
        self.sources=sources;self.document.blockSignals(True);self.document.clear();self.document.addItems([s['id']+' · '+s['name'] for s in sources]);self.document.blockSignals(False);self.changed_document()
    def changed_document(self):
        if not self.sources:return
        s=self.sources[max(0,self.document.currentIndex())];self.page.blockSignals(True);self.page.clear();self.page.addItems([f'Page {i+1}' for i in range(len(s['pages']))]);self.page.blockSignals(False);self.show_page()
    def show_page(self):
        if not self.sources:return
        s=self.sources[max(0,self.document.currentIndex())];n=max(0,self.page.currentIndex())+1
        try:
            image,_=render(s['path'],n);w,h=image.size;self.points=w/(300/72)
            self.image=QPixmap.fromImage(QImage(image.tobytes(),w,h,w*3,QImage.Format.Format_RGB888).copy());self.scale()
        except Exception as exc:self.label.setText(str(exc))
    def scale(self,*args):
        if self.image is None:return
        width=max(200,self.scroll.viewport().width()-8) if self.zoom.currentText()=='Fit width' else round(self.points*int(self.zoom.currentText()[:-1])/100)
        ratio=self.devicePixelRatioF();pix=self.image.scaledToWidth(round(width*ratio),Qt.TransformationMode.SmoothTransformation);pix.setDevicePixelRatio(ratio);self.label.setPixmap(pix);self.label.setMinimumSize(round(pix.width()/ratio),round(pix.height()/ratio))
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Resize:QTimer.singleShot(0,self.scale)
        return super().eventFilter(obj,event)
    def locate(self,sid,page):
        index=next((i for i,s in enumerate(self.sources) if s['id']==sid),None)
        if index is not None:self.document.setCurrentIndex(index);self.page.setCurrentIndex(page-1)

class AuditAssistant(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('Audit Assistant '+VERSION);self.resize(1460,960);self.setMinimumSize(1060,740)
        self.config=configuration();self.target=None;self.references=[];self.job=None;self.worker=None;self.connection_client=None;self.phase=0;self.closing=False
        self.temp=tempfile.TemporaryDirectory(prefix='audit-assistant-');self.tasks={};self.started={}
        self.build();self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(1000)
    def build(self):
        root=QWidget(objectName='root');self.setCentralWidget(root);layout=QVBoxLayout(root);layout.setContentsMargins(18,14,18,10)
        brand=QLabel('Audit Assistant');brand.setObjectName('brand');layout.addWidget(brand)
        sub=QLabel('Reference-led review with in-house GPU models · Leads for the auditor to examine');sub.setObjectName('subheading');sub.setWordWrap(True);layout.addWidget(sub)
        servers=QHBoxLayout();self.settings_button=button('GPU server settings…',self.settings);servers.addWidget(self.settings_button);self.connect_button=button('Test servers',self.connect_servers);servers.addWidget(self.connect_button);self.server_status=QLabel('Server configuration loaded from .env / saved settings');servers.addWidget(self.server_status,1);layout.addLayout(servers)
        files=QHBoxLayout();self.target_button=button('Choose document to audit…',self.choose_target);files.addWidget(self.target_button);self.target_label=QLabel('One PDF');files.addWidget(self.target_label,1);self.refs_button=button('Choose reference PDFs…',self.choose_references);files.addWidget(self.refs_button);self.refs_label=QLabel('1–5 reference/rule books');self.refs_label.setWordWrap(True);files.addWidget(self.refs_label,1);self.demo=button('Load demo packet',self.load_demo);files.addWidget(self.demo);layout.addLayout(files)
        limits=QLabel('PDF limits: target 30 pages · references 100 pages combined, 50 each · 15 MB/file, 60 MB total · 20 image-bearing pages.');limits.setWordWrap(True);layout.addWidget(limits)
        actions=QHBoxLayout();self.next_button=button('1 · Build Compliance Book',self.next_phase,True);actions.addWidget(self.next_button);self.cancel=button('Cancel',self.cancel_work);actions.addWidget(self.cancel);self.new=button('New run',self.new_run);actions.addWidget(self.new);self.export_button=button('Export review pack…',self.export);actions.addWidget(self.export_button);self.progress=QProgressBar();self.progress.setRange(0,0);actions.addWidget(self.progress);layout.addLayout(actions)
        self.current=QLabel('Choose a target PDF and reference books, or load the synthetic demo packet.');self.current.setTextFormat(Qt.TextFormat.PlainText);self.current.setWordWrap(True);self.current.setObjectName('subheading');layout.addWidget(self.current)
        split=QSplitter(Qt.Orientation.Horizontal);layout.addWidget(split,1);left=QWidget();v=QVBoxLayout(left);v.setContentsMargins(0,0,0,0)
        self.tabs=QTabWidget();v.addWidget(self.tabs,3)
        rule_page=QWidget();rule_layout=QVBoxLayout(rule_page);rule_layout.setContentsMargins(0,0,0,0)
        rule_bar=QHBoxLayout();self.add_rule_button=button('Add rule…',self.add_rule);self.edit_rule_button=button('Edit selected rule…',self.edit_rule);self.remove_rule_button=button('Remove selected rule',self.remove_rule)
        for b in [self.add_rule_button,self.edit_rule_button,self.remove_rule_button]:rule_bar.addWidget(b)
        rule_bar.addStretch();rule_layout.addLayout(rule_bar)
        self.rule_hint=QLabel('Build the Compliance Book to review and change its rules.');self.rule_hint.setWordWrap(True);rule_layout.addWidget(self.rule_hint)
        self.rules=QTableWidget(0,5);self.rules.setHorizontalHeaderLabels(['Rule','Requirement','Conditions / exceptions','Reference','Source / changes']);rule_layout.addWidget(self.rules);self.tabs.addTab(rule_page,'1 · Compliance Book')
        self.candidates=QTableWidget(0,4);self.candidates.setHorizontalHeaderLabels(['Lead','Target location','Possible concern','Rule IDs']);self.tabs.addTab(self.candidates,'2 · Candidate locations')
        self.reviews=QTableWidget(0,5);self.reviews.setHorizontalHeaderLabels(['Lead','Disposition','Model confidence','Audit note','Validation / evidence']);self.tabs.addTab(self.reviews,'3 · Reviewed leads')
        self.coverage=QPlainTextEdit();self.coverage.setReadOnly(True);self.tabs.addTab(self.coverage,'Coverage / scope')
        v.addWidget(QLabel('Live activity'))
        self.feed=QListWidget();self.feed.setWordWrap(True);self.feed.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);v.addWidget(self.feed,1)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setPlaceholderText('Select a rule or lead to read its evidence and source excerpt.')
        for table in [self.rules,self.candidates,self.reviews]:
            table.setWordWrap(True);table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive);table.horizontalHeader().setStretchLastSection(True)
        self.rules.cellClicked.connect(self.rule_clicked);self.candidates.cellClicked.connect(self.candidate_clicked);self.reviews.cellClicked.connect(self.review_clicked)
        self.rules.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.rules.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.rules.itemSelectionChanged.connect(self.update_controls);self.rules.cellDoubleClicked.connect(lambda *_:self.edit_rule())
        self.rules.setColumnWidth(0,70);self.rules.setColumnWidth(1,255);self.rules.setColumnWidth(2,240);self.rules.setColumnWidth(3,130)
        self.candidates.setColumnWidth(0,70);self.candidates.setColumnWidth(1,150);self.candidates.setColumnWidth(2,390)
        self.reviews.setColumnWidth(0,70);self.reviews.setColumnWidth(1,140);self.reviews.setColumnWidth(2,110);self.reviews.setColumnWidth(3,350)
        split.addWidget(left);right=QWidget();rv=QVBoxLayout(right);rv.setContentsMargins(0,0,0,0);self.preview=SourcePreview();rv.addWidget(self.preview,3);rv.addWidget(QLabel('Selected rule / lead · evidence details'));rv.addWidget(self.details,1);split.addWidget(right);split.setSizes([870,550])
        self.statusBar().showMessage('Documents are processed on the configured in-house servers.');self.update_controls()
    def update_controls(self):
        busy=self.worker is not None;editable=not busy and self.job is None
        for b in [self.settings_button,self.connect_button,self.target_button,self.refs_button,self.demo]:b.setEnabled(editable)
        has_rules=self.phase!=1 or bool(self.job and self.job.book and self.job.book['rules'])
        self.next_button.setEnabled(not busy and self.phase<3 and bool(self.target) and bool(self.references) and has_rules);self.next_button.setText(['1 · Build Compliance Book','2 · Screen target document','3 · Review candidate leads','Review complete'][self.phase])
        self.cancel.setEnabled(busy);self.new.setEnabled(not busy);self.export_button.setEnabled(not busy and self.job is not None);self.progress.setVisible(busy)
        editable_rules=not busy and self.phase==1;selected=self.rules.currentRow()>=0
        self.add_rule_button.setEnabled(editable_rules);self.edit_rule_button.setEnabled(editable_rules and selected);self.remove_rule_button.setEnabled(editable_rules and selected)
        self.rule_hint.setText('Review, add, edit or remove rules before screening. Double-click a rule to edit it.' if self.phase==1 else 'Rules are fixed for this screening run. Start a new run to build a different book.' if self.phase>1 else 'Build the Compliance Book to review and change its rules.')
    def settings(self):
        d=ServerSettings(self.config,self)
        if d.exec()==QDialog.DialogCode.Accepted:
            self.config=d.values();folder=Path.home()/'.audit-assistant';folder.mkdir(exist_ok=True)
            path=folder/'servers.json';path.write_text(json.dumps(self.config,indent=2)+'\n');path.chmod(0o600);self.server_status.setText('Server settings saved. Use Test servers to verify.')
    def connect_servers(self):
        client=ServerClient(self.config);self.connection_client=client
        def fn(emit):
            values={}
            for role in ['reasoning','vision']:
                emit({'id':'connection-'+role,'label':'Discovering '+role+' models on '+self.config['AUDIT_'+role.upper()+'_BASE_URL'],'role':role,'state':'active'})
                values[role]=client.models(role)
                emit({'id':'connection-'+role,'label':role.capitalize()+' model discovery complete','role':role,'state':'complete'})
            return values
        def done(values):
            self.server_status.setText(' · '.join(role+': '+', '.join(x['id'] for x in models) for role,models in values.items()));self.connection_client=None
            self.current.setText('Server model discovery complete. Choose the PDFs or load the demo packet.')
        self.start_task(fn,done)
    def choose_target(self):
        p,_=QFileDialog.getOpenFileName(self,'Document to audit','','PDF (*.pdf)')
        if p:self.target=p;self.target_label.setText(Path(p).name);self.update_controls()
    def choose_references(self):
        files,_=QFileDialog.getOpenFileNames(self,'Select 1–5 reference books','','PDF (*.pdf)')
        if not files:return
        if len(files)>5:QMessageBox.information(self,'Reference books','Choose at most five reference PDFs.');return
        self.references=files;self.refs_label.setText(', '.join(Path(p).name for p in files));self.update_controls()
    def load_demo(self):
        folder=ROOT/'pilot/inputs';self.target=str(folder/'Procurement_Dossier_Mixed.pdf');self.references=[str(folder/'Procurement_Procedure.pdf'),str(folder/'Payment_Checklist.pdf')]
        self.target_label.setText('Synthetic procurement dossier');self.refs_label.setText('Synthetic procurement procedure + payment checklist');self.current.setText('Synthetic demo loaded. Build the Compliance Book first.');self.update_controls()
    def can_change_rules(self):return self.worker is None and self.phase==1 and self.job is not None
    def apply_rule_change(self,action,values=None,rule_id=None):
        if not self.can_change_rules():return
        try:changed=self.job.change_rule(action,values,rule_id)
        except ValueError as exc:QMessageBox.information(self,'Rule change',str(exc));return
        self.refresh_results();self.details.clear();self.update_controls()
        if changed:
            index=next(i for i,r in enumerate(self.job.book['rules']) if r['id']==changed['id']);self.rules.selectRow(index);self.rule_clicked(index,0)
        self.current.setText(f'Compliance Book updated · {len(self.job.book["rules"])} rules. Review the rules, then screen the target document.')
    def add_rule(self):
        if not self.can_change_rules():return
        dialog=RuleDialog(self.job.sources[1:],parent=self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.apply_rule_change('add',dialog.values())
    def edit_rule(self):
        if not self.can_change_rules() or self.rules.currentRow()<0:return
        rule=self.job.book['rules'][self.rules.currentRow()];dialog=RuleDialog(self.job.sources[1:],rule,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.apply_rule_change('edit',dialog.values(),rule['id'])
    def remove_rule(self):
        if not self.can_change_rules() or self.rules.currentRow()<0:return
        rule=self.job.book['rules'][self.rules.currentRow()]
        self.apply_rule_change('remove',rule_id=rule['id'])
    def start_task(self,fn,done):
        worker=Task(fn,self);self.worker=worker;outcome={};worker.activity_event.connect(self.activity);worker.success.connect(lambda v:outcome.update(value=v));worker.error.connect(lambda e:outcome.update(error=e))
        def finished():
            self.worker=None;worker.deleteLater()
            if self.closing:self.temp.cleanup();self.close();return
            for task in self.tasks.values():
                if task['state']=='active':task['state']='stopped'
            self.tick();self.update_controls()
            if 'error' in outcome:
                self.current.setText(outcome['error']);self.statusBar().showMessage('Run paused; completed results remain in this session.')
                if not outcome['error'].startswith('Cancelled'):QMessageBox.information(self,'Audit Assistant',outcome['error'])
            elif 'value' in outcome:done(outcome['value'])
        worker.finished.connect(finished);self.update_controls();worker.start()
    def activity(self,event):
        sid=event['id']
        if sid not in self.tasks:
            item=QListWidgetItem();self.feed.insertItem(0,item);self.tasks[sid]={'item':item,'started':time.monotonic(),**event}
        else:self.tasks[sid].update(event)
        if event['state']!='active':self.tasks[sid]['elapsed']=time.monotonic()-self.tasks[sid]['started']
        if self.job:
            with (self.job.directory/'activity.jsonl').open('a',encoding='utf-8') as file:file.write(json.dumps(event,ensure_ascii=False)+'\n')
        self.tick()
    def tick(self):
        active=[]
        for task in self.tasks.values():
            seconds=task.get('elapsed',time.monotonic()-task['started']);status={'active':'Working','complete':'Done','stopped':'Stopped'}[task['state']]
            label=f'{status} · {task.get("role","local")} · {task["label"]} · {seconds:.0f}s';task['item'].setText(label);task['item'].setToolTip(label)
            bounds=self.feed.fontMetrics().boundingRect(QRect(0,0,max(120,self.feed.viewport().width()-22),1000),Qt.TextFlag.TextWordWrap,label)
            task['item'].setSizeHint(QSize(0,max(38,bounds.height()+14)))
            if task['state']=='active':active.append(task['label'])
        if active:self.current.setText(' | '.join(active[:2])+(' …' if len(active)>2 else ''))
    def next_phase(self):
        if self.worker is not None:return
        if self.job is None:
            directory=Path(self.temp.name)/datetime.now().strftime('%Y%m%d_%H%M%S_%f');self.job=AuditJob(self.target,self.references,self.config,directory)
        self.job.client.cancelled.clear();stage=self.phase+1;self.current.setText(f'Starting phase {stage}…')
        def fn(emit):self.job.event=emit;return [self.job.phase1,self.job.phase2,self.job.phase3][stage-1]()
        def done(value):
            self.phase=stage;self.refresh_results();self.tabs.setCurrentIndex(stage-1)
            self.current.setText({1:'Compliance Book ready. Review its sources and scope, then screen the target.',2:'Candidate locations ready. Review them, then start the skeptical review.',3:'Review complete. These are leads for human examination, with unresolved evidence kept visible.'}[stage]);self.update_controls()
        self.start_task(fn,done)
    def refresh_results(self):
        sources=[dict(s) for s in self.job.sources]
        if self.job.highlight_file:sources[0]['path']=self.job.highlight_file;sources[0]['name']+=' · candidate highlights'
        self.preview.load(sources)
        def fill(table,rows):
            table.setRowCount(len(rows))
            for i,values in enumerate(rows):
                for j,value in enumerate(values):item=QTableWidgetItem(str(value));item.setToolTip(str(value));table.setItem(i,j,item)
            table.resizeRowsToContents()
            for i in range(table.rowCount()):table.setRowHeight(i,min(90,table.rowHeight(i)))
        fill(self.rules,[[r['id'],r['requirement'],r['conditions']+'\n'+r['exceptions'],source_label(r),
            ('User-edited · ' if r.get('user_modified') else '')+('Excerpt matched reading' if r['quote_verified'] else 'No reference linked' if not r.get('source_id') else 'Check supporting excerpt')] for r in (self.job.book or {}).get('rules',[])])
        fill(self.candidates,[[c['id'],f'PDF page {c["page"]} · {c["chunk_id"]}',c['possible_concern'],', '.join(c['rule_ids'])] for c in self.job.candidates])
        fill(self.reviews,[[r['candidate_id'],r['disposition'].replace('_',' '),r['confidence'],r.get('audit_note',''),'; '.join(r['validation_flags']) or 'Inspect cited source evidence'] for r in self.job.reviews])
        for i,r in enumerate(self.job.reviews):
            colour='#fff0cc' if r['validation_flags'] or r['disposition']=='insufficient_evidence' else '#fbe1e2' if r['disposition']=='retained' else '#e0f2e5'
            for j in range(self.reviews.columnCount()):self.reviews.item(i,j).setBackground(QColor(colour))
        lines=['Completed phases: '+(', '.join(map(str,self.job.completed)) or 'None'),f'Model requests: {self.job.calls}',
          f'Rules in current book: {len((self.job.book or {}).get("rules",[]))}',f'User rule changes: {len((self.job.book or {}).get("rule_changes",[]))}', '', 'Source documents']
        for s in self.job.sources:lines.append(f'{s["id"]} · {s["name"]} · {len(s["pages"])} PDF pages')
        lines.extend(['','Reference scope notes'])
        for note in (self.job.book or {}).get('scope_notes',[]):
            if note:lines.append(readable(note))
        lines.extend(['','Screening coverage'])
        for c in self.job.coverage:lines.extend([f'PDF page {c["page"]} · {c["chunk_id"]}', 'Rules supplied: '+(', '.join(c['rules_supplied']) or 'None'), 'Rules reported considered: '+(', '.join(c.get('rules_reported_considered',[])) or 'None'),readable(c.get('note','')),''])
        if not self.job.coverage:lines.append('Target screening has not completed.')
        lines.extend(['','Source highlights'])
        for h in self.job.highlight_mapping:lines.append(f'{h["id"]} · PDF page {h["page"]} · '+('Passage highlighted' if h['status']=='highlighted' else 'Use the page and excerpt to inspect this lead'))
        lines.extend(['','No candidate is not proof of compliance. Confidence is model-reported and qualitative. Quotes on scans are matched to model readings; check the original page visually.'])
        self.coverage.setPlainText('\n'.join(lines))
    def rule_clicked(self,index,column):
        r=self.job.book['rules'][index];self.details.setPlainText(rule_details(r))
        if r.get('source_id'):self.preview.locate(r['source_id'],r['page'])
    def candidate_clicked(self,index,column):
        c=self.job.candidates[index];self.details.setPlainText('\n\n'.join([f'{c["id"]} · PDF page {c["page"]}', 'Possible concern\n'+c['possible_concern'],'Target excerpt\n'+c['quote'],
            'Rules\n'+', '.join(c['rule_ids']),'Context to check\n'+readable(c.get('missing_context')),
            'Source check\n'+('Excerpt matched the page reading.' if c['quote_verified'] else 'Excerpt needs source validation.')+(' This is a scanned page; check the original visually.' if c['reading_route']=='vision' else '')]));self.preview.locate('TARGET',c['page'])
    def review_clicked(self,index,column):
        r=self.job.reviews[index];c=next(c for c in self.job.candidates if c['id']==r['candidate_id'])
        lines=[f'{r["candidate_id"]} · {r["disposition"].replace("_"," ")}',f'Model confidence: {r["confidence"]}', '', 'Audit note',r.get('audit_note',''),'','Basis and limits',r.get('rationale',''),'','Target excerpt',c['quote'],'','Supporting evidence']
        for q in r.get('supporting_quotes',[]):lines.extend([f'{q.get("source_id", "Unknown source")} · PDF page {q.get("page", "unknown")}',q.get('quote','')])
        lines.extend(['','Evidence still needed'])
        lines.append(readable(r.get('missing_evidence',[])));lines.extend(['','Source / validation checks']);lines.extend(r['validation_flags'] or ['Inspect the cited source evidence.'])
        self.details.setPlainText('\n'.join(lines));self.preview.locate('TARGET',c['page'])
    def cancel_work(self):
        if self.job:self.job.client.cancel()
        if self.connection_client:self.connection_client.cancel()
        self.current.setText('Cancelling the active request…')
    def new_run(self):
        self.job=None;self.phase=0;self.tasks={};self.feed.clear();self.details.clear();self.coverage.clear()
        for t in [self.rules,self.candidates,self.reviews]:t.setRowCount(0)
        self.preview.sources=[];self.preview.document.clear();self.preview.page.clear();self.preview.image=None;self.preview.label.clear();self.preview.label.setText('Source PDF preview');self.preview.label.setMinimumSize(0,0)
        self.current.setText('Ready for a new run. Choose or replace the input PDFs.');self.update_controls()
    def export(self):
        p,_=QFileDialog.getSaveFileName(self,'Export completed phases','Audit_Assistant_Review.zip','ZIP archive (*.zip)')
        if not p:return
        self.current.setText('Preparing review pack and source highlights…')
        def fn(emit):self.job.event=emit;return self.job.export(p)
        self.start_task(fn,lambda path:self.current.setText('Review pack saved: '+path))
    def closeEvent(self,event):
        if self.worker is not None:self.closing=True;self.cancel_work();event.ignore();return
        self.temp.cleanup();event.accept()

def main():
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setStyleSheet(STYLE);window=AuditAssistant();window.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
