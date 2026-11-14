from __future__ import annotations
import os, subprocess, sys, json
from pathlib import Path
from .core import Ledger, export_jsonl

def publish_dataset(ledger: Ledger, working_dir: str|Path, dataset_slug: str, message: str) -> Path:
    """Prepare and publish one Kaggle dataset version after a batch.

    Kaggle credentials must already be configured by Kaggle Secrets/API.
    Dataset privacy is controlled in Kaggle settings, not this function.
    """
    if not dataset_slug or "/" not in dataset_slug: raise ValueError("dataset_slug must be owner/dataset")
    root=Path(working_dir); root.mkdir(parents=True,exist_ok=True)
    data=root/"experiments.jsonl"; export_jsonl(ledger,data)
    metadata={"title":"AutoSemilla experiment memory","id":dataset_slug,
              "licenses":[{"name":"CC0-1.0"}],
              "keywords":["quantum","circuit-compilation","seed-search"]}
    (root/"dataset-metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    cmd=[sys.executable,"-m","kaggle","datasets","version","-p",str(root),"-m",message,"--dir-mode","zip"]
    p=subprocess.run(cmd,text=True,capture_output=True)
    if p.returncode:
        raise RuntimeError("Kaggle dataset version failed. Check Kaggle API setup and dataset ownership. "+p.stderr[-1500:])
    return data
