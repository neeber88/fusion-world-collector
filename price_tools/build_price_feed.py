#!/usr/bin/env python3
"""TCGplayer market prices via TCGCSV. Exact, conservative card-print matching.
Usage: python price_tools/build_price_feed.py --catalog catalog.json --output prices.json
Requires internet. Python standard library only. No TCGplayer API key needed.
"""
import argparse
import datetime as dt
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE='https://tcgcsv.com/tcgplayer/80'

def clean(text):
    s=unicodedata.normalize('NFKD',str(text or ''))
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()

def download(url):
    req=urllib.request.Request(url,headers={'User-Agent':'FusionWorldCollectorPriceImporter/1.7 (+personal collector; cached daily)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as r:
        if r.status!=200:raise RuntimeError(f'HTTP {r.status}: {url}')
        return json.load(r)

def group_set(name,sets):
    n=clean(name)
    # Standalone market groups for true promotion printings / energy markers.
    # Tournament promos are kept separate from booster copies even if the
    # printed card number is identical.
    if n in ('fusion world promotion cards and packs', 'tournament and championship promos'):
        return 'PROMO' if 'PROMO' in sets else None
    if n == 'fusion world energy markers':
        return 'ENERGY' if 'ENERGY' in sets else None
    # Never value a booster / starter copy using a reprint or event market group.
    if any(w in n for w in ('release event','championship','tournament','promotion','promo','prize','energy marker','limited pack','winner','pre release','prerelease','reprints','reprint')):
        return None
    for code,meta in sets.items():
        if code in ('PROMO','ENERGY'):continue
        title=clean(meta['name'])
        if code.startswith('FB') and n==title:return code
        if code.startswith('SB') and n==title:return code
        if code=='ST01' and n in ('story booster 01','story booster 1'):return code
    m=re.search(r'\b(?:starter deck(?: ex)?|starter)(?:\s*:?\s*)(\d{1,2})\b',n)
    if m:
        code=f'FS{int(m.group(1)):02d}'
        if code in sets:return code
    # Starter products are named by character in some TCGplayer groups.
    if n.startswith('starter deck'):
        for code,meta in sets.items():
            if code.startswith('FS') and clean(meta['name']) in n and len(clean(meta['name']))>=7:
                return code
    return None

CARD_NUMBER_RE=re.compile(r'\b((?:FB|FS|SB|ST)\d{2}-\d{1,3}|(?:FP|E)-\d{1,3})\b',re.I)

def canonical_number(value):
    match=CARD_NUMBER_RE.fullmatch(str(value or '').upper())
    if not match:return str(value or '').upper()
    prefix,digits=match.group(1).rsplit('-',1)
    return f'{prefix}-{int(digits)}'


def extract_number(product):
    fields={clean(x.get('name')):str(x.get('value','')) for x in product.get('extendedData',[]) if isinstance(x,dict)}
    name=str(product.get('name') or '')
    for val in (fields.get('number',''),name):
        m=CARD_NUMBER_RE.search(val)
        if m:return m.group(1).upper()
    return None

def print_type(product):
    n=clean(product.get('name',''))
    if re.search(r'\b(serial|numbered|manga|gold|silver|championship|winner|prize|event|exclusive|judge|stamped|reprint)\b',n):return 'SPECIAL'
    if re.search(r'\b(alternate|alt art|alternative|parallel|bonus pack)\b',n):return 'ALT'
    return 'BASE'

def get_subtype_price(pairs):
    available=[p for p in pairs if isinstance(p.get('marketPrice'),(int,float)) and 0 <= p['marketPrice'] <= 1e6]
    if not available:return None
    if len(available)==1:return available[0]
    # Prefer an unambiguous Normal subtype only when other rows are absent;
    # different holo prices cannot safely be treated as the same printing.
    values={round(p['marketPrice'],2) for p in available}
    if len(values)==1:return available[0]
    return None

def make_feed(catalog,groups,fetch,wait=0.3):
    sets={s['id']:s for s in catalog['sets']}
    cards=catalog['cards']
    index=defaultdict(list)
    for c in cards:index[(c['set'],canonical_number(c['number']),c['variant'])].append(c)
    result={};conflicted_ids=set();stats={'groups_checked':0,'products_examined':0,'conflicts':0,'reprints_ignored':0,'no_number':0,'unmatched':0,'no_market_price':0,'ambiguous':0,'sets_checked':[]}
    for g in groups:
        sid=group_set(g['name'],sets)
        if not sid:continue
        gid=g['groupId']
        products=fetch(f'{BASE}/{gid}/products')['results']
        if wait:time.sleep(wait)
        prices=fetch(f'{BASE}/{gid}/prices')['results']
        if wait:time.sleep(wait)
        stats['groups_checked']+=1;stats['sets_checked'].append(sid)
        if sid in ('FS01','FS03','FS11','FB01','FB11','SB01'):
            alts=[(str(p.get('name') or ''),print_type(p),extract_number(p),p.get('extendedData',[])[:2]) for p in products if print_type(p)=='ALT']
            print('ALT SOURCE SAMPLE',sid,'total=',len(alts),repr(alts[:6]),flush=True)
        pmap=defaultdict(list)
        for p in prices:pmap[p['productId']].append(p)
        candidates=defaultdict(list)
        for p in products:
            stats['products_examined']+=1
            num=extract_number(p)
            if not num:stats['no_number']+=1;continue
            # Promo catalog entries may carry original FB/FS/SB numbers, but
            # they must originate in an explicitly promotional market group.
            if sid=='PROMO':
                if num.startswith('E-'):
                    stats['reprints_ignored']+=1;continue
            elif sid=='ENERGY':
                if not num.startswith('E-'):
                    stats['reprints_ignored']+=1;continue
            elif not num.startswith(sid+'-'):
                stats['reprints_ignored']+=1;continue
            var=print_type(p)
            if var=='SPECIAL':stats['reprints_ignored']+=1;continue
            matches=index.get((sid,canonical_number(num),'ALT' if var=='ALT' else 'NORMAL'),[])
            if not matches:stats['unmatched']+=1;continue
            # Keep name matching strict where product titles carry the printed name.
            pname=str(p.get('name','')).split(' - '+num)[0]
            if sid=='ENERGY':
                # TCGplayer labels the character series 'Energy Marker (E-28)'
                # rather than the plain catalog name. Require an explicit E-xx
                # number from the dedicated marker group; E01-xx series labels
                # are NOT equivalent and require a separate verified crosswalk.
                if not clean(p.get('name','')).startswith('energy marker '):
                    stats['unmatched']+=1;continue
            elif pname and clean(pname) not in (clean(c['name']) for c in matches):
                stats['unmatched']+=1;continue
            price=get_subtype_price(pmap[p['productId']])
            if price is None:stats['no_market_price']+=1;continue
            candidates[(sid,num,var)].append((p,price,matches))
        for key,rows in candidates.items():
            # Exactly one market product and one matching official print.
            if len(rows)!=1 or len(rows[0][2])!=1:
                stats['ambiguous']+=len(rows);continue
            prod,pr,matching=rows[0]
            c=matching[0]
            if c['id'] in conflicted_ids:
                stats['conflicts']+=1;continue
            if c['id'] in result:
                stats['conflicts']+=1;result.pop(c['id'],None)
                conflicted_ids.add(c['id'])
                continue
            url=str(prod.get('url',''))
            result[c['id']]={'amount':round(pr['marketPrice'],2),'productId':prod['productId'], 'date':dt.datetime.now(dt.timezone.utc).date().isoformat(),'url':url if url.startswith('https://www.tcgplayer.com/') else ''}
    coverage=defaultdict(lambda:{'catalog':0,'priced':0})
    for c in cards:
        coverage[c['set']]['catalog']+=1
        if c['id'] in result:coverage[c['set']]['priced']+=1
    stats['by_set']={sid:counts for sid,counts in sorted(coverage.items())}
    return {'kind':'fusion-world-market-prices','schema_version':1,'updated_at':dt.datetime.now(dt.timezone.utc).date().isoformat(),'source':'TCGplayer Market Price via TCGCSV','currency':'USD','prices':result,'stats':{**stats,'priced_variants':len(result),'catalog_variants':len(cards)}}

def main():
    p=argparse.ArgumentParser();p.add_argument('--catalog',default='catalog.json');p.add_argument('--output',default='prices.json');p.add_argument('--delay',type=float,default=0.4);p.add_argument('--min-prices',type=int,default=0);args=p.parse_args()
    catalog=json.loads(Path(args.catalog).read_text(encoding='utf8'))
    groups=download(f'{BASE}/groups')['results']
    feed=make_feed(catalog,groups,download,args.delay)
    if feed['stats']['priced_variants']<args.min_prices:raise RuntimeError(f"Zu wenige zugeordnete Kartenpreise: {feed['stats']['priced_variants']} (Minimum {args.min_prices}). Alter Online-Preisstand wird nicht überschrieben.")
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(feed,ensure_ascii=False,indent=2),encoding='utf8')
    print(f"Matched {feed['stats']['priced_variants']} of {feed['stats']['catalog_variants']} printings in {feed['stats']['groups_checked']} groups")
    print('Set coverage:',json.dumps(feed['stats']['by_set'],sort_keys=True))
    print('Not priced:',feed['stats']['ambiguous'],'ambiguous product/print matches,',feed['stats']['no_market_price'],'missing/inconsistent market prices')

if __name__=='__main__':main()