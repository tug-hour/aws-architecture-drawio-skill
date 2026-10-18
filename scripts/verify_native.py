from service_labels import display_label
"""Check native SVG exports against extracted PPTX style and size rules."""
import argparse,base64,json,re,math,tempfile,shutil,subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from browser_runtime import invoke,RuntimeFailure
from catalog import manifest
from version import get_version
SCALE=4/3
def overlap(a,b):return a['x']<b['x']+b['w']-.2 and b['x']<a['x']+a['w']-.2 and a['y']<b['y']+b['h']-.2 and b['y']<a['y']+a['h']-.2
def points(d):
    # Desktop rounds exported coordinates to hundredths of a pixel. Normalize
    # axis drift up to .03px before orthogonal collision checks; keep real diagonals.
    number=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
    if not d.lstrip().startswith('M') or re.search('[^ML0-9., +eE-]',d) or d.count('M')!=1:return []
    nums=[float(x) for x in re.findall(number,d)]
    if len(nums)%2 or any(not math.isfinite(x) for x in nums):return []
    result=[]
    for x,y in zip(nums[::2],nums[1::2]):
        if result:
            px,py=result[-1]
            if abs(x-px)<=.03:x=px
            elif abs(y-py)<=.03:y=py
        result.append((x,y))
    return result
def inspect(a,m,t,v,lay):
    errors=[];warn=[];nodes={n['id']:n for n in a['nodes']};groups={g['id']:g for g in a['groups']}
    def error(code,ids=()):errors.append({'code':code,'element_ids':list(ids),'theme':t})
    glossary={g['id']:g['text'] for g in lay.get('glossary',[])+lay.get('connection_labels',[])}
    label_ids={l['id'] for l in v['labels']};expected={'label.'+n for n in nodes}|{'header.label.'+g for g in groups}|set(glossary)
    if label_ids!=expected or len(v['labels'])!=len(expected):error('E_LABEL_ELEMENTS')
    if v['images']:error('E_EMBEDDED_IMAGE')
    for label in v['labels']:
        key=label['id'];text=display_label(nodes[key[6:]]) if key.startswith('label.') else glossary[key] if key.startswith(('glossary.','connection.label.')) else groups[key[13:]]['label']
        if label['text']!=text.replace('\n',''):error('E_LABEL_TEXT',[key])
        if not label['font_sizes'] or any(abs(size-16)>.01 for size in label['font_sizes']):error('E_LABEL_SIZE',[key])
        if any(color!=('rgb(255, 255, 255)' if t=='dark' else 'rgb(0, 0, 0)') for color in label['colors']):error('E_LABEL_COLOR',[key])
        if label['x']<-.2 or label['y']<-.2 or label['x']+label['w']>v['dimensions']['width']+.2 or label['y']+label['h']>v['dimensions']['height']+.2:error('E_LABEL_OVERFLOW',[key])
        for icon in v['icons']:
            if overlap(label,icon):error('E_LABEL_ICON',[key,icon['id']])
    for i,label in enumerate(v['labels']):
        for other in v['labels'][i+1:]:
            if overlap(label,other):error('E_LABEL_COLLISION',[label['id'],other['id']])
    if {i['id'] for i in v['icons']}!={'icon.base.'+n for n in nodes}:error('E_ICON_ELEMENTS')
    if {g['id'] for g in v['glyphs']}!={'icon.glyph.'+n for n in nodes}:error('E_GLYPH_ELEMENTS')
    for glyph in v['glyphs']:
        asset=m['assets'][nodes[glyph['id'][11:]]['asset_id']]
        if not glyph['primitives'] or min(glyph['w'],glyph['h'])<=0:error('E_GLYPH_EMPTY',[glyph['id']])
        color='#FFFFFF' if asset['role']=='service' else asset.get('theme_colors',{}).get(t,asset['color'])
        if color.upper() not in {f.upper() for f in glyph['fills']}:error('E_GLYPH_COLOR',[glyph['id']])
    for icon in v['icons']:
        asset=m['assets'][nodes[icon['id'][10:]]['asset_id']]
        if abs(icon['w']-asset['width_pt']*SCALE)>.1 or abs(icon['h']-asset['height_pt']*SCALE)>.1:error('E_ICON_SIZE',[icon['id']])
        if asset['role']=='service' and icon['fill'].upper()!=asset['color'].upper():error('E_ICON_COLOR',[icon['id']])
    expected_headers={'header.icon.'+g['id'] for g in groups.values() if m['groups'][g['type']]['native_icon']}
    if {h['id'] for h in v['headers']}!=expected_headers:error('E_GROUP_ICON_ELEMENTS')
    for h in v['headers']:
        if abs(h['w']-40)>.1 or abs(h['h']-40)>.1:error('E_GROUP_ICON_SIZE',[h['id']])
        g=groups[h['id'][12:]];expected_color=('#FFFFFF' if t=='dark' else '#242F3E') if g['type']=='group.aws-cloud' else m['groups'][g['type']]['color'][t]
        if expected_color not in {f.upper() for f in h['fills']}:error('E_GROUP_ICON_COLOR',[g['id']])
    if {f['id'] for f in v['frames']}!={'frame.'+g for g in groups}:error('E_FRAME_ELEMENTS')
    for frame in v['frames']:
        g=groups[frame['id'][6:]];preset=m['groups'][g['type']]
        if frame['fill'] not in (None,'none'):error('E_GROUP_FILL',[g['id']])
        if (frame['stroke'] or '').upper()!=preset['color'][t].upper() or abs(frame['width']-1.25*SCALE)>.01:error('E_GROUP_LINE',[g['id']])
        expected_dash=m['dash_patterns'][preset['dash']]
        actual=[float(n) for n in frame['dash'].split()] if frame['dash'] else None
        if expected_dash is None and actual is not None or expected_dash is not None and (actual is None or any(abs(x*SCALE*1.25-y)>.02 for x,y in zip(expected_dash,actual)) or len(actual)!=2):error('E_GROUP_DASH',[g['id']])
    edge_inputs={e['id']:e for e in a['edges']}
    if {e['id'] for e in v['edges']}!={'edge.'+e for e in edge_inputs}:error('E_EDGE_ELEMENTS')
    color='#8FA7C4' if t=='dark' else '#000000'
    from routing import rect_hit,shared_length
    segments=[]
    for edge in v['edges']:
        visible=[p for p in edge['paths'] if p['stroke'] and p['stroke'].upper()==color]
        if any(p['fill']!='none' or abs(p['width']-1.25*SCALE)>.01 for p in visible):error('E_ARROW_STYLE',[edge['id']])
        required={'forward':2,'both':3,'none':1}[edge_inputs[edge['id'][5:]]['direction']]
        if len(visible)!=required:error('E_ARROW_MARKER_COUNT',[edge['id']])
        if not visible:continue
        route=max((points(p['d']) for p in visible),key=lambda p:sum(math.dist(x,y) for x,y in zip(p,p[1:])))
        if len(route)<2:error('E_EDGE_PATH_UNSUPPORTED',[edge['id']]);continue
        input_edge=edge_inputs[edge['id'][5:]]
        # Open and OpenThin trim the shaft equally at this line width; retain the existing 9px allowance.
        terminal_min=24*SCALE-9
        if math.dist(route[0],route[1])<terminal_min or math.dist(route[-1],route[-2])<terminal_min:error('E_RENDERED_TERMINAL',[edge['id']])
        for x,y in zip(route,route[1:]):
            if min(*x,*y)<-.2 or max(x[0],y[0])>v['dimensions']['width']+.2 or max(x[1],y[1])>v['dimensions']['height']+.2:error('E_EDGE_OVERFLOW',[edge['id']])
            for icon in v['icons']:
                if icon['id'][10:] not in (input_edge['source'],input_edge['target']) and rect_hit(x,y,icon):error('E_EDGE_ICON',[edge['id'],icon['id']])
            for old_id,u,z in segments:
                if old_id!=edge['id'] and shared_length(x,y,u,z)>.3:error('E_EDGE_OVERLAP',[edge['id'],old_id])
            segments.append((edge['id'],x,y))
            region={'x':min(x[0],y[0])-.84,'y':min(x[1],y[1])-.84,'w':abs(x[0]-y[0])+1.68,'h':abs(x[1]-y[1])+1.68}
            for label in v['labels']:
                if overlap(region,label):error('E_EDGE_LABEL',[edge['id'],label['id']])
    return errors,warn

def verify(source,output,runtime,binary=None,profile=None,expected_input=None):
    from schema import Failure,load,fail
    from build_drawio import normalize,author,export_file,measurement_texts,drawio_version
    from layout import layout
    from integrity import check,compare_model,xml_fingerprint,sha
    report=None
    try:
        if output.exists():fail('E_OUTPUT_EXISTS','QA output already exists')
        release_version=get_version()
        built=load(source/'validation.json')
        if not isinstance(built,dict) or not isinstance(built.get('candidate_version'),str):fail('E_VALIDATION_METADATA','validation.json must be an object with a string candidate_version')
        if built.get('candidate_version')!=release_version:fail('E_RELEASE_VERSION_MISMATCH','Use the skill release that generated these artifacts')
        m=manifest();a=normalize(load(source/'architecture.json'),m)
        themes=['light','dark'] if a['theme']=='both' else [a['theme']]
        required=['architecture.json','layout.json','measurements.json','validation.json']+[theme+'.'+ext for theme in themes for ext in ('drawio','svg','png')]
        # Model errors are more useful than a generic changed-file error.
        metrics=load(source/'measurements.json');lay=load(source/'layout.json')
        if a['mode']=='production' and metrics is None:fail('E_METRICS_REQUIRED','Production needs measured labels')
        recomputed,_=layout(a,m,metrics)
        if recomputed!=lay:fail('E_LAYOUT_MISMATCH','Layout does not match validated input/measurements')
        if expected_input is not None and normalize(load(expected_input),m)!=a:fail('E_INPUT_MISMATCH','Archived input differs from requested input')
        for theme in themes:compare_model((source/(theme+'.drawio')).read_text(),author(a,lay,m,theme),theme)
        hashes=check(source,required)
        if binary is None or profile is None:fail('E_RUNTIME_REQUIRED','Verification requires installed draw.io and dedicated profile',exit_code=3)
        version=drawio_version(binary,profile)
        if a['mode']=='production' and version!=m['tested_drawio_version']:fail('E_DRAWIO_UNTESTED','Unsupported production draw.io version',exit_code=3)
        with tempfile.TemporaryDirectory(prefix='aws-native-check-') as scratch:
            stage=Path(scratch);images={}
            for theme in themes:
                target=stage/(theme+'.svg');export_file(binary,profile,source/(theme+'.drawio'),target,'svg')
                fresh=target.read_text()
                if xml_fingerprint(fresh,svg=True)!=xml_fingerprint((source/(theme+'.svg')).read_text(),svg=True):fail('E_EXPORT_MISMATCH','Stored SVG differs from freshly rendered native model: '+theme)
                png=stage/(theme+'.png');export_file(binary,profile,source/(theme+'.drawio'),png,'png')
                if sha(png)!=sha(source/(theme+'.png')):fail('E_PNG_EXPORT_MISMATCH','Stored PNG differs from fresh render: '+theme)
                images[theme]=fresh
            value=invoke(runtime,{'operation':'inspect-native','images':images,'texts':measurement_texts(a)})
        errors=[];evidence={};previous=None;payload={}
        for theme,svg in images.items():
            elements={e.get('data-cell-id'):e for e in ET.fromstring(svg).iter() if e.get('data-cell-id')}
            for g in a['groups']:
                if g['type']=='group.aws-cloud':
                    cell=elements.get('header.base.'+g['id'])
                    fills={e.get('fill','').upper() for e in cell.iter()} if cell is not None else set()
                    expected='#232F3E' if theme=='dark' else '#FFFFFF'
                    if expected not in fills:errors.append({'code':'E_CLOUD_ICON_BACKING','theme':theme,'element_ids':[g['id']]})
        for theme in themes:
            v=value['themes'][theme];errs,_=inspect(a,m,theme,v,lay);errors.extend(errs)
            geom=[(x['id'],x['x'],x['y'],x['w'],x['h']) for x in v['labels']+v['icons']+v['headers']+v['frames']]
            if previous is not None and geom!=previous:errors.append({'code':'E_THEME_GEOMETRY'})
            previous=geom;payload[theme+'.browser.png']=base64.b64decode(v.pop('png_base64'));evidence[theme]=v
        if built['environment'].get('font_sha256')!=value['environment']['font_sha256']:errors.append({'code':'E_FONT_ENVIRONMENT_CHANGED'})
        warnings=list(built.get('warnings',[]))
        topology=None
        if 'availability' in a:
            from topology import validate_availability
            topology=validate_availability(a)
        report={'topology':topology,'readability':lay.get('readability'),'status':'failed' if errors else 'passed','stage':'native-model-and-render','mode':a['mode'],'production_eligible':a['mode']=='production' and not errors,'aws_conformance':'partial','conformance_scope':{'service_names':'registered names checked; other names require visual review; max two service-name lines','abbreviations':'source-backed full definitions precede the diagram','native_artwork':'approximation','arrow_geometry':'approximation','japanese_font':'extension','unsupported':['numbered callouts','custom service groups','portrait-document','training-certification','automatic region logo selection'],'certification':'No AWS approval or complete PPTX conformance is asserted'},'errors':errors,'warnings':warnings,'environment':dict(value['environment'],drawio=version),'candidate_version':release_version,'themes':evidence,'binding':hashes,'manifest_sha256':sha(source/'artifact-manifest.json'),'limitations':['Native artwork and standard open arrows approximate PPTX originals','Arbitrary edge crossings/frame crossings may need human review','Architecture technical correctness is outside style checks']}
        if errors:
            output.mkdir(parents=True,exist_ok=False);(output/'browser-validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False));return report,2
        output.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.aws-qa-',dir=output.parent) as publishing:
            stage=Path(publishing)/'prepared';stage.mkdir()
            for name,data in payload.items():(stage/name).write_bytes(data)
            (stage/'browser-validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False));stage.rename(output)
        return report,0
    except Failure as e:report,code={'status':'failed','production_eligible':False,'errors':[e.issue]},e.exit_code
    except (RuntimeFailure,OSError,ValueError,KeyError,TypeError,ET.ParseError,subprocess.TimeoutExpired) as e:report,code={'status':'failed','production_eligible':False,'errors':[{'code':'E_VERIFICATION_RUNTIME','message':str(e)}]},3
    if not output.exists():
        output.mkdir(parents=True,exist_ok=False);(output/'browser-validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    return report,code

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--drawio',type=Path,default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'));p.add_argument('--profile',type=Path,required=True);p.add_argument('--expected-input',type=Path);args=p.parse_args()
    result,code=verify(args.input,args.output,args.runtime,args.drawio,args.profile,args.expected_input)
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(code)
