#!/usr/bin/env python3
"""Conservative English Fusion World -> TCGplayer mapping through TCGCSV.
Requires: requests. Only exact, unambiguous set/number/name/printing matches are accepted.
Does not overwrite the user's catalog or existing ownership data.
"""
import json, re, time, datetime, pathlib, unicodedata
import requests

ROOT=pathlib.Path(__file__).resolve().parent.parent
CATALOG=ROOT/"catalog.json"
OUTPUT=ROOT/"tcgplayer-product-ids.json"
REPORT=ROOT/"tcgplayer-mapping-report.json"
API="https://tcgcsv.com/tcgplayer"
sess=requests.Session()
sess.headers.update({"User-Agent":"FusionWorldCollector-IDMapper/1.0 (GitHub maintenance; daily sync)"})

def get(url):
    for attempt in range(3):
        try:
            resp=sess.get(url, timeout=40)
            resp.raise_for_status()
            data=resp.json()
            if not data.get("success", True): raise RuntimeError(str(data.get("errors")))
            time.sleep(.2)
            return data["results"]
        except (requests.RequestException, ValueError, RuntimeError):
            if attempt==2: raise
            time.sleep(2*(attempt+1))
def norm(s):
    s=unicodedata.normalize("NFKD", str(s or "")).casefold()
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return " ".join(s.split())
def set_code(s):
    return re.search(r"\b(?:FB|FS)\d{2}\b",str(s or ""),re.I)
def source_variant(name):
    n=norm(name)
    if re.search(r"\b(super alternate art|super alt art|alt art 2|alternate art 2|alt 2)\b",n):return "ALT-2"
    if re.search(r"\b(alternate art|alt art|parallel|alt 1)\b",n):return "ALT-1"
    return "NORMAL"
def clean_name(name):
    name=re.sub(r"\((?:super )?(?:alternate|alt) art(?:\s*[12])?\)","",str(name),flags=re.I)
    return norm(name)
def number_of(p):
    ext=p.get("extendedData") or []
    if isinstance(ext,dict):ext=[{"name":k,"value":v} for k,v in ext.items()]
    for x in ext:
        if norm(x.get("name")) in ("number","card number","cardnumber","number in set"):
            m=re.search(r"\b(FB|FS)\d{2}-\d{1,3}\b",str(x.get("value")),re.I)
            if m:return m.group().upper()
    for value in [p.get("name"),p.get("cleanName")]:
        m=re.search(r"\b(FB|FS)\d{2}-\d{1,3}\b",str(value or ""),re.I)
        if m:return m.group().upper()
    return None
def run():
    catalog=json.loads(CATALOG.read_text())
    existing=json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {"ids":{}}
    ids=dict(existing.get("ids",{}))
    checks=[]
    categories=get(API+"/categories")
    cat=next((x for x in categories if "fusion world" in norm(x.get("name") or x.get("displayName"))),None)
    if not cat:raise RuntimeError("Fusion World category not found")
    category_id=cat["categoryId"]
    groups=get(f"{API}/{category_id}/groups")
    by_set={}
    for group in groups:
        label=norm(group.get("name"))
        abbr=norm(group.get("abbreviation"))
        for entry in catalog["sets"]:
            code=entry["id"]
            name=norm(entry.get("name"))
            # TCGplayer often omits FBxx codes from expansion titles.
            exact_code=code.casefold() in (abbr,label.split())
            exact_title=bool(name and len(name)>5 and (label==name or label.endswith(" "+name)))
            if exact_code or exact_title:
                by_set.setdefault(code,[]).append(group)
    stats={}
    for entry in catalog["sets"]:
        code=entry["id"]; group_list=by_set.get(code,[])
        local=[c for c in catalog["cards"] if c["set"]==code]
        statuses={"matched":0,"already_known":0,"ambiguous":0,"unmatched":0,"set_not_found":0}
        if len(group_list)!=1:
            statuses["set_not_found"]=len(local);stats[code]=statuses
            checks.extend({"id":c["id"],"reason":"set_not_unique","groups":len(group_list)} for c in local)
            continue
        group=group_list[0]
        products=get(f"{API}/{category_id}/{group['groupId']}/products")
        for card in local:
            key=card["id"]
            if key in ids:
                statuses["already_known"]+=1;continue
            v="NORMAL" if card["variant"] in ("NORMAL","BASE") else ("ALT-"+str(card["variant"]).split("-")[-1] if "ALT" in card["variant"] else str(card["variant"]).upper())
            # App uses ALT-1 and ALT-2; stop if a nonstandard variant is encountered.
            if v not in ("NORMAL","ALT-1","ALT-2"):
                statuses["unmatched"]+=1;checks.append({"id":key,"reason":"unknown_printing"});continue
            exact=[p for p in products if number_of(p)==card["number"] and
                   clean_name(p.get("name"))==norm(card["name"]) and
                   source_variant(p.get("name"))==v]
            # Never guess between two product IDs, or infer a variant by sorting products.
            unique={int(p["productId"]):p for p in exact}
            if len(unique)==1:
                ids[key]=next(iter(unique))
                statuses["matched"]+=1
            else:
                reason="ambiguous" if len(unique)>1 else "unmatched"
                statuses[reason]+=1
                checks.append({"id":key,"reason":reason,"candidates":list(unique)})
        stats[code]=statuses
    reverse={}
    for k,v in ids.items():reverse.setdefault(str(v),[]).append(k)
    duplicate={k:v for k,v in reverse.items() if len(v)>1}
    if duplicate:raise RuntimeError("Duplicate product ID assigned across variants: "+str(duplicate)[:500])
    if not ids:
        REPORT.write_text(json.dumps({"sets":stats,"review":checks,"mapped":0,"review_count":len(checks)},indent=2)+"\n")
        raise RuntimeError("Zero IDs matched; refusing empty mapping")
    OUTPUT.write_text(json.dumps({"source":"TCGCSV / TCGplayer","updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"ids":dict(sorted(ids.items()))},indent=2)+"\n")
    REPORT.write_text(json.dumps({"sets":stats,"review":checks,"mapped":len(ids),"review_count":len(checks)},indent=2)+"\n")
    print(f"Verified product IDs: {len(ids)}; review required: {len(checks)}")
if __name__=="__main__":run()
