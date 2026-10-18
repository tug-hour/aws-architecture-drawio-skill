"""Optional read-only comparison of explicit draw.io routes. No rendering or gating."""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zlib

from routing import EPS, check_path, compact, route_quality, review_warnings
from schema import Failure


def style(cell):
    return dict(item.split('=',1) if '=' in item else (item,'1')
                for item in cell.get('style','').split(';') if item)


def number(value):
    result=float(value)
    if not math.isfinite(result):raise ValueError('Nonfinite coordinate')
    return result


def pages(xml):
    root=ET.fromstring(xml)
    if root.tag=='mxGraphModel':return [('0',root)]
    result=[]
    for index,page in enumerate(root.findall('diagram')):
        model=page.find('mxGraphModel')
        if model is None:
            model=ET.fromstring(unquote(zlib.decompress(base64.b64decode(page.text or ''),-15).decode()))
        result.append((page.get('id',str(index)),model))
    if not result:raise ValueError('No diagram pages')
    return result


def inspect_page(model):
    items=list(model.iter('mxCell'))
    cells={c.get('id'):c for c in items}
    if None in cells or len(cells)!=len(items):raise ValueError('Missing or duplicate cell IDs')
    styles={key:style(c) for key,c in cells.items()}
    boxes={};unresolved=[];issues=[];edges=[];edge_inputs=[];frames=[]
    def unknown(ident,reason):
        item={'element_id':ident,'reason':reason}
        if item not in unresolved:unresolved.append(item)
    def ancestors(ident):
        seen=set();parent=cells[ident].get('parent')
        while parent in cells:
            if parent in seen:raise ValueError('Cyclic cell parent')
            seen.add(parent);yield parent;parent=cells[parent].get('parent')
    def box(ident):
        if ident in boxes:return boxes[ident]
        cell=cells[ident];g=cell.find('mxGeometry');parents=list(ancestors(ident))
        if g is None:raise ValueError('Missing vertex geometry')
        if any(cells[p].get('edge')=='1' for p in parents):raise ValueError('Edge-relative label geometry needs draw.io')
        if any(styles[k].get('rotation','0')!='0' or styles[k].get('flipH')=='1' or styles[k].get('flipV')=='1' for k in [ident]+parents):
            raise ValueError('Transformed geometry needs draw.io')
        parent=cell.get('parent');owner=box(parent) if parent in cells and cells[parent].get('vertex')=='1' else dict(x=0,y=0,w=0,h=0)
        relative=g.get('relative')=='1'
        # All shared routing checks use pt; native XML uses px.
        x=number(g.get('x',0))*(owner['w'] if relative else .75)+owner['x']
        y=number(g.get('y',0))*(owner['h'] if relative else .75)+owner['y']
        offset=g.find("mxPoint[@as='offset']")
        if offset is not None:x+=number(offset.get('x',0))*.75;y+=number(offset.get('y',0))*.75
        result=dict(id=ident,x=x,y=y,w=number(g.get('width',0))*.75,h=number(g.get('height',0))*.75)
        if result['w']<0 or result['h']<0:raise ValueError('Negative vertex dimensions')
        boxes[ident]=result
        return result
    for ident,cell in cells.items():
        if cell.get('vertex')=='1':
            try:
                b=box(ident);s=styles[ident];text=cell.get('value','')
                # A lower bound, not font measurement. Never enlarge geometry silently:
                # overflow text may extend beyond the stored obstacle used below.
                if text and s.get('html','0')=='0' and 'fontSize' in s:
                    if b['h']+EPS<number(s['fontSize'])*.75*len(text.split('\n')):
                        unknown(ident,'Stored text height is smaller than font size × lines; rendered bounds need draw.io')
            except (ValueError,KeyError) as error:unknown(ident,str(error))
    frame_ids={ident for ident in boxes if styles[ident].get('group')!='1' and
               (styles[ident].get('container')=='1' or styles[ident].get('shape')=='mxgraph.aws4.group')}
    for ident in frame_ids:
        if not any(c.get('parent')==ident for c in cells.values()):
            unknown(ident,'Frame without children: containment or overlay is not known')
            continue
        frames.append(dict(boxes[ident],role='containment'))
    def owner(ident):return next((p for p in ancestors(ident) if p in frame_ids),None)
    architecture={'nodes':[{'id':k,'group_id':owner(k)} for k in boxes if k not in frame_ids],
                  'groups':[{'id':k,'role':'containment','parent_id':owner(k)} for k in frame_ids], 'edges':edge_inputs}
    def endpoint(ident,s,prefix):
        b=box(ident);x=number(s[prefix+'X']);y=number(s[prefix+'Y'])
        if s.get(prefix+'Perimeter')!='0':raise ValueError('Perimeter projection needs draw.io')
        if any(number(s.get(prefix+k,0)) for k in ('Dx','Dy')):raise ValueError('Offset connection needs draw.io')
        side='left' if x==0 else 'right' if x==1 else 'top' if y==0 else 'bottom' if y==1 else None
        if side is None or not (0<=x<=1 and 0<=y<=1):raise ValueError('Nonboundary connection needs visual review')
        return [b['x']+b['w']*x,b['y']+b['h']*y],side
    reserved=[]
    for ident,cell in cells.items():
        if cell.get('edge')!='1':continue
        s=styles[ident]
        try:
            if s.get('edgeStyle') not in (None,'none') or s.get('curved')=='1' or s.get('rounded')=='1':
                raise ValueError('Computed or curved route needs draw.io')
            source,target=cell.get('source'),cell.get('target')
            if source not in boxes or target not in boxes:raise ValueError('Unresolved endpoint')
            if source in frame_ids or target in frame_ids:raise ValueError('Frame connection needs visual membership review')
            start,ss=endpoint(source,s,'exit');end,ts=endpoint(target,s,'entry')
            parent=cell.get('parent');origin=box(parent) if parent in boxes else dict(x=0,y=0)
            if parent in cells and cells[parent].get('vertex')=='1' and parent not in boxes:raise ValueError('Unresolved edge parent')
            inner=[[origin['x']+number(p.get('x',0))*.75,origin['y']+number(p.get('y',0))*.75]
                   for p in cell.findall("mxGeometry/Array[@as='points']/mxPoint")]
            points=[start]+inner+[end]
            simplified=compact(points)
            # Do not erase a backtracking segment before the existing reentry check.
            length=lambda pts:sum(math.dist(p,q) for p,q in zip(pts,pts[1:]))
            if abs(length(points)-length(simplified))<EPS:points=simplified
            if len(points)<2 or any(abs(p[0]-q[0])>EPS and abs(p[1]-q[1])>EPS for p,q in zip(points,points[1:])):
                raise ValueError('Route is not explicitly orthogonal')
        except (KeyError,ValueError) as error:
            unknown(ident,str(error));continue
        edge=dict(id=ident,points=points)
        # Exclude enclosing frames and decorative icon children, but retain text cells.
        obstacles=[]
        for key,b in boxes.items():
            st=styles[key];c=cells[key]
            if key in (source,target) or key in frame_ids or st.get('group')=='1' or st.get('locked')=='1' and c.get('connectable')=='0' and not c.get('value'):continue
            if (source in set(ancestors(key)) or target in set(ancestors(key))) and not c.get('value'):continue
            obstacles.append(b)
        try:check_path(edge,points,boxes[source],boxes[target],obstacles,reserved,math.inf,math.inf,ss,ts,check_bounds=False)
        except Failure as error:issues.append(error.issue)
        reserved.extend(zip(points,points[1:]));edges.append(edge)
        edge_inputs.append(dict(id=ident,source=source,target=target))
    issues.extend(review_warnings(architecture,edges,frames))
    topology=sorted((k,c.get('parent'),c.get('source'),c.get('target'),styles[k].get('startArrow'),styles[k].get('endArrow'))
                    for k,c in cells.items() if c.get('vertex')=='1' or c.get('edge')=='1')
    return {'analyzed_edges':[e['id'] for e in edges], 'total_edges':sum(c.get('edge')=='1' for c in cells.values()),
            'quality':route_quality(edges),'issues':issues,'unresolved':unresolved,'topology':topology,
            'text_bounds':'stored_geometry_not_font_measurement','canvas_bounds':'not_checked'}


def inspect_xml(xml):
    return {'source_sha256':hashlib.sha256(xml.encode()).hexdigest(),
            'pages':[dict(inspect_page(model),page_id=ident) for ident,model in pages(xml)],
            'visual_review_required':True}


def compare(xmls):
    results=[inspect_xml(xml) for xml in xmls]
    signatures=[[(p['page_id'],p['topology']) for p in result['pages']] for result in results]
    coverage=[[(p['page_id'],sorted(p['analyzed_edges'])) for p in result['pages']] for result in results]
    return {'same_topology':all(s==signatures[0] for s in signatures),
            'same_route_coverage':all(c==coverage[0] for c in coverage),
            'results':results,'visual_review_required':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('diagrams',nargs='+',type=Path)
    parser.add_argument('--details',action='store_true',help='Include per-cell topology used by the comparison')
    args=parser.parse_args()
    try:
        report=compare([p.read_bytes().decode('utf-8') for p in args.diagrams])
        for result,path in zip(report['results'],args.diagrams):result['file']=str(path)
        if not args.details:
            for result in report['results']:
                for page in result['pages']:page.pop('topology',None)
        print(json.dumps(report,ensure_ascii=False));return 0
    except (OSError,ValueError,ET.ParseError,zlib.error) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
