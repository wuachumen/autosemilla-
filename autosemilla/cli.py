import argparse,json
from .core import Ledger,AdaptiveSearch,export_jsonl
def main():
    ap=argparse.ArgumentParser(description="AutoSemilla VQCC candidate search")
    ap.add_argument("--db",default="state/ledger.sqlite")
    ap.add_argument("--benchmark",choices=["invsqrt","dqi","dfthcsos"],default="invsqrt")
    ap.add_argument("--n",type=int,default=64)
    ap.add_argument("--exploration",type=float,default=.30)
    ap.add_argument("--export",default="state/experiments.jsonl")
    a=ap.parse_args(); ledger=Ledger(a.db); search=AdaptiveSearch(ledger,exploration=a.exploration)
    rows=search.run(a.benchmark,a.n); promoted=search.promote(a.benchmark,5); export_jsonl(ledger,a.export)
    print(json.dumps({"benchmark":a.benchmark,"evaluated":len(rows),"history":ledger.count(a.benchmark),
      "verified_history":ledger.verified_count(a.benchmark),"promoted":len(promoted),
      "best_proxy":[{"seed_id":s.id,"proxy_score":e.cheap_score,"params":s.params} for s,e in rows[:5]],
      "export":a.export,"warning":"proxy_score is not the official VQCC score"},indent=2))
if __name__=="__main__": main()
