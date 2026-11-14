"""Fail-closed ingestion of measured Kickmix/verifier outcomes. Does not run Kickmix."""
import json,math
from pathlib import Path
from .core import Ledger

VALID={"PASS","VERIFIED","SUCCESS"}
def ingest_kickmix_jsonl(ledger:Ledger,source):
    counts={"compiled":0,"verified":0,"rejected":0,"missing_seed":0,"unknown_seed":0}
    with Path(source).open(encoding="utf-8") as f:
        for line_no,line in enumerate(f,1):
            if not line.strip(): continue
            try: row=json.loads(line)
            except Exception as exc: raise ValueError(f"invalid JSON at line {line_no}: {exc}") from exc
            sid=row.get("seed_id")
            if not sid: counts["missing_seed"]+=1; continue
            if not ledger.exists(sid): counts["unknown_seed"]+=1; continue
            compiled=row.get("compiled") is True
            verified=compiled and row.get("verified") is True and str(row.get("verifier_status","")).upper() in VALID
            state="verified" if verified else ("compiled" if compiled else "rejected")
            rank=row.get("ranking_value")
            if verified and (not isinstance(rank,(int,float)) or isinstance(rank,bool) or not math.isfinite(float(rank))):
                raise ValueError(f"line {line_no}: verified result requires finite ranking_value (higher is better)")
            digest=row.get("report_sha256")
            if digest is not None and (not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdefABCDEF" for c in digest)):
                raise ValueError(f"line {line_no}: report_sha256 must be 64 hex characters")
            outcome={"compiled":compiled,"verified":verified,"verifier_status":row.get("verifier_status","UNKNOWN"),
              "official_metric":row.get("official_metric"),"ranking_value":rank if verified else None,
              "metrics":row.get("metrics",{}),"report_sha256":digest,"source_line":line_no}
            ledger.annotate(sid,state,outcome); counts[state]+=1
    return counts
