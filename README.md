# AutoSemilla — consolidated VQCC engine

This branch consolidates the accessible AutoSemilla code and hardens its evidence loop. It does **not** claim to restore the historical `results-6.zip` package, its missing operators or `kickmix.so`; that archive was not available to this build.

## What is implemented
- Deterministic candidate IDs and parent lineage.
- SQLite WAL ledger, schema migration, idempotent JSONL export/import.
- Cheap schema/range gate without circuit materialization.
- Exploration until real verified outcomes exist; exploitation mutates only officially verified parents.
- Fail-closed Kickmix/verifier result ingestion: exact seed ID, explicit booleans, accepted verifier status and finite normalized score.
- Officially verified outcomes rank above proxy candidates and cannot be downgraded by a later failure.
- Checkpoint preparation is separate from Kaggle dataset publication; no license or privacy metadata is silently changed.

## Critical limits
`cheap_score` is a proxy, never the official competition score. Current parameter descriptors are not mapped to the historical circuit transformations. This branch does not yet invoke `kickmix.so`, rewrite `.kmb` circuits, or execute official verifiers. The verification notebook tests the engine and discovers competition inputs; it reports official verification as PENDING until real artifacts are available and a documented verifier invocation is run.

## Run
```bash
python -m unittest discover -s tests -v
python -m autosemilla.cli --benchmark invsqrt --n 128
python -m autosemilla.cli --benchmark dqi --n 128
python -m autosemilla.cli --benchmark dfthcsos --n 128
```
Python 3.10+, standard library only.

## Kickmix result format
One JSON object per tested seed in `kickmix_results.jsonl`:
```json
{"seed_id":"<exact-id>","compiled":true,"verified":true,"verifier_status":"PASS","official_metric":123.4,"ranking_value":123.4,"metrics":{"qubits":64},"report_sha256":"<64-hex>"}
```
Normalize `ranking_value` so higher is better within that benchmark. It must be the actual official metric, never a proxy. Keep original artifacts and verifier reports separately.

## Kaggle
Attach the private history dataset and official competition inputs. Run `notebooks/AutoSemilla_VQCC_Verification.ipynb`. Inspect the inventory, run the official verifier using its actual documented CLI, and ingest the resulting evidence on the next run. Publish a new private dataset version only after reviewing contents and visibility. No QPU is needed for classical Kickmix verification.
