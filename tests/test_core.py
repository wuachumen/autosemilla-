import tempfile, unittest
from pathlib import Path
from autosemilla.core import Seed, Ledger, CheapEvaluator, AdaptiveSearch, export_jsonl, import_jsonl

class TestAutoSemilla(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.ledger=Ledger(Path(self.tmp.name)/"state.sqlite")
    def tearDown(self): self.tmp.cleanup()
    def test_seed_deterministic(self):
        a=Seed("invsqrt","x",{"bits":64,"precision":32,"ancilla":4,"layers":4},1)
        b=Seed("invsqrt","x",{"layers":4,"ancilla":4,"precision":32,"bits":64},1)
        self.assertEqual(a.id,b.id)
    def test_invalid_rejected(self):
        s=Seed("invsqrt","x",{"bits":999,"precision":32,"ancilla":4,"layers":4},1)
        self.assertFalse(CheapEvaluator().evaluate(s).valid)
    def test_search_and_resume(self):
        search=AdaptiveSearch(self.ledger,seed=4); rows=search.run("dqi",10)
        self.assertEqual(len(rows),10); self.assertEqual(self.ledger.count("dqi"),10)
        path=Path(self.tmp.name)/"memory.jsonl"; export_jsonl(self.ledger,path)
        other=Ledger(Path(self.tmp.name)/"other.sqlite"); self.assertEqual(import_jsonl(other,path),10)
        self.assertEqual(other.count("dqi"),10)
    def test_no_circuit_build(self):
        s=Seed("dfthcsos","x",{"qubits":32,"precision":24,"factor_rank":8,"tree_width":4},4)
        ev=CheapEvaluator().evaluate(s); self.assertTrue(ev.valid); self.assertLess(ev.elapsed_ms,100)

if __name__=="__main__": unittest.main()
