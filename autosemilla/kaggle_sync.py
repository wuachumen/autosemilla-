"""Prepare a checkpoint. Dataset publication is an explicit separate action."""
from pathlib import Path
from .core import export_jsonl
def prepare_checkpoint(ledger,working_dir):
    root=Path(working_dir); root.mkdir(parents=True,exist_ok=True)
    p=root/"experiments.jsonl"; n=export_jsonl(ledger,p)
    return {"path":str(p),"records":n}
