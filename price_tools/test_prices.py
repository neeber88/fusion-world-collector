import json,unittest
from pathlib import Path
from build_price_feed import group_set,print_type,get_subtype_price,make_feed,canonical_number,printed_name,BASE
class ImportTests(unittest.TestCase):
 def setUp(self):
  self.catalog={'sets':[{'id':'FB11','name':'Brightness of Hope'},{'id':'FS10','name':'Giblet EX'},{'id':'PROMO','name':'Promo'},{'id':'ENERGY','name':'Energy Marker'}],'cards':[
   {'set':'FB11','number':'FB11-001','variant':'NORMAL','id':'FB11-001#BASE','name':'Son Goku'},
   {'set':'FB11','number':'FB11-001','variant':'ALT','id':'FB11-001#ALT-1','name':'Son Goku'},
   {'set':'FB11','number':'FB11-002','variant':'ALT','id':'FB11-002#ALT-1','name':'Vegeta'},
   {'set':'FB11','number':'FB11-002','variant':'ALT','id':'FB11-002#ALT-2','name':'Vegeta'},
   {'set':'PROMO','number':'FP-001','variant':'NORMAL','id':'FP-001#BASE','name':'Son Goku'},
   {'set':'PROMO','number':'FB11-003','variant':'ALT','id':'FB11-003#ALT-1','name':'Gotenks'},
   {'set':'ENERGY','number':'E-123','variant':'NORMAL','id':'E-123#BASE','name':'Energy Marker'}]}
 def test_groups(self):
  groups={x['id']:x for x in self.catalog['sets']}
  self.assertEqual(group_set('Brightness of Hope',groups),'FB11');self.assertEqual(group_set('Brightness of Hope Release Event Cards',groups),None)
  self.assertEqual(group_set('Starter Deck EX 10: Giblet',groups),'FS10')
  self.assertEqual(group_set('Fusion World Promotion Cards and Packs',groups),'PROMO')
  self.assertEqual(group_set('Tournament and Championship Promos',groups),'PROMO')
  self.assertEqual(group_set('Fusion World Energy Markers',groups),'ENERGY')
  self.assertIsNone(group_set('Awakened Pulse Alternate Art Reprints',groups))
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
 def test_promos_and_energy_separate_from_boosters(self):
  groups=[{'name':'Fusion World Promotion Cards and Packs','groupId':1},
          {'name':'Fusion World Energy Markers','groupId':2},
          {'name':'Brightness of Hope','groupId':3}]
  products={1:[{'productId':21,'name':'Son Goku - FP-001'},
               {'productId':22,'name':'Gotenks - FB11-003 (Alternate Art)'}],
            2:[{'productId':23,'name':'Energy Marker (E-123)'}],
            3:[{'productId':24,'name':'Son Goku - FB11-001'}]}
  prices={i:[{'productId':p['productId'],'marketPrice':i+0.5} for p in products[i]] for i in products}
  def fake(url):
   gid=int(url.split('/')[-2]);return {'results':products[gid] if url.endswith('/products') else prices[gid]}
  data=make_feed(self.catalog,groups,fake,0)['prices']
  self.assertEqual(data['FP-001#BASE']['amount'],1.5)
  self.assertEqual(data['FB11-003#ALT-1']['amount'],1.5)
  self.assertEqual(data['E-123#BASE']['amount'],2.5)
  self.assertEqual(data['FB11-001#BASE']['amount'],3.5)
  self.assertNotIn('FB11-001#ALT-1',data)
 def test_conflict_across_promo_groups_blocks_key(self):
  groups=[{'name':'Fusion World Promotion Cards and Packs','groupId':1},
          {'name':'Tournament and Championship Promos','groupId':2},
          {'name':'Fusion World Promotion Cards and Packs','groupId':3}]
  def fake(url):
   gid=int(url.split('/')[-2]);
   return {'results':[{'productId':100+gid,'name':'Son Goku - FP-001'}] if url.endswith('/products')
     else [{'productId':100+gid,'marketPrice':gid}]}
  data=make_feed(self.catalog,groups,fake,0)['prices']
  self.assertNotIn('FP-001#BASE',data)
 def test_number_format_padding(self):
  self.assertEqual(canonical_number('E-002'),canonical_number('E-2'))
  self.assertEqual(canonical_number('FS01-016'),canonical_number('FS01-16'))
  self.assertEqual(canonical_number('FP-001'),canonical_number('FP-1'))
 def test_alt_qualifiers_are_not_character_names(self):
  self.assertEqual(printed_name({'name':'Whis (Bonus Pack Alternate Art)','extendedData':[{'name':'Number','value':'FS01-02'}]},'FS01-02'),'Whis')
  self.assertEqual(printed_name({'name':'Son Goku - FB01-139 (Alternate Art)'},'FB01-139'),'Son Goku')
  self.assertEqual(printed_name({'name':'Shallet (Super Alternate Art)'},'FB11-122'),'Shallet')
  self.assertEqual(printed_name({'name':'Son Gohan : Adolescence (Bonus Pack Alternate Art)'},'FS01-09'),'Son Gohan : Adolescence')
 def test_bonus_pack_alts_match_only_the_single_exact_card(self):
  catalogue={'sets':[{'id':'FS01','name':'Son Goku'}],'cards':[{'set':'FS01','number':'FS01-02','variant':'NORMAL','id':'FS01-02#BASE','name':'Whis'},{'set':'FS01','number':'FS01-02','variant':'ALT','id':'FS01-02#ALT-1','name':'Whis'}]}
  products=[{'productId':900,'name':'Whis (Bonus Pack Alternate Art)','extendedData':[{'name':'Number','value':'FS01-02'}]}]
  prices=[{'productId':900,'marketPrice':12.25,'subTypeName':'Normal'}]
  def mock(url):return {'results':products if url.endswith('/products') else prices}
  result=make_feed(catalogue,[{'name':'Starter Deck 01','groupId':1}],mock,0)
  self.assertNotIn('FS01-02#BASE',result['prices'])
  self.assertEqual(result['prices']['FS01-02#ALT-1']['amount'],12.25)
 def test_mixed_market_subtypes_ignored(self):
  self.assertIsNone(get_subtype_price([{'marketPrice':1.23},{'marketPrice':2.99}]))
if __name__=='__main__':unittest.main()