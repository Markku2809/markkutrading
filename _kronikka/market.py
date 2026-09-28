"""Auditable price context, never a trading or order engine."""
from __future__ import annotations
import math
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone, date, time
sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
from zoneinfo import ZoneInfo

UTC = timezone.utc
NY = ZoneInfo('America/New_York')
FI = ZoneInfo('Europe/Helsinki')

def stamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Missing timezone')
    return result.astimezone(UTC)

def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def observed(d):
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d

def nth(y, m, weekday, n):
    d = date(y, m, 1)
    return d + timedelta(days=(weekday-d.weekday()) % 7 + (n-1)*7)

def easter(y):
    a=y%19; b=y//100; c=y%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    return date(y,(h+l-7*m+114)//31,(h+l-7*m+114)%31+1)

def cash_holidays(y):
    last_may = date(y,5,31)
    # NYSE does not observe a Saturday Jan 1 on the previous Friday.
    newyear = date(y,1,1)
    if newyear.weekday() == 6: newyear += timedelta(days=1)
    return {newyear, nth(y,1,0,3), nth(y,2,0,3), easter(y)-timedelta(days=2),
            last_may-timedelta(days=last_may.weekday()), observed(date(y,6,19)),
            observed(date(y,7,4)), nth(y,9,0,1), nth(y,11,3,4), observed(date(y,12,25))}

def cash_day(d):
    return d.weekday() < 5 and d not in cash_holidays(d.year)

def next_open(now):
    local=now.astimezone(NY)
    for i in range(12):
        d=local.date()+timedelta(days=i)
        opening=datetime.combine(d,time(9,30),NY)
        if cash_day(d) and opening > local:
            return opening.astimezone(UTC).isoformat()

def futures_pause(now):
    d=now.astimezone(NY); minute=d.hour*60+d.minute
    return d.weekday()==5 or (d.weekday()==6 and minute<1080) or (d.weekday()==4 and minute>=1020) or (d.weekday()<4 and 1020<=minute<1080)

def session_start(now):
    d=now.astimezone(NY)
    start=d.replace(hour=18,minute=0,second=0,microsecond=0)
    if d<start: start-=timedelta(days=1)
    return start.astimezone(UTC)

def parse_chart(payload, symbol, label, now):
    data=payload['chart']['result'][0]; meta=data['meta']; raw=data['indicators']['quote'][0]
    bars=[]
    for i, ts in enumerate(data.get('timestamp') or []):
        vals={key: (raw.get(key) or [])[i] if i<len(raw.get(key) or []) else None for key in ('open','high','low','close','volume')}
        if not all(finite(vals[k]) and vals[k]>0 for k in ('open','high','low','close')): continue
        if vals['high']<max(vals['open'],vals['close'],vals['low']) or vals['low']>min(vals['open'],vals['close']): continue
        # Yahoo can append a synthetic last quote with a non-bar timestamp.
        if not finite(ts) or ts % 300 != 0 or ts+300>now.timestamp(): continue
        vals['volume']=vals['volume'] if finite(vals['volume']) and vals['volume']>=0 else 0
        bars.append(dict(ts=int(ts),**vals))
    bars=sorted({b['ts']:b for b in bars}.values(),key=lambda b:b['ts'])
    price=meta.get('regularMarketPrice'); previous=meta.get('previousClose')
    quote_at=meta.get('regularMarketTime')
    if not finite(price) or price<=0 or not finite(quote_at): raise ValueError('Invalid quote')
    return {'symbol':symbol,'label':label,'contract':meta.get('shortName',label), 'price':price,
        'previous':previous if finite(previous) and previous>0 else None,
        'change':(price/previous-1)*100 if finite(previous) and previous>0 else None,
        'at':stamp(quote_at).isoformat(),'bars':bars[-1600:],'source':'Yahoo Finance',
        'url':'https://finance.yahoo.com/quote/'+symbol.replace('^','%5E').replace('=','%3D')+'/',
        'delayed':True,'delay_note':'Julkinen, mahdollisesti viivästetty data; tarkkaa viivettä ei taata.'}

def analyze(quote, now):
    base={'title':'TIETOA ODOTETAAN','direction':'unknown','confidence':'Ei arviota','reasons':[],
          'condition':'Suuntanäkymä muodostuu vasta riittävästä ja ajantasaisesta aineistosta.',
          'scope':'Futuurien tekninen tilanne — ei koko päivän ennuste', 'metrics':{},'chart':[]}
    if not quote:
        base['reasons']=['Futuuridataa ei saatu. Päivän suuntaa ei päätellä ilman sitä.']; return base
    bars=quote.get('bars',[])
    base['chart']=bars[-180:]
    base['quote_at']=quote['at']
    if futures_pause(now):
        base.update(title='MARKKINATAUKO',direction='closed',reasons=['Futuurien tavanomainen viikonloppu- tai päivätauko. Näytössä viimeisin saatavilla oleva aineisto.'])
        return base
    age=(now-stamp(quote['at'])).total_seconds()
    if age < -60 or age>1200 or not bars or now.timestamp()-(bars[-1]['ts']+300)>1200:
        base.update(title='TIETO VANHENTUNUT',direction='stale',reasons=['Hintatieto on vanhaa tai aikaleima on epäkelpo. Aiempi suunta-arvio ei ole voimassa.'])
        return base
    current=[b for b in bars if b['ts']>=session_start(now).timestamp()]
    if len(current)<24:
        base['reasons']=['Tämän futuurijakson suljettuja 5 minuutin kynttilöitä on liian vähän (tarvitaan vähintään 24).']; return base
    if any(b['ts']-a['ts']>600 for a,b in zip(current[-24:],current[-23:])):
        base.update(title='DATASSA AUKKO',direction='stale',reasons=['Tuoreimmassa hintahistoriassa on katkos. Suunta-arvio keskeytetty.']); return base
    last=current[-1]['close']; opening=current[0]['open']; change=(last/opening-1)*100
    weighted=sum(((b['high']+b['low']+b['close'])/3)*b['volume'] for b in current)
    volume=sum(b['volume'] for b in current)
    vwap=weighted/volume if volume>0 else None
    momentum=(last/current[-7]['close']-1)*100
    score=(1 if change>.10 else -1 if change<-.10 else 0)+(1 if momentum>.04 else -1 if momentum<-.04 else 0)
    if vwap: score+=(1 if last/vwap-1>.0003 else -1 if last/vwap-1<-.0003 else 0)
    direction='up' if score>=2 else 'down' if score<=-2 else 'neutral'
    recent=current[-12:]; vol=sum(b['volume'] for b in recent)
    downvol=sum(b['volume'] for b in recent if b['close']<b['open'])
    sell=downvol/vol*100 if vol else None
    pressure='Ei volyymitietoa' if sell is None else 'Laskevat kynttilät painottuvat' if sell>60 else 'Nousevat kynttilät painottuvat' if sell<40 else 'Paine jakautuu tasaisesti'
    high=max(b['high'] for b in current); low=min(b['low'] for b in current)
    reasons=[f'Futuurijakson alusta {change:+.2f} %; viimeiset 30 minuuttia {momentum:+.2f} %.']
    if vwap: reasons.append('Hinta on jakson volyymipainotetun keskihinnan '+('yläpuolella.' if last>vwap else 'alapuolella.'))
    else: reasons.append('Volyymi puuttuu: keskihintavahvistusta ei käytetä.')
    tr=[b['high']-b['low'] for b in current]
    activity=(sum(tr[-6:])/6)/(sum(tr[-24:-6])/18) if sum(tr[-24:-6])>0 else None
    base.update(title={'up':'NOUSUPAINOTTEINEN','down':'LASKUPAINOTTEINEN','neutral':'EPÄSELVÄ / SIVUTTAINEN'}[direction], direction=direction,
       confidence='Alustava — julkinen hintadata',reasons=reasons,
       condition=(f'Nousutulkinta heikkenee, jos hinta laskee keskihinnan alle ja 30 minuutin liike kääntyy negatiiviseksi. Jakson pohja {low:.2f}.' if direction=='up' else
                  f'Laskutulkinta heikkenee, jos hinta nousee keskihinnan päälle ja 30 minuutin liike kääntyy positiiviseksi. Jakson huippu {high:.2f}.' if direction=='down' else
                  f'Seuraa hintaa suhteessa jakson vaihteluväliin {low:.2f}–{high:.2f} ja volyymipainotettuun keskihintaan.') if vwap else 'Volyymivahvistus puuttuu. Suuntatulkinta on tavallista heikompi.',
       metrics={'vwap':vwap,'high':high,'low':low,'session_change':change,'momentum':momentum,'selling':sell,'pressure':pressure,
                'activity':activity,'activity_label':'Ei vertailua' if activity is None else 'Poikkeuksellinen' if activity>=2 else 'Aktiivinen' if activity>=1.3 else 'Rauhallinen',
                'last':last,'session_start':session_start(now).isoformat()},chart=current[-288:])
    return base

def apply_context(analysis, now, news, events, health):
    """Never infer market direction from headlines; suspend rather than overstate."""
    alerts=[]
    for item in news:
        if not item.get('risk') or not item.get('published'): continue
        age=(now-stamp(item['published'])).total_seconds()
        if 0<=age<=1800:
            alerts.append({'id':item['id'],'kind':'news','title':'Tarkistettava uutisotsikko','detail':item['title'],
                           'at':item['published'],'url':item['url'],'source':item['source']})
    near=[e for e in events if e['impact']=='High' and -600 <= (stamp(e['at'])-now).total_seconds() <= 900]
    for event in near:
        alerts.append({'id':'event-'+event['at']+event['title'],'kind':'event','title':'Merkittävä talousjulkaisu lähellä',
                       'detail':event['title_fi'],'at':event['at'],'url':event['url'],'source':'Forex Factory'})
    momentum=analysis.get('metrics',{}).get('momentum',0)
    if abs(momentum)>=.6:
        alerts.append({'id':'price-'+str(int(now.timestamp()//1800)),'kind':'price','title':'Poikkeuksellinen hintaliike',
                       'detail':f'ES-futuuri {momentum:+.2f} % / 30 min. Julkinen data voi olla viivästettyä; liikkeen syytä ei päätellä.',
                       'at':analysis.get('quote_at'),'url':'https://finance.yahoo.com/quote/ES%3DF/','source':'Yahoo Finance'})
    if alerts and analysis['direction'] in ('up','down','neutral'):
        analysis['technical_title']=analysis['title']
        analysis.update(title='TILANNE EPÄVARMA',direction='caution',confidence='Uudelleenarviointi tarpeen')
        analysis['reasons'].insert(0,'Uutis-, tapahtuma- tai hintahälytys: aiempaan suuntanäkymään ei pidä nojata sellaisenaan.')
    missing=[h['name'] for h in health if h['group'] in ('news','calendar') and not h['ok']]
    if missing:
        analysis['reasons'].append('Uutis- tai kalenteriseuranta on osittainen. Puuttuvia lähteitä: '+', '.join(missing)+'.')
    return alerts[:12]
