"""Present recorded results without recomputing quality gates or exit codes."""

LABELS = {'failed':'生成・検証失敗', 'review':'要確認',
          'passed':'機械検査合格（目視確認が必要）', 'unknown':'結果未確認'}


def view_presentation(record):
    quality = record.get('operational_quality', {})
    if record.get('status') == 'failed' or record.get('exit_code', 0) != 0:
        state = 'failed'
    elif record.get('status') == 'passed' and record.get('exit_code') == 0:
        state = {'passed':'passed', 'needs-review-or-split':'review'}.get(quality.get('status'), 'unknown')
    else:
        state = 'unknown'
    issues = []
    for field, kind in (('errors','エラー'), ('warnings','警告')):
        for issue in record.get(field, []):
            issues.append({'kind':kind, 'code':issue.get('code',''),
                           'element_ids':issue.get('element_ids',[]), 'message':issue.get('message','')})
    # Use the recorded gate: do not repeat its warning allowlist or thresholds.
    known = {i['code'] for i in issues}
    for code in quality.get('blocking_warnings', []):
        if code not in known:
            issues.append({'kind':'警告','code':code,'element_ids':[],'message':''})
    display = quality.get('display_quality', record.get('display_quality', {}))
    if display.get('status') == 'needs-split':
        issues.append({'kind':'表示品質','code':'needs-split','element_ids':[],
                       'message':'指定表示サイズで文字が不足しています。図の分割を確認してください。'})
    return {'state':state, 'label':LABELS[state], 'issues':issues}


def project_presentation(report):
    views = {key:dict(view_presentation(value), title=value.get('title',key))
             for key,value in report.get('views',{}).items()}
    states = {v['state'] for v in views.values()}
    if report.get('errors') or 'failed' in states:
        state = 'failed'
    elif 'review' in states:
        state = 'review'
    elif not states or 'unknown' in states or report.get('status') != 'passed':
        state = 'unknown'
    else:
        state = 'passed'
    return {'state':state, 'label':LABELS[state], 'views':views, 'errors':report.get('errors',[])}
