"""Generate auditable views from one canonical architecture, never inventing edges."""
import argparse,copy,hashlib,json,re
from pathlib import Path
from version import get_version
from schema import load,fail,object_keys,Failure,unique_pairs,valid_text
from build_drawio import normalize
from catalog import manifest
from run import run
from semantics import validate_semantics
from quality import display_quality,operational_quality
from review_status import project_presentation

def project_views(project):
    object_keys(project,('project_version','model','views'),('project_version','model','views'))
    if project['project_version']!='1.0':fail('E_PROJECT_VERSION','Unsupported project version')
    model=normalize(project['model'],manifest());semantic=validate_semantics(model)
    if model['mode']=='production' and semantic['status']!='passed':fail('E_PROJECT_CONTRACT','Production project needs critical flow contracts')
    nodes={n['id']:n for n in model['nodes']};edges={e['id']:e for e in model['edges']};groups={g['id']:g for g in model['groups']}
    if not isinstance(project['views'],list) or not project['views'] or len(project['views'])>50:fail('E_VIEW_SCHEMA','Declare 1..50 views')
    views={};coverage=set();flow_coverage=set();flow_byid={f['id']:f for f in model.get('semantics',{}).get('flows',[])}
    for view in project['views']:
        object_keys(view,('id','title','node_ids','edge_ids','flow_ids','layout','glossary','display'),('id','title','node_ids','edge_ids','flow_ids','layout','display'))
        valid_text(view['title'],'view-title')
        ident=view['id']
        if not isinstance(ident,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',ident) or ident in ('project','project-report') or ident in views:fail('E_VIEW_ID','Invalid or duplicate view ID')
        for key,lookup in (('node_ids',nodes),('edge_ids',edges),('flow_ids',flow_byid)):
            values=view[key]
            if not isinstance(values,list) or any(not isinstance(n,str) or n not in lookup for n in values) or len(set(values))!=len(values):fail('E_VIEW_REFERENCE','Invalid '+key,[ident])
        if not view['node_ids']:fail('E_VIEW_SCHEMA','Empty view',[ident])
        if any(edges[e]['source'] not in view['node_ids'] or edges[e]['target'] not in view['node_ids'] for e in view['edge_ids']):fail('E_VIEW_ENDPOINT','Both endpoints must be visible',[ident])
        owners=set()
        for n in view['node_ids']:
            parent=nodes[n].get('group_id')
            while parent:owners.add(parent);parent=groups[parent].get('parent_id')
        a={k:copy.deepcopy(model[k]) for k in ('schema_version','mode','theme','profile','direction')}
        a.update(nodes=[copy.deepcopy(nodes[n]) for n in view['node_ids']],edges=[copy.deepcopy(edges[e]) for e in view['edge_ids']],groups=[copy.deepcopy(g) for g in groups.values() if g['id'] in owners or g['role']=='overlay' and set(g['members'])<=set(view['node_ids'])],layout=view['layout'],canvas={'mode':'auto'},glossary=view.get('glossary',[]))
        if view['flow_ids']:
            spec=model['semantics'];a['semantics']={'flows':[flow_byid[f] for f in view['flow_ids']], 'standby_nodes':[n for n in spec.get('standby_nodes',[]) if n in view['node_ids']], 'required_edges':[r for r in spec.get('required_edges',[]) if r['id'] in view['edge_ids']]}
        a=normalize(a,manifest())
        display=view['display'];object_keys(display,('width_px','height_px','min_text_px'),('width_px','height_px','min_text_px'))
        if any(type(display[k]) not in (int,float) or not 1<=display[k]<=10000 for k in display):fail('E_DISPLAY_SCHEMA','Invalid viewport')
        crossing=[e['id'] for e in model['edges'] if (e['source'] in view['node_ids']) != (e['target'] in view['node_ids'])]
        hidden=[e['id'] for e in model['edges'] if e['source'] in view['node_ids'] and e['target'] in view['node_ids'] and e['id'] not in view['edge_ids']]
        views[ident]={'architecture':a,'title':view['title'],'display':display,'omitted_boundary_edges':crossing,'omitted_internal_edges':hidden,'flow_ids':view['flow_ids']}
        coverage.update(view['edge_ids']);flow_coverage.update(view['flow_ids'])
    if coverage!=set(edges):fail('E_VIEW_COVERAGE','Every canonical connection must appear in a delivered view',sorted(set(edges)-coverage))
    if flow_coverage!=set(flow_byid):fail('E_VIEW_FLOW_COVERAGE','Every critical flow needs a complete delivered view',sorted(set(flow_byid)-flow_coverage))
    return model,views

def render_project(path,output,binary,profile,runtime):
    if output.exists():fail('E_OUTPUT_EXISTS','Output exists')
    release_version=get_version()
    raw=path.read_bytes()
    model,views=project_views(json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=lambda x:fail('E_SCHEMA','Non-finite JSON value')));output.mkdir(parents=True)
    report={'version':release_version,'status':'running','model_sha256':hashlib.sha256(raw).hexdigest(),'semantic_validation':validate_semantics(model),'views':{},'scope':'Mac local rendering; no skill installation or AWS deployment'}
    (output/'project.json').write_bytes(raw)
    for ident,v in views.items():
        source=output/(ident+'.json');source.write_text(json.dumps(v['architecture'],ensure_ascii=False,indent=2))
        result,code=run(source,output/ident,binary,profile,runtime)
        record={k:v[k] for k in ('title','display','omitted_boundary_edges','omitted_internal_edges','flow_ids')};record.update(status=result['status'],exit_code=code,errors=result.get('errors',[]),warnings=result.get('warnings',[]))
        if code==0:
            lay=load(output/ident/'layout.json')
            quality=operational_quality(result,lay,v['display'])
            record['display_quality']=quality['display_quality']
            record['operational_quality']=quality
        report['views'][ident]=record
        (output/'project-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({ident:record},ensure_ascii=False),flush=True)
    report['status']='passed' if all(v['exit_code']==0 and v['operational_quality']['status']=='passed' for v in report['views'].values()) else 'failed'
    if path.read_bytes()!=raw:report.update(status='failed',errors=[{'code':'E_PROJECT_CHANGED','message':'Project changed during rendering; rerun against fixed input'}])
    (output/'project-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report,0 if report['status']=='passed' else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--drawio',type=Path,default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'));a=p.parse_args()
    try:r,c=render_project(a.input,a.output,a.drawio,a.profile,a.runtime)
    except Failure as e:r,c={'status':'failed','errors':[e.issue]},e.exit_code
    except (OSError,ValueError,TypeError,KeyError) as e:r,c={'status':'failed','errors':[{'code':'E_PROJECT_PROCESSING','message':str(e)}]},2
    print(json.dumps({'status':r['status'],'errors':r.get('errors',[]),'presentation':project_presentation(r)},ensure_ascii=False));raise SystemExit(c)
