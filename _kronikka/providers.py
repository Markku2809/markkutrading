"""Public sources. Headlines only: no paywall access or fabricated analyst views."""
from __future__ import annotations
import concurrent.futures
import hashlib
import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from datetime import datetime, timedelta
from market import UTC, stamp, parse_chart, FI

ROOT=Path(__file__).resolve().parent
ANALYSTS=[
 {'name':'Tom Lee','role':'Fundstrat · markkinastrategia','query':'"Tom Lee" ("S&P 500" OR "stock market") when:7d','url':'https://fsinsight.com/','note':'Julkiset maininnat. Varsinainen tutkimus on tilauspalvelussa.'},
 {'name':'Mike Wilson','role':'Morgan Stanley · USA:n osakkeet','query':'"Mike Wilson" ("S&P 500" OR "stocks") when:7d','url':'https://www.morganstanley.com/insights/podcasts/thoughts-on-the-market','note':'Julkiset maininnat; podcast ja tekstiversiot lähdesivulla.'},
 {'name':'Ed Yardeni','role':'Yardeni Research · talous ja tulokset','query':'"Ed Yardeni" ("S&P 500" OR "stocks") when:7d','url':'https://yardeni.com/','note':'Julkiset maininnat. Aamuraportin koko sisältö vaatii tilauksen.'},
 {'name':'FuturesTrader71','role':'Morad Askar · futuuritreidaaja','query':'"FuturesTrader71" ("Trader Bite" OR "futures") when:7d','url':'https://edgeclear.com/traderbite/','note':'Trader Bite: tarkista tämän päivän video lähdesivulta. Videon sisältöä ei tulkita otsikosta.'},
]
ALLOWED_PUBLISHERS={'Reuters','CNBC','The Wall Street Journal','Yahoo Finance','Bloomberg.com','Bloomberg','Barron\'s','MarketWatch','Business Insider','Morgan Stanley','Fundstrat','FS Insight','Yardeni Research','YouTube','Convergent Trading','EdgeClear'}
PUBLISHER_ALIASES={'finance.yahoo.com':'Yahoo Finance','businessinsider.com':'Business Insider','cnbc.com':'CNBC',
 'wsj.com':'The Wall Street Journal','reuters.com':'Reuters','bloomberg.com':'Bloomberg','marketwatch.com':'MarketWatch',
 'youtube.com':'YouTube','fundstrat.com':'Fundstrat','fsinsight.com':'FS Insight','yardeni.com':'Yardeni Research'}

def google_feed(query):
    return 'https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'en-US','gl':'US','ceid':'US:en'})

FEEDS=[
 ('CNBC','https://www.cnbc.com/id/100003114/device/rss/rss.html',False),
 ('WSJ','https://feeds.content.dowjones.io/public/rss/RSSMarketsMain',False),
 ('Reuters / Google News',google_feed('site:reuters.com ("stocks" OR "futures" OR "Federal Reserve" OR "war" OR "missile" OR "ceasefire") when:2d'),True),
]
RISK=re.compile(r'\b(war|missiles?|invasion|airstrikes?|air strikes?|nuclear|ceasefire|emergency rate|terror|attack|attacks|martial law|trading halt|circuit breaker|bank failure)\b',re.I)
IRRELEVANT=re.compile(r'\b(football|soccer|pochettino|balogun|nfl|nba|mlb|nhl|world cup|premier league|box office|horoscope)\b',re.I)
THEMES=[(r'\b(war|missile|iran|military|ceasefire|invasion|attack)\b','Geopolitiikka'),
        (r'\b(fed|rates|inflation|cpi|pce|payroll|jobs)\b','Korot ja talous'),
        (r'\b(oil|crude|opec|energy)\b','Energia'),
        (r'\b(earnings|nvidia|apple|microsoft|amazon|meta|alphabet)\b','Yhtiöt ja tulokset'),
        (r'\b(stocks|futures|s&p|nasdaq|market)\b','Markkinat')]

def clean(text):
    return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>','',text or ''))).strip()

def safe_url(url):
    p=urllib.parse.urlsplit(url or '')
    return url if p.scheme=='https' and p.hostname and not p.username else ''

def parse_feed(raw, source, now, search=False, analyst=False):
    root=ET.fromstring(raw)
    items=[]
    for node in root.findall('.//item'):
        title=clean(node.findtext('title'))[:400]
        url=safe_url(node.findtext('link'))
        publisher=clean(node.findtext('source')) if search else source
        raw_publisher=publisher
        publisher=PUBLISHER_ALIASES.get(publisher.lower(),publisher)
        if analyst and publisher not in ALLOWED_PUBLISHERS: continue
        if source.startswith('Reuters') and publisher != 'Reuters': continue
        if not title or not url or IRRELEVANT.search(title): continue
        try:
            dt=parsedate_to_datetime(node.findtext('pubDate','')).astimezone(UTC)
        except (ValueError,TypeError,AttributeError,OverflowError): continue
        age=(now-dt).total_seconds()
        if age < -300 or age> (7*86400 if analyst else 72*3600): continue
        if search and raw_publisher and title.endswith(' - '+raw_publisher): title=title[:-len(' - '+raw_publisher)]
        if analyst:
            # A search hit is not proof that the named person said something.
            aliases={'Tom Lee':('tom lee',),'Mike Wilson':('mike wilson','michael wilson'),
                     'Ed Yardeni':('yardeni',),'FuturesTrader71':('futurestrader71','ft71','trader bite','morad askar')}
            if not any(term in title.lower() for term in aliases.get(source,(source.lower(),))):continue
        topic=next((label for pattern,label in THEMES if re.search(pattern,title,re.I)),'Muu uutinen')
        if not analyst and topic=='Muu uutinen': continue
        items.append({'id':hashlib.sha256((publisher+'|'+title.lower()).encode()).hexdigest()[:20],
          'title':title,'url':url,'published':dt.isoformat(),'source':publisher or source,'via':'Google News' if search else 'RSS',
          'topic':topic,'risk':bool(RISK.search(title)),'today':dt.astimezone(FI).date()==now.astimezone(FI).date(),
          'note':'Alkuperäinen otsikko; ei koko artikkelin analyysi.'})
    return sorted(items,key=lambda x:x['published'],reverse=True)

class PublicClient:
    def __init__(self):
        self.cache={}; self.lock=threading.Lock()

    def get(self, key, url, ttl):
        now=time.time()
        with self.lock: cached=self.cache.get(key)
        if cached and now-cached['attempt']<ttl: return dict(cached)
        result={'attempt':now,'fetched':cached['fetched'] if cached else None,'raw':cached['raw'] if cached else None,'ok':False,'error':''}
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; US500Kronikka/1.0; personal dashboard)','Accept':'application/json, application/rss+xml, application/xml, text/xml, */*'})
            with urllib.request.urlopen(req,timeout=12) as response: raw=response.read(4_000_001)
            if len(raw)>4_000_000: raise ValueError('Response too large')
            result.update(raw=raw,fetched=now,ok=True)
        except Exception as exc:
            result['error']=('HTTP '+str(exc.code)) if hasattr(exc,'code') else 'Lähteeseen ei saatu yhteyttä'
        with self.lock: self.cache[key]=dict(result)
        return result

def event_fi(title):
    names={'Non-Farm Employment Change':'USA:n työpaikkaraportti (NFP)','Unemployment Rate':'Työttömyysaste',
       'Unemployment Claims':'Työttömyyskorvaushakemukset','Federal Funds Rate':'Fedin korkopäätös',
       'FOMC Statement':'Fedin korkolausunto','FOMC Press Conference':'Fedin tiedotustilaisuus',
       'FOMC Meeting Minutes':'Fedin kokouspöytäkirja','CB Consumer Confidence':'Kuluttajien luottamus',
       'JOLTS Job Openings':'Avoimet työpaikat (JOLTS)','ISM Manufacturing PMI':'Teollisuuden ISM-indeksi',
       'ISM Services PMI':'Palvelualojen ISM-indeksi','Core PCE Price Index m/m':'PCE-pohjainflaatio, kuukausi',
       'CPI m/m':'Kuluttajahinnat, kuukausi','CPI y/y':'Kuluttajahinnat, vuosi','Core CPI m/m':'Pohjainflaatio, kuukausi',
       'Retail Sales m/m':'Vähittäismyynti, kuukausi','Advance GDP q/q':'BKT:n ennakkotieto, neljännes',
       'Final GDP q/q':'BKT:n lopullinen tieto, neljännes'}
    if title in names:return names[title]
    if 'FOMC' in title and 'Speaks' in title:return 'Fedin puhe: '+title.replace('FOMC Member ','').replace(' Speaks','')
    return title

def parse_calendar(raw, now):
    result=[]
    for e in json.loads(raw):
        if e.get('country')!='USD':continue
        try: at=stamp(e['date'])
        except (ValueError,KeyError,TypeError):continue
        if not now-timedelta(hours=12)<=at<=now+timedelta(days=8): continue
        title=clean(e.get('title',''))
        result.append({'title':title,'title_fi':event_fi(title),'at':at.isoformat(),'impact':e.get('impact','Unknown'),
                       'forecast':clean(e.get('forecast','')),'previous':clean(e.get('previous','')),
                       'url':'https://www.forexfactory.com/calendar','country':'USD'})
    return sorted(result,key=lambda x:x['at'])

def finite_number(v):
    import math
    return isinstance(v,(int,float)) and math.isfinite(v) and v>0

def collect(client, now):
    specs=[]
    for symbol,label in [('ES=F','S&P 500 -futuuri'),('NQ=F','Nasdaq-futuuri'),('^VIX','VIX'),('^N225','Nikkei 225')]:
        url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='')+'?range=5d&interval=5m'
        specs.append((symbol,label,'price',url,60))
    for name,url,_ in FEEDS:specs.append((name,name,'news',url,180))
    for a in ANALYSTS:specs.append((a['name'],a['name'],'analyst',google_feed(a['query']),900))
    specs.append(('calendar','Talouskalenteri','calendar','https://nfs.faireconomy.media/ff_calendar_thisweek.json',3600))
    quotes=[]; news=[]; analysts=[]; events=[]; health=[]
    def job(s):return s,client.get(s[0],s[3],s[4])
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(job,specs))
    for (key,name,group,url,ttl), r in results:
        h={'name':name,'group':group,'ok':r['ok'],'error':r['error'],'fetched':stamp(r['fetched']).isoformat() if r['fetched'] else None,'cached':not r['ok'] and r['raw'] is not None}
        try:
            if r['raw'] is None: raise ValueError('No content')
            if group=='price':
                q=parse_chart(json.loads(r['raw']),key,name,now); q['fetch_ok']=r['ok']; quotes.append(q)
            elif group=='news':news.extend(parse_feed(r['raw'],name,now,search=key.startswith('Reuters')))
            elif group=='analyst':
                a=dict(next(a for a in ANALYSTS if a['name']==key)); a.pop('query',None)
                a['items']=parse_feed(r['raw'],name,now,search=True,analyst=True)[:3]; a['fetch_ok']=r['ok']; analysts.append(a)
            else:events=parse_calendar(r['raw'],now)
        except Exception:
            h.update(ok=False,error=r['error'] or 'Lähteen sisältöä ei voitu lukea')
            if group=='analyst':
                a=dict(next(a for a in ANALYSTS if a['name']==key)); a.pop('query',None); a.update(items=[],fetch_ok=False);analysts.append(a)
        health.append(h)
    # Duplicate headlines are one story, not independent confirmations.
    unique={}
    for n in sorted(news,key=lambda n:n['published'],reverse=True):
        key=re.sub('[^a-z0-9]','',n['title'].lower())
        if key not in unique:unique[key]=n
    news=list(unique.values())[:45]
    return {'quotes':quotes,'news':news,'analysts':analysts,'events':events,'health':health,'ig':{'fresh':False,'note':'Verkkoversio käyttää julkisia lähteitä. Kotikoneen IG-scannerin tietoja ei julkaista.'}}