import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market import *
from providers import parse_feed, parse_calendar

class OutlookTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,22,12,0,tzinfo=UTC)

    def quote(self, direction=1, volume=100):
        bars=[]
        for i in range(48):
            p=6000+direction*i*1.5
            bars.append({'ts':int((self.now-timedelta(minutes=(48-i)*5)).timestamp()),
                         'open':p,'high':p+2,'low':p-2,'close':p+direction,'volume':volume})
        return {'bars':bars,'at':self.now.isoformat(),'price':bars[-1]['close']}

    def test_up_and_down(self):
        for d,label in [(1,'up'),(-1,'down')]:self.assertEqual(analyze(self.quote(d),self.now)['direction'],label)

    def test_old_quote_abstains(self):
        q=self.quote();q['at']=(self.now-timedelta(minutes=21)).isoformat()
        self.assertEqual(analyze(q,self.now)['direction'],'stale')

    def test_future_quote_abstains(self):
        q=self.quote();q['at']=(self.now+timedelta(minutes=5)).isoformat()
        self.assertEqual(analyze(q,self.now)['direction'],'stale')

    def test_old_candles_abstain_even_when_quote_is_fresh(self):
        q=self.quote();q['bars']=q['bars'][:-6]
        self.assertEqual(analyze(q,self.now)['direction'],'stale')

    def test_weekend_has_no_direction(self):
        sunday=datetime(2026,9,27,12,tzinfo=UTC)
        self.assertEqual(analyze(self.quote(),sunday)['direction'],'closed')

    def test_no_data_and_insufficient_history(self):
        self.assertEqual(analyze(None,self.now)['direction'],'unknown')
        q=self.quote();q['bars']=q['bars'][-10:]
        self.assertEqual(analyze(q,self.now)['direction'],'unknown')

    def test_data_gap_suspends(self):
        q=self.quote();del q['bars'][-12:-8]
        self.assertEqual(analyze(q,self.now)['direction'],'stale')

    def test_missing_volume_not_selling_pressure(self):
        a=analyze(self.quote(volume=0),self.now)
        self.assertIsNone(a['metrics']['selling']);self.assertIsNone(a['metrics']['vwap'])

    def test_new_risk_headline_suspends_not_bearish(self):
        a=analyze(self.quote(),self.now)
        news=[{'risk':True,'published':self.now.isoformat(),'id':'war','title':'Military attack','url':'https://example.com','source':'Reuters'}]
        alerts=apply_context(a,self.now,news,[],[])
        self.assertEqual(a['direction'],'caution');self.assertEqual(len(alerts),1)

    def test_old_risk_headline_does_not_trigger(self):
        a=analyze(self.quote(),self.now)
        news=[{'risk':True,'published':(self.now-timedelta(hours=2)).isoformat(),'id':'old','title':'war','url':'https://example.com','source':'Reuters'}]
        self.assertEqual(apply_context(a,self.now,news,[],[]),[]);self.assertEqual(a['direction'],'up')

    def test_calendar_event_guard(self):
        a=analyze(self.quote(),self.now)
        event={'at':(self.now+timedelta(minutes=10)).isoformat(),'impact':'High','title':'CPI','title_fi':'Inflaatio','url':'https://example.com'}
        apply_context(a,self.now,[],[event],[]);self.assertEqual(a['direction'],'caution')

    def test_dst_opening(self):
        march=next_open(datetime(2026,3,16,6,tzinfo=UTC))
        self.assertEqual(stamp(march).astimezone(FI).hour,15)
        april=next_open(datetime(2026,4,6,6,tzinfo=UTC))
        self.assertEqual(stamp(april).astimezone(FI).hour,16)

    def test_holiday_no_fake_open(self):
        self.assertFalse(cash_day(date(2026,12,25)))
        self.assertFalse(cash_day(date(2026,4,3)))
        self.assertEqual(stamp(next_open(datetime(2026,12,25,6,tzinfo=UTC))).astimezone(NY).date(),date(2026,12,28))

    def test_chart_ignores_unclosed_and_nan(self):
        q=self.quote(); bars=q['bars'][-3:]
        data={'chart':{'result':[{'meta':{'regularMarketPrice':6000,'regularMarketTime':self.now.timestamp(),'previousClose':5900},
            'timestamp':[bars[0]['ts'],bars[1]['ts'],self.now.timestamp()],
            'indicators':{'quote':[{'open':[6000,float('nan'),6000],'high':[6002,6002,6002],'low':[5999,5999,5999],'close':[6001,6001,6001],'volume':[10,10,10]}]}}]}}
        parsed=parse_chart(data,'ES=F','ES',self.now)
        self.assertEqual(len(parsed['bars']),1)
        self.assertAlmostEqual(parsed['change'],(6000/5900-1)*100)

    def test_feed_rejects_bad_links_and_future_dates(self):
        xml=b'<rss><channel><item><title>Stocks rally</title><link>javascript:alert(1)</link><pubDate>Tue, 22 Sep 2026 11:00:00 GMT</pubDate></item><item><title>Stocks rise</title><link>https://example.com</link><pubDate>Tue, 22 Sep 2030 11:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(parse_feed(xml,'CNBC',self.now),[])

    def test_feed_verifies_reuters_source(self):
        xml=b'<rss><channel><item><title>Stocks rally</title><source>Fake News</source><link>https://example.com</link><pubDate>Tue, 22 Sep 2026 11:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(parse_feed(xml,'Reuters / Google News',self.now,search=True),[])

    def test_calendar_timezone_and_currency(self):
        raw='[{"country":"USD","date":"2026-09-22T08:30:00-04:00","title":"CPI m/m","impact":"High"},{"country":"JPY","date":"2026-09-22T08:30:00-04:00"}]'
        events=parse_calendar(raw,self.now)
        self.assertEqual(len(events),1);self.assertEqual(stamp(events[0]['at']).hour,12)

    def test_analyst_publisher_domain_alias(self):
        xml=b'<rss><channel><item><title>Tom Lee sees stock rally - finance.yahoo.com</title><source>finance.yahoo.com</source><link>https://example.com</link><pubDate>Tue, 22 Sep 2026 11:00:00 GMT</pubDate></item></channel></rss>'
        items=parse_feed(xml,'Tom Lee',self.now,search=True,analyst=True)
        self.assertEqual(len(items),1);self.assertEqual(items[0]['source'],'Yahoo Finance')

    def test_related_search_hit_not_attributed_to_analyst(self):
        xml=b'<rss><channel><item><title>Stocks rally</title><source>Yahoo Finance</source><link>https://example.com</link><pubDate>Tue, 22 Sep 2026 11:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(parse_feed(xml,'Tom Lee',self.now,search=True,analyst=True),[])

    def test_sports_story_not_market_energy_news(self):
        xml=b'<rss><channel><item><title>Pochettino changes US energy</title><source>Reuters</source><link>https://example.com</link><pubDate>Tue, 22 Sep 2026 11:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(parse_feed(xml,'Reuters / Google News',self.now,search=True),[])

if __name__=='__main__':unittest.main()
