"""Build a public, time-limited snapshot from public sources only."""
import json
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from market import UTC, FI, NY, analyze, apply_context, next_open, stamp
from providers import PublicClient, collect

ROOT = Path(__file__).resolve().parents[1]

def build(result, now, previous=None):
    previous = previous or {}
    quote = next((q for q in result['quotes'] if q['symbol'] == 'ES=F'), None)
    analysis = analyze(quote, now)
    alerts = apply_context(analysis, now, result['news'], result['events'], result['health'])
    today = now.astimezone(FI).date().isoformat()
    history = [h for h in previous.get('history', []) if isinstance(h, dict) and all(k in h for k in ('at','title','direction','reason'))][:14]
    entry = {'at':now.isoformat(), 'title':analysis['title'], 'direction':analysis['direction'], 'reason':analysis['reasons'][0] if analysis['reasons'] else ''}
    if not history or history[0]['title'] != entry['title']:
        history.insert(0, entry)
    reports = previous.get('reports', {}) if previous.get('report_day') == today else {}
    if analysis['direction'] in ('up','down','neutral'):
        report = {**entry, 'condition':analysis['condition'], 'quote_at':analysis.get('quote_at')}
        if 5 <= now.astimezone(FI).hour < 12 and 'morning' not in reports:
            reports['morning'] = report
        ny = now.astimezone(NY)
        if (ny.hour,ny.minute) < (9,30):
            reports['premarket'] = report
    until = now + timedelta(minutes=15)
    if quote and analysis['direction'] in ('up','down','neutral','caution'):
        until = min(until, stamp(quote['at'])+timedelta(minutes=20), stamp(quote['bars'][-1]['ts']+300)+timedelta(minutes=20))
    for q in result['quotes']:
        q['stale'] = not -60 <= (now-stamp(q['at'])).total_seconds() <= 1200
        q.pop('bars', None)
    result.update(schema_version=1, analysis=analysis, alerts=alerts, history=history[:15], reports=reports,
                  report_day=today, now=now.isoformat(), collected_at=now.isoformat(), valid_until=until.isoformat(),
                  next_open=next_open(now), refreshing=False, watch=True, error='', cooldown=0)
    return result

def main():
    previous = {}
    try:
        req=urllib.request.Request('https://aimtrading.fi/kronikka/data/state.json',headers={'User-Agent':'AIM-Kronikka/1.0','Cache-Control':'no-cache'})
        with urllib.request.urlopen(req,timeout=15) as response:
            previous=json.loads(response.read(2_000_000))
        if not isinstance(previous,dict) or previous.get('schema_version') != 1:
            previous={}
    except Exception:
        pass
    result=collect(PublicClient(),datetime.now(UTC))
    state=build(result,datetime.now(UTC),previous)
    destination=ROOT/'kronikka/data/state.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(state,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    failed=[h['name'] for h in state['health'] if not h['ok']]
    print('Published snapshot:',state['collected_at'],state['analysis']['title'])
    print('Unavailable sources:',', '.join(failed) or 'none')

if __name__=='__main__':
    main()
