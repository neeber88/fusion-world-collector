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
        all_prices.setdefault(pid,[]).append(p)
    time.sleep(.25)
today=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
prices={};ambiguous=[]
# Supplemental independent or cross-checked dated references; never re-date them.
reference_file=ROOT/"price-references.json"
references=json.loads(reference_file.read_text()).get("references",{}) if reference_file.exists() else {}
def valid(n):
    return type(n) in (int,float) and math.isfinite(n) and 0<n<1000000
for cardid,pid in ids.items():
    variants=all_prices.get(pid,[])
    by_subtype={}
    for p in variants:by_subtype.setdefault(str(p.get("subTypeName","")).lower(),[]).append(p)
    if len(by_subtype)>1:
        ambiguous.append({"id":cardid,"productId":pid,"subtypes":list(by_subtype)})
        continue
    chosen=next(iter(by_subtype.values()))[0] if len(by_subtype)==1 else None
    url=f"https://www.tcgplayer.com/product/{pid}"
    if chosen and valid(chosen.get("marketPrice")):
        prices[cardid]={"amount":round(chosen["marketPrice"],2),"date":today,"product_id":pid,"url":url,"source":"TCGCSV / TCGplayer","price_type":"market"}
        continue
    ref=references.get(cardid)
    if ref and int(ref.get("product_id",0))==pid and valid(ref.get("amount")) and ref.get("date") and ref.get("source") and str(ref.get("url","")).startswith("https://"):
        prices[cardid]={"amount":round(ref["amount"],2),"date":ref["date"],"product_id":pid,"url":ref["url"],"source":ref["source"],"price_type":"dated_reference"}
        continue
    # Listing mid/low prices are not sale prices. Do not mix them into collection valuation.
# Restore dated fallback values for catalogued cards without a newer feed price.
historical_path=ROOT/"historical-prices.json"
if historical_path.exists():
    historical=json.loads(historical_path.read_text()).get("prices",{})
    known_keys={c["id"] for c in catalog.get("cards",[])}
    for key,item in historical.items():
        if key not in known_keys or not isinstance(item,dict) or not valid(item.get("amount")):continue
        expected=ids.get(key)
        if expected and item.get("product_id") and int(item["product_id"])!=expected:continue
        prices.setdefault(key,{**item,"source":item.get("source","2026-10-20 backup"),"price_type":"historical"})
old_path=ROOT/"prices.json"
if old_path.exists():
    old=json.loads(old_path.read_text())
    for key,value in old.get("prices",{}).items():
        if key in {c["id"] for c in catalog.get("cards",[])} and isinstance(value,dict) and (not ids.get(key) or not value.get("product_id") or value.get("product_id")==ids[key]):
            # Existing undated prices are labelled historic, not refreshed market values.
            prices.setdefault(key,{**value,"source":value.get("source","Previous import"),"price_type":value.get("price_type","historical")})
if not prices:raise RuntimeError("No valid prices; refusing empty feed")
result={"kind":"fusion-world-market-prices","schema_version":1,"updated_at":today,"prices":prices,"stats":{"matched_product_ids":len(ids),"priced":len(prices),"ambiguous_prices":len(ambiguous),"unpriced_verified":len(ids)-len([k for k in ids if k in prices]),"references_used":sum(p.get("price_type")=="dated_reference" for p in prices.values())}}
old_path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
(ROOT/"tcgplayer-price-audit.json").write_text(json.dumps({"ambiguous":ambiguous,"missing":[k for k in ids if k not in prices]},indent=2)+"\n")
print("Verified IDs:",len(ids),"Priced cards:",len(prices),"Ambiguous:",len(ambiguous))
