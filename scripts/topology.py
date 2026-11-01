from service_labels import display_label
"""Explicit, opt-in warm-standby topology contracts. Never infer cloud resources."""
from schema import fail, object_keys

def directed_connections(edges):
    """Yield actual traversal directions, leaving the declared edges unchanged."""
    for edge in edges:
        if edge['direction']=='none':continue
        yield edge,edge['source'],edge['target']
        if edge['direction']=='both':yield edge,edge['target'],edge['source']

def validate_availability(a):
    spec=a['availability'];object_keys(spec,('strategy','regions','aurora_clusters','replication_assets'),('strategy','regions','aurora_clusters','replication_assets'))
    if spec['strategy']!='warm-standby':fail('E_AVAILABILITY_STRATEGY','Only explicit warm-standby contracts are currently supported')
    nodes={n['id']:n for n in a['nodes']};groups={g['id']:g for g in a['groups']}
    connections=list(directed_connections(a['edges']))
    def ancestor(n,kind):
        gid=nodes[n].get('group_id')
        while gid:
            if groups[gid]['type']==kind:return gid
            gid=groups[gid].get('parent_id')
        return None
    def refs(values):
        if not isinstance(values,list) or not values or any(not isinstance(n,str) or n not in nodes for n in values) or len(set(values))!=len(values):fail('E_AVAILABILITY_REFERENCE','Expected distinct existing node IDs')
        return values
    regions=spec['regions']
    if not isinstance(regions,list) or len(regions)!=2:fail('E_MULTI_REGION','Warm standby needs two declared regions')
    declared={};roles=[]
    for region in regions:
        object_keys(region,('group_id','role','entry_nodes','regional_nodes'),('group_id','role','entry_nodes','regional_nodes'))
        gid=region['group_id'];role=region['role']
        if not isinstance(gid,str) or gid not in groups or groups[gid]['type']!='group.region' or gid in declared or role not in ('primary','standby'):fail('E_MULTI_REGION','Invalid or duplicate region declaration')
        roles.append(role);declared[gid]=region
        for n in refs(region['regional_nodes'])+refs(region['entry_nodes']):
            if ancestor(n,'group.region')!=gid:fail('E_REGION_MEMBERSHIP','Declared service belongs to another region',[n,gid])
        if not set(region['entry_nodes'])<=set(region['regional_nodes']):fail('E_AVAILABILITY_REFERENCE','Entries must be included in regional nodes',[gid])
        apps=[n for n in region['regional_nodes'] if nodes[n]['asset_id']=='aws4.fargate']
        if len({ancestor(n,'group.availability-zone') for n in apps if ancestor(n,'group.availability-zone')})<2:fail('E_APP_MULTI_AZ','Each region needs Fargate in at least two AZs',[gid])
        for n in region['entry_nodes']:
            purpose='traffic' if role=='primary' else 'failover'
            if not any(target==n and ancestor(source,'group.region') is None and e.get('purpose','traffic')==purpose for e,source,target in connections):fail('E_REGION_ENTRY','Missing normal or conditional failover entry',[n])
    if sorted(roles)!=['primary','standby']:fail('E_MULTI_REGION','Expected one primary and one standby')
    # Symmetric service presence is necessary, but it does not prove working DR.
    asset_sets=[{nodes[n]['asset_id'] for n in r['regional_nodes']} for r in regions]
    if asset_sets[0]!=asset_sets[1]:fail('E_REGION_SERVICE_PARITY','Declared regional service types differ')
    clusters=spec['aurora_clusters']
    if not isinstance(clusters,list) or len(clusters)!=2:fail('E_DB_MULTI_REGION','Expected one Aurora cluster declaration per region')
    cluster_regions=set();db_seen=set();cluster_units=set()
    for c in clusters:
        object_keys(c,('region_id','writer','readers','cluster_node'),('region_id','writer','readers'))
        gid=c['region_id']
        if not isinstance(gid,str) or gid not in declared or gid in cluster_regions:fail('E_DB_MULTI_REGION','Duplicate or unknown cluster region')
        unit=c.get('cluster_node')
        if unit is not None:
            if not isinstance(unit,str) or unit not in nodes or nodes[unit]['asset_id']!='aws4.aurora' or ancestor(unit,'group.region')!=gid or nodes[unit].get('group_id')!=gid or unit in cluster_units:fail('E_DB_CLUSTER_UNIT','Logical cluster must belong directly to its declared region')
            cluster_units.add(unit)
        cluster_regions.add(gid);members=refs(c['readers']);writer=c['writer']
        if declared[gid]['role']=='primary':
            if not isinstance(writer,str) or writer not in nodes:fail('E_DB_ROLE','Primary requires one writer')
            members=members+[writer]
        elif writer is not None:fail('E_DB_ROLE','Standby must not have a writer before promotion')
        if len(set(members))!=len(members) or set(members)&db_seen:fail('E_DB_ROLE','DB roles overlap')
        db_seen.update(members)
        azs=set()
        for n in members:
            az=ancestor(n,'group.availability-zone')
            if nodes[n]['asset_id']!='aws4.aurora' or ancestor(n,'group.region')!=gid or not az or groups[nodes[n].get('group_id')]['type']!='group.private-subnet':fail('E_DB_PLACEMENT','Aurora instances require private subnets in declared AZs',[n])
            azs.add(az)
        if len(azs)<2:fail('E_DB_MULTI_AZ','DB compute roles require at least two different AZs',[gid])
        if not set(members)<=set(declared[gid]['regional_nodes']):fail('E_AVAILABILITY_REFERENCE','DB instances must be declared regional nodes',[gid])
    actual={n['id'] for n in a['nodes'] if n['asset_id']=='aws4.aurora' and ancestor(n['id'],'group.region') in declared}
    if actual-cluster_units!=db_seen:fail('E_DB_ROLE','Every depicted Aurora instance in declared regions needs a cluster role')
    if cluster_units:
        if len(cluster_units)!=2:fail('E_DB_CLUSTER_UNIT','Both regions must declare logical cluster units')
        if any(e.get('purpose')=='replication' and nodes[e['source']]['asset_id']=='aws4.aurora' and (e['source'] not in cluster_units or e['target'] not in cluster_units) for e in a['edges']):fail('E_DB_CLUSTER_UNIT','Aurora replication must attach to logical clusters')
    for c in clusters:
        for n in c['readers']:
            if 'reader' not in display_label(nodes[n]).lower():fail('E_DB_ROLE_LABEL','Reader caption must identify its role',[n])
        if c['writer'] and 'writer' not in display_label(nodes[c['writer']]).lower():fail('E_DB_ROLE_LABEL','Writer caption must identify its role',[c['writer']])
    assets=spec['replication_assets']
    if not isinstance(assets,list) or not assets or len(set(x for x in assets if isinstance(x,str)))!=len(assets):fail('E_AVAILABILITY_REFERENCE','Distinct replication asset IDs required')
    for asset in assets:
        if not isinstance(asset,str) or any(asset not in s for s in asset_sets):fail('E_REPLICATION','Replication asset absent in a region')
        if not any(e.get('purpose')=='replication' and nodes[e['source']]['asset_id']==asset and nodes[e['target']]['asset_id']==asset and ancestor(e['source'],'group.region') in declared and ancestor(e['target'],'group.region') in declared and ancestor(e['source'],'group.region')!=ancestor(e['target'],'group.region') for e in a['edges']):fail('E_REPLICATION','Missing declared cross-region replication',[asset])
    for asset in ('aws4.aurora','aws4.s3','aws4.dynamodb'):
        if asset not in assets:continue
        matching=[e for e in a['edges'] if e.get('purpose')=='replication' and nodes[e['source']]['asset_id']==asset and nodes[e['target']]['asset_id']==asset and ancestor(e['source'],'group.region')!=ancestor(e['target'],'group.region')]
        if asset=='aws4.dynamodb':
            valid=any(e['direction']=='both' for e in matching)
        else:
            valid=any(declared.get(ancestor(e['source'],'group.region'),{}).get('role')=='primary' and declared.get(ancestor(e['target'],'group.region'),{}).get('role')=='standby' and e['direction']=='forward' for e in matching)
        if not valid:fail('E_REPLICATION_DIRECTION','Declared warm-standby replication has the wrong direction',[asset])
    for r in regions:
        alb=[n for n in r['entry_nodes'] if nodes[n]['asset_id']=='aws4.application_load_balancer']
        connected={target for e,source,target in connections if source in alb and nodes[target]['asset_id']=='aws4.fargate' and ancestor(target,'group.region')==r['group_id'] and e.get('purpose','traffic')==('traffic' if r['role']=='primary' else 'failover')}
        if len({ancestor(n,'group.availability-zone') for n in connected if ancestor(n,'group.availability-zone')})<2:fail('E_APP_ENTRY','ALB must connect to application instances in two AZs',[r['group_id']])
    # Verify user data paths rather than mistaking DNS selection for API traffic.
    frontend_clients={source for e,source,target in connections if nodes[target]['asset_id']=='aws4.cloudfront' and nodes[source]['asset_id'] in ('aws4.user','aws4.users','aws4.client') and e.get('purpose','traffic')=='traffic'}
    identities={nodes[n].get('logical_id') for n in frontend_clients}-{None}
    frontend_clients.update(n['id'] for n in nodes.values() if n.get('logical_id') in identities)
    has_frontend=any(n['asset_id']=='aws4.cloudfront' for n in nodes.values())
    for r in regions:
        purpose='traffic' if r['role']=='primary' else 'failover'
        for n in r['entry_nodes']:
            if nodes[n]['asset_id']!='aws4.application_load_balancer':continue
            if any(n in (e['source'],e['target']) and any(nodes[end]['asset_id']=='aws4.route_53' for end in (e['source'],e['target'])) and e.get('purpose','traffic') in ('traffic','failover') for e in a['edges']):fail('E_DNS_DATA_PATH','Route 53 does not proxy API data',[n])
            if has_frontend:
                adjacency={}
                for e,source,target in connections:
                    if e.get('purpose','traffic') not in (('traffic',) if r['role']=='primary' else ('traffic','failover')) or nodes[source]['asset_id']=='aws4.route_53' or nodes[target]['asset_id']=='aws4.route_53':continue
                    adjacency.setdefault(source,set()).add(target)
                seen=set(frontend_clients);pending=list(seen)
                while pending:
                    for target in adjacency.get(pending.pop(),()):
                        if target not in seen:seen.add(target);pending.append(target)
                if n not in seen:fail('E_FRONTEND_API_PATH','SPA browser cannot reach regional API in the declared traffic graph',[n])
    for r in regions:
        allowed=('traffic',) if r['role']=='primary' else ('traffic','failover')
        for node in r['regional_nodes']:
            if nodes[node]['asset_id']!='aws4.sqs':continue
            if not any(e.get('purpose','traffic') in allowed and target==node for e,source,target in connections):fail('E_QUEUE_PRODUCER_PATH','Queue needs a producer path, not only a consumer connection',[node])
    for c in clusters:
        for db in c['readers']+([c['writer']] if c['writer'] else []):
            purpose='traffic' if declared[c['region_id']]['role']=='primary' else 'failover'
            if not any(target==db and nodes[source]['asset_id']=='aws4.fargate' and ancestor(source,'group.region')==c['region_id'] and e.get('purpose','traffic') in (purpose,'failover') for e,source,target in connections):fail('E_DB_CLIENT_PATH','Depicted DB instance needs a client read/write or explicit failover path',[db])
    for e,source,target in connections:
        if e.get('purpose','traffic')=='traffic' and target in db_seen:
            standby=next((r['group_id'] for r in regions if r['role']=='standby'),None)
            if ancestor(target,'group.region')==standby:fail('E_STANDBY_WRITE_PATH','Standby DB connection must be conditional failover in this contract',[e['id']])
    return {'strategy':'warm-standby','regions':2,'aurora_clusters':2,'status':'passed','scope':'Declared topology only; no AWS runtime validation'}
