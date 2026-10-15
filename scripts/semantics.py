"""Declared application-flow contracts, independent of AWS service blueprints.
No resources or missing connections are inferred. Paths preserve phase and direction.
"""
from schema import fail, object_keys, valid_text

def validate_semantics(a):
    spec=a.get('semantics')
    if spec is None:return {'status':'not-declared','scope':'No application flow contract'}
    object_keys(spec,('flows','standby_nodes','required_edges'),('flows',))
    nodes={n['id']:n for n in a['nodes']};edges={e['id']:e for e in a['edges']}
    flows=spec['flows']
    if not isinstance(flows,list) or not flows or len(flows)>200:fail('E_FLOW_SCHEMA','Declare 1..200 critical flows')
    standby=spec.get('standby_nodes',[])
    if not isinstance(standby,list) or any(not isinstance(n,str) or n not in nodes for n in standby) or len(set(standby))!=len(standby):fail('E_FLOW_REFERENCE','Invalid standby nodes')
    for e in a['edges']:
        if e.get('purpose','traffic')=='traffic' and (e['source'] in standby or e['target'] in standby):fail('E_STANDBY_TRAFFIC','Standby application traffic requires failover purpose',[e['id']])
        if e.get('purpose','traffic') in ('traffic','failover') and any(nodes[n]['asset_id']=='aws4.route_53' for n in (e['source'],e['target'])):fail('E_DNS_DATA_PATH','DNS must be an association, not application traffic',[e['id']])
    requirements=spec.get('required_edges',[])
    if not isinstance(requirements,list):fail('E_FLOW_SCHEMA','required_edges must be a list')
    for r in requirements:
        object_keys(r,('id','source','target','purpose','direction'),('id','source','target','purpose','direction'))
        if any(not isinstance(r[k],str) for k in ('id','source','target','purpose','direction')) or r['source'] not in nodes or r['target'] not in nodes or r['purpose'] not in ('traffic','failover','replication','association') or r['direction'] not in ('forward','both','none'):fail('E_FLOW_SCHEMA','Invalid required connection')
        if r['id'] not in edges or any(edges[r['id']].get(k,'traffic' if k=='purpose' else 'forward')!=r[k] for k in ('source','target','purpose','direction')):fail('E_REQUIRED_CONNECTION','Required connection is missing or changed',[r['id']])
    seen=set();results=[]
    for f in flows:
        object_keys(f,('id','kind','phase','path'),('id','kind','phase','path'))
        valid_text(f['id'],'flow')
        if f['id'] in seen:fail('E_FLOW_SCHEMA','Duplicate flow ID',[f['id']])
        seen.add(f['id'])
        if f['kind'] not in ('web','serverless','async','realtime','dr','monitoring','custom') or f['phase'] not in ('normal','failover','replication'):fail('E_FLOW_SCHEMA','Unknown flow kind or phase',[f['id']])
        path=f['path']
        if not isinstance(path,list) or len(path)<2 or len(path)>200 or any(not isinstance(n,str) or n not in nodes for n in path):fail('E_FLOW_REFERENCE','Flow path must reference existing nodes',[f['id']])
        allowed={'normal':{'traffic'},'failover':{'traffic','failover'},'replication':{'replication'}}[f['phase']]
        adj={n:set() for n in nodes}
        for e in edges.values():
            if e.get('purpose','traffic') not in allowed or e['direction']=='none':continue
            adj[e['source']].add(e['target'])
            if e['direction']=='both':adj[e['target']].add(e['source'])
        # Require one continuous walk visiting the stages in order. Reaching each
        # pair separately could accept branch-only paths or reversed via stages.
        start=(path[0],1);queue=[start];visited={start};complete=False
        while queue:
            n,index=queue.pop()
            if index==len(path):complete=True;break
            for target in adj[n]:
                # A later mandatory stage may not be traversed before the next.
                if target in path[index+1:] and target!=path[index]:continue
                state=(target,index+1 if target==path[index] else index)
                if state not in visited:visited.add(state);queue.append(state)
        if not complete:fail('E_FLOW_PATH','Missing directed application path in declared phase',[f['id']])
        results.append({'id':f['id'],'kind':f['kind'],'phase':f['phase'],'status':'passed'})
    return {'status':'passed','flows':results,'scope':'Declared critical paths; AWS configuration is not validated'}
