from service_labels import display_label,az_label_warnings
from schema import fail
from auto_layout import automatic_positions,label_width

def frame_overlap_warnings(architecture,frames):
    """Inspect final containment rectangles without changing layout or gates."""
    groups={g['id']:g for g in architecture['groups']}
    containers=sorted((g for g in frames if g['role']=='containment'),key=lambda g:g['id'])
    ancestors={}
    for g in containers:
        parents=set();parent=groups[g['id']].get('parent_id')
        while parent:
            parents.add(parent);parent=groups[parent].get('parent_id')
        ancestors[g['id']]=parents
    warnings=[]
    for index,g in enumerate(containers):
        for other in containers[index+1:]:
            if g['id'] in ancestors[other['id']] or other['id'] in ancestors[g['id']]:continue
            x=max(g['x'],other['x']);y=max(g['y'],other['y'])
            w=min(g['x']+g['w'],other['x']+other['w'])-x
            h=min(g['y']+g['h'],other['y']+other['h'])-y
            if w>0 and h>0:
                warnings.append({'code':'W_FRAME_OVERLAP','element_ids':[g['id'],other['id']],
                                 'details':{'overlap_rect_pt':{'x':x,'y':y,'w':w,'h':h}},
                                 'message':'Unrelated containment frames overlap; review visual membership'})
    return warnings

def geometry(a,m,metrics=None):
    if a['layout']['mode']=='auto':
        try:positions=automatic_positions(a,m,metrics)
        except ValueError as e:fail('E_LAYOUT_CYCLE',str(e))
    else:positions={p['node_id']:p for p in a['layout']['positions']}
    ns=[]
    for n in a['nodes']:
        icon=m['assets'][n['asset_id']];p=positions[n['id']];lines=display_label(n).split('\n')
        # Estimates are restricted to draft mode; they are never reported as browser metrics.
        width=max(120,label_width(display_label(n),metrics)+8)
        ns.append({'id':n['id'],'asset_id':n['asset_id'],'x':p['x_pt'],'y':p['y_pt'],'w':icon['width_pt'],'h':icon['height_pt'],'label':lines,'label_x':p['x_pt']+(icon['width_pt']-width)/2,'label_y':p['y_pt']+icon['height_pt']+16,'label_w':width,'bottom':p['y_pt']+icon['height_pt']+4+len(lines)*14.4,'group_id':n.get('group_id')})
    padding=a['layout'].get('frame_padding_pt',12)
    byid={n['id']:n for n in ns};gs={};warnings=az_label_warnings(a)
    def extent(items,padding,header):
        left=min(i.get('label_x',i['x']) for i in items)-padding
        right=max(i.get('label_x',i['x'])+i.get('label_w',i['w']) for i in items)+padding
        top=min(i['y'] for i in items)-padding-header;bottom=max(i.get('bottom',i['y']+i['h']) for i in items)+padding
        return {'x':left,'y':top,'w':right-left,'h':bottom-top,'bottom':bottom}
    def container(g):
        if g['id'] in gs:return gs[g['id']]
        kids=[n for n in ns if n['group_id']==g['id']]+[container(x) for x in a['groups'] if x.get('parent_id')==g['id']]
        if not kids:fail('E_GROUP_EMPTY','Empty containment group',[g['id']])
        box=extent(kids,padding,54);box['w']=max(box['w'],label_width(g['label'],metrics)+48);box.update(id=g['id'],type=g['type'],label=g['label'],role=g['role']);gs[g['id']]=box;return box
    for g in a['groups']:
        if g['role']=='containment':container(g)
    for g in a['groups']:
        if g['role']=='overlay':
            box=extent([byid[x] for x in g['members']],12,42);box.update(id=g['id'],type=g['type'],label=g['label'],role=g['role']);gs[g['id']]=box
            # Keep an overlay heading separate from the existing group headings.
            # Only extend its frame upward; member coordinates never change.
            for _ in range(len(gs)+1):
                conflicts=[o for o in gs.values() if o['id']!=box['id'] and box['x']<o['x']+o['w'] and o['x']<box['x']+box['w'] and box['y']<o['y']+(54 if o['role']=='overlay' else 30) and o['y']<box['y']+54]
                if not conflicts:break
                top=min(o['y'] for o in conflicts)-60
                box['h']+=box['y']-top;box['y']=top
            for other in gs.values():
                if other['id']==box['id']:continue
                vertical_overlap=max(box['y'],other['y'])<min(box['bottom'],other['bottom'])
                horizontal_overlap=max(box['x'],other['x'])<min(box['x']+box['w'],other['x']+other['w'])
                same_vertical=any(abs(x-y)<0.01 for x in (box['x'],box['x']+box['w']) for y in (other['x'],other['x']+other['w']))
                same_horizontal=any(abs(x-y)<0.01 for x in (box['y'],box['bottom']) for y in (other['y'],other['bottom']))
                if (vertical_overlap and same_vertical) or (horizontal_overlap and same_horizontal):
                    warnings.append({'code':'W_GROUP_SHARED_BORDER','element_ids':[box['id'],other['id']]})
            for n in ns:
                if n['id'] not in g['members'] and box['x']<n['x']<box['x']+box['w'] and box['y']<n['y']<box['bottom']:warnings.append({'code':'W_OVERLAY_INCLUDES_NONMEMBER','element_ids':[g['id'],n['id']]})
    # A bounding frame must not visually claim unrelated nodes as its members.
    input_groups={g['id']:g for g in a['groups']}
    for n in ns:
        ancestors=set();owner=n['group_id']
        while owner:
            ancestors.add(owner);owner=input_groups[owner].get('parent_id')
        cx,cy=n['x']+n['w']/2,n['y']+n['h']/2
        for gid,g in gs.items():
            if g['role']=='containment' and gid not in ancestors and g['x']+.01<cx<g['x']+g['w']-.01 and g['y']+.01<cy<g['bottom']-.01:fail('E_GROUP_VISUAL_MEMBERSHIP','Foreign node appears inside containment frame',[n['id'],gid])
    for g in gs.values():
        icon_width=36 if m['groups'][g['type']]['native_icon'] else 6
        g['header_w']=g['w'] if g['role']=='overlay' else min(g['w'],label_width(g['label'],metrics)+icon_width+8)
    items=ns+list(gs.values())
    if a['canvas']['mode']=='auto':
        box=extent(items,24,0);dx=-box['x'];dy=-box['y'];cw,ch=box['w'],box['h']
        for i in items:
            i['x']+=dx;i['y']+=dy;i['bottom']+=dy
            if 'label_x' in i:i['label_x']+=dx;i['label_y']+=dy
    else:cw,ch=a['canvas']['width_pt'],a['canvas']['height_pt']
    for i in items:
        if min(i.get('label_x',i['x']),i['x'],i['y'])<0 or max(i['x']+i['w'],i.get('label_x',i['x'])+i.get('label_w',i['w']))>cw or i['bottom']>ch:fail('E_LAYOUT_OVERFLOW','Element exceeds canvas',[i['id']])
    for i,n in enumerate(ns):
        for other in ns[i+1:]:
            if min(n['x'],n['label_x'])<max(other['x']+other['w'],other['label_x']+other['label_w']) and min(other['x'],other['label_x'])<max(n['x']+n['w'],n['label_x']+n['label_w']) and n['y']<other['bottom'] and other['y']<n['bottom']:fail('E_LAYOUT_COLLISION','Node regions overlap',[n['id'],other['id']])
    return ns,gs,cw,ch,warnings

def layout(a,m,metrics=None):
    ns,gs,cw,ch,warnings=geometry(a,m,metrics)
    items=ns+list(gs.values())
    from routing import route_edges
    edges=route_edges(a,ns,list(gs.values()),cw,ch)
    from connection_labels import place
    from routing import route_quality
    edge_labels=place(a,ns,list(gs.values()),edges,cw,ch,metrics)
    quality=route_quality(edges)
    from routing import readability
    visual_quality,visual_warnings=readability(edges,list(gs.values()))
    warnings.extend(visual_warnings)
    if quality['crossings']:warnings.append({'code':'W_EDGE_CROSSINGS','details':quality,'message':'Review wire crossings; adjust ports/positions or split the view'})
    glossary=[]
    if a['glossary']:
        offset=24+len(a['glossary'])*20
        for index,g in enumerate(a['glossary']):
            text=(g['short_name']+'：'+g['full_name']) if g.get('kind')=='note' else g['full_name']+' ('+g['short_name']+')'
            glossary.append({'id':'glossary.'+str(index),'text':text,'x':24,'y':12+index*20,'w':label_width(text,metrics)+8,'h':18})
        if a['canvas']['mode']=='auto':
            for item in items:
                item['y']+=offset;item['bottom']+=offset
                if 'label_y' in item:item['label_y']+=offset
            for edge in edges:
                for point in edge['points']:point[1]+=offset
            for item in edge_labels:item['y']+=offset
            cw=max(cw,max(g['x']+g['w']+24 for g in glossary));ch+=offset
        else:
            # Fixed-coordinate inputs retain their declared coordinates. Require
            # explicit space above every diagram item and wire for definitions.
            top=min([i['y'] for i in items]+[p[1] for e in edges for p in e['points']])
            if top<offset or max(g['x']+g['w'] for g in glossary)>cw:fail('E_GLOSSARY_OVERFLOW','Reserve space above fixed diagram for name definitions')
    from routing import review_warnings
    warnings.extend(review_warnings(a,edges,list(gs.values())))
    warnings.extend(frame_overlap_warnings(a,list(gs.values())))
    return {'schema_version':'1.0','canvas':{'width_pt':cw,'height_pt':ch},'nodes':ns,'groups':list(gs.values()),'edges':edges,'glossary':glossary,'connection_labels':edge_labels,'routing_quality':quality,'readability':visual_quality,'measurement':'browser' if metrics is not None else 'estimated-draft-only'},warnings
