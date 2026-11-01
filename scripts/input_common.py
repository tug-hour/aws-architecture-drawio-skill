"""Shared input errors and JSON primitives, independent of legacy schema rules."""
import json
import math

class Failure(Exception):
    def __init__(self,code,message,ids=(),exit_code=2):
        self.issue={'code':code,'message':message,'element_ids':list(ids),'rule_id':None,'source_ref':None,'details':{}}
        self.exit_code=exit_code
        super().__init__(message)
def fail(code,message,ids=(),exit_code=2,*,details=None):
    error=Failure(code,message,ids,exit_code)
    if details is not None:error.issue['details']=details
    raise error
def object_keys(obj,allowed,required=()):
    if not isinstance(obj,dict):fail('E_SCHEMA','Expected object')
    if set(obj)-set(allowed) or set(required)-set(obj):fail('E_SCHEMA','Unknown or missing fields: '+str(sorted((set(obj)-set(allowed))|(set(required)-set(obj)))))
def finite(n,positive=False):
    if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or positive and n<=0:fail('E_SCHEMA','Invalid coordinate or dimension')
def valid_text(value,ident):
    if not isinstance(value,str) or not value.strip() or len(value)>2048:fail('E_SCHEMA','Invalid or excessive label',[ident])
    if any(ord(c)<32 and c!='\n' or 0x7f<=ord(c)<0xa0 or 0xd800<=ord(c)<=0xdfff or 0x202a<=ord(c)<=0x202e or 0x2066<=ord(c)<=0x2069 for c in value):fail('E_TEXT_UNSUPPORTED','Control or bidirectional formatting character',[ident])
    if any(not line.strip() for line in value.split('\n')):fail('E_SCHEMA','Empty label line',[ident])
def unique_pairs(pairs):
    d={}
    for k,v in pairs:
        if k in d:fail('E_SCHEMA','Duplicate JSON key: '+k)
        d[k]=v
    return d
def loads(data):
    try:return json.loads(data.decode('utf-8') if isinstance(data,bytes) else data,object_pairs_hook=unique_pairs,parse_constant=lambda x:fail('E_SCHEMA','Non-finite JSON value'))
    except (json.JSONDecodeError,UnicodeError):fail('E_SCHEMA','Invalid JSON encoding or syntax')
def load(path):
    return loads(path.read_bytes())

