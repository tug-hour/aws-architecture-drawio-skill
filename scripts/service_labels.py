"""Bind service captions to catalog identities and emit source-backed definitions."""
import json
import re
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[1] / 'references/service-names.json'

def policy():
    return json.loads(POLICY_PATH.read_text())

def display_label(node):
    return node['label'] + ('\n' + node['description'] if node.get('description') else '')

def name_failure(node, code, message, fail, names=None):
    """Attach reviewable migration guidance without changing or accepting input."""
    if names is None:
        names = policy()['services'].get(node['asset_id'], {}).get('allowed_names', [])
    guidance = {
        'field': 'label', 'asset_id': node['asset_id'], 'input_label': node['label'],
        'allowed_names': list(names), 'existing_description': node.get('description'),
        'automatic': False,
        'instructions': 'labelにはこのアイコンの許可名だけを指定し、用途・Writer/Reader・昇格条件はdescriptionへ移してください。既存descriptionも保持し、1行・120文字以内にしてください。名前とアイコンが異なる場合は意図したサービスを確認してください。',
    }
    joined = ' '.join(node['label'].split('\n'))
    for name in sorted(names, key=len, reverse=True):
        if joined == name:
            guidance['suggested_fields'] = {'label': name}
            break
        # Suggest a split only for an approved name followed by an explicit separator.
        if joined.startswith(name) and joined[len(name):len(name)+1] in (' ', '・', ':', '：'):
            purpose = joined[len(name):].lstrip(' ・:：')
            description = ' / '.join(x for x in (purpose, node.get('description')) if x)
            if purpose and '\n' not in description and len(description) <= 120:
                guidance['suggested_fields'] = {'label': name, 'description': description}
            break
    fail(code, message + ' 詳細はdetails.migrationを確認してください。', [node['id']],
         details={'migration': guidance})


_AZ_NAME = re.compile(r'(?<![A-Za-z0-9_-])AZ-[A-Za-z0-9]+(?![A-Za-z0-9_-])')

def single_az_name(text):
    """Read one explicit AZ token, excluding compact lists and inferred aliases."""
    matches = list(_AZ_NAME.finditer(text))
    mentions = {match.group() for match in matches}
    if len(mentions) != 1:
        return None
    def suffix_shape(value):
        return re.sub(r'[0-9]+', '#', re.sub(r'[A-Za-z]', 'a', value))
    for match in matches:
        tail = re.match(r'\s*[/／,，、]\s*([A-Za-z0-9]+)(?![A-Za-z0-9_-])', text[match.end():])
        # AZ-A/C and AZ-1/22 are lists; AZ-A / 主系 or / primary are context.
        # Compare spelling structure only; never infer a second AZ identity.
        if tail and suffix_shape(tail.group(1)) == suffix_shape(match.group()[3:]):
            return None
    return next(iter(mentions))

def az_label_warnings(a):
    """Review explicit AZ mentions against one unambiguous containment ancestor."""
    groups = {g['id']: g for g in a['groups']}
    warnings = []
    for node in a['nodes']:
        ancestors = []
        group = groups.get(node.get('group_id'))
        while group is not None:
            if group['type'] == 'group.availability-zone':
                ancestors.append(group)
            group = groups.get(group.get('parent_id'))
        if len(ancestors) != 1:
            continue
        frame = ancestors[0]
        frame_az = single_az_name(frame['label'])
        if frame_az is None:
            continue
        mention = single_az_name(display_label(node))
        if mention is None:
            continue
        code = 'W_AZ_LABEL_REDUNDANT' if mention == frame_az else 'W_AZ_LABEL_MISMATCH'
        message = ('AZ枠と同じAZ名への言及があります。所属だけを表す重複なら省略し、役割・条件の説明は保持してください。'
                   if mention == frame_az else
                   'AZ枠と異なるAZ名への言及があります。所属表記か、接続先・切替条件の説明かを確認してください。')
        warnings.append({'code': code, 'message': message, 'element_ids': [node['id'], frame['id']],
                         'details': {'frame_az': frame_az, 'mentioned_az': mention,
                                     'fields': [key for key in ('label', 'description')
                                                if mention in _AZ_NAME.findall(node.get(key, ''))]}})
    return warnings

def validate_names(a, m, fail):
    rules = policy()
    for n in a['nodes']:
        if m['assets'][n['asset_id']]['role'] != 'service':
            continue
        names = rules['services'].get(n['asset_id'])
        if not names:
            fail('E_SERVICE_NAME_UNVERIFIED', 'Service name policy is unavailable; add a source-backed policy', [n['id']])
        lines = n['label'].split('\n')
        # Joining with a space cannot reassemble a word broken across two lines.
        if len(lines) > 2 or any(x != x.strip() or x in ('AWS', 'Amazon') for x in lines):
            name_failure(n, 'E_SERVICE_LABEL', 'Use at most two lines; keep AWS/Amazon with the first service word', fail, names['allowed_names'])
        if ' '.join(lines) not in names['allowed_names']:
            name_failure(n, 'E_SERVICE_NAME', 'Caption must match this icon\'s approved service name at word boundaries; put purpose text in description', fail, names['allowed_names'])

def prepare_glossary(a, m, fail):
    rules = policy()
    known = {k: v for k, v in rules['services'].items() if v.get('short_name')}
    entries = []
    used = set()
    for entry in a['glossary']:
        ident = entry['asset_id']
        item = known.get(ident)
        if entry.get('kind') == 'note':
            if entry['short_name'] in {v['short_name'] for v in known.values()} or any(re.fullmatch(re.escape(t),entry['short_name']) for v in known.values() for t in v.get('tokens', [])):
                fail('E_GLOSSARY_NAME', 'A service abbreviation cannot be disguised as a note', [ident])
            entries.append(entry)
            continue
        if not item or entry['short_name'] != item['short_name'] or entry['full_name'] != item['full_name']:
            fail('E_GLOSSARY_NAME', 'Definition must match the source-backed name policy', [ident])
        if entry['short_name'] in used:
            fail('E_GLOSSARY', 'Duplicate abbreviation')
        used.add(entry['short_name']); entries.append(entry)
    # Include service abbreviations used in descriptions, group headings and wires,
    # even when that service has no separate icon in this view (for example ECS).
    outside_nodes = [g['label'] for g in a['groups']] + [e.get('label', '') for e in a['edges']] + [g[key] for g in entries if g.get('kind')=='note' for key in ('short_name','full_name')]
    for ident, item in sorted(known.items()):
        # A full service caption precedes its own description. Other nodes,
        # headings and wires have no guaranteed reading order in a diagram.
        text = '\n'.join(outside_nodes + [display_label(n) for n in a['nodes']
                        if not (n['asset_id'] == ident and ' '.join(n['label'].split('\n')) == item['full_name'])])
        tokens = item.get('tokens', [item['short_name']])
        if any(re.search(r'(?<![A-Za-z0-9])' + re.escape(t) + r'(?![A-Za-z0-9])', text) for t in tokens):
            if item['short_name'] not in used:
                entries.append({'asset_id': ident, 'short_name': item['short_name'], 'full_name': item['full_name']})
                used.add(item['short_name'])
    a['glossary'] = [e for e in entries if e.get('kind')!='note'] + [e for e in entries if e.get('kind')=='note']
