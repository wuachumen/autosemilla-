# AutoSemilla 3.0 — Adaptive VQCC Seed Search

AutoSemilla searches for **potentially useful parameter seeds**. It does not generate complete circuits, claim official scores, compile Kickmix artifacts, or replace the competition verifier. Promoted candidates must be compiled and verified separately.

## Design

1. Generate a compact, deterministic seed (benchmark, strategy, parameters, RNG seed, generation and optional parent).
2. Apply low-cost parameter/constraint checks and compute a benchmark-specific **proxy ranking**. No circuit object is constructed in this stage.
3. Persist each attempt in SQLite (WAL, indexed, append-oriented) including invalid attempts and reasons.
4. Balance exploration and exploitation; exploitation mutates historical promising seeds, exploration samples new parameter regions. The default 30% exploration is a tunable starting point, not a learned optimum.
5. Promote a small shortlist for an external Kickmix compilation and official verification stage.
6. Record external outcomes and export/import JSONL to resume across Kaggle sessions.

## Important score boundary

`cheap_score` is only an inexpensive heuristic used to order candidates. It is **not** the VQCC objective and does not establish correctness. Calibrate the proxy against observed official Kickmix results; do not report it as competition performance.

## Quick start

```bash
python -m autosemilla.cli --benchmark invsqrt --n 128
python -m autosemilla.cli --benchmark dqi --n 128 --db state/ledger.sqlite --export state/experiments.jsonl
python -m autosemilla.cli --benchmark dfthcsos --n 128
python -m unittest discover -s tests -v
```

Python 3.10+, standard library only.

## Kaggle persistence

Attach the previous private dataset as an input, import its `experiments.jsonl`, run a batch, then export a new version. Do **not** upload after every seed: checkpoint after a batch (for example every 100–500 candidates or at notebook end).

```python
from autosemilla.core import Ledger, AdaptiveSearch, import_jsonl, export_jsonl
ledger = Ledger('/kaggle/working/autosemilla/ledger.sqlite')
# Import the previous dataset's experiments.jsonl once:
# import_jsonl(ledger, '/kaggle/input/autosemilla/experiments.jsonl')
search = AdaptiveSearch(ledger, exploration=0.30)
ranked = search.run('invsqrt', n=200)
export_jsonl(ledger, '/kaggle/working/autosemilla/experiments.jsonl')
```

The `autosemilla.kaggle_sync.publish_dataset` helper calls the Kaggle CLI to create a dataset version when API credentials and permissions are configured. Verify private visibility in Kaggle dataset settings; the helper does not override privacy settings. Dataset versions are batch checkpoints, not per-candidate writes.

## Resource profile

- Candidate metadata only; no expanded circuit graphs or statevectors.
- SQLite disk-backed ledger; JSONL export/import streams records.
- Candidate count capped per invocation (1–10,000).
- No GPU, QPU, network, or third-party model is needed for search.

## Reproducibility and provenance

The canonical seed is JSON-serialized with sorted keys; its ID is a SHA-256 prefix. The RNG seed and parent seed ID are stored. Keep source documents/experiment notes with their SHA-256 in the notes table. Retain original Kickmix output, verifier report, and source version separately; attach compact measured metrics as external outcomes.

## Benchmark parameter schema

- `invsqrt`: `bits`, `precision`, `ancilla`, `layers`.
- `dqi`: `qubits`, `precision`, `scratch`, `depth_hint`.
- `dfthcsos`: `qubits`, `precision`, `factor_rank`, `tree_width`.

These are search controls / coarse descriptors, not a claim that the schema models every benchmark's complete circuit-generation constraints. Extend them only after mapping to actual Kickmix inputs and empirical outcomes.
