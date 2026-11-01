"""Read-only routing checks and metrics; no automatic route search."""

import math

from input_common import fail

EPS = 0.01


TERMINAL = 24.0


def rect_hit(p, q, box, padding=0):
    x0, y0 = box['x']-padding, box['y']-padding
    x1, y1 = box['x']+box['w']+padding, box['y']+box['h']+padding
    if abs(p[0]-q[0]) < EPS:
        return x0+EPS < p[0] < x1-EPS and max(min(p[1],q[1]),y0) < min(max(p[1],q[1]),y1)-EPS
    if abs(p[1]-q[1]) < EPS:
        return y0+EPS < p[1] < y1-EPS and max(min(p[0],q[0]),x0) < min(max(p[0],q[0]),x1)-EPS
    return True


def shared_length(p, q, u, v):
    if abs(p[1]-q[1]) < EPS and abs(u[1]-v[1]) < EPS and abs(p[1]-u[1]) < EPS:
        return max(0,min(max(p[0],q[0]),max(u[0],v[0]))-max(min(p[0],q[0]),min(u[0],v[0])))
    if abs(p[0]-q[0]) < EPS and abs(u[0]-v[0]) < EPS and abs(p[0]-u[0]) < EPS:
        return max(0,min(max(p[1],q[1]),max(u[1],v[1]))-max(min(p[1],q[1]),min(u[1],v[1])))
    return 0


def compact(points):
    result=[]
    for p in points:
        p=list(p)
        if result and math.dist(result[-1],p)<EPS:continue
        if len(result)>1 and (abs(result[-2][0]-result[-1][0])<EPS and abs(result[-1][0]-p[0])<EPS or abs(result[-2][1]-result[-1][1])<EPS and abs(result[-1][1]-p[1])<EPS):result.pop()
        result.append(p)
    return result


def crossing(p,q,u,v,grid_step=False):
    horizontal=abs(p[1]-q[1])<EPS;other_horizontal=abs(u[1]-v[1])<EPS
    if horizontal==other_horizontal:return False
    h1,h2,z1,z2=(p,q,u,v) if horizontal else (u,v,p,q)
    if grid_step:
        return min(h1[0],h2[0])-EPS<=z1[0]<=max(h1[0],h2[0])+EPS and min(z1[1],z2[1])-EPS<=h1[1]<=max(z1[1],z2[1])+EPS
    return min(h1[0],h2[0])+EPS<z1[0]<max(h1[0],h2[0])-EPS and min(z1[1],z2[1])+EPS<h1[1]<max(z1[1],z2[1])-EPS


def route_quality(edges):
    segments=[(e['id'],p,q) for e in edges for p,q in zip(e['points'],e['points'][1:])]
    crossings=[]
    for i,(ident,p,q) in enumerate(segments):
        for other,u,v in segments[i+1:]:
            if ident!=other and crossing(p,q,u,v):crossings.append([ident,other])
    return {'crossings':len(crossings),'crossing_pairs':crossings,'bends':sum(max(0,len(e['points'])-2) for e in edges),'total_length_pt':round(sum(math.dist(p,q) for _,p,q in segments),2)}


def check_path(e,points,source,target,boxes,reserved,width,height,source_side=None,target_side=None,check_bounds=True):
    """Shared post-route checks; callers decide whether failures gate or advise."""
    for segment_index,(p,q) in enumerate(zip(points,points[1:])):
        if abs(p[0]-q[0])>EPS and abs(p[1]-q[1])>EPS:fail('E_EDGE_OBSTACLE','Waypoints must form orthogonal segments',[e['id']])
        for owner in (source,target):
            allowed=owner['id']==source['id'] and segment_index==0 or owner['id']==target['id'] and segment_index==len(points)-2
            if not allowed and rect_hit(p,q,owner):fail('E_EDGE_REENTRY','Edge reenters source/target icon',[e['id']])
        if check_bounds and (min(*p,*q)<0 or max(p[0],q[0])>width or max(p[1],q[1])>height):fail('E_ROUTE_OVERFLOW','Edge exceeds canvas',[e['id']])
        hit=next((b['id'] for b in boxes if rect_hit(p,q,b)),None)
        if hit:fail('E_EDGE_OBSTACLE','Edge intersects '+hit+' (icon/label/header)',[e['id']],details={'obstacle':hit,'segment':[p,q]})
        if any(shared_length(p,q,u,v)>EPS for u,v in reserved):fail('E_EDGE_OVERLAP','Edges share a segment',[e['id']])
    if source_side is not None and target_side is not None:
        check_terminals(e,points,source_side,target_side)


def check_terminals(edge,points,source_side,target_side):
    vectors={'left':(-1,0),'right':(1,0),'top':(0,-1),'bottom':(0,1)}
    for name,p,q,side in [('source',points[0],points[1],source_side),('target',points[-1],points[-2],target_side)]:
        dx,dy=q[0]-p[0],q[1]-p[1];vx,vy=vectors[side]
        if abs(dx*vy-dy*vx)>EPS or dx*vx+dy*vy<TERMINAL-EPS:
            fail('E_EDGE_TERMINAL','Endpoint needs an outward straight segment of at least 24 pt',[edge['id']])


def _on_segment(point, p, q):
    if abs(p[0]-q[0]) < EPS:
        return abs(point[0]-p[0]) < EPS and min(p[1],q[1])-EPS <= point[1] <= max(p[1],q[1])+EPS
    return abs(point[1]-p[1]) < EPS and min(p[0],q[0])-EPS <= point[0] <= max(p[0],q[0])+EPS


def review_warnings(architecture, edges, frames):
    """Inspect final routes only; never participate in routing or input acceptance."""
    warnings = []
    groups = {g['id']: g for g in architecture['groups']}
    owners = {}
    for node in architecture['nodes']:
        ancestors = set()
        parent = node.get('group_id')
        while parent:
            ancestors.add(parent)
            parent = groups[parent].get('parent_id')
        owners[node['id']] = ancestors
    inputs = {e['id']: e for e in architecture['edges']}
    for edge in edges:
        source = inputs[edge['id']]
        related = owners[source['source']] | owners[source['target']]
        for frame in frames:
            if frame['role'] != 'containment' or frame['id'] in related:
                continue
            segments = [i for i,(p,q) in enumerate(zip(edge['points'],edge['points'][1:])) if rect_hit(p,q,frame)]
            if segments:
                warnings.append({'code':'W_EDGE_FRAME_TRANSIT','element_ids':[edge['id'],frame['id']],
                                 'details':{'segment_indices':segments},
                                 'message':'Wire enters a containment frame unrelated to either endpoint; review its meaning'})

    for index, edge in enumerate(edges):
        for other in edges[index+1:]:
            left = list(zip(edge['points'],edge['points'][1:]))
            right = list(zip(other['points'],other['points'][1:]))
            shared = [(p,q,u,v) for p,q in left for u,v in right if shared_length(p,q,u,v) > EPS]
            contacts = []
            for i,(p,q) in enumerate(left):
                for j,(u,v) in enumerate(right):
                    if crossing(p,q,u,v):
                        continue
                    for point in (p,q,u,v):
                        if not (_on_segment(point,p,q) and _on_segment(point,u,v)):
                            continue
                        # These cases already have overlap or endpoint diagnostics.
                        if any(_on_segment(point,a,b) and _on_segment(point,c,d) for a,b,c,d in shared):
                            continue
                        if all(any(math.dist(point,end) < EPS for end in (e['points'][0],e['points'][-1])) for e in (edge,other)):
                            continue
                        if any(math.dist(point,c['point_pt']) < EPS for c in contacts):
                            continue
                        contacts.append({'point_pt':list(point),'segment_indices':[i,j]})
            if contacts:
                warnings.append({'code':'W_EDGE_CONTACT','element_ids':[edge['id'],other['id']],
                                 'details':{'contacts':contacts},
                                 'message':'Distinct wires touch at a segment end or bend; review possible connection ambiguity'})
    return warnings
