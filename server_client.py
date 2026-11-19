"""Small configured-host-only OpenAI-compatible client for the feasibility pilot."""
import http.client
import json
from pathlib import Path
import time
import socket
import threading
import os
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
def dotenv_path():
    if not getattr(sys,'frozen',False):return ROOT/'.env'
    executable=Path(sys.executable).resolve()
    folder=executable.parents[3] if sys.platform=='darwin' and executable.parent.name=='MacOS' else executable.parent
    return folder/'.env'

def configuration():
    values={'AUDIT_REASONING_BASE_URL':'','AUDIT_VISION_BASE_URL':'',
      'AUDIT_REASONING_MODEL':'openai/gpt-oss-120b','AUDIT_VISION_MODEL':'nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16',
      'AUDIT_REASONING_API_KEY':'','AUDIT_VISION_API_KEY':''}
    dotenv=dotenv_path()
    if dotenv.exists():
        for line in dotenv.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key,value=line.split('=',1)
                if key.strip() in values:values[key.strip()]=value.strip().strip('"').strip("'")
    settings=Path.home()/'.audit-assistant'/'servers.json'
    if settings.exists():values.update(json.loads(settings.read_text()))
    for key in values:
        if key in os.environ:values[key]=os.environ[key]
    return values

def request(role,path,payload=None,timeout=120,config=None,client=None):
    conf=config or configuration();prefix='AUDIT_'+role.upper()+'_';base=conf[prefix+'BASE_URL'].rstrip('/')
    if base.endswith('/models'):base=base[:-7]
    url=urlsplit(base)
    if url.scheme not in ['http','https'] or not url.hostname or url.username or url.password:raise ValueError('Invalid configured server base URL')
    cls=http.client.HTTPSConnection if url.scheme=='https' else http.client.HTTPConnection
    conn=cls(url.hostname,url.port,timeout=min(timeout,8))
    try:
        headers={'Content-Type':'application/json'}
        if conf.get(prefix+'API_KEY'):headers['Authorization']='Bearer '+conf[prefix+'API_KEY']
        body=None if payload is None else json.dumps(payload,ensure_ascii=False).encode()
        if client:client.check_cancelled()
        conn.connect()
        if client:client.active_socket=conn.sock;client.check_cancelled()
        conn.sock.settimeout(timeout)
        conn.request('GET' if payload is None else 'POST',url.path+path,body,headers)
        response=conn.getresponse();raw=response.read()
        if client:client.check_cancelled()
        if response.status!=200:raise RuntimeError(f'Server HTTP {response.status}: {raw[:1500].decode(errors="replace")}')
        return json.loads(raw)
    except (OSError,http.client.HTTPException):
        if client:client.check_cancelled()
        raise
    finally:
        if client:client.active_socket=None
        conn.close()

def chat(role,messages,max_tokens=4096,config=None,client=None):
    conf=config or configuration();model=conf['AUDIT_'+role.upper()+'_MODEL']
    payload={'model':model,'messages':messages,'temperature':0,'max_tokens':max_tokens,'stream':False}
    if role=='reasoning' and 'gpt-oss' in model:payload['reasoning_effort']='low'
    start=time.monotonic();response=request(role,'/chat/completions',payload,config=conf,client=client)
    choice=response['choices'][0];content=choice['message'].get('content')
    if choice.get('finish_reason')=='length':raise ValueError('Model output was truncated; raw response requires review.')
    if not isinstance(content,str) or not content.strip():raise ValueError('Model returned no final answer; reasoning is not substituted for it.')
    return {'text':content,'elapsed_seconds':round(time.monotonic()-start,3),'response':response,'request':payload}

class ServerClient:
    def __init__(self,config):self.config=dict(config);self.cancelled=threading.Event();self.active_socket=None
    def check_cancelled(self):
        if self.cancelled.is_set():raise InterruptedError('Cancelled; completed intermediate results are retained in this session.')
    def cancel(self):
        self.cancelled.set()
        if self.active_socket:
            try:self.active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:pass
    def models(self,role):return request(role,'/models',timeout=10,config=self.config,client=self).get('data',[])
    def chat(self,role,messages,max_tokens=4096):return chat(role,messages,max_tokens,config=self.config,client=self)
