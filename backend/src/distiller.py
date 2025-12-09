"""Thin wrapper for the canonical Distiller implementation.

This module intentionally re-exports the canonical implementation in
`core.distiller_impl` so that external callers can import `core.distiller`
without depending on a specific implementation file.
"""
from .distiller_impl import (
	DistilledEntity,
	DistilledMoment,
	Distiller,
	distill_moment,
	annotate_chunk,
	_safe_validate_moment,
	filter_and_consolidate,
	make_compact_summary,
)

__all__ = [
	"DistilledEntity",
	"DistilledMoment",
	"Distiller",
	"distill_moment",
	"annotate_chunk",
	"_safe_validate_moment",
	"filter_and_consolidate",
	"make_compact_summary",
]
