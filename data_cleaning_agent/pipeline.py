"""Readiness is explicit; unfinished stages never masquerade as successful ones."""

STAGE_STATUS = {
    "schema": "implemented; requires prepared input; cross-file reconciliation pending",
    "structured": "not implemented",
    "categories": "implemented for selected scalar values; requires prepared input",
    "text": "implemented; optional heuristic enrichment and masking",
    "validation": "not implemented",
    "privacy": "preparation/restoration not implemented; prepared-input boundary only",
}


def run_pipeline(*args, **kwargs):
    raise NotImplementedError(
        "Full pipeline is not ready: privacy preparation/restoration, structured-data "
        "normalization, and final validation are missing. Run individual stages instead."
    )
