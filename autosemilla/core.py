from __future__ import annotations
import hashlib,json,math,random,sqlite3,time
from contextlib import contextmanager
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Any

BENCHMARKS={"invsqrt","dqi","dfthcsos"}

@dataclass(frozen=True)
class Seed:
    benchmark:str
    strategy:str
    params:dict[str,Any]
    seed:int
    generation:int=0
    parent_id:str|None=None
    def canonical(self): return json.dumps(asdict(self),sort_keys=True,separators=(",",":"))
    @property
    def id(self): return hashlib.sha256(self.canonical().encode()).hexdigest()[:20]

@dataclass
class Evaluation:
    seed_id:str
    valid:bool
    cheap_score:float
    features:dict[str,float]
    reasons:list[str]
    elapsed_ms:float

class Ledger:
    def __init__(self,path):
        self.path=str(path); Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS experiments(
              seed_id TEXT PRIMARY KEY,seed_json TEXT NOT NULL,benchmark TEXT NOT NULL,strategy TEXT NOT NULL,
              valid INTEGER NOT NULL,cheap_score REAL NOT NULL,features_json TEXT NOT NULL,reasons_json TEXT NOT NULL,
              elapsed_ms REAL NOT NULL,created_at REAL NOT NULL,promotion TEXT NOT NULL DEFAULT 'candidate',
              outcome_json TEXT,ranking_value REAL,official_verified INTEGER NOT NULL DEFAULT 0)""")
            cols={r[1] for r in db.execute("PRAGMA table_info(experiments)")}
            if "ranking_value" not in cols: db.execute("ALTER TABLE experiments ADD COLUMN ranking_value REAL")
            if "official_verified" not in cols: db.execute("ALTER TABLE experiments ADD COLUMN official_verified INTEGER NOT NULL DEFAULT 0")
            db.execute("CREATE INDEX IF NOT EXISTS idx_exp_verified ON experiments(benchmark,official_verified,ranking_value)")
            db.execute("CREATE TABLE IF NOT EXISTS notes(note_id TEXT PRIMARY KEY,kind TEXT,body TEXT,source_hash TEXT,created_at REAL)")
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            yield db; db.commit()
        except Exception:
            db.rollback(); raise
        finally: db.close()
    def add(self,s,e):
        with self.connect() as db:
            cur=db.execute("""INSERT OR IGNORE INTO experiments
              (seed_id,seed_json,benchmark,strategy,valid,cheap_score,features_json,reasons_json,elapsed_ms,created_at,promotion)
              VALUES(?,?,?,?,?,?,?,?,?,?,'candidate')""",
              (s.id,s.canonical(),s.benchmark,s.strategy,int(e.valid),e.cheap_score,json.dumps(e.features,sort_keys=True),
               json.dumps(e.reasons),e.elapsed_ms,time.time()))
            return cur.rowcount==1
    def annotate(self,sid,state,outcome=None):
        if state not in {"candidate","promoted","compiled","verified","rejected"}: raise ValueError("invalid state")
        with self.connect() as db:
            old=db.execute("SELECT official_verified FROM experiments WHERE seed_id=?",(sid,)).fetchone()
            if not old: raise KeyError("unknown seed_id: "+sid)
            good=bool(outcome and outcome.get("compiled") is True and outcome.get("verified") is True
              and str(outcome.get("verifier_status","")).upper() in {"PASS","VERIFIED","SUCCESS"}
              and isinstance(outcome.get("ranking_value"),(int,float)) and not isinstance(outcome.get("ranking_value"),bool)
              and math.isfinite(float(outcome["ranking_value"])))
            if old[0] and not good: return
            db.execute("UPDATE experiments SET promotion=?,outcome_json=?,ranking_value=?,official_verified=? WHERE seed_id=?",
              ("verified" if good else state,json.dumps(outcome,sort_keys=True) if outcome is not None else None,
               float(outcome["ranking_value"]) if good else None,int(good),sid))
    def add_note(self,kind,body,source=""):
        h=hashlib.sha256((kind+"\0"+body+"\0"+source).encode()).hexdigest()
        with self.connect() as db: db.execute("INSERT OR IGNORE INTO notes VALUES(?,?,?,?,?)",(h,kind,body,source,time.time()))
    def count(self,b=None):
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM experiments"+(" WHERE benchmark=?" if b else ""),( (b,) if b else () )).fetchone()[0]
    def verified_count(self,b=None):
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM experiments WHERE official_verified=1"+(" AND benchmark=?" if b else ""),( (b,) if b else () )).fetchone()[0]
    def exists(self,sid):
        with self.connect() as db: return db.execute("SELECT 1 FROM experiments WHERE seed_id=?",(sid,)).fetchone() is not None
    def top(self,b,limit=20,verified_only=False):
        if limit<1:return []
        where="benchmark=? AND valid=1"+(" AND official_verified=1" if verified_only else "")
        with self.connect() as db:
            rows=db.execute(f"""SELECT seed_id,seed_json,cheap_score,features_json,promotion,ranking_value,
              official_verified,outcome_json FROM experiments WHERE {where}
              ORDER BY official_verified DESC,ranking_value DESC,cheap_score DESC LIMIT ?""",(b,limit)).fetchall()
        return [dict(seed_id=r[0],seed=json.loads(r[1]),cheap_score=r[2],features=json.loads(r[3]),promotion=r[4],
          ranking_value=r[5],official_verified=bool(r[6]),outcome=json.loads(r[7]) if r[7] else None) for r in rows]
    def iter_records(self,batch=500):
        with self.connect() as db:
            cur=db.execute("SELECT seed_json,valid,cheap_score,features_json,reasons_json,elapsed_ms,promotion,outcome_json FROM experiments ORDER BY created_at")
            while rows:=cur.fetchmany(batch):
                for row in rows: yield row

class CheapEvaluator:
    LIMITS={"invsqrt":{"bits":(8,256),"precision":(8,64),"ancilla":(0,256),"layers":(1,64)},
      "dqi":{"qubits":(8,2048),"precision":(8,64),"scratch":(0,512),"depth_hint":(1,128)},
      "dfthcsos":{"qubits":(8,128),"precision":(8,64),"factor_rank":(1,256),"tree_width":(1,128)}}
    def evaluate(self,s):
        t=time.perf_counter(); p=s.params; reasons=[]; spec=self.LIMITS.get(s.benchmark,{})
        if s.benchmark not in BENCHMARKS: reasons.append("unknown_benchmark")
        if not p: reasons.append("empty_params")
        for k,(lo,hi) in spec.items():
            v=p.get(k)
            if not isinstance(v,(int,float)) or isinstance(v,bool) or not lo<=v<=hi: reasons.append(f"{k}_outside_{lo}_{hi}")
        unknown=set(p)-set(spec)-{"variant","tag"}
        if unknown: reasons.append("unknown_params:"+",".join(sorted(unknown)))
        f={k:float(v) for k,v in p.items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
        if s.benchmark=="invsqrt": score=f.get("precision",0)*1.8-.32*f.get("bits",999)-.18*f.get("ancilla",999)-.1*f.get("layers",999)
        elif s.benchmark=="dqi": score=f.get("precision",0)*1.5-.12*f.get("qubits",9999)-.08*f.get("scratch",999)-.04*f.get("depth_hint",999)
        else: score=f.get("precision",0)*1.4-.22*f.get("qubits",9999)-.07*f.get("factor_rank",999)-.06*f.get("tree_width",999)
        return Evaluation(s.id,not reasons,float(score) if not reasons else -math.inf,f,reasons,(time.perf_counter()-t)*1000)

class AdaptiveSearch:
    def __init__(self,ledger,evaluator=None,exploration=.30,seed=20261114):
        if not 0<=exploration<=1: raise ValueError("exploration must be in [0,1]")
        self.ledger=ledger; self.evaluator=evaluator or CheapEvaluator(); self.exploration=exploration; self.rng=random.Random(seed)
    def _random(self,b,g,parent=None):
        params={k:self.rng.randint(lo,hi) for k,(lo,hi) in self.evaluator.LIMITS[b].items()}
        return Seed(b,"explore",params,self.rng.randrange(2**31),g,parent)
    def _mutate(self,b,parent,g):
        base=parent["seed"]; p=dict(base["params"]); spec=self.evaluator.LIMITS[b]; k=self.rng.choice(list(spec)); lo,hi=spec[k]
        span=max(1,(hi-lo)//8); p[k]=max(lo,min(hi,int(p[k])+self.rng.randint(-span,span)))
        return Seed(b,"exploit",p,self.rng.randrange(2**31),g,parent["seed_id"])
    def propose(self,b,n=32):
        if b not in BENCHMARKS: raise ValueError("unknown benchmark")
        if not 1<=n<=10000: raise ValueError("n must be 1..10000")
        elite=self.ledger.top(b,min(30,n),True); g=self.ledger.count(b)//n+1; out=[]
        for _ in range(n):
            use=bool(elite) and self.rng.random()>=self.exploration
            out.append(self._mutate(b,self.rng.choice(elite),g) if use else self._random(b,g))
        return out
    def run(self,b,n=32):
        out=[]
        for s in self.propose(b,n):
            e=self.evaluator.evaluate(s); self.ledger.add(s,e); out.append((s,e))
        return sorted(out,key=lambda x:x[1].cheap_score,reverse=True)
    def promote(self,b,limit=5):
        rows=[r for r in self.ledger.top(b,max(limit*5,limit)) if not r["official_verified"]][:limit]; out=[]
        for r in rows:
            if r["promotion"]=="candidate": self.ledger.annotate(r["seed_id"],"promoted"); out.append(r)
        return out

def export_jsonl(ledger,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); n=0
    with path.open("w",encoding="utf-8") as f:
        for r in ledger.iter_records():
            seed,valid,score,features,reasons,elapsed,state,outcome=r
            f.write(json.dumps({"seed":json.loads(seed),"valid":bool(valid),"cheap_score":score,"features":json.loads(features),
              "reasons":json.loads(reasons),"elapsed_ms":elapsed,"promotion":state,"outcome":json.loads(outcome) if outcome else None},
              sort_keys=True,allow_nan=False)+"\n"); n+=1
    return n

def import_jsonl(ledger,path):
    n=0
    with Path(path).open(encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip(): continue
            try:
                r=json.loads(line); x=r["seed"]; s=Seed(x["benchmark"],x["strategy"],x["params"],x["seed"],x.get("generation",0),x.get("parent_id"))
                e=Evaluation(s.id,bool(r["valid"]),float(r["cheap_score"]),r["features"],r["reasons"],float(r["elapsed_ms"]))
            except Exception as exc: raise ValueError(f"invalid AutoSemilla JSONL line {i}: {exc}") from exc
            if ledger.add(s,e): n+=1
            if r.get("promotion") in {"promoted","compiled","verified","rejected"}: ledger.annotate(s.id,r["promotion"],r.get("outcome"))
    return n
