#!/usr/bin/env python3
"""Live TCGCSV per-product audit of currently unpriced booster/starter variants.
No guessed values are published. Product IDs, subtypes and evidence are retained.
"""
import csv,json,re,urllib.request,time,collections,datetime,pathlib
ROOT='https://tcgcsv.com/tcgplayer/80'
def load(url):
    req=urllib.request.Request(url,headers={'User-Agent':'FusionWorldCollectorAudit/2.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response: obj=json.load(response)
    if not obj.get('success',False):raise ValueError('TCGCSV failed: '+url)
    return obj['results']
def number(s):
    m=re.search(r'\\b(?:FB|FS|SB|ST)\\d{2}-\\d{1,3}\\b',str(s or ''),re.I)
    return m.group(0).upper() if m else ''
def print_group(name, sets):
    n=name.lower()
    for key,title in sets.items():
        if not key.startswith(('FB','FS','SB','ST')):continue
        if key.startswith(('FB','SB')) and title.lower()==n:return key
        if key=='ST01' and ('story booster' in n):return key
        if key.startswith('FS') and re.search(r'starter deck(?: ex)?\\s*:?\\s*0?'+str(int(key[2:]))+r'(?:\\D|$)',n):return key
    return None
def kind(name):
    n=name.lower()
    if any(w in n for w in ('winner','prize','serial','manga','signed','judge','stamped','tournament','championship','reprint','limited pack')):return 'special'
    if any(w in n for w in ('alternate art','alt art','bonus pack','parallel','(gold)')):return 'alt'
    return 'base'
def main():
    catalog=json.loads(pathlib.Path('catalog.json').read_text())
    feed=json.loads(pathlib.Path('dist/prices.json').read_text())
    cards=[c for c in catalog['cards'] if c['set'].startswith(('FB','FS','SB','ST'))]
    known=set(feed['prices'])
    missing={c['id']:c for c in cards if c['id'] not in known}
    sets={s['id']:s['name'] for s in catalog['sets']}
    groups=load(ROOT+'/groups')
    candidates=collections.defaultdict(list)
    checked=0
    for g in groups:
        sid=print_group(g.get('name',''),sets)
        if not sid:continue
        gid=g['groupId']
        products=load(f'{ROOT}/{gid}/products')
        prices=load(f'{ROOT}/{gid}/prices')
        pmap=collections.defaultdict(list)
        for p in prices:pmap[str(p.get('productId'))].append(p)
        for p in products:
            pid=str(p.get('productId'))
            pname=p.get('name','')
            ext=p.get('extendedData') or []
            rawnum=number(pname)
            for field in ext:
                if isinstance(field,dict) and str(field.get('name','')).lower()=='number':
                    rawnum=rawnum or number(field.get('value'))
            for c in missing.values():
                if c['set']!=sid:continue
                if rawnum and number(c['number'])!=rawnum:continue
                # If product does not contain a number, name is an investigative lead, not verified.
                if not rawnum and str(c['name']).lower() not in str(pname).lower():continue
                typ=kind(pname)
                market=[{'subtype':row.get('subTypeName'),'marketPrice':row.get('marketPrice')} for row in pmap[pid]]
                candidates[c['id']].append({'product_id':pid,'product_name':pname,'group_id':gid,'group':g['name'],'printed_number':rawnum,'print_type':typ,'market_rows':market})
        checked+=1
        time.sleep(.12)
    pathlib.Path('dist').mkdir(exist_ok=True)
    rows=[]
    for cid,c in missing.items():
        hits=candidates.get(cid,[])
        rows.append({'app_id':cid,'card_name':c['name'],'set':c['set'],'variant':c['variant'],'candidate_ids':';'.join(sorted({h['product_id'] for h in hits})),'candidate_count':len(hits),'product_evidence':json.dumps(hits,ensure_ascii=False)})
    with open('dist/price-id-audit.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['app_id']);w.writeheader();w.writerows(rows)
    summary={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'groups_checked':checked,'unpriced_booster_starter_variants':len(rows),'variants_with_product_candidates':sum(bool(candidates.get(x['app_id'])) for x in rows),'note':'Potential IDs are evidence for manual variant verification, not automatically approved market prices'}
    pathlib.Path('dist/price-id-audit-summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
