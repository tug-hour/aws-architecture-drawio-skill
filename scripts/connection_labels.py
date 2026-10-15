"""Place readable native connection labels beside routes, away from all graphics."""
import math
from auto_layout import label_width
from schema import fail
from routing import rect_hit

def overlaps(a,b):
    return a['x']<b['x']+b['w']+2 and b['x']<a['x']+a['w']+2 and a['y']<b['y']+b['h']+2 and b['y']<a['y']+a['h']+2

def place(a,nodes,groups,routes,width,height,metrics):
    boxes=[{'x':n['label_x'],'y':n['y'],'w':max(n['label_w'],n['w']),'h':n['bottom']-n['y']} for n in nodes]
    boxes += [{'x':g['x'],'y':g['y'],'w':g.get('header_w',g['w']),'h':54 if g['role']=='overlay' else 30} for g in groups]
    for g in groups:
        boxes += [{'x':g['x']-2,'y':g['y'],'w':4,'h':g['h']},{'x':g['x']+g['w']-2,'y':g['y'],'w':4,'h':g['h']},{'x':g['x'],'y':g['y']-2,'w':g['w'],'h':4},{'x':g['x'],'y':g['y']+g['h']-2,'w':g['w'],'h':4}]
    segments=[(p,q) for e in routes for p,q in zip(e['points'],e['points'][1:])]
    byid={e['id']:e for e in routes};labels=[]
    for edge in a['edges']:
        if 'label' not in edge:continue
        w=label_width(edge['label'],metrics)+8;h=18
        choices=sorted(zip(byid[edge['id']]['points'],byid[edge['id']]['points'][1:]),key=lambda pair:(abs(pair[0][1]-pair[1][1])>.01,-math.dist(*pair)))
        candidates=[]
        for p,q in choices:
            if abs(p[1]-q[1])<.01:
                positions=[p[0]+(q[0]-p[0])*fraction-w/2 for fraction in (.5,.25,.75)]
                positions += [x for box in boxes+labels for x in (box['x']-w-4,box['x']+box['w']+4) if min(p[0],q[0])<=x+w/2<=max(p[0],q[0])]
                for x in positions:
                    candidates += [{'x':x,'y':p[1]-h-6,'w':w,'h':h},{'x':x,'y':p[1]+6,'w':w,'h':h}]
            else:
                y=(p[1]+q[1]-h)/2
                candidates += [{'x':p[0]+6,'y':y,'w':w,'h':h},{'x':p[0]-w-6,'y':y,'w':w,'h':h}]
        chosen=next((b for b in candidates if b['x']>=0 and b['y']>=0 and b['x']+w<=width and b['y']+h<=height and not any(overlaps(b,o) for o in boxes+labels) and not any(rect_hit(p,q,b,2) for p,q in segments)),None)
        if chosen is None:fail('E_CONNECTION_LABEL_SPACE','No clear space for edge label; increase spacing or split diagram',[edge['id']])
        labels.append(dict(chosen,id='connection.label.'+edge['id'],text=edge['label']))
    return labels
