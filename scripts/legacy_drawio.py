"""Author native AWS shapes and export through installed draw.io Desktop."""
import argparse,copy,json,subprocess,tempfile,shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from catalog import manifest
from version import get_version
from schema import validate,load,Failure,fail
from layout import layout
SCALE=4/3
FONT='Arial,Arial Unicode MS'
from service_labels import display_label
from drawing import document, vertex as xml_vertex, edge as xml_edge

def style(**values):return ';'.join(k+'='+str(v) for k,v in values.items())+';'
def normalize(a,m):
    if not isinstance(a,dict):fail('E_SCHEMA','Expected object at JSON root')
    a=copy.deepcopy(a)
    for key in ('nodes','glossary'):
        if key in a and not isinstance(a[key],list):fail('E_SCHEMA',key+' must be an array')
    for n in a.get('nodes',[]):
        if isinstance(n,dict) and isinstance(n.get('asset_id'),str):n['asset_id']=m['aliases'].get(n['asset_id'],n['asset_id'])
    for g in a.get('glossary',[]):
        if isinstance(g,dict) and isinstance(g.get('asset_id'),str):g['asset_id']=m['aliases'].get(g['asset_id'],g['asset_id'])
    return validate(a,m)

def author(a,lay,m,theme):
    dark=theme=='dark';fg='#FFFFFF' if dark else '#000000';bg='#000000' if dark else '#FFFFFF';arrow='#8FA7C4' if dark else '#000000'
    doc,root=document('aws-'+theme,theme,dict(grid='0',page='0',background=bg,connect='1',arrows='1',adaptiveColors='none'))
    def vertex(ident,parent,sty,x,y,w,h,text='',connectable='0'):
        return xml_vertex(root,ident,parent,sty,(x,y,w,h),text,connectable,scale=SCALE)
    def caption(ident,parent,x,y,w,h,text,align='left',bold=False,size=12,color=fg):
        vertex(ident,parent,'text;'+style(html=0,whiteSpace='nowrap',overflow='visible',align=align,verticalAlign='top',spacing=0,fontSize=size*SCALE,fontFamily=FONT,fontStyle=1 if bold else 0,fontColor=color,strokeColor='none',fillColor='none'),x,y,w,h,text)
    vertex('canvas','1',style(shape='rect',fillColor=bg,strokeColor='none',locked=1),0,0,lay['canvas']['width_pt'],lay['canvas']['height_pt'])
    input_groups={g['id']:g for g in a['groups']};groups={g['id']:g for g in lay['groups']}
    def make_group(gid):
        g=groups[gid];src=input_groups[gid];parent_id=src.get('parent_id');parent='frame.'+parent_id if parent_id else '1'
        if parent_id and not any(c.get('id')==parent for c in root):make_group(parent_id)
        ox,oy=(groups[parent_id]['x'],groups[parent_id]['y']) if parent_id else (0,0)
        if any(c.get('id')=='frame.'+gid for c in root):return
        preset=m['groups'][g['type']];frame=style(shape='rect',fillColor='none',strokeColor=preset['color'][theme],strokeWidth=1.25*SCALE,rounded=0,pointerEvents=0)
        if preset['dash']!='solid':frame+=style(dashed=1,dashPattern=' '.join(str(x) for x in m['dash_patterns'][preset['dash']]),fixDash=0)
        vertex('frame.'+gid,parent,frame+style(container=1,collapsible=0,recursiveResize=0),g['x']-ox,g['y']-oy,g['w'],g['h'])
        if preset['native_icon']:
            x=(g['w']-30)/2 if g['role']=='overlay' else 0
            icon_color=('#FFFFFF' if dark else '#242F3E') if g['type']=='group.aws-cloud' else preset['color'][theme]
            backing=('#232F3E' if dark else '#FFFFFF') if g['type']=='group.aws-cloud' else '#FFFFFF'
            vertex('header.base.'+gid,'frame.'+gid,style(shape='rect',fillColor=backing,strokeColor='none'),x,0,30,30)
            shape='mxgraph.aws4.group_aws_cloud' if src.get('cloud_icon')=='cloud' else preset['native_icon']
            vertex('header.icon.'+gid,'frame.'+gid,style(shape=shape,fillColor=icon_color,strokeColor='none',aspect='fixed'),x,0,30,30)
            if g['role']=='overlay':caption('header.label.'+gid,'frame.'+gid,3,33,g['w']-6,18,g['label'],'center')
            else:caption('header.label.'+gid,'frame.'+gid,36,3,g['w']-39,27,g['label'])
        else:caption('header.label.'+gid,'frame.'+gid,6,3,g['w']-12,27,g['label'])
    for gid in groups:make_group(gid)
    nodes={n['id']:n for n in lay['nodes']};owners={}
    for n in lay['nodes']:
        item=m['assets'][n['asset_id']];parent='frame.'+n['group_id'] if n.get('group_id') else '1';owners[n['id']]=n.get('group_id')
        ox,oy=(groups[n['group_id']]['x'],groups[n['group_id']]['y']) if n.get('group_id') else (0,0)
        parent_node='node.'+n['id'];left=min(n['x'],n['label_x']);width=max(n['x']+n['w'],n['label_x']+n['label_w'])-left
        vertex(parent_node,parent,'group;'+style(recursiveResize=0,container=1,resizable=0,rotatable=0),left-ox,n['y']-oy,width,n['bottom']-n['y'])
        ix=n['x']-left
        fill=item['color'] if item['role']=='service' else 'none'
        vertex('icon.base.'+n['id'],parent_node,style(shape='rect',fillColor=fill,strokeColor='none',perimeter='rectanglePerimeter'),ix,0,n['w'],n['h'],connectable='1')
        # Native glyph, sized to the PPTX's 56/80 inner service viewport.
        factor=(n['w']*SCALE*.7 if item['role']=='service' else n['w']*SCALE)/max(item['native_width'],item['native_height'])
        gw=item['native_width']*factor/SCALE;gh=item['native_height']*factor/SCALE
        color='#FFFFFF' if item['role']=='service' else item.get('theme_colors',{}).get(theme,item['color'])
        vertex('icon.glyph.'+n['id'],parent_node,style(shape=item['shape'],fillColor=color,strokeColor='none',aspect='fixed',resizable=0,movable=0,rotatable=0),ix+(n['w']-gw)/2,(n['h']-gh)/2,gw,gh)
        caption('label.'+n['id'],parent_node,n['label_x']-left,n['h']+4,n['label_w'],len(n['label'])*14.4,'\n'.join(n['label']),'center')
    def ancestors(node):
        result=[];g=owners[node]
        while g:result.append(g);g=input_groups[g].get('parent_id')
        return result
    for edge,route in zip(a['edges'],lay['edges']):
        target_anc=ancestors(edge['target']);common=next((g for g in ancestors(edge['source']) if g in target_anc),None);parent='frame.'+common if common else '1'
        ox,oy=(groups[common]['x'],groups[common]['y']) if common else (0,0)
        sty=style(html=0,rounded=0,strokeColor=arrow,strokeWidth=1.25*SCALE,startArrow=m['arrow']['native_type'] if edge['direction']=='both' else 'none',endArrow='none' if edge['direction']=='none' else m['arrow']['native_type'],startFill=0,endFill=0,startSize=m['arrow']['size_px'],endSize=m['arrow']['size_px'],exitX=route['source_port'][0],exitY=route['source_port'][1],entryX=route['target_port'][0],entryY=route['target_port'][1],exitPerimeter=0,entryPerimeter=0)
        xml_edge(root,'edge.'+edge['id'],parent,sty,'icon.base.'+edge['source'],'icon.base.'+edge['target'],
                 [(x-ox,y-oy) for x,y in route['points'][1:-1]],scale=SCALE)
    for g in lay.get('connection_labels',[]):caption(g['id'],'1',g['x'],g['y'],g['w'],g['h'],g['text'])
    for g in lay.get('glossary',[]):caption(g['id'],'1',g['x'],g['y'],g['w'],g['h'],g['text'])
    if a['callouts']:fail('E_FEATURE_UNSUPPORTED','Native callout validation is not implemented')
    return ET.tostring(doc,encoding='unicode',xml_declaration=True)

def export_file(binary,profile,source,target,kind):
    binary=binary.resolve();profile=profile.resolve();source=source.resolve();target=target.resolve()
    if target.exists():fail('E_EXPORT_EXISTS','Refuse stale export target: '+str(target))
    command=[str(binary),'--disable-update','--user-data-dir='+str(profile),'--export','--format',kind,'--theme','light','--timeout','30','--check','--output',str(target),str(source)]
    if kind=='svg':command[command.index('--output'):command.index('--output')]=['--embed-svg-fonts','false','--embed-svg-metadata','--embed-diagram']
    p=subprocess.run(command,text=True,capture_output=True,timeout=45)
    if p.returncode or not target.is_file():fail('E_DRAWIO_EXPORT',(p.stderr or p.stdout)[-1500:],exit_code=4)

def measurement_texts(a):
    return sorted({line for item in a['nodes']+a['groups'] for line in (display_label(item) if 'asset_id' in item else item['label']).split('\n')} | {(g['short_name']+'：'+g['full_name']) if g.get('kind')=='note' else g['full_name']+' ('+g['short_name']+')' for g in a['glossary']} | {e['label'] for e in a['edges'] if 'label' in e})

def drawio_version(binary,profile):
    binary=binary.resolve();profile=profile.resolve()
    if not binary.is_file():fail('E_RUNTIME_UNAVAILABLE','Installed draw.io executable required',exit_code=3)
    import re
    proc=subprocess.run([str(binary),'--disable-update','--user-data-dir='+str(profile),'--version'],text=True,capture_output=True,timeout=15)
    match=re.search(r'(?:draw\.io\s+)?(\d+\.\d+\.\d+)',proc.stdout)
    if proc.returncode or not match:fail('E_DRAWIO_VERSION','Cannot confirm draw.io version',exit_code=3)
    return match.group(1)

def build(path,output,binary,profile,runtime=None):
    try:
        if output.exists():fail('E_OUTPUT_EXISTS','Output path already exists')
        release_version=get_version();m=manifest();a=normalize(load(path),m);metrics=None;environment={}
        version=drawio_version(binary,profile)
        if a['mode']=='production' and version!=m['tested_drawio_version']:fail('E_DRAWIO_UNTESTED','Production requires tested draw.io '+m['tested_drawio_version'],exit_code=3)
        if a['mode']=='production' and runtime is None:fail('E_RUNTIME_REQUIRED','Production requires browser measurement',exit_code=3)
        if runtime:
            from browser_runtime import invoke,RuntimeFailure
            try:
                result=invoke(runtime,{'operation':'measure','texts':measurement_texts(a)});metrics=result['metrics'];environment=result['environment']
            except RuntimeFailure as e:fail('E_BROWSER_RUNTIME',str(e),exit_code=3)
        lay,warnings=layout(a,m,metrics);themes=['light','dark'] if a['theme']=='both' else [a['theme']]
        environment['drawio']=version
        if version!=m['tested_drawio_version']:warnings.append({'code':'W_UNTESTED_DRAWIO_VERSION','message':version})
        if metrics is None:warnings.append({'code':'W_ESTIMATED_LABELS','message':'No browser measurement; label layout unverified'})
        unverified=[n['id'] for n in a['nodes'] if m['assets'][n['asset_id']].get('support_status')!='verified']
        if unverified:warnings.append({'code':'W_UNVERIFIED_ASSET','element_ids':unverified,'message':'PPTX role/style/rendering unverified'})
        with tempfile.TemporaryDirectory(prefix='aws-drawio-') as scratch:
            stage=Path(scratch);artifacts=[]
            for theme in themes:
                source=stage/(theme+'.drawio');source.write_text(author(a,lay,m,theme),encoding='utf-8')
                for kind in ('svg','png'):export_file(binary,profile,source,stage/(theme+'.'+kind),kind)
                artifacts.extend([theme+'.drawio',theme+'.svg',theme+'.png'])
            report={'status':'exported','stage':'native-export','mode':a['mode'],'aws_conformance':'unverified','errors':[],'warnings':warnings+[{'code':'W_NATIVE_ARROW_GEOMETRY','message':'Native open-arrow geometry approximates OOXML med/sm'},{'code':'W_NATIVE_ICON_GEOMETRY','message':'Native AWS4 artwork is not the original PPTX SVG'},{'code':'W_JAPANESE_FONT_EXTENSION','message':'Japanese Arial Unicode MS is an extension to the PPTX Arial rule'}],'environment':environment,'renderer':'draw.io','candidate_version':release_version,'artifacts':artifacts}
            for name,value in [('architecture.json',a),('layout.json',lay),('measurements.json',metrics),('validation.json',report)]:
                (stage/name).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
            from integrity import record
            report_files=artifacts+['architecture.json','layout.json','measurements.json','validation.json']
            (stage/'artifact-manifest.json').write_text(json.dumps(record(stage,report_files),indent=2))
            output.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.aws-publish-',dir=output.parent) as publishing:
                prepared=Path(publishing)/'prepared';shutil.copytree(stage,prepared)
                if output.exists():fail('E_OUTPUT_EXISTS','Output appeared during rendering')
                prepared.rename(output)
        return report,0
    except Failure as e:return {'status':'failed','errors':[e.issue],'artifacts':[]},e.exit_code
    except (OSError,ValueError,TypeError,KeyError,ET.ParseError,subprocess.TimeoutExpired) as e:return {'status':'failed','errors':[{'code':'E_PROCESSING','message':str(e)}],'artifacts':[]},4


def main():
    parser = argparse.ArgumentParser(description='Compatibility renderer for schema_version 1.0')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--drawio', type=Path, default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'))
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--runtime', type=Path)
    args = parser.parse_args()
    result, code = build(args.input, args.output, args.drawio, args.profile, args.runtime)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
