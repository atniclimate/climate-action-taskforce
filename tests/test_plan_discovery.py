import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('merge',Path(__file__).parents[1]/'scripts/merge_plan_discovery.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class DiscoveryTests(unittest.TestCase):
    def test_public_projection_keeps_raw_evidence_local(self):
        raw='Nation A is named in the search excerpt: Plan title \ue200cite\ue202example\ue201 [wordlim: 200] This is a placeholder section.'
        candidate={'discovery_note':raw,'relationship_evidence':raw,'host_relationship':None,'date_evidence':None,'relationships':[{'evidence':raw,'host_relationship':None}]}
        result={'candidates':[candidate]}
        public=m.participant_projection(result)['candidates'][0]
        self.assertIn('placeholder',public['relationship_evidence'])
        self.assertNotIn('\ue200',str(public))
        self.assertNotIn('discovery_note',public)
        self.assertEqual(candidate['discovery_note'],raw)
    def test_receipt_timestamp_precision(self):
        m.validate_times({'searched_at':'2026-10-21','receipt':{'checked_utc':'2026-10-21T12:25:14Z'}})
        with self.assertRaises(ValueError):
            m.validate_times({'receipt':{'checked_utc':'2026-10-21T12:65:00Z'}})
    def test_shared_url_preserves_relationships(self):
        public={}
        for tid, evidence in [('nation-a','A participates'),('nation-b','B participates')]:
            m.add_relationship(public,{'id':tid,'tribe_ids':[tid],'document_class':m.CLASSES[0],'relationship_evidence':evidence})
        self.assertEqual(public['relationship_evidence'],['A participates','B participates'])
        self.assertEqual(public['relationships'][1]['tribe_ids'],['nation-b'])
    def test_dates_require_evidence_and_keep_unknown(self):
        self.assertEqual(m.age({'publication_year':2024})['age_bin'],'Unknown')
        self.assertEqual(m.age({'publication_year':2020,'date_evidence':['title page']})['age_bin'],'6–10 years')
        self.assertEqual(m.age({'publication_year':2010,'update_year':2021,'date_evidence':['updated edition']})['age_bin'],'0–5 years')
        self.assertEqual(m.age({'adoption_date':'2015-06-01','publication_year':2024,'date_evidence':['resolution']})['age_bin'],'Over 10 years')
        self.assertEqual(m.age({'publication_year':2027,'date_evidence':['future plan']})['age_bin'],'Unknown')
    def test_blocked_class_prevents_definite_gap(self):
        cats={c:{'outcome':'no_matching_public_document_located'} for c in m.CLASSES}
        risk={'high_risk':True,'coverage_status':'evaluated'}
        self.assertEqual(len(m.attention(risk,cats)),3)
        cats[m.CLASSES[1]]['outcome']='blocked'
        self.assertEqual(m.attention(risk,cats),[])
        cats[m.CLASSES[1]]['outcome']='found'
        self.assertEqual(len(m.attention(risk,cats)),2)
        self.assertEqual(m.attention({'high_risk':False},cats),[])
    def test_url_boundary(self):
        self.assertEqual(m.public_url('https://EXAMPLE.org/Plan.pdf#page=4'),'https://example.org/Plan.pdf')
        self.assertEqual(m.public_url('https://example.org/plan?v=2'),'https://example.org/plan?v=2')
        for url in ['javascript:alert(1)','file:///I:/private','https://user:pass@example.org/','http://localhost/data']:
            with self.assertRaises(ValueError):m.public_url(url)

if __name__=='__main__':unittest.main()
