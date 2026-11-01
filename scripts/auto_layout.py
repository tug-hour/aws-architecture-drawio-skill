from service_labels import display_label
"""Deterministic hierarchical DAG placement, without external layout packages."""
from collections import defaultdict
import unicodedata

FONT_FAMILY = 'Arial, "AWS Japanese", "Arial Unicode MS", sans-serif'

def estimated_width(text):
    return sum(0 if unicodedata.combining(c) else 12 if unicodedata.east_asian_width(c) in ('W','F') else 7.2 for c in text)

def label_width(text, metrics=None):
    if metrics is not None:
        return max(metrics[line]['width'] for line in text.split('\n'))
    return max(estimated_width(line) for line in text.split('\n'))

def automatic_positions(a, manifest, metrics=None):
    """Pack each containment scope independently, preserving declared ownership.

    Edges contracted to siblings establish ranks. Cyclic scope constraints are
    rejected rather than deleting edges or inventing an ordering.
    """
    nodes={n['id']:n for n in a['nodes']}
    groups={g['id']:g for g in a['groups'] if g['role']=='containment'}
    parents={n['id']:n.get('group_id') for n in nodes.values()}
    parents.update({g['id']:g.get('parent_id') for g in groups.values()})
    children=defaultdict(list)
    for ident,parent in parents.items():children[parent].append(ident)
    def representative(node, scope):
        cur=node
        while parents.get(cur)!=scope:
            cur=parents.get(cur)
            if cur is None:return None
        return cur
    padding=a['layout'].get('frame_padding_pt',12)
    def pack(scope):
        items=sorted(children[scope]);blocks={}
        for ident in items:
            if ident in groups:blocks[ident]=pack(ident)
            else:
                n=nodes[ident];asset=manifest['assets'][n['asset_id']]
                width=max(120,label_width(display_label(n),metrics)+8,asset['width_pt'])
                blocks[ident]=(width,asset['height_pt']+8+14.4*len(display_label(n).split('\n')),{ident:((width-asset['width_pt'])/2,0)})
        adj={i:set() for i in items};indegree={i:0 for i in items}
        for e in a['edges']:
            src=representative(e['source'],scope);dst=representative(e['target'],scope)
            if src is not None and dst is not None and src!=dst and dst not in adj[src]:adj[src].add(dst);indegree[dst]+=1
        ranks={i:0 for i in items};ready=sorted(i for i in items if not indegree[i]);visited=0
        while ready:
            cur=ready.pop(0);visited+=1
            for dst in sorted(adj[cur]):
                ranks[dst]=max(ranks[dst],ranks[cur]+1);indegree[dst]-=1
                if not indegree[dst]:ready.append(dst);ready.sort()
        if visited!=len(items):raise ValueError('Cyclic dependencies in containment scope: '+str(scope))
        layers=defaultdict(list)
        for ident in items:layers[ranks[ident]].append(ident)
        # Order siblings by their predecessor positions rather than ID alone.
        # Deterministic barycentric ordering reduces avoidable fan-in crossings.
        order={}
        for rank in sorted(layers):
            def barycenter(ident):
                prev=[order[src] for src in items if ident in adj[src] and src in order]
                return (sum(prev)/len(prev) if prev else float('inf'),ident)
            layers[rank].sort(key=barycenter)
            for index,ident in enumerate(layers[rank]):order[ident]=index
        gap=max([96]+[label_width(e['label'],metrics)+24 for e in a['edges'] if 'label' in e and representative(e['source'],scope)!=representative(e['target'],scope) and representative(e['source'],scope) in ranks and representative(e['target'],scope) in ranks])
        horizontal=a['direction']=='left-to-right';positions={};along=0;cross_max=0;layer_coords=[]
        for rank in sorted(layers):
            across=0;depth=0;members=[]
            for ident in layers[rank]:
                w,h,coords=blocks[ident];x,y=(along,across) if horizontal else (across,along)
                for nid,(nx,ny) in coords.items():positions[nid]=(x+nx,y+ny);members.append(nid)
                across+=(h if horizontal else w)+48;depth=max(depth,w if horizontal else h)
            layer_coords.append((members,max(0,across-48)))
            cross_max=max(cross_max,max(0,across-48));along+=depth+gap
        for members,size in layer_coords:
            shift=(cross_max-size)/2
            for nid in members:
                x,y=positions[nid];positions[nid]=(x,y+shift) if horizontal else (x+shift,y)
        width,height=(max(0,along-gap),cross_max) if horizontal else (cross_max,max(0,along-gap))
        if scope is not None:
            width=max(width,label_width(groups[scope]['label'],metrics)+48)
            positions={i:(x+padding,y+54+padding) for i,(x,y) in positions.items()};width+=2*padding;height+=54+2*padding
        return width,height,positions
    _,_,positions=pack(None)
    return {i:{'node_id':i,'x_pt':x+24,'y_pt':y+24} for i,(x,y) in positions.items()}
