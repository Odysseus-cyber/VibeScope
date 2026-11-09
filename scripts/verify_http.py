#!/usr/bin/env python3
"""Exercise a running demo stack through its public HTTP interface."""
import argparse
import json
import time
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--base-url',default='http://127.0.0.1:5180')
args=parser.parse_args()
base=args.base_url.rstrip('/')+'/api/v1'

def request(path,data=None):
    req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=15) as response:
        raw=response.read()
        return json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw.decode('utf-8-sig')

assert request('/health')['status']=='ok'
assert request('/meta')['mode']=='demo','Use a demo stack; this test creates a report job'
counts=[]
for window in (7,30,90):
    result=request('/overview?window='+str(window))
    assert len(result['daily'])==window
    assert result['kpis']['tracked']>=60
    assert sum(row['count'] for row in result['categories'])==result['kpis']['eligible']
    counts.append(result['kpis']['tracked'])
assert len(set(counts))==1
apps=request('/apps?page_size=1000')
assert apps['total']>=60
app=request('/apps/'+str(apps['items'][0]['id']))
assert app['history'] and app['classification']['evidence']
assert request('/apps?created_after=2026-01-01')['total']>=0
assert 'data_mode' in request('/apps/export.csv')
quality=request('/quality')
assert next(x['rows'] for x in quality['layers'] if x['name'].startswith('DWS'))>=30
assert not any(x['status']=='fail' for x in quality['checks'])
job=request('/reports',{})
for _ in range(45):
    state=request('/jobs/'+job['id'])
    if state['status'] not in ('queued','running'): break
    time.sleep(1)
assert state['status']=='succeeded',state
report=request('/reports/'+state['summary']['report_id'])
assert report['mode']=='demo'
assert str(report['facts']['kpis']['eligible']) in report['body']
assert all(source['url'] in report['body'] for source in report['sources'])
print(json.dumps({'status':'passed','mode':'demo','tracked':counts[0],'eligible':apps['total'],'history_days':len(app['history']),'windows':[7,30,90],'report_job_status':state['status'],'report_method':report['method']},ensure_ascii=False,indent=2))
