import json,tempfile,unittest
from pathlib import Path
from autosemilla.core import Seed,Ledger,CheapEvaluator,AdaptiveSearch,export_jsonl,import_jsonl
from autosemilla.kickmix_ingest import ingest_kickmix_jsonl
class TestConsolidated(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.db=Ledger(self.root/"db.sqlite")
 def tearDown(self): self.tmp.cleanup()
 def seed(self,n=1): return Seed("invsqrt","test",{"bits":64,"precision":32,"ancilla":4,"layers":4},n)
 def test_deterministic_id(self):
  a=self.seed(); b=Seed("invsqrt","test",{"layers":4,"ancilla":4,"precision":32,"bits":64},1); self.assertEqual(a.id,b.id)
 def test_search_export_resume_idempotent(self):
  rows=AdaptiveSearch(self.db,seed=4).run("dqi",10); self.assertEqual(len(rows),10)
  p=self.root/"history.jsonl"; export_jsonl(self.db,p); other=Ledger(self.root/"other.sqlite")
  self.assertEqual(import_jsonl(other,p),10); self.assertEqual(import_jsonl(other,p),0)
 def test_verified_rank_and_exploitation(self):
  s=self.seed(); self.db.add(s,CheapEvaluator().evaluate(s))
  self.db.annotate(s.id,"verified",{"compiled":True,"verified":True,"verifier_status":"PASS","ranking_value":42.0})
  self.assertEqual(self.db.top("invsqrt",1)[0]["seed_id"],s.id)
  proposed=AdaptiveSearch(self.db,exploration=0,seed=1).propose("invsqrt",10)
  self.assertTrue(all(x.strategy=="exploit" and x.parent_id==s.id for x in proposed))
 def test_ingestion_known_seed_only(self):
  s=self.seed(); self.db.add(s,CheapEvaluator().evaluate(s)); p=self.root/"results.jsonl"
  p.write_text("\n".join(json.dumps(x) for x in [
   {"seed_id":s.id,"compiled":True,"verified":True,"verifier_status":"PASS","ranking_value":1.0},
   {"seed_id":"unknown","compiled":True,"verified":True,"verifier_status":"PASS","ranking_value":99.0}])+"\n")
  r=ingest_kickmix_jsonl(self.db,p); self.assertEqual(r["verified"],1); self.assertEqual(r["unknown_seed"],1)
 def test_failed_result_cannot_downgrade_verified(self):
  s=self.seed(); self.db.add(s,CheapEvaluator().evaluate(s))
  self.db.annotate(s.id,"verified",{"compiled":True,"verified":True,"verifier_status":"PASS","ranking_value":2.0})
  self.db.annotate(s.id,"rejected",{"compiled":False,"verified":False})
  self.assertEqual(self.db.verified_count(),1)
 def test_bad_schema_rejected(self):
  s=Seed("invsqrt","bad",{"bits":999,"precision":20,"ancilla":0,"layers":2},2)
  self.assertFalse(CheapEvaluator().evaluate(s).valid)
if __name__=="__main__": unittest.main()
