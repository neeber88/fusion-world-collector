#!/usr/bin/env python3
"""Generate a safe, variant-specific TCGplayer market-price feed from verified IDs."""
import json, pathlib, datetime, requests, time, math
ROOT=pathlib.Path(__file__).resolve().parent.parent
ids=json.loads((ROOT/"tcgplayer-product-ids.json").read_text())["ids"]
catalog=json.loads((ROOT/"catalog.json").read_text())
session=requests.Session()
session.headers["User-Agent"]="FusionWorldCollector-PriceSync/1.0"
api="https://tcgcsv.com/tcgplayer"
def fetch(url):
    for attempt in range(3):
        try:
            r=session.get(url,timeout=45);r.raise_for_status();return r.json()["results"]
        except (requests.RequestException,KeyError,ValueError):
            if attempt==2:raise
            time.sleep(attempt+2)
categories=fetch(api+"/categories")
cat=next(x for x in categories if "fusion world" in str(x.get("name","")).lower())
category_id=cat["categoryId"]
groups=fetch(f"{api}/{category_id}/groups")
# Collect only one unambiguous price per product; never choose arbitrarily between subtypes.
all_prices={}
wanted_ids=set(ids.values())
for group in groups:
    rows=fetch(f"{api}/{category_id}/{group['groupId']}/prices")
    for p in rows:
        pid=int(p["productId"])
        if pid not in wanted_ids:continue
        price=p.get("marketPrice")
        if not isinstance(price,(int,float)) or not math.isfinite(price) or price<0:continue
        all_prices.setdefault(pid,[]).append(p)
    time.sleep(.25)
today=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
prices={};ambiguous=[]
for cardid,pid in ids.items():
    variants=all_prices.get(pid,[])
    distinct={(str(p.get("subTypeName","")).lower(),round(p["marketPrice"],2)):p for p in variants}
    if len(distinct)!=1:
        if len(distinct)>1:ambiguous.append({"id":cardid,"productId":pid,"subtypes":list(map(list,distinct))})
        continue
    price=next(iter(distinct.values()))["marketPrice"]
    prices[cardid]={"amount":round(price,2),"date":today,"product_id":pid,"url":f"https://www.tcgplayer.com/product/{pid}"}
old_path=ROOT/"prices.json"
if old_path.exists():
    old=json.loads(old_path.read_text())
    for key,value in old.get("prices",{}).items():
        prices.setdefault(key,value)
if not prices:raise RuntimeError("No valid prices; refusing empty feed")
result={"kind":"fusion-world-market-prices","schema_version":1,"updated_at":today,"prices":prices,"stats":{"matched_product_ids":len(ids),"priced":len(prices),"ambiguous_prices":len(ambiguous),"unpriced_verified":len(ids)-len([k for k in ids if k in prices])}}
old_path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
(ROOT/"tcgplayer-price-audit.json").write_text(json.dumps({"ambiguous":ambiguous,"missing":[k for k in ids if k not in prices]},indent=2)+"\n")
print("Verified IDs:",len(ids),"Priced cards:",len(prices),"Ambiguous:",len(ambiguous))
