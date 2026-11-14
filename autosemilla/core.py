from __future__ import annotations
import hashlib, json, math, random, sqlite3, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

BENCHMARKS = {"invsqrt", "dqi", "dfthcsos"}

@dataclass(frozen=True)
class Seed:
    benchmark: str
    strategy: str
    params: dict[str, Any]
    seed: int
    generation: int = 0
    parent_id: str | None = None
    def canonical(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
    @property
    def id(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()[:20]

@dataclass
class Evaluation:
    seed_id: str
    valid: bool
    cheap_score: float
    features: dict[str, float]
    reasons: list[str]
    elapsed_ms: float

class Ledger:
    """SQLite-backed experiment history with bounded-memory reads."""
    def __init__(self, path: str | Path):
        self.path = str(path); Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS experiments (
                seed_id TEXT PRIMARY KEY, seed_json TEXT NOT NULL, benchmark TEXT NOT NULL,
                strategy TEXT NOT NULL, valid INTEGER NOT NULL, cheap_score REAL NOT NULL,
                features_json TEXT NOT NULL, reasons_json TEXT NOT NULL,
                elapsed_ms REAL NOT NULL, created_at REAL NOT NULL,
                promotion TEXT NOT NULL DEFAULT 'candidate', outcome_json TEXT)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_exp_bench_score ON experiments(benchmark, valid, cheap_score)")
            db.execute("CREATE TABLE IF NOT EXISTS notes (note_id TEXT PRIMARY KEY, kind TEXT, body TEXT, source_hash TEXT, created_at REAL)")
    def connect(self): return sqlite3.connect(self.path, timeout=30)
    def add(self, seed: Seed, ev: Evaluation):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)",
                (seed.id, seed.canonical(), seed.benchmark, seed.strategy, int(ev.valid), ev.cheap_score,
                 json.dumps(ev.features, sort_keys=True), json.dumps(ev.reasons), ev.elapsed_ms, time.time(), "candidate"))
    def annotate(self, seed_id: str, promotion: str, outcome: dict | None = None):
        if promotion not in {"candidate", "promoted", "compiled", "verified", "rejected"}: raise ValueError("invalid promotion")
        with self.connect() as db:
            db.execute("UPDATE experiments SET promotion=?, outcome_json=? WHERE seed_id=?",
                       (promotion, json.dumps(outcome) if outcome is not None else None, seed_id))
    def add_note(self, kind: str, body: str, source: str = ""):
        digest = hashlib.sha256((kind+"\0"+body+"\0"+source).encode()).hexdigest()
        with self.connect() as db: db.execute("INSERT OR IGNORE INTO notes VALUES (?,?,?,?,?)", (digest,kind,body,source,time.time()))
    def count(self, benchmark: str | None = None) -> int:
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM experiments" + (" WHERE benchmark=?" if benchmark else ""), ((benchmark,) if benchmark else ())).fetchone()[0]
    def top(self, benchmark: str, limit: int = 20) -> list[dict]:
        # Verified results with an explicitly normalized ranking_value outrank proxy-only candidates.
        # ranking_value must be higher-is-better; caller converts the benchmark's official metric.
        with self.connect() as db:
            rows=db.execute("""SELECT seed_json,cheap_score,features_json,promotion,outcome_json
                FROM experiments WHERE benchmark=? AND valid=1
                ORDER BY CASE WHEN promotion='verified' AND json_extract(outcome_json,'$.ranking_value') IS NOT NULL THEN 1 ELSE 0 END DESC,
                CASE WHEN promotion='verified' AND json_extract(outcome_json,'$.ranking_value') IS NOT NULL
                     THEN CAST(json_extract(outcome_json,'$.ranking_value') AS REAL) ELSE cheap_score END DESC LIMIT ?""",(benchmark,limit)).fetchall()
        return [{"seed":json.loads(a),"cheap_score":b,"features":json.loads(c),"promotion":d,
                 "outcome":json.loads(e) if e else None} for a,b,c,d,e in rows]
    def iter_records(self, batch: int = 500):
        with self.connect() as db:
            cur=db.execute("SELECT seed_json,valid,cheap_score,features_json,reasons_json,elapsed_ms,promotion,outcome_json FROM experiments ORDER BY created_at")
            while rows:=cur.fetchmany(batch):
                for row in rows: yield row

class CheapEvaluator:
    """Ranks compact metadata only; no circuits are materialized.

    cheap_score is an exploratory proxy, never an official VQCC score or proof.
    """
    LIMITS = {
      "invsqrt": {"bits": (8, 256), "precision": (8, 64), "ancilla": (0, 256), "layers": (1, 64)},
      "dqi": {"qubits": (8, 2048), "precision": (8, 64), "scratch": (0, 512), "depth_hint": (1, 128)},
      "dfthcsos": {"qubits": (8, 128), "precision": (8, 64), "factor_rank": (1, 256), "tree_width": (1, 128)},
    }
    def evaluate(self, seed: Seed) -> Evaluation:
        t=time.perf_counter(); reasons=[]; p=seed.params
        if seed.benchmark not in BENCHMARKS: reasons.append("unknown_benchmark")
        expected=self.LIMITS.get(seed.benchmark,{})
        if not p: reasons.append("empty_params")
        for key,(lo,hi) in expected.items():
            val=p.get(key)
            if not isinstance(val,(int,float)) or isinstance(val,bool) or not lo <= val <= hi: reasons.append(f"{key}_outside_{lo}_{hi}")
        unknown=set(p)-set(expected)-{"variant","tag"}
        if unknown: reasons.append("unknown_params:"+",".join(sorted(unknown)))
        f={k:float(v) for k,v in p.items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
        if seed.benchmark=="invsqrt":
            score=f.get("precision",0)*1.8 - .32*f.get("bits",999) - .18*f.get("ancilla",999) - .1*f.get("layers",999)
        elif seed.benchmark=="dqi":
            score=f.get("precision",0)*1.5 - .12*f.get("qubits",9999) - .08*f.get("scratch",999) - .04*f.get("depth_hint",999)
        else:
            score=f.get("precision",0)*1.4 - .22*f.get("qubits",9999) - .07*f.get("factor_rank",999) - .06*f.get("tree_width",999)
        elapsed=(time.perf_counter()-t)*1000
        return Evaluation(seed.id,not reasons,float(score) if not reasons else -math.inf,f,reasons,elapsed)

class AdaptiveSearch:
    def __init__(self, ledger: Ledger, evaluator: CheapEvaluator | None=None, exploration: float=.30, seed: int=20261114):
        if not 0 <= exploration <= 1: raise ValueError("exploration must be in [0,1]")
        self.ledger=ledger; self.evaluator=evaluator or CheapEvaluator(); self.exploration=exploration; self.rng=random.Random(seed)
    def _bounds(self, benchmark): return self.evaluator.LIMITS[benchmark]
    def _random_seed(self, benchmark: str, generation: int=0, parent_id: str|None=None) -> Seed:
        spec=self._bounds(benchmark)
        params={k:self.rng.randint(lo,hi) for k,(lo,hi) in spec.items()}
        return Seed(benchmark,"explore",params,self.rng.randrange(2**31),generation,parent_id)
    def _mutate(self, benchmark: str, parent: dict, generation: int) -> Seed:
        base=parent["seed"]; params=dict(base["params"]); spec=self._bounds(benchmark)
        key=self.rng.choice(list(spec)); lo,hi=spec[key]; span=max(1,(hi-lo)//8)
        params[key]=max(lo,min(hi,int(params[key])+self.rng.randint(-span,span)))
        return Seed(benchmark,"exploit",params,self.rng.randrange(2**31),generation,base.get("id"))
    def propose(self, benchmark: str, n: int=32) -> list[Seed]:
        if benchmark not in BENCHMARKS: raise ValueError(f"benchmark must be one of {sorted(BENCHMARKS)}")
        if n<1 or n>10000: raise ValueError("n must be 1..10000")
        elite=self.ledger.top(benchmark, min(30,max(1,n)))
        generation=self.ledger.count(benchmark)//max(1,n)+1; out=[]
        for _ in range(n):
            exploit=bool(elite) and self.rng.random() >= self.exploration
            out.append(self._mutate(benchmark,self.rng.choice(elite),generation) if exploit else self._random_seed(benchmark,generation))
        return out
    def run(self, benchmark: str, n: int=32) -> list[tuple[Seed,Evaluation]]:
        results=[]
        for seed in self.propose(benchmark,n):
            ev=self.evaluator.evaluate(seed); self.ledger.add(seed,ev); results.append((seed,ev))
        return sorted(results,key=lambda x:x[1].cheap_score,reverse=True)
    def promote(self, benchmark: str, limit: int=5) -> list[dict]:
        rows=self.ledger.top(benchmark,limit); promoted=[]
        for row in rows:
            if row["promotion"]=="candidate":
                raw=json.dumps(row["seed"],sort_keys=True,separators=(",",":"))
                sid=hashlib.sha256(raw.encode()).hexdigest()[:20]
                self.ledger.annotate(sid,"promoted"); promoted.append(row)
        return promoted

def export_jsonl(ledger: Ledger, destination: str | Path) -> int:
    """Stream history to portable JSONL without loading all records into memory."""
    count=0; dst=Path(destination); dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("w",encoding="utf-8") as f:
        for row in ledger.iter_records():
            seed,valid,score,features,reasons,elapsed,promotion,outcome=row
            f.write(json.dumps({"seed":json.loads(seed),"valid":bool(valid),"cheap_score":score,"features":json.loads(features),"reasons":json.loads(reasons),"elapsed_ms":elapsed,"promotion":promotion,"outcome":json.loads(outcome) if outcome else None},sort_keys=True)+"\n"); count+=1
    return count

def import_jsonl(ledger: Ledger, source: str | Path) -> int:
    added=0
    with Path(source).open(encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            r=json.loads(line); s=r["seed"]; seed=Seed(s["benchmark"],s["strategy"],s["params"],s["seed"],s.get("generation",0),s.get("parent_id"))
            ev=Evaluation(seed.id,r["valid"],r["cheap_score"],r["features"],r["reasons"],r["elapsed_ms"]); before=ledger.count(); ledger.add(seed,ev); added+=ledger.count()-before
            if r.get("promotion")!="candidate": ledger.annotate(seed.id,r["promotion"],r.get("outcome"))
    return added
