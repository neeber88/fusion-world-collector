import json,unittest
from pathlib import Path
from build_price_feed import group_set,print_type,get_subtype_price,make_feed,BASE
class ImportTests(unittest.TestCase):
 def setUp(self):
  self.catalog={'sets':[{'id':'FB11','name':'Brightness of Hope'},{'id':'FS10','name':'Giblet EX'},{'id':'PROMO','name':'Promo'}],'cards':[
   {'set':'FB11','number':'FB11-001','variant':'NORMAL','id':'FB11-001#BASE','name':'Son Goku'},
   {'set':'FB11','number':'FB11-001','variant':'ALT','id':'FB11-001#ALT-1','name':'Son Goku'},
   {'set':'FB11','number':'FB11-002','variant':'ALT','id':'FB11-002#ALT-1','name':'Vegeta'},
   {'set':'FB11','number':'FB11-002','variant':'ALT','id':'FB11-002#ALT-2','name':'Vegeta'}]}
 def test_groups(self):
  groups={x['id']:x for x in self.catalog['sets']}
  self.assertEqual(group_set('Brightness of Hope',groups),'FB11');self.assertEqual(group_set('Brightness of Hope Release Event Cards',groups),None)
  self.assertEqual(group_set('Starter Deck EX 10: Giblet',groups),'FS10')
 def test_ambiguous_safety(self):
  products=[{'productId':10,'name':'Son Goku - FB11-001'}, {'productId':11,'name':'Son Goku - FB11-001 (Alternate Art)'}, {'productId':12,'name':'Vegeta - FB11-002 (Alternate Art)'}, {'productId':13,'name':'Son Goku - FB11-001 (Gold)'}]
  prices=[{'productId':x,'marketPrice':v,'subTypeName':'Normal'} for x,v in ((10,.13),(11,12.35),(12,87.55),(13,999))]
  def mock(url):return {'results':products if url.endswith('/products') else prices}
  result=make_feed(self.catalog,[{'name':'Brightness of Hope','groupId':24716}],mock,0)
  self.assertEqual(result['prices']['FB11-001#BASE']['amount'],.13)
  self.assertEqual(result['prices']['FB11-001#ALT-1']['amount'],12.35)
  self.assertNotIn('FB11-002#ALT-1',result['prices'])
  self.assertNotIn('FB11-002#ALT-2',result['prices'])
  self.assertEqual(len(result['prices']),2)
 def test_mixed_market_subtypes_ignored(self):
  self.assertIsNone(get_subtype_price([{'marketPrice':1.23},{'marketPrice':2.99}]))
if __name__=='__main__':unittest.main()