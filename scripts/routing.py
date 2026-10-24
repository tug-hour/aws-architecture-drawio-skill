"""Deterministic orthogonal routing around icons, labels and group headers."""
import heapq
import math
from bisect import bisect_left
from input_common import fail

EPS = 0.01
CLEARANCE = 5.0
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

def search(start,end,boxes,reserved,width,height,crossing_penalty=120,frames=()):
    xs={start[0],end[0],8.0,width-8};ys={start[1],end[1],8.0,height-8}
    for b in boxes:
        for margin in (CLEARANCE, CLEARANCE+8):
            xs.update((b['x']-margin,b['x']+b['w']+margin))
            ys.update((b['y']-margin,b['y']+b['h']+margin))
    for g in frames:
        for lane in (18,30):
            xs.update((g['x']-lane,g['x']+lane,g['x']+g['w']-lane,g['x']+g['w']+lane))
            ys.update((g['y']-lane,g['y']+lane,g['y']+g['h']-lane,g['y']+g['h']+lane))
    # Nearby lanes make parallel connections distinguishable without extra libraries.
    for p,q in reserved:
        xs.update((p[0]-8,p[0]+8,q[0]-8,q[0]+8))
        ys.update((p[1]-8,p[1]+8,q[1]-8,q[1]+8))
    xs=sorted(x for x in xs if 0<=x<=width);ys=sorted(y for y in ys if 0<=y<=height)
    if len(xs)*len(ys)>160000:fail('E_ROUTING_LIMIT','Routing grid too large; split the diagram')
    origin=(bisect_left(xs,start[0]),bisect_left(ys,start[1]),-1)
    checks={}
    goal=(bisect_left(xs,end[0]),bisect_left(ys,end[1]));cost={origin:0};parent={};queue=[(abs(start[0]-end[0])+abs(start[1]-end[1]),0,origin,0)];serial=0
    while queue:
        _,_,state,total=heapq.heappop(queue);i,j,direction=state
        if total!=cost[state]:continue
        if (i,j)==goal:
            path=[]
            while True:
                path.append([xs[state[0]],ys[state[1]]])
                if state==origin:break
                state=parent[state]
            return compact(path[::-1])
        p=(xs[i],ys[j])
        for ni,nj,axis in ((i-1,j,0),(i+1,j,0),(i,j-1,1),(i,j+1,1)):
            if not (0<=ni<len(xs) and 0<=nj<len(ys)):continue
            q=(xs[ni],ys[nj])
            key=tuple(sorted(((i,j),(ni,nj))))
            if key not in checks:
                checks[key]=None if any(rect_hit(p,q,b,CLEARANCE-.1) for b in boxes) or any(shared_length(p,q,u,v)>EPS for u,v in reserved) else math.dist(p,q)+crossing_penalty*sum(crossing(p,q,u,v,grid_step=True) for u,v in reserved)+4*sum(border_exposure(p,q,g) for g in frames)
            step=checks[key]
            if step is None:continue
            nxt=(ni,nj,axis);value=total+step+(16 if direction not in (-1,axis) else 0)
            if value<cost.get(nxt,float('inf')):
                cost[nxt]=value;parent[nxt]=state;serial+=1;heapq.heappush(queue,(value+abs(q[0]-end[0])+abs(q[1]-end[1]),serial,nxt,value))
    fail('E_ROUTE_UNAVAILABLE','No safe route; supply manual positions/waypoints or split the diagram')

def edge_sides(a,e,byid):
    """Return the source/target sides, applying the defaults used by routing."""
    n,t=byid[e['source']],byid[e['target']];forward=t['x']>=n['x']
    return e.get('source_side','right' if forward else 'left'),e.get('target_side',('left' if forward else 'right') if a['direction']=='left-to-right' else 'top')

def allocate_ports(a,nodes):
    """Assign every edge endpoint a port fraction on its side.

    Ports on one side are ordered by the other end's x (top/bottom sides) or y (left/right side),
    then horizontal pairs whose icon centres align are moved onto one shared y.
    Returns {edge_id: {'source_side','target_side','source_port','target_port','start','end'}}.
    """
    byid={n['id']:n for n in nodes};connections={}
    for e in a['edges']:
        source_side,target_side=edge_sides(a,e,byid)
        connections.setdefault((e['source'],source_side),[]).append(('source',e['id']))
        connections.setdefault((e['target'],target_side),[]).append(('target',e['id']))
    edge_inputs={e['id']:e for e in a['edges']}
    for (node_id,side),values in connections.items():
        def order_port(item):
            role,ident=item;edge=edge_inputs[ident]
            other=byid[edge['target'] if role=='source' else edge['source']]
            return (other['x'] if side in ('top','bottom') else other['y'],ident,role)
        values.sort(key=order_port)
    allocated={}
    for key,values in connections.items():
        for value in values:allocated[(key,value)]=.1+.8*(values.index(value)+1)/(len(values)+1)
    # Align unobstructed horizontal pairs without collapsing distinct endpoint lanes.
    for e in a['edges']:
        n,t=byid[e['source']],byid[e['target']];ss,ts=edge_sides(a,e,byid)
        if (ss,ts) not in (('right','left'),('left','right')):continue
        if abs(n['y']+n['h']/2-t['y']-t['h']/2)>EPS:continue
        sk=((n['id'],ss),('source',e['id']));tk=((t['id'],ts),('target',e['id']))
        low=max(n['y']+.1*n['h'],t['y']+.1*t['h']);high=min(n['y']+.9*n['h'],t['y']+.9*t['h']);mid=(n['y']+allocated[sk]*n['h']+t['y']+allocated[tk]*t['h'])/2
        candidates=sorted({mid,low,high}|{low+i*8 for i in range(int(max(0,high-low)/8)+1)},key=lambda y:abs(y-mid))
        for y in candidates:
            if not low<=y<=high:continue
            if any(abs(y-byid[key[0][0]]['y']-v*byid[key[0][0]]['h'])<8-EPS for key,v in allocated.items() if key not in (sk,tk) and key[0] in (sk[0],tk[0])):continue
            allocated[sk]=(y-n['y'])/n['h'];allocated[tk]=(y-t['y'])/t['h'];break
    ports={}
    for e in a['edges']:
        n,t=byid[e['source']],byid[e['target']];ss,ts=edge_sides(a,e,byid)
        sy=allocated[((n['id'],ss),('source',e['id']))];ty=allocated[((t['id'],ts),('target',e['id']))]
        sp={'right':(1,sy),'left':(0,sy),'top':(sy,0),'bottom':(sy,1)}[ss];tp={'right':(1,ty),'left':(0,ty),'top':(ty,0),'bottom':(ty,1)}[ts]
        ports[e['id']]={'source_side':ss,'target_side':ts,'source_port':sp,'target_port':tp,
                        'start':[n['x']+sp[0]*n['w'],n['y']+sp[1]*n['h']],'end':[t['x']+tp[0]*t['w'],t['y']+tp[1]*t['h']]}
    return ports

def obstacle_boxes(nodes,groups,exclude=()):
    """Icons (except the edge's own ends), every node label and every frame header."""
    boxes=[{'id':'icon.'+v['id'],'x':v['x'],'y':v['y'],'w':v['w'],'h':v['h']} for v in nodes if v['id'] not in exclude]
    boxes += [{'id':'label.'+v['id'],'x':v['label_x'],'y':v['y']+v['h']+4,'w':v['label_w'],'h':len(v['label'])*14.4} for v in nodes]
    boxes += [{'id':'header.'+g['id'],'x':g['x'],'y':g['y'],'w':g.get('header_w',g['w']),'h':54 if g['role']=='overlay' else 30} for g in groups]
    return boxes


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


def _route_edges(a,nodes,groups,width,height,order):
    byid={n['id']:n for n in nodes};ports=allocate_ports(a,nodes)
    reserved=[];result=[]
    for e in order:
        n,t=byid[e['source']],byid[e['target']]
        port=ports[e['id']]
        source_side,target_side=port['source_side'],port['target_side']
        source_port,target_port=port['source_port'],port['target_port']
        start,end=port['start'],port['end']
        vectors={'right':(TERMINAL,0),'left':(-TERMINAL,0),'top':(0,-TERMINAL),'bottom':(0,TERMINAL)}
        sv,tv=vectors[source_side],vectors[target_side]
        first=[start[0]+sv[0],start[1]+sv[1]];last=[end[0]+tv[0],end[1]+tv[1]]
        boxes=obstacle_boxes(nodes,groups,(n['id'],t['id']))
        if 'waypoints' in e:
            points=compact([start]+[[p['x_pt'],p['y_pt']] for p in e['waypoints']]+[end])
        else:
            endpoint_boxes=[{'x':v['x'],'y':v['y'],'w':v['w'],'h':v['h']} for v in (n,t)]
            try:points=compact([start]+search(first,last,boxes+endpoint_boxes,reserved,width,height,frames=groups)+[end])
            except Exception as error:
                if hasattr(error,'issue'):error.issue['element_ids']=[e['id']]
                raise
        check_path(e,points,n,t,boxes,reserved,width,height,source_side,target_side)
        reserved.extend(zip(points,points[1:]));result.append({'id':e['id'],'points':points,'direction':e['direction'],'source_port':list(source_port),'target_port':list(target_port)})
    lookup={r['id']:r for r in result}
    return [lookup[e['id']] for e in a['edges']]


def route_edges(a,nodes,groups,width,height):
    from input_common import Failure
    byid={n['id']:n for n in nodes}
    def distance(edge):
        source,target=byid[edge['source']],byid[edge['target']]
        return math.dist((source['x'],source['y']),(target['x'],target['y']))
    orders=[sorted(a['edges'],key=lambda e:e['id']),a['edges'],sorted(a['edges'],key=lambda e:('waypoints' not in e,-distance(e),e['id']))]
    tried=set();candidates=[];last=None
    for order in orders:
        key=tuple(e['id'] for e in order)
        if key in tried:continue
        tried.add(key)
        try:
            result=_route_edges(a,nodes,groups,width,height,order)
            quality=route_quality(result)
            candidates.append(((quality['total_length_pt']+48*quality['bends']+240*quality['crossings'],quality['crossings'],quality['bends']),result))
        except Failure as error:last=error
    if not candidates:raise last
    return min(candidates,key=lambda item:item[0])[1]


def check_terminals(edge,points,source_side,target_side):
    vectors={'left':(-1,0),'right':(1,0),'top':(0,-1),'bottom':(0,1)}
    for name,p,q,side in [('source',points[0],points[1],source_side),('target',points[-1],points[-2],target_side)]:
        dx,dy=q[0]-p[0],q[1]-p[1];vx,vy=vectors[side]
        if abs(dx*vy-dy*vx)>EPS or dx*vx+dy*vy<TERMINAL-EPS:
            fail('E_EDGE_TERMINAL','Endpoint needs an outward straight segment of at least 24 pt',[edge['id']])

def readability(edges,frames=()):
    warnings=[];metrics=[];ports={}
    for e in edges:
        points=e['points'];length=sum(math.dist(p,q) for p,q in zip(points,points[1:]));direct=abs(points[-1][0]-points[0][0])+abs(points[-1][1]-points[0][1]);ratio=length/max(direct,1)
        item={'edge_id':e['id'],'length_pt':round(length,2),'detour_ratio':round(ratio,3),'first_segment_pt':round(math.dist(points[0],points[1]),2),'last_segment_pt':round(math.dist(points[-1],points[-2]),2)};metrics.append(item)
        if ratio>1.5 and length>180:warnings.append({'code':'W_EDGE_DETOUR','element_ids':[e['id']],'details':item,'message':'Review placement and ports; obstacle avoidance can cause a long detour'})
        for g in frames:
            exposure=sum(border_exposure(p,q,g) for p,q in zip(points,points[1:]))
            if exposure>48:warnings.append({'code':'W_FRAME_WIRE_PROXIMITY','element_ids':[e['id'],g['id']],'details':{'parallel_length_pt':round(exposure,2)},'message':'Wire runs within 18 pt of a frame for more than 48 pt'})
        for point in (points[0],points[-1]):
            # Distinct ends at any positions, including neighboring icons, must leave visible arrow room.
            for ident,old in ports.values():
                if ident!=e['id'] and math.dist(point,old)<8-EPS:warnings.append({'code':'W_PORT_PROXIMITY','element_ids':[e['id'],ident],'message':'Endpoints are closer than 8 pt; review arrowheads'})
            ports[(e['id'],tuple(point))]=(e['id'],point)
    return {'terminal_minimum_pt':TERMINAL,'endpoint_warning_distance_pt':8,'detour_warning_ratio':1.5,'edges':metrics},warnings


def border_exposure(p,q,g,clearance=18):
    if abs(p[1]-q[1])<EPS:
        if min(abs(p[1]-g['y']),abs(p[1]-g['y']-g['h']))>=clearance-EPS:return 0
        return max(0,min(max(p[0],q[0]),g['x']+g['w'])-max(min(p[0],q[0]),g['x']))
    if abs(p[0]-q[0])<EPS:
        if min(abs(p[0]-g['x']),abs(p[0]-g['x']-g['w']))>=clearance-EPS:return 0
        return max(0,min(max(p[1],q[1]),g['y']+g['h'])-max(min(p[1],q[1]),g['y']))
    return 0


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
