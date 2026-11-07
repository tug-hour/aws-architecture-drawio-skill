"""Apply explicit operations to an expanded drawing without mutating its source."""
import copy

from drawing import author_document
from input_common import fail, object_keys
from parts import add_part, copy_part, move_part


def _affected(elements, ident):
    descendants = {ident}
    while True:
        expanded = descendants | {key for key, item in elements.items() if item.get('parent') in descendants}
        if expanded == descendants:
            break
        descendants = expanded
    return [key for key, item in elements.items() if 'source' in item and
            (key == ident or item.get('source') in descendants or item.get('target') in descendants
             or item.get('parent', '1') in descendants)]


def apply_operations(source, operations, *, validate=True):
    if not isinstance(operations, list):
        fail('E_SCHEMA', 'operations must be an array')
    current = copy.deepcopy(source)
    results = []
    for op in operations:
        if not isinstance(op, dict):
            fail('E_SCHEMA', 'Each operation must be an object')
        action = op.get('op')
        if action == 'add':
            object_keys(op, ('op', 'id', 'at', 'asset', 'shape', 'name', 'role', 'parent', 'kind', 'color', 'theme', 'size'), ('op', 'id', 'at'))
            current, result = add_part(current, op['id'], **{k: v for k, v in op.items() if k not in ('op', 'id')})
        elif action in ('copy', 'move'):
            allowed = ('op', 'roots', 'offset', 'parent', 'prefix') if action == 'copy' else ('op', 'roots', 'offset', 'parent')
            required = ('op', 'roots', 'prefix') if action == 'copy' else ('op', 'roots')
            object_keys(op, allowed, required)
            fn = copy_part if action == 'copy' else move_part
            current, result = fn(current, op['roots'], **{k: v for k, v in op.items() if k not in ('op', 'roots')})
        elif action in ('put', 'remove'):
            object_keys(op, ('op', 'id', 'element') if action == 'put' else ('op', 'id'),
                        ('op', 'id', 'element') if action == 'put' else ('op', 'id'))
            ident = op['id']
            elements = current.get('elements', {})
            affected = _affected(elements, ident)
            if action == 'put':
                if ident in elements or ident in ('0', '1') or not isinstance(ident, str) or not ident:
                    fail('E_DUPLICATE_ID', 'Element ID already exists or is reserved', [ident])
                if not isinstance(op['element'], dict):
                    fail('E_SCHEMA', 'element must be an object', [ident])
                elements[ident] = copy.deepcopy(op['element'])
            else:
                if ident not in elements:
                    fail('E_SCHEMA', 'Unknown element', [ident])
                del elements[ident]
            result = {'ids': {ident: ident}, 'affected_edges': list(dict.fromkeys(affected + _affected(elements, ident)))}
        elif action == 'set':
            object_keys(op, ('op', 'id', 'fields'), ('op', 'id', 'fields'))
            ident = op['id']
            elements = current.get('elements', {})
            if ident not in elements:
                fail('E_SCHEMA', 'Unknown element', [ident])
            if not isinstance(op['fields'], dict):
                fail('E_SCHEMA', 'fields must be an object', [ident])
            elements[ident].update(copy.deepcopy(op['fields']))
            affected = _affected(elements, ident)
            result = {'ids': {ident: ident}, 'affected_edges': affected}
        else:
            fail('E_SCHEMA', 'Unknown operation')
        results.append({'op': action, **result})
    if validate:
        author_document(current)
    return current, results
