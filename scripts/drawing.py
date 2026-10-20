"""Explicit JSON-to-draw.io adapter and shared XML authoring primitives."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
import xml.etree.ElementTree as ET

from schema import fail, finite, loads, object_keys
from version import get_version


def document(ident, name, settings):
    doc = ET.Element('mxfile', host='Electron', version='32.4.1', compressed='false')
    page = ET.SubElement(doc, 'diagram', id=ident, name=name)
    model = ET.SubElement(page, 'mxGraphModel', **settings)
    root = ET.SubElement(model, 'root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    return doc, root


def vertex(root, ident, parent, style, bounds, text='', connectable='0', scale=1):
    cell = ET.SubElement(root, 'mxCell', id=ident, parent=parent, vertex='1',
                         connectable=connectable, value=text, style=style)
    ET.SubElement(cell, 'mxGeometry', attrib={
        **{key: str(value * scale) for key, value in zip(('x', 'y', 'width', 'height'), bounds)},
        'as': 'geometry',
    })
    return cell


def edge(root, ident, parent, style, source, target, points, text='', scale=1):
    cell = ET.SubElement(root, 'mxCell', id=ident, parent=parent, edge='1',
                         source=source, target=target, value=text, style=style)
    geometry = ET.SubElement(cell, 'mxGeometry', relative='1', attrib={'as': 'geometry'})
    array = ET.SubElement(geometry, 'Array', attrib={'as': 'points'})
    for x, y in points:
        ET.SubElement(array, 'mxPoint', x=str(x * scale), y=str(y * scale))
    return cell


def _style(values):
    if not isinstance(values, dict):
        fail('E_SCHEMA', 'Style must be an object')
    for key, value in values.items():
        if not key or any(c in key for c in ';='):
            fail('E_SCHEMA', 'Invalid style key')
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float))):
            fail('E_SCHEMA', 'Style value must be text, number or null')
        if isinstance(value, (int, float)):
            finite(value)
        if isinstance(value, str) and ';' in value:
            fail('E_SCHEMA', 'Use separate keys for style properties')
    return ''.join(key + ('' if value is None else '=' + str(value)) + ';'
                   for key, value in values.items())


def _coordinates(values, size):
    if not isinstance(values, list) or len(values) != size:
        fail('E_SCHEMA', 'Expected %d coordinates' % size)
    for value in values:
        finite(value)
    return values


def author_document(source):
    """Serialize fixed px geometry without layout, catalog gating or route changes."""
    object_keys(source, ('format', 'page', 'styles', 'elements'), ('format', 'elements'))
    if source['format'] != 'drawio/1':
        fail('E_VERSION', 'Unsupported drawing format')
    elements = source['elements']
    styles = source.get('styles', {})
    if not isinstance(elements, dict) or not isinstance(styles, dict):
        fail('E_SCHEMA', 'elements and styles must be objects keyed by stable IDs')
    for values in styles.values():
        _style(values)
    page = source.get('page', {})
    object_keys(page, ('id', 'name', 'model'))
    settings = dict(grid='0', page='0', background='#FFFFFF')
    model = page.get('model', {})
    if not isinstance(model, dict) or any(not isinstance(v, (str, int, float)) for v in model.values()):
        fail('E_SCHEMA', 'page.model must contain scalar settings')
    settings.update({key: str(value) for key, value in model.items()})
    settings['adaptiveColors'] = 'none'
    doc, root = document(page.get('id', 'drawing'), page.get('name', 'Architecture'), settings)
    for ident, item in elements.items():
        if not ident or ident in ('0', '1'):
            fail('E_SCHEMA', 'Element ID is empty or reserved')
        object_keys(item, ('parent', 'bounds', 'style', 'overrides', 'value', 'connectable',
                           'source', 'target', 'source_port', 'target_port', 'waypoints'))
        parent = item.get('parent', '1')
        if parent != '1' and (parent not in elements or 'source' in elements[parent]):
            fail('E_SCHEMA', 'Unknown or edge parent', [ident])
        seen = {ident}
        while parent != '1':
            if parent in seen:
                fail('E_SCHEMA', 'Cyclic parent', [ident])
            seen.add(parent)
            if parent not in elements:
                fail('E_SCHEMA', 'Unknown ancestor', [ident])
            parent = elements[parent].get('parent', '1')
        base = item.get('style')
        if base is not None and base not in styles:
            fail('E_SCHEMA', 'Unknown style', [ident])
        overrides = item.get('overrides', {})
        _style(overrides)
        values = {**styles.get(base, {}), **overrides}
        text = item.get('value', '')
        if not isinstance(text, str):
            fail('E_SCHEMA', 'value must be text', [ident])
        parent = item.get('parent', '1')
        if 'source' in item or 'target' in item:
            if 'bounds' in item or 'connectable' in item:
                fail('E_SCHEMA', 'Edge cannot have vertex geometry', [ident])
            for endpoint in ('source', 'target'):
                target = item.get(endpoint)
                if target not in elements or 'source' in elements[target] or 'target' in elements[target]:
                    fail('E_SCHEMA', 'Unknown or non-vertex endpoint', [ident])
            for field, prefix in (('source_port', 'exit'), ('target_port', 'entry')):
                if field in item:
                    if any(prefix + suffix in values for suffix in ('X', 'Y', 'Perimeter')):
                        fail('E_SCHEMA', 'Define ports once, outside styles', [ident])
                    x, y = _coordinates(item[field], 2)
                    values.update({prefix + 'X': x, prefix + 'Y': y, prefix + 'Perimeter': 0})
            points = item.get('waypoints', [])
            if not isinstance(points, list):
                fail('E_SCHEMA', 'waypoints must be an array', [ident])
            for point in points:
                _coordinates(point, 2)
            edge(root, ident, parent, _style(values), item['source'], item['target'], points, text)
        else:
            if any(key in item for key in ('source_port', 'target_port', 'waypoints')):
                fail('E_SCHEMA', 'Route fields require an edge', [ident])
            bounds = _coordinates(item.get('bounds'), 4)
            if bounds[2] < 0 or bounds[3] < 0:
                fail('E_SCHEMA', 'Negative dimensions', [ident])
            connectable = item.get('connectable', True)
            if not isinstance(connectable, bool):
                fail('E_SCHEMA', 'connectable must be boolean', [ident])
            vertex(root, ident, parent, _style(values), bounds, text, '1' if connectable else '0')
    xml = ET.tostring(doc, encoding='unicode', xml_declaration=True)
    try:
        ET.fromstring(xml)
    except (ET.ParseError, UnicodeError):
        fail('E_SCHEMA', 'Input contains XML-incompatible text or attributes')
    return xml


def generate(path, output):
    """Write a new source/output pair; no browser, export, layout or optional QA."""
    start = time.perf_counter()
    path, output = Path(path), Path(output)
    if output.exists():
        fail('E_OUTPUT_EXISTS', 'Output path already exists')
    data = path.read_bytes()
    xml = author_document(loads(data))
    report = {
        'status': 'authored', 'candidate_version': get_version(),
        'source_sha256': hashlib.sha256(data).hexdigest(),
        'artifacts': ['architecture.json', 'diagram.drawio'],
        'output': str(output.resolve()), 'rendered': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.drawing-', dir=output.parent) as temporary:
        prepared = Path(temporary) / 'prepared'
        prepared.mkdir()
        (prepared / 'architecture.json').write_bytes(data)
        (prepared / 'diagram.drawio').write_text(xml, encoding='utf-8')
        report['seconds'] = round(time.perf_counter() - start, 6)
        (prepared / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            fail('E_OUTPUT_EXISTS', 'Output appeared during generation')
        prepared.rename(output)
    return report, 0
