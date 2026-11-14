import argparse, json
from .core import Ledger, AdaptiveSearch, export_jsonl

def main():
    ap=argparse.ArgumentParser(description="AutoSemilla adaptive candidate seed search")
    ap.add_argument("--db",default="autosemilla_state/ledger.sqlite")
    ap.add_argument("--benchmark",choices=["invsqrt","dqi","dfthcsos"],default="invsqrt")
    ap.add_argument("--n",type=int,default=64)
    ap.add_argument("--exploration",type=float,default=.30)
    ap.add_argument("--export",default="autosemilla_state/experiments.jsonl")
    args=ap.parse_args(); ledger=Ledger(args.db); search=AdaptiveSearch(ledger,exploration=args.exploration)
    results=search.run(args.benchmark,args.n); promoted=search.promote(args.benchmark,5)
    export_jsonl(ledger,args.export)
    print(json.dumps({"benchmark":args.benchmark,"evaluated":len(results),"history":ledger.count(args.benchmark),
      "promoted_candidates":len(promoted),"best_cheap_candidates":[{"seed_id":s.id,"cheap_score":e.cheap_score,"params":s.params,"reasons":e.reasons} for s,e in results[:5]],
      "export":args.export,"note":"cheap_score is a proxy only; compile and verify promoted seeds with official Kickmix/verifier"},indent=2))
if __name__=="__main__": main()
