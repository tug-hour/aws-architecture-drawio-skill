"""Validate architecture inputs; production rendering is gated on browser QA."""
import copy,json,math,re
import xml.etree.ElementTree as ET

SVG='http://www.w3.org/2000/svg'
ET.register_namespace('',SVG)
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
def load(path):
    try:return json.loads(path.read_text(),object_pairs_hook=unique_pairs,parse_constant=lambda x:fail('E_SCHEMA','Non-finite JSON value'))
    except (json.JSONDecodeError,UnicodeError):fail('E_SCHEMA','Invalid JSON encoding or syntax')

def validate(a,m):
    object_keys(a,('schema_version','mode','theme','profile','direction','canvas','layout','nodes','edges','groups','callouts','glossary','regions','annotations','availability','semantics'),('schema_version','nodes','edges'))
    if a['schema_version']!='1.0':fail('E_VERSION','Unsupported schema version')
    a=copy.deepcopy(a)
    for k,v in {'mode':'production','theme':'light','profile':'standard','direction':'left-to-right','groups':[],'callouts':[],'glossary':[],'regions':[],'annotations':[],'canvas':{'mode':'auto'},'layout':{'mode':'auto'}}.items():a.setdefault(k,v)
    if a['mode'] not in ('production','draft'):fail('E_MODE','Invalid operating mode')
    if a['theme'] not in ('light','dark','both'):fail('E_THEME','Invalid theme')
    if a['profile'] not in ('standard','portrait-document','training-certification'):fail('E_PROFILE','Invalid profile')
    if a['profile']!='standard':
        if a['theme']!='light':fail('E_PROFILE_THEME','This profile requires a white background')
        fail('E_PROFILE_UNSUPPORTED','This implementation supports standard only')
    if a['direction'] not in ('left-to-right','top-to-bottom'):fail('E_SCHEMA','Invalid direction')
    for k in ('nodes','edges','groups','callouts','glossary','regions','annotations'):
        if not isinstance(a[k],list):fail('E_SCHEMA',k+' must be an array')
    object_keys(a['layout'],('mode','positions','frame_padding_pt'),('mode',))
    object_keys(a['canvas'],('mode','width_pt','height_pt'),('mode',))
    if 'frame_padding_pt' in a['layout']:
        finite(a['layout']['frame_padding_pt'])
        if not 12<=a['layout']['frame_padding_pt']<=72:fail('E_LAYOUT_PADDING','frame_padding_pt must be between 12 and 72')
    if not a['nodes']:fail('E_SCHEMA','At least one node is required')
    if a['annotations'] or a['regions']:fail('E_FEATURE_UNSUPPORTED','Annotations and region selection are not implemented in this draft engine')
    if a['callouts']:fail('E_FEATURE_UNSUPPORTED','Callouts are not implemented')
    if len(a['nodes'])>200 or len(a['edges'])>500 or len(a['groups'])>60:fail('E_INPUT_LIMIT','Maximum 200 nodes, 500 edges, 60 groups')
    seen=set()
    def ident(obj):
        v=obj['id']
        if not isinstance(v,str) or not re.fullmatch('[A-Za-z0-9_.-]+',v):fail('E_SCHEMA','Invalid element ID')
        if v in seen:fail('E_DUPLICATE_ID','Duplicate ID',[v])
        seen.add(v)
    for n in a['nodes']:
        object_keys(n,('id','asset_id','label','label_kind','group_id','line_breaks','logical_id','description'),('id','asset_id'));ident(n)
        if not isinstance(n['asset_id'],str):fail('E_SCHEMA','asset_id must be a string',[n['id']])
        if n.get('group_id') is not None and not isinstance(n['group_id'],str):fail('E_SCHEMA','group_id must be a string',[n['id']])
        if n['asset_id'] not in m['assets']:fail('E_ASSET_UNKNOWN','Unknown asset',[n['id']])
        asset=m['assets'][n['asset_id']]
        if asset['role'] not in ('service','resource','general'):fail('E_ASSET_ROLE','This asset is not a node icon',[n['id']])
        if 'logical_id' in n and (asset['role']!='general' or not isinstance(n['logical_id'],str) or not re.fullmatch('[A-Za-z0-9_.-]+',n['logical_id'])):fail('E_NODE_IDENTITY','logical_id is only supported for general actors',[n['id']])
        expected='service-name' if asset['role']=='service' else 'general-label' if asset['role']=='general' else 'resource-name'
        n.setdefault('label_kind',expected)
        if n['label_kind']!=expected:fail('E_LABEL_ROLE','Label kind does not match asset role',[n['id']])
        n.setdefault('label',asset['name'])
        valid_text(n['label'],n['id'])
        if 'description' in n:
            valid_text(n['description'],n['id'])
            if '\n' in n['description'] or len(n['description'])>120:fail('E_DESCRIPTION','Description needs one line, at most 120 characters',[n['id']])
        if 'line_breaks' in n:fail('E_FEATURE_UNSUPPORTED','Use explicit newlines for draft labels',[n['id']])
        if expected=='service-name':
            lines=n['label'].split('\n')
            if len(lines)>2 or any(l.strip() in ('AWS','Amazon') for l in lines):
                from service_labels import name_failure
                name_failure(n,'E_SERVICE_LABEL','Service label must use at most two lines and keep the brand with its first word',fail)
    from service_labels import validate_names
    validate_names(a,m,fail)
    identities={}
    for n in a['nodes']:
        if 'logical_id' in n:
            key=n['logical_id']
            if key in identities and identities[key]!=n['asset_id']:fail('E_NODE_IDENTITY','Repeated actor must use the same asset type',[n['id']])
            identities[key]=n['asset_id']
    nodes={n['id']:n for n in a['nodes']};groups={}
    for g in a['groups']:
        object_keys(g,('id','type','role','label','parent_id','members','region_id','cloud_icon'),('id','type','role'));ident(g)
        if not isinstance(g['type'],str) or not isinstance(g['role'],str):fail('E_SCHEMA','Group type and role must be strings',[g['id']])
        if g.get('parent_id') is not None and not isinstance(g['parent_id'],str):fail('E_SCHEMA','parent_id must be a string',[g['id']])
        if 'cloud_icon' in g and (g['type']!='group.aws-cloud' or g['cloud_icon'] not in ('logo','cloud')):fail('E_GROUP_ICON','Invalid AWS Cloud icon choice',[g['id']])
        if g['type'] not in m['groups']:fail('E_GROUP_TYPE','Unknown group type',[g['id']])
        preset=m['groups'][g['type']]
        if g['role']!=preset['role']:fail('E_GROUP_ROLE','Group role does not match preset',[g['id']])
        g.setdefault('label',preset['name'])
        valid_text(g['label'],g['id'])
        if '\n' in g['label']:fail('E_SCHEMA','Group headings must use one line',[g['id']])
        if 'region_id' in g:fail('E_FEATURE_UNSUPPORTED','Region-specific logo selection is not implemented',[g['id']])
        if g['role']=='containment':
            if 'members' in g:fail('E_GROUP_ROLE','Containment cannot use members',[g['id']])
        else:
            members=g.get('members')
            if 'parent_id' in g or not isinstance(members,list) or len(members)<2 or not all(isinstance(x,str) for x in members) or len(set(members))!=len(members) or not set(members)<=set(nodes):fail('E_GROUP_MEMBERS','Invalid overlay membership',[g['id']])
        groups[g['id']]=g
    for g in groups.values():
        trail=set();cur=g
        while cur.get('parent_id') is not None:
            pid=cur['parent_id']
            if pid not in groups or groups[pid]['role']!='containment':fail('E_GROUP_PARENT','Invalid parent',[g['id']])
            if pid in trail or pid==g['id']:fail('E_GROUP_CYCLE','Group parent cycle',[g['id']])
            trail.add(pid);cur=groups[pid]
    for n in nodes.values():
        if n.get('group_id') is not None and (n['group_id'] not in groups or groups[n['group_id']]['role']!='containment'):fail('E_GROUP_REFERENCE','Invalid node containment',[n['id']])
    for e in a['edges']:
        object_keys(e,('id','source','target','direction','label','waypoints','source_side','target_side','purpose'),('id','source','target'));ident(e)
        if not isinstance(e['source'],str) or not isinstance(e['target'],str):fail('E_SCHEMA','Edge endpoints must be strings',[e['id']])
        if e['source'] not in nodes or e['target'] not in nodes or e['source']==e['target']:fail('E_EDGE_REFERENCE','Invalid edge endpoints',[e['id']])
        e.setdefault('direction','forward')
        if e['direction'] not in ('forward','both','none'):fail('E_SCHEMA','Invalid edge direction',[e['id']])
        if 'purpose' in e and e['purpose'] not in ('traffic','replication','failover','association'):fail('E_EDGE_PURPOSE','Invalid connection purpose',[e['id']])
        if 'purpose' in e and ('label' not in e or e['purpose']=='association' and e['direction']!='none'):fail('E_EDGE_PURPOSE','Semantic connections require labels; associations require no arrows',[e['id']])
        if 'label' in e:
            valid_text(e['label'],e['id'])
            if '\n' in e['label'] or len(e['label'])>80:fail('E_EDGE_LABEL','Edge labels need one line, at most 80 characters',[e['id']])
        for side in ('source_side','target_side'):
            if side in e and e[side] not in ('left','right','top','bottom'):fail('E_EDGE_PORT','Supported sides: left, right, top, bottom',[e['id']])
        if 'waypoints' in e:
            if not isinstance(e['waypoints'],list) or not e['waypoints']:fail('E_SCHEMA','waypoints must be a nonempty array',[e['id']])
            for p in e['waypoints']:
                object_keys(p,('x_pt','y_pt'),('x_pt','y_pt'));finite(p['x_pt']);finite(p['y_pt'])
                if min(p['x_pt'],p['y_pt'])<0:fail('E_SCHEMA','Waypoints must be nonnegative',[e['id']])
            if a['layout']['mode']!='manual' or a['canvas']['mode']!='fixed':fail('E_WAYPOINT_MODE','Explicit waypoints require manual layout and fixed canvas',[e['id']])
    if 'semantics' in a:
        from semantics import validate_semantics
        validate_semantics(a)
    if 'availability' in a:
        from topology import validate_availability
        validate_availability(a)
    if a['edges'] and a['mode']=='production':
        used={e['source'] for e in a['edges']}|{e['target'] for e in a['edges']}
        orphaned=set(nodes)-used
        if orphaned:fail('E_ORPHAN_NODE','Production architecture has disconnected nodes; connect them or split the view',sorted(orphaned))
    for g in a['glossary']:
        object_keys(g,('asset_id','full_name','short_name','kind'),('asset_id','full_name','short_name'))
        if not isinstance(g['asset_id'],str) or g['asset_id'] not in m['assets']:fail('E_GLOSSARY','Invalid glossary asset')
        if g.get('kind','definition') not in ('definition','note'):fail('E_GLOSSARY','Invalid glossary kind')
        for k in ('full_name','short_name'):valid_text(g[k],g['asset_id'])
        if any('\n' in g[k] for k in ('full_name','short_name')):fail('E_GLOSSARY','Glossary entries must be single-line')
    if len({g['short_name'] for g in a['glossary']})!=len(a['glossary']):fail('E_GLOSSARY','Duplicate abbreviation')
    from service_labels import prepare_glossary
    prepare_glossary(a,m,fail)
    object_keys(a['canvas'],('mode','width_pt','height_pt'),('mode',))
    if a['canvas']['mode']=='fixed':
        if not {'width_pt','height_pt'}<=set(a['canvas']):fail('E_SCHEMA','Fixed canvas needs dimensions')
        for k in ('width_pt','height_pt'):finite(a['canvas'][k],True)
    elif a['canvas']!={'mode':'auto'}:fail('E_SCHEMA','Invalid canvas')
    object_keys(a['layout'],('mode','positions','frame_padding_pt'),('mode',))
    if a['layout']['mode']=='auto':
        if 'positions' in a['layout']:fail('E_LAYOUT_POSITION','Auto layout cannot specify positions')
        return a
    if a['layout']['mode']!='manual':fail('E_LAYOUT_MODE','Unknown layout mode')
    ps=a['layout'].get('positions')
    if not isinstance(ps,list):fail('E_SCHEMA','Missing positions')
    pids=[]
    for p in ps:
        object_keys(p,('node_id','x_pt','y_pt'),('node_id','x_pt','y_pt'));finite(p['x_pt']);finite(p['y_pt']);
        if not isinstance(p['node_id'],str):fail('E_SCHEMA','node_id must be a string')
        pids.append(p['node_id'])
    if len(pids)!=len(set(pids)) or set(pids)!=set(nodes):fail('E_LAYOUT_POSITION','Each node needs exactly one position')
    return a
