"""Optional placement-table helper. Author native files; export only when requested."""
import argparse
import ast
import copy
import json
import math
import tempfile
import subprocess
from pathlib import Path

from build_drawio import normalize, author, measurement_texts, export_file
from catalog import manifest
from browser_runtime import RuntimeFailure
from layout import geometry, layout
from routing import allocate_ports, compact
from schema import Failure, fail, load


def read_spec(path):
    """Read JSON or Python literal assignments without executing a supplied file."""
    if path.suffix == '.json':
        return load(path)
    values = {}
    for statement in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            continue
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            fail('E_PLACEMENT_SPEC', 'Use literal assignments (POS, W, H, SIDES, LANES, AUTO); Python is not executed')
        name = statement.targets[0].id
        if name in values:fail('E_PLACEMENT_SPEC', 'Duplicate placement key: '+name)
        values[name] = ast.literal_eval(statement.value)
    return values


def auto_sides(source, target):
    dx, dy = target[0]-source[0], target[1]-source[1]
    if abs(dy) <= 30:return ('right','left') if dx > 0 else ('left','right')
    if abs(dx) <= 30:return None,None
    if dy > 0:return ('right','top') if dx > 0 else ('left','top')
    return ('top','left') if dx > 0 else ('top','right')


def build_path(start, end, source_side, target_side, lanes):
    pts=[start];cur=start;axis='v' if source_side in ('top','bottom') else 'h'
    for value in lanes:
        cur=(value,cur[1]) if axis=='h' else (cur[0],value)
        pts.append(cur);axis='v' if axis=='h' else 'h'
    if target_side in ('top','bottom'):
        if axis=='h':pts.append((end[0],cur[1]))
        elif abs(cur[0]-end[0]) > .01:
            raise ValueError('Vertical entry is not aligned with target x; adjust LANES')
    elif axis=='v':pts.append((cur[0],end[1]))
    elif abs(cur[1]-end[1]) > .01:
        mid=(cur[0]+end[0])/2;pts.extend([(mid,cur[1]),(mid,end[1])])
    pts.append(end)
    return compact(pts)


def apply_spec(raw, spec, catalog):
    a=copy.deepcopy(raw)
    if not isinstance(a,dict):fail('E_SCHEMA','Expected architecture object')
    if not isinstance(spec,dict) or set(spec)-{'POS','W','H','SIDES','LANES','AUTO'} or not {'POS','W','H'} <= set(spec):
        fail('E_PLACEMENT_SPEC','Placement needs POS, W, H and optional SIDES, LANES, AUTO')
    def number(value):
        if type(value) not in (int,float) or not math.isfinite(value):fail('E_PLACEMENT_SPEC','Coordinates must be finite numbers')
    for key in ('W','H'):number(spec[key])
    nodes=a.get('nodes',[]);edges=a.get('edges',[])
    if not isinstance(nodes,list) or not isinstance(edges,list):fail('E_SCHEMA','nodes and edges must be arrays')
    if any(not isinstance(n,dict) or not isinstance(n.get('id'),str) for n in nodes+edges):fail('E_SCHEMA','Elements need string IDs')
    node_ids={n['id'] for n in nodes};edge_ids={e['id'] for e in edges}
    pos=spec['POS'];sides=spec.get('SIDES',{});lanes=spec.get('LANES',{});auto=spec.get('AUTO',[])
    if not isinstance(pos,dict) or set(pos)!=node_ids:fail('E_PLACEMENT_SPEC','POS must name every node exactly once')
    for name,values in [('SIDES',sides),('LANES',lanes)]:
        if not isinstance(values,dict) or not set(values)<=edge_ids:fail('E_PLACEMENT_SPEC',name+' contains an unknown edge')
    if not isinstance(auto,(list,tuple)) or any(not isinstance(k,str) or k not in edge_ids for k in auto):fail('E_PLACEMENT_SPEC','AUTO contains an unknown edge')
    if set(auto)&set(lanes):fail('E_PLACEMENT_SPEC','An AUTO edge cannot also specify LANES')
    positions=[];centers={}
    for n in nodes:
        xy=pos[n['id']]
        if not isinstance(xy,(list,tuple)) or len(xy)!=2:fail('E_PLACEMENT_SPEC','POS coordinates need x, y')
        for value in xy:number(value)
        asset=n.get('asset_id');asset=catalog['aliases'].get(asset,asset) if isinstance(asset,str) else None
        if asset not in catalog['assets']:fail('E_ASSET_UNKNOWN','Unknown asset',[n['id']])
        item=catalog['assets'][asset]
        positions.append({'node_id':n['id'],'x_pt':xy[0]+(60-item['width_pt'])/2,'y_pt':xy[1]+(60-item['height_pt'])/2})
        centers[n['id']]=(xy[0]+30,xy[1]+30)
    a['layout']={**a.get('layout',{}),'mode':'manual','positions':positions}
    a['canvas']={'mode':'fixed','width_pt':spec['W'],'height_pt':spec['H']}
    for e in edges:
        if e.get('source') not in centers or e.get('target') not in centers:fail('E_EDGE_REFERENCE','Unknown endpoint',[e['id']])
        for key in ('source_side','target_side','waypoints'):e.pop(key,None)
        pair=sides.get(e['id'],auto_sides(centers[e['source']],centers[e['target']]))
        if not isinstance(pair,(list,tuple)) or len(pair)!=2 or any(s not in (None,'left','right','top','bottom') for s in pair):fail('E_PLACEMENT_SPEC','SIDES needs two values: left, right, top, bottom or None',[e['id']])
        for key,value in zip(('source_side','target_side'),pair):
            if value is not None:e[key]=value
        values=lanes.get(e['id'],[])
        if not isinstance(values,(list,tuple)):fail('E_PLACEMENT_SPEC','LANES must be an array',[e['id']])
        for value in values:number(value)
    return normalize(a,catalog)


def build(a, spec, catalog, metrics=None):
    a=apply_spec(a,spec,catalog)
    nodes,_,_,_,_=geometry(a,catalog,metrics)
    ports=allocate_ports(a,nodes)
    for e in a['edges']:
        if e['id'] in spec.get('AUTO',[]):continue
        p=ports[e['id']]
        try:points=build_path(tuple(p['start']),tuple(p['end']),p['source_side'],p['target_side'],spec.get('LANES',{}).get(e['id'],[]))
        except ValueError as error:fail('E_PLACEMENT_SPEC',str(error),[e['id']])
        inner=points[1:-1] or [[(points[0][0]+points[-1][0])/2,(points[0][1]+points[-1][1])/2]]
        e['waypoints']=[{'x_pt':x,'y_pt':y} for x,y in inner]
    # Reuse the existing obstacle/terminal/overlap checks, not a second HIT checker.
    lay,warnings=layout(a,catalog,metrics)
    lay['measurement']='browser' if metrics is not None else 'estimated'
    return a,lay,warnings


def generate(source, spec_path, output, runtime=None, binary=None, profile=None):
    try:
        if output.exists():fail('E_OUTPUT_EXISTS','Output already exists')
        if binary is not None and profile is None:fail('E_RUNTIME_REQUIRED','Export needs an existing dedicated profile',exit_code=3)
        catalog=manifest();raw=load(source);spec=read_spec(spec_path);metrics=None
        if runtime is not None:
            from browser_runtime import invoke
            metrics=invoke(runtime,{'operation':'measure','texts':measurement_texts(apply_spec(raw,spec,catalog))})['metrics']
        a,lay,warnings=build(raw,spec,catalog,metrics)
        themes=['light','dark'] if a['theme']=='both' else [a['theme']]
        report={'status':'authored','measurement':'browser' if metrics is not None else 'estimated',
                'visual_review':'required','routing_quality':lay['routing_quality'],'warnings':warnings,
                'artifacts':['architecture.json','layout.json','report.json']}
        from version import get_version
        report['version']=get_version()
        unknown=[n['id'] for n in a['nodes'] if catalog['assets'][n['asset_id']].get('support_status')!='verified']
        if unknown:report['warnings'].append({'code':'W_UNVERIFIED_ASSET','element_ids':unknown,'message':'Confirm used native shapes visually; catalog history is not a usage restriction'})
        with tempfile.TemporaryDirectory(prefix='aws-waypoints-') as tmp:
            stage=Path(tmp)
            for theme in themes:
                path=stage/(theme+'.drawio');path.write_text(author(a,lay,catalog,theme),encoding='utf-8');report['artifacts'].append(path.name)
                if binary is not None:
                    for kind in ('svg','png'):
                        target=stage/(theme+'.'+kind);export_file(binary,profile,path,target,kind);report['artifacts'].append(target.name)
            if binary is not None:report['status']='exported'
            for name,value in [('architecture.json',a),('layout.json',lay),('report.json',report)]:
                (stage/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            # Reserve the final directory exclusively, preserving any existing work.
            output.mkdir(parents=True,exist_ok=False)
            import shutil
            for path in stage.iterdir():shutil.copyfile(path,output/path.name)
        return report,0
    except Failure as error:return {'status':'failed','errors':[error.issue]},error.exit_code
    except (RuntimeFailure,subprocess.TimeoutExpired) as error:
        return {'status':'failed','errors':[{'code':'E_RUNTIME_UNAVAILABLE','message':str(error)}]},3
    except (OSError,ValueError,TypeError,KeyError,SyntaxError) as error:
        return {'status':'failed','errors':[{'code':'E_PLACEMENT_SPEC','message':str(error)}]},2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('input','spec','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--runtime',type=Path,help='Optional existing browser metrics runtime')
    parser.add_argument('--export',action='store_true',help='Also export SVG and PNG once through installed draw.io')
    parser.add_argument('--drawio',type=Path,default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'))
    parser.add_argument('--profile',type=Path)
    args=parser.parse_args()
    result,code=generate(args.input,args.spec,args.output,args.runtime,args.drawio if args.export else None,args.profile)
    print(json.dumps(result,ensure_ascii=False));return code

if __name__=='__main__':raise SystemExit(main())
