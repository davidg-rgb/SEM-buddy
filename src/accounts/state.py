"""Pipeline state machine — tracks stage completion per client."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

PIPELINE_STAGES = [
    "intake",
    "research",
    "competitors",
    "keywords",
    "campaign",
    "validate",
    "export",
    "report",
]

STAGE_PREREQUISITES: dict[str, list[str]] = {
    "intake": [],
    "research": ["intake"],
    "competitors": ["intake"],
    "keywords": ["intake", "research"],
    "campaign": ["keywords"],
    "validate": ["campaign"],
    "export": ["campaign"],
    "report": ["campaign"],
}

_STATE_FILE = "workflow_state.json"


def _state_path(client_dir: Path) -> Path:
    return client_dir / _STATE_FILE


def initialize_state(client_dir: Path) -> dict:
    """Create workflow_state.json with all stages set to 'pending'.

    Args:
        client_dir: Path to the client's directory.

    Returns:
        The initial state dict.

    Side effects:
        Writes workflow_state.json to client_dir.
    """
    state: dict = {
        "created_at": datetime.now().isoformat(),
        "stages": {
            stage: {"status": "pending", "updated_at": None}
            for stage in PIPELINE_STAGES
        },
    }
    with open(_state_path(client_dir), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    return state


def get_pipeline_state(client_dir: Path) -> dict:
    """Read and return the current pipeline state dict.

    Args:
        client_dir: Path to the client's directory.

    Returns:
        State dict with 'created_at' and 'stages' keys.

    Raises:
        FileNotFoundError: If workflow_state.json does not exist.
    """
    path = _state_path(client_dir)
    if not path.exists():
        raise FileNotFoundError(f"workflow_state.json not found in {client_dir}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_state(
    client_dir: Path, stage: str, status: str, metadata: Optional[dict] = None
) -> None:
    """Update a stage's status, timestamp, and optional metadata, then persist.

    Args:
        client_dir: Path to the client's directory.
        stage: One of PIPELINE_STAGES.
        status: One of 'pending', 'in_progress', 'completed', 'failed'.
        metadata: Optional extra info (e.g., duration, error message).

    Raises:
        ValueError: If stage is not in PIPELINE_STAGES.
        FileNotFoundError: If workflow_state.json is missing.
    """
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Unknown stage '{stage}'. Valid stages: {PIPELINE_STAGES}")

    state = get_pipeline_state(client_dir)
    stage_entry: dict = {
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }
    if metadata:
        stage_entry["metadata"] = metadata
    state["stages"][stage] = stage_entry

    with open(_state_path(client_dir), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def check_prerequisites(client_dir: Path, stage: str) -> tuple[bool, list[str]]:
    """Check whether all prerequisite stages for a given stage are completed.

    Args:
        client_dir: Path to the client's directory.
        stage: Stage to check prerequisites for.

    Returns:
        (ok, missing_stages) where ok is True if all prerequisites are completed
        and missing_stages is the list of prerequisite stage names not yet completed.

    Raises:
        ValueError: If stage is not in PIPELINE_STAGES.
    """
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Unknown stage '{stage}'. Valid stages: {PIPELINE_STAGES}")

    required = STAGE_PREREQUISITES.get(stage, [])
    if not required:
        return True, []

    state = get_pipeline_state(client_dir)
    stages = state.get("stages", {})

    missing: list[str] = [
        req
        for req in required
        if stages.get(req, {}).get("status") != "completed"
    ]

    return len(missing) == 0, missing


def get_next_stage(client_dir: Path) -> Optional[str]:
    """Return the first pipeline stage with status 'pending', or None if all complete.

    Args:
        client_dir: Path to the client's directory.

    Returns:
        Stage name string, or None.
    """
    state = get_pipeline_state(client_dir)
    stages = state.get("stages", {})
    for stage in PIPELINE_STAGES:
        if stages.get(stage, {}).get("status") == "pending":
            return stage
    return None
