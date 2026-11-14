"""Import measured Kickmix/verifier outcomes into AutoSemilla's learning ledger.

Input JSONL: one object per tested seed:
{"seed_id":"...","compiled":true,"verified":true,"verifier_status":"PASS",
 "official_metric":123.4,"ranking_value":-123.4,
 "metrics":{"qubits":64,"toffolis":1000},"report_sha256":"..."}

ranking_value MUST already be normalized so larger is better for that benchmark.
A failed or missing verifier result is never marked verified.
"""
from __future__ import annotations
import json
from pathlib import Path
from .core import Ledger

def ingest_kickmix_jsonl(ledger: Ledger, source: str | Path) -> dict[str,int]:
    counts={"compiled":0,"verified":0,"rejected":0,"missing_seed":0}
    with Path(source).open(encoding="utf-8") as stream:
        for line_no,line in enumerate(stream,1):
            if not line.strip(): continue
            row=json.loads(line); sid=row.get("seed_id")
            if not sid:
                counts["missing_seed"]+=1; continue
            compiled=bool(row.get("compiled"))
            verified=compiled and row.get("verified") is True and str(row.get("verifier_status","")).upper() in {"PASS","VERIFIED","SUCCESS"}
            state="verified" if verified else ("compiled" if compiled else "rejected")
            outcome={
                "compiled":compiled,"verified":verified,
                "verifier_status":row.get("verifier_status","UNKNOWN"),
                "official_metric":row.get("official_metric"),
                "ranking_value":row.get("ranking_value") if verified else None,
                "metrics":row.get("metrics",{}),
                "report_sha256":row.get("report_sha256"),
                "source_line":line_no
            }
            if verified and not isinstance(outcome["ranking_value"],(int,float)):
                raise ValueError(f"line {line_no}: verified rows require numeric ranking_value normalized higher-is-better")
            ledger.annotate(sid,state,outcome)
            counts[state]+=1
    return counts
