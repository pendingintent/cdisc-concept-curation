"""MCP server exposing cdisc-concept-curation data as tools.

Run via ``python -m mcp_server``. The server communicates over stdio and
is registered in ``.mcp.json`` for automatic pickup by Claude Code.

Handlers run inside a Flask app context (the app factory is shared with
the web app, so both processes resolve the same instance/ SQLite file)
and use the same ORM models and service clients as the routes.

Read tools (8):
  list_bcs              Search/paginate curated Biomedical Concepts
  get_bc                Full BC detail incl. DECs, specializations, governance
  search_ncit           Search the NCI Thesaurus (EVS)
  get_ncit_concept      Full NCIt concept detail
  search_loinc          Search LOINC via NLM Clinical Tables
  search_cdisc_library  Search published BCs in the CDISC Library
  get_library_bc        Fetch one published BC from the CDISC Library
  list_review_queue     Governance board summary + pending ingestion count

Write tools (6) — same service code path as the web routes, every write
audited; actor defaults to "mcp" so agent writes are distinguishable:
  create_bc             Create a provisional BC (optionally with DECs)
  update_bc             Update BC fields
  map_ncit_to_bc        Attach an NCIt code (promotes IMPORT_ ids)
  submit_bc_for_review  provisional -> sme_review
  advance_governance    Advance one governance stage
  reject_bc             Reject back to provisional
"""

import asyncio
import functools
import json
import logging
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

logger = logging.getLogger("cdisc_curation.mcp")

server = Server("cdisc-curation")

# Lazy app singleton. Tests inject their own app here so handlers run
# against the in-memory test database.
_app = None


def _get_app():
    global _app
    if _app is None:
        from app import create_app
        from db_bootstrap import ensure_db

        _app = create_app()
        ensure_db(_app)
    return _app


def _with_app_context(fn):
    """Push a fresh app context per call.

    Required inside the decorator (not at server start) because handlers
    run on executor worker threads.
    """

    @functools.wraps(fn)
    def wrapper(args):
        with _get_app().app_context():
            return fn(args)

    return wrapper


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_TOOLS = [
    types.Tool(
        name="list_bcs",
        description=(
            "Search and paginate locally curated Biomedical Concepts. Filters: q (substring of short_name, bc_id, or ncit_code), status (provisional, sme_review, cdisc_approval, published)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search text matched against short_name, bc_id, ncit_code"},
                "status": {"type": "string", "enum": ["provisional", "sme_review", "cdisc_approval", "published"]},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "per_page": {"type": "integer", "minimum": 1, "maximum": 200, "default": 25},
            },
        },
    ),
    types.Tool(
        name="get_bc",
        description=("Get full detail for one curated Biomedical Concept: all fields plus its Data Element Concepts, dataset specializations, and governance history."),
        inputSchema={
            "type": "object",
            "properties": {"bc_id": {"type": "string", "description": "BC primary key (NCIt C-code)"}},
            "required": ["bc_id"],
        },
    ),
    types.Tool(
        name="search_ncit",
        description="Search the NCI Thesaurus (EVS API) for concepts matching a term. Returns code, name, and definition per match.",
        inputSchema={
            "type": "object",
            "properties": {
                "term": {"type": "string"},
                "size": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["term"],
        },
    ),
    types.Tool(
        name="get_ncit_concept",
        description="Fetch full NCIt concept detail (definitions, synonyms, parents, children, semantic type) by C-code.",
        inputSchema={
            "type": "object",
            "properties": {"ncit_code": {"type": "string", "description": "NCIt C-code, e.g. C64849"}},
            "required": ["ncit_code"],
        },
    ),
    types.Tool(
        name="search_loinc",
        description="Search LOINC codes by code or name via the NLM Clinical Tables API.",
        inputSchema={
            "type": "object",
            "properties": {
                "term": {"type": "string"},
                "size": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["term"],
        },
    ),
    types.Tool(
        name="search_cdisc_library",
        description=(
            "Search published Biomedical Concepts in the live CDISC Library by title substring. "
            "Requires CDISC_API_KEY (or CDISC_SUBSCRIPTION_KEY). Useful for duplicate detection against local drafts."
        ),
        inputSchema={
            "type": "object",
            "properties": {"q": {"type": "string", "description": "Case-insensitive title substring; empty lists all"}},
        },
    ),
    types.Tool(
        name="get_library_bc",
        description="Fetch one published Biomedical Concept from the live CDISC Library by concept id (NCIt C-code).",
        inputSchema={
            "type": "object",
            "properties": {"concept_id": {"type": "string"}},
            "required": ["concept_id"],
        },
    ),
    types.Tool(
        name="list_review_queue",
        description=("Summarize work awaiting review: BCs in sme_review and cdisc_approval (governance board columns) plus counts of pending ingestion records."),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="create_bc",
        description=("Create a new provisional Biomedical Concept. bc_id should be the NCIt C-code. Optionally include decs, a list of Data Element Concept objects. The write is audit-logged."),
        inputSchema={
            "type": "object",
            "properties": {
                "bc_id": {"type": "string", "description": "Primary key (NCIt C-code)"},
                "short_name": {"type": "string"},
                "definition": {"type": "string"},
                "ncit_code": {"type": "string"},
                "parent_bc_id": {"type": "string"},
                "bc_categories": {"type": "string", "description": "Semicolon-separated"},
                "synonyms": {"type": "string"},
                "result_scales": {"type": "string"},
                "loinc_code": {"type": "string"},
                "package_date": {"type": "string"},
                "submitter": {"type": "string"},
                "actor": {"type": "string", "default": "mcp"},
                "decs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dec_id": {"type": "string"},
                            "ncit_dec_code": {"type": "string"},
                            "dec_label": {"type": "string"},
                            "data_type": {"type": "string"},
                            "example_set": {"type": "string"},
                        },
                        "required": ["dec_label"],
                    },
                },
            },
            "required": ["bc_id", "short_name"],
        },
    ),
    types.Tool(
        name="update_bc",
        description=(
            "Update fields on an existing BC. Only supplied fields change; clearing ncit_code/loinc_code/parent_bc_id requires passing an empty string. Audit-logged with before/after state."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "bc_id": {"type": "string"},
                "short_name": {"type": "string"},
                "definition": {"type": "string"},
                "ncit_code": {"type": "string"},
                "parent_bc_id": {"type": "string"},
                "bc_categories": {"type": "string"},
                "synonyms": {"type": "string"},
                "result_scales": {"type": "string"},
                "loinc_code": {"type": "string"},
                "package_date": {"type": "string"},
                "actor": {"type": "string", "default": "mcp"},
            },
            "required": ["bc_id"],
        },
    ),
    types.Tool(
        name="map_ncit_to_bc",
        description=("Attach an NCIt C-code to a BC. Temporary IMPORT_ ids are promoted to the resolved code (the primary key changes). Audit-logged."),
        inputSchema={
            "type": "object",
            "properties": {
                "bc_id": {"type": "string"},
                "ncit_code": {"type": "string"},
                "actor": {"type": "string", "default": "mcp"},
            },
            "required": ["bc_id", "ncit_code"],
        },
    ),
    types.Tool(
        name="submit_bc_for_review",
        description="Move a BC from provisional to sme_review. Audit-logged.",
        inputSchema={
            "type": "object",
            "properties": {
                "bc_id": {"type": "string"},
                "actor": {"type": "string", "default": "mcp"},
            },
            "required": ["bc_id"],
        },
    ),
    types.Tool(
        name="advance_governance",
        description=("Advance a BC one stage (provisional -> sme_review -> cdisc_approval -> published). Writes a GovernanceRecord and an audit entry; returns advanced=false if already published."),
        inputSchema={
            "type": "object",
            "properties": {
                "bc_id": {"type": "string"},
                "comment": {"type": "string"},
                "actor": {"type": "string", "default": "mcp"},
            },
            "required": ["bc_id"],
        },
    ),
    types.Tool(
        name="reject_bc",
        description="Reject a BC back to provisional (stage 0). Writes a GovernanceRecord and an audit entry.",
        inputSchema={
            "type": "object",
            "properties": {
                "bc_id": {"type": "string"},
                "comment": {"type": "string"},
                "actor": {"type": "string", "default": "mcp"},
            },
            "required": ["bc_id"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return _TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _dispatch, name, arguments or {})
    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _dispatch(name: str, args: dict) -> Any:
    handlers = {
        "list_bcs": _list_bcs,
        "get_bc": _get_bc,
        "search_ncit": _search_ncit,
        "get_ncit_concept": _get_ncit_concept,
        "search_loinc": _search_loinc,
        "search_cdisc_library": _search_cdisc_library,
        "get_library_bc": _get_library_bc,
        "list_review_queue": _list_review_queue,
        "create_bc": _create_bc,
        "update_bc": _update_bc,
        "map_ncit_to_bc": _map_ncit_to_bc,
        "submit_bc_for_review": _submit_bc_for_review,
        "advance_governance": _advance_governance,
        "reject_bc": _reject_bc,
    }
    fn = handlers.get(name)
    if fn is None:
        raise ValueError(f"Unknown tool: {name!r}")
    return fn(args)


# ---------------------------------------------------------------------------
# Tool handlers (read-only)
# ---------------------------------------------------------------------------


def _bc_full_dict(bc):
    """to_dict() plus the fields it omits, without metadata JSON blobs."""
    data = bc.to_dict()
    data.update(
        {
            "code": bc.code,
            "source": bc.source,
            "history_of_change": bc.history_of_change,
            "created_at": bc.created_at,
            "updated_at": bc.updated_at,
        }
    )
    return data


@_with_app_context
def _list_bcs(args: dict) -> dict:
    from models.bc import BiomedicalConcept

    q = str(args.get("q") or "").strip()
    status = str(args.get("status") or "").strip()
    page = max(int(args.get("page") or 1), 1)
    per_page = min(max(int(args.get("per_page") or 25), 1), 200)

    query = BiomedicalConcept.query
    if q:
        query = query.filter(BiomedicalConcept.short_name.ilike(f"%{q}%") | BiomedicalConcept.bc_id.ilike(f"%{q}%") | BiomedicalConcept.ncit_code.ilike(f"%{q}%"))
    if status:
        query = query.filter_by(status=status)
    pagination = query.order_by(BiomedicalConcept.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [_bc_full_dict(bc) for bc in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    }


@_with_app_context
def _get_bc(args: dict) -> dict:
    from extensions import db
    from models.bc import BiomedicalConcept, DataElementConcept
    from models.governance import GovernanceRecord

    bc_id = str(args.get("bc_id") or "").strip()
    if not bc_id:
        raise ValueError("bc_id is required")
    bc = db.session.get(BiomedicalConcept, bc_id)
    if bc is None:
        raise ValueError(f"BC {bc_id!r} not found")

    decs = DataElementConcept.query.filter_by(bc_id=bc_id).order_by(DataElementConcept.sort_order).all()
    data = _bc_full_dict(bc)
    data["decs"] = [
        {
            "dec_id": d.dec_id,
            "ncit_dec_code": d.ncit_dec_code,
            "dec_label": d.dec_label,
            "data_type": d.data_type,
            "example_set": d.example_set,
            "required": d.required,
            "sort_order": d.sort_order,
        }
        for d in decs
    ]
    data["specializations"] = [
        {
            "vlm_group_id": s.vlm_group_id,
            "domain": s.domain,
            "short_name": s.short_name,
            "variables": s.variables,
        }
        for s in bc.specializations
    ]
    data["governance_records"] = [
        {
            "stage": g.stage,
            "action": g.action,
            "actor": g.actor,
            "comment": g.comment,
            "created_at": g.created_at,
        }
        for g in GovernanceRecord.query.filter_by(bc_id=bc_id).order_by(GovernanceRecord.id).all()
    ]
    return data


@_with_app_context
def _search_ncit(args: dict) -> list:
    from services.ncit_api import NCItApiClient

    term = str(args.get("term") or "").strip()
    if not term:
        raise ValueError("term is required")
    size = min(max(int(args.get("size") or 10), 1), 50)
    return NCItApiClient().search_concept(term, size=size)


@_with_app_context
def _get_ncit_concept(args: dict) -> dict:
    from services.ncit_api import NCItApiClient

    ncit_code = str(args.get("ncit_code") or "").strip()
    if not ncit_code:
        raise ValueError("ncit_code is required")
    return NCItApiClient().get_concept(ncit_code)


@_with_app_context
def _search_loinc(args: dict) -> list:
    from services.loinc_api import LoincApiClient

    term = str(args.get("term") or "").strip()
    if not term:
        raise ValueError("term is required")
    size = min(max(int(args.get("size") or 10), 1), 50)
    return LoincApiClient().search(term, size=size)


@_with_app_context
def _search_cdisc_library(args: dict) -> list:
    from services.cdisc_api import CDISCApiClient

    q = str(args.get("q") or "").strip().lower()
    links = CDISCApiClient().get_biomedical_concepts()
    if links and "error" in links[0]:
        return links
    if q:
        links = [lnk for lnk in links if q in (lnk.get("title") or "").lower()]
    return links


@_with_app_context
def _get_library_bc(args: dict) -> dict:
    from services.cdisc_api import CDISCApiClient

    concept_id = str(args.get("concept_id") or "").strip()
    if not concept_id:
        raise ValueError("concept_id is required")
    return CDISCApiClient().get_bc(concept_id)


@_with_app_context
def _list_review_queue(_args: dict) -> dict:
    from models.bc import BiomedicalConcept
    from models.ingestion import IngestionRecord

    queue = {}
    for status in ("sme_review", "cdisc_approval"):
        bcs = BiomedicalConcept.query.filter_by(status=status).order_by(BiomedicalConcept.updated_at.desc()).all()
        queue[status] = [{"bc_id": bc.bc_id, "short_name": bc.short_name, "submitter": bc.submitter, "updated_at": bc.updated_at} for bc in bcs]
    pending_ingestion = IngestionRecord.query.filter_by(status="pending").count()
    return {
        "sme_review": queue["sme_review"],
        "cdisc_approval": queue["cdisc_approval"],
        "pending_ingestion_records": pending_ingestion,
    }


# ---------------------------------------------------------------------------
# Tool handlers (writes — shared service code path, audit-logged)
# ---------------------------------------------------------------------------


@_with_app_context
def _create_bc(args: dict) -> dict:
    from services import bc_service

    actor = str(args.get("actor") or "mcp")
    bc = bc_service.create_bc(args, actor=actor)
    decs = args.get("decs") or []
    if decs:
        bc_service.save_decs(bc.bc_id, decs)
    return _get_bc.__wrapped__({"bc_id": bc.bc_id})


@_with_app_context
def _update_bc(args: dict) -> dict:
    from services import bc_service

    bc_id = str(args.get("bc_id") or "").strip()
    if not bc_id:
        raise ValueError("bc_id is required")
    actor = str(args.get("actor") or "mcp")
    # Only fields present in args change; absent fields keep their value
    bc = bc_service.update_bc(bc_id, args, actor=actor)
    return _bc_full_dict(bc)


@_with_app_context
def _map_ncit_to_bc(args: dict) -> dict:
    from services import bc_service

    bc_id = str(args.get("bc_id") or "").strip()
    if not bc_id:
        raise ValueError("bc_id is required")
    actor = str(args.get("actor") or "mcp")
    bc = bc_service.map_ncit_to_bc(bc_id, args.get("ncit_code"), actor=actor)
    return _bc_full_dict(bc)


@_with_app_context
def _submit_bc_for_review(args: dict) -> dict:
    from services import bc_service

    bc_id = str(args.get("bc_id") or "").strip()
    if not bc_id:
        raise ValueError("bc_id is required")
    actor = str(args.get("actor") or "mcp")
    bc = bc_service.submit_bc_for_review(bc_id, actor=actor)
    return _bc_full_dict(bc)


@_with_app_context
def _advance_governance(args: dict) -> dict:
    from services import governance_service

    bc_id = str(args.get("bc_id") or "").strip()
    if not bc_id:
        raise ValueError("bc_id is required")
    actor = str(args.get("actor") or "mcp")
    return governance_service.advance_governance(bc_id, actor=actor, comment=str(args.get("comment") or ""))


@_with_app_context
def _reject_bc(args: dict) -> dict:
    from services import governance_service

    bc_id = str(args.get("bc_id") or "").strip()
    if not bc_id:
        raise ValueError("bc_id is required")
    actor = str(args.get("actor") or "mcp")
    return governance_service.reject_bc(bc_id, actor=actor, comment=str(args.get("comment") or ""))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_run())


async def _run() -> None:
    async with stdio_server() as streams:
        await server.run(*streams, server.create_initialization_options())


if __name__ == "__main__":
    main()
