"""Bind an input, native model and exports. Hashes detect stale/mixed artifacts."""
import hashlib
import json
import xml.etree.ElementTree as ET
from schema import fail, load

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def record(directory, files):
    return {'schema_version':'1.0','algorithm':'sha256','files':{name:sha(directory/name) for name in files}}

def check(directory, required):
    value=load(directory/'artifact-manifest.json')
    if not isinstance(value,dict) or value.get('schema_version')!='1.0' or value.get('algorithm')!='sha256' or not isinstance(value.get('files'),dict):fail('E_ARTIFACT_MANIFEST','Invalid manifest')
    if set(value['files'])!=set(required):fail('E_ARTIFACT_MANIFEST','Artifact set does not match input')
    for name in required:
        p=directory/name
        if not p.is_file() or sha(p)!=value['files'][name]:fail('E_ARTIFACT_INTEGRITY','Changed or missing artifact: '+name)
    return value

def xml_fingerprint(text,svg=False):
    root=ET.fromstring(text)
    def clean(element):
        attrib=dict(sorted(element.attrib.items()))
        if svg and element is root:attrib.pop('content',None)
        return (element.tag,attrib,(element.text or '').strip(),[clean(c) for c in element])
    return clean(root)

def compare_model(actual,expected,theme):
    actual_root=ET.fromstring(actual);expected_root=ET.fromstring(expected)
    cells={c.get('id'):c for c in actual_root.iter('mxCell')};other={c.get('id'):c for c in expected_root.iter('mxCell')}
    if len(cells)!=len(list(actual_root.iter('mxCell'))) or set(cells)!=set(other):fail('E_MODEL_ELEMENTS','Native cell set differs: '+theme)
    for ident,c in cells.items():
        expected_cell=other[ident]
        if c.get('source')!=expected_cell.get('source') or c.get('target')!=expected_cell.get('target'):fail('E_MODEL_ENDPOINT','Unexpected source/target',[ident])
        if c.get('parent')!=expected_cell.get('parent'):fail('E_MODEL_PARENT','Unexpected parent',[ident])
        def style_values(cell):return dict(part.split('=',1) for part in cell.get('style','').split(';') if '=' in part)
        if style_values(c).get('shape')!=style_values(expected_cell).get('shape'):fail('E_MODEL_SHAPE','Unexpected stencil',[ident])
    if xml_fingerprint(actual)!=xml_fingerprint(expected):fail('E_MODEL_MISMATCH','Native model differs from validated input/layout: '+theme)
