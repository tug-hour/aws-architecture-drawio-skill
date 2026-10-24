"""Create and transform parts in expanded drawio/1 JSON without rerouting."""
import copy
import unicodedata

from input_common import fail, finite


def _elements(doc):
    if doc.get('format') != 'drawio/1' or not isinstance(doc.get('elements'), dict):
        fail('E_SCHEMA', 'Part operations require drawio/1 elements')
    return doc['elements']


def _origin(elements, ident):
    x = y = 0
    seen = set()
    while ident != '1':
        if ident in seen or ident not in elements or 'bounds' not in elements[ident]:
            fail('E_SCHEMA', 'Unknown or cyclic vertex parent', [ident])
        seen.add(ident)
        item = elements[ident]
        x += item['bounds'][0]
        y += item['bounds'][1]
        ident = item.get('parent', '1')
    return x, y


def _selection(elements, roots):
    roots = [roots] if isinstance(roots, str) else list(roots)
    if not roots or any(r not in elements or 'bounds' not in elements[r] for r in roots):
        fail('E_SCHEMA', 'Select existing vertex roots')
    requested = list(dict.fromkeys(roots))
    roots = set(requested)
    selected = set()
    top = []
    for ident, item in elements.items():
        if 'bounds' not in item:
            continue
        current = ident
        seen = set()
        while current != '1':
            if current in seen or current not in elements:
                fail('E_SCHEMA', 'Unknown or cyclic vertex parent', [ident])
            seen.add(current)
            if current in roots:
                selected.add(ident)
            current = elements[current].get('parent', '1')
        if ident in roots and not (seen - {ident}) & roots:
            top.append(ident)
    return selected, [ident for ident in requested if ident in top]


def _edges(elements, selected):
    internal, affected = [], []
    for ident, item in elements.items():
        if 'source' not in item:
            continue
        count = int(item['source'] in selected) + int(item['target'] in selected)
        if count == 2:
            internal.append(ident)
        elif count or item.get('parent', '1') in selected:
            affected.append(ident)
    return internal, affected


def _delta(offset):
    if len(offset) != 2:
        fail('E_SCHEMA', 'Offset requires two px coordinates')
    for n in offset:
        finite(n)
    return offset


def _points(item, old_origin, new_origin, offset=(0, 0)):
    if 'waypoints' in item:
        item['waypoints'] = [[x + old_origin[0] + offset[0] - new_origin[0],
                              y + old_origin[1] + offset[1] - new_origin[1]]
                             for x, y in item['waypoints']]


def _parents(elements, ident):
    result = []
    while ident != '1':
        ident = elements[ident].get('parent', '1')
        if ident in result:
            fail('E_SCHEMA', 'Cyclic parent', [ident])
        result.append(ident)
    return result


def copy_part(source, roots, *, prefix, target=None, parent=None, offset=(0, 0)):
    """Copy complete subtrees and internal edges; return (new JSON, ID/review map).

    Root positions are relative to the first selected root's parent, plus offset,
    in the destination parent. External edges are listed, never duplicated.
    Source and target dictionaries are not modified. Conflicts fail atomically.
    """
    original = _elements(source)
    destination = source if target is None else target
    selected, top = _selection(original, roots)
    internal, affected = _edges(original, selected)
    parent = (top and original[top[0]].get('parent', '1')) if parent is None else parent
    dest = _elements(destination)
    if parent != '1' and parent not in dest:
        fail('E_SCHEMA', 'Unknown destination parent', [parent])
    offset = _delta(offset)
    base = _origin(original, original[top[0]].get('parent', '1'))
    dest_origin = _origin(dest, parent)
    translation = (dest_origin[0] - base[0] + offset[0], dest_origin[1] - base[1] + offset[1])
    chosen = selected | set(internal)
    mapping = {ident: prefix + ident for ident in original if ident in chosen}
    if not prefix or any(v in dest or v in ('0', '1') for v in mapping.values()):
        fail('E_DUPLICATE_ID', 'Copy prefix conflicts with existing IDs')
    result = copy.deepcopy(destination)
    output = result['elements']
    styles = result.setdefault('styles', {})
    style_map = {}
    for ident in mapping:
        name = original[ident].get('style')
        if name is None or name in style_map:
            continue
        values = source.get('styles', {}).get(name)
        if values is None:
            fail('E_SCHEMA', 'Unknown source style', [ident])
        new_name = name
        if name in styles and styles[name] != values:
            new_name = prefix + name
            while new_name in styles and styles[new_name] != values:
                new_name = prefix + new_name
        styles.setdefault(new_name, copy.deepcopy(values))
        style_map[name] = new_name
    for ident, new_id in mapping.items():
        item = copy.deepcopy(original[ident])
        owner = item.get('parent', '1')
        item['parent'] = mapping.get(owner, parent)
        if item.get('style') in style_map:
            item['style'] = style_map[item['style']]
        if ident in top:
            absolute = _origin(original, ident)
            item['bounds'][:2] = [absolute[i] + translation[i] - dest_origin[i] for i in (0, 1)]
        if ident in internal:
            item['source'] = mapping[item['source']]
            item['target'] = mapping[item['target']]
            if owner not in selected:
                _points(item, _origin(original, owner), dest_origin, translation)
        output[new_id] = item
    return result, {'ids': mapping, 'affected_edges': affected}


def move_part(source, roots, *, offset=(0, 0), parent=None):
    """Translate selected subtrees in absolute px, optionally changing parent.

    Internal routes translate once. Boundary waypoints keep their absolute
    positions; their endpoints follow the moved vertices and need local review.
    """
    original = _elements(source)
    selected, top = _selection(original, roots)
    internal, affected = _edges(original, selected)
    offset = _delta(offset)
    if parent in selected:
        fail('E_SCHEMA', 'Cannot move a part under its own subtree', [parent])
    result = copy.deepcopy(source)
    output = result['elements']
    for ident in top:
        item = output[ident]
        owner = original[ident].get('parent', '1') if parent is None else parent
        destination = _origin(original, owner)
        absolute = _origin(original, ident)
        item['parent'] = owner
        item['bounds'][:2] = [absolute[i] + offset[i] - destination[i] for i in (0, 1)]
    for ident in internal + affected:
        item = output[ident]
        old_owner = original[ident].get('parent', '1')
        # Preserve a valid owner instead of creating unrelated JSON changes.
        common = [p for p in _parents(output, item['source']) if p in _parents(output, item['target'])]
        owner = old_owner if old_owner in common else common[0]
        item['parent'] = owner
        _points(item, _origin(original, old_owner), _origin(output, owner), offset if ident in internal else (0, 0))
    return result, {'ids': {ident: ident for ident in original if ident in selected or ident in internal},
                    'affected_edges': affected}


def _caption(text, x, y, width=250, align='center', color='#000000'):
    lines = str(text).split('\n')
    units = max((sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in line) for line in lines), default=0)
    actual_width = max(width, units * 8 + 16)
    if align == 'center':
        x += (width - actual_width) / 2
    return {'bounds': [x, y, actual_width, max(22, len(lines) * 22)],
            'value': text, 'connectable': False,
            'overrides': {'text': None, 'html': 0, 'whiteSpace': 'nowrap', 'overflow': 'visible',
                          'align': align, 'verticalAlign': 'top', 'spacing': 0, 'fontSize': 16,
                          'fontFamily': 'Arial,Arial Unicode MS', 'fontColor': color,
                          'strokeColor': 'none', 'fillColor': 'none'}}


def add_part(source, ident, *, at, asset=None, shape=None, name=None, role='',
             parent='1', kind=None, color=None, theme='light', size=None):
    """Create an expanded icon or frame; catalog values are optional presets.

    A standard shape absent from the catalog can be supplied with shape/color.
    No preset remains linked to the resulting JSON or is reapplied on build.
    """
    original = _elements(source)
    _origin(original, parent)
    x, y = _delta(at)
    preset = {}
    catalog = None
    if asset:
        from catalog import manifest
        catalog = manifest()
        asset = catalog.get('aliases', {}).get(asset, asset)
        preset = catalog['assets'].get(asset, catalog['groups'].get(asset, {}))
        if not preset and not shape:
            fail('E_SCHEMA', 'No preset found; supply explicit shape and appearance', [ident])
    is_frame = bool(preset.get('native_icon') is not None or asset in (catalog or {}).get('groups', {})) or kind == 'frame'
    kind = 'frame' if is_frame else (kind or preset.get('role', 'service'))
    fg = '#FFFFFF' if theme == 'dark' else '#000000'
    name = name if name is not None else preset.get('name', ident)
    if kind == 'service' and '\n' not in name and len(name) > 28:
        # Choose at most two lines at a word boundary, keeping the brand attached.
        words = name.split()
        breaks = range(2 if words[0] in ('AWS', 'Amazon') else 1, len(words))
        if breaks:
            split = min(breaks, key=lambda i: abs(len(' '.join(words[:i])) - len(' '.join(words[i:]))))
            name = ' '.join(words[:split]) + '\n' + ' '.join(words[split:])
    if size is None:
        size = (600, 400) if is_frame else (preset.get('width_pt', 60 if kind == 'service' else 36) * 4 / 3,
                                          preset.get('height_pt', 60 if kind == 'service' else 36) * 4 / 3)
    w, h = _delta(size)
    if min(w, h) < 0:
        fail('E_SCHEMA', 'Negative dimensions', [ident])
    color = color if color is not None else preset.get('color')
    if isinstance(color, dict):
        color = color.get(theme, fg)
    color = color or fg
    result = copy.deepcopy(source)
    output = result['elements']
    items = {}
    if is_frame:
        overlay = preset.get('role') == 'overlay'
        border = {'shape': 'rect', 'fillColor': 'none', 'strokeColor': color,
                  'strokeWidth': 1.6667, 'rounded': 0, 'container': int(not overlay),
                  'collapsible': 0, 'recursiveResize': 0}
        dash = preset.get('dash', 'solid')
        if dash != 'solid':
            border.update(dashed=1, dashPattern=' '.join(str(n) for n in catalog['dash_patterns'][dash]), fixDash=0)
        items[ident] = {'parent': parent, 'bounds': [x, y, w, h], 'overrides': border, 'connectable': False}
        icon = shape or preset.get('native_icon')
        if icon:
            cloud = asset == 'group.aws-cloud'
            icon_x = (w - 40) / 2 if overlay else 0
            items[ident + '.header-base'] = {'parent': ident, 'bounds': [icon_x, 0, 40, 40], 'connectable': False,
                                           'overrides': {'shape': 'rect', 'fillColor': '#FFFFFF', 'strokeColor': 'none'}}
            items[ident + '.glyph'] = {'parent': ident, 'bounds': [icon_x, 0, 40, 40], 'connectable': False,
                                      'overrides': {'shape': icon, 'fillColor': ('#232F3E' if theme == 'dark' else '#242F3E') if cloud else color,
                                                    'strokeColor': 'none', 'aspect': 'fixed'}}
        items[ident + '.name'] = (_caption(name, 0, 44, w, 'center', fg) if overlay
                                  else _caption(name, 46 if icon else 8, 4, max(0, w - 54), 'left', fg))
        items[ident + '.name']['parent'] = ident
    else:
        shape = shape or preset.get('shape')
        if not shape:
            fail('E_SCHEMA', 'Supply a native shape or catalog preset', [ident])
        items[ident] = {'parent': parent, 'bounds': [x, y, w, h], 'connectable': False,
                        'overrides': {'group': None, 'recursiveResize': 0}}
        items[ident + '.icon'] = {'parent': ident, 'bounds': [0, 0, w, h],
                                'overrides': {'shape': 'rect', 'fillColor': color if kind == 'service' else 'none',
                                              'strokeColor': 'none', 'perimeter': 'rectanglePerimeter'}}
        nw, nh = preset.get('native_width', 1), preset.get('native_height', 1)
        factor = min(w, h) * (0.7 if kind == 'service' else 1) / max(nw, nh)
        gw, gh = nw * factor, nh * factor
        glyph_color = '#FFFFFF' if kind == 'service' else preset.get('theme_colors', {}).get(theme, color)
        items[ident + '.glyph'] = {'parent': ident + '.icon', 'bounds': [(w - gw) / 2, (h - gh) / 2, gw, gh],
                                  'connectable': False, 'overrides': {'shape': shape, 'fillColor': glyph_color,
                                                                   'strokeColor': 'none', 'aspect': 'fixed', 'resizable': 0, 'rotatable': 0}}
        items[ident + '.name'] = _caption(name, (w - 250) / 2, h + 8, color=fg)
        items[ident + '.name']['parent'] = ident
        if role:
            bottom = h + 8 + items[ident + '.name']['bounds'][3] + 12
            items[ident + '.role'] = _caption(role, (w - 250) / 2, bottom, color=fg)
            items[ident + '.role']['parent'] = ident
    if set(items) & (set(output) | {'0', '1'}):
        fail('E_DUPLICATE_ID', 'Part IDs already exist', sorted(set(items) & set(output)))
    output.update(items)
    return result, {'ids': {key: key for key in items}, 'affected_edges': []}
