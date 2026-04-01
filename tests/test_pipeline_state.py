"""Unit tests for src/accounts/state.py — pipeline state machine.

All tests use tmp_path as the client directory so workflow_state.json is
written to a temporary location and never touches real client data.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestInitializeState:
    def test_initialize_state_creates_file(self, tmp_path: Path):
        from src.accounts.state import initialize_state

        initialize_state(tmp_path)

        assert (tmp_path / "workflow_state.json").exists()

    def test_initialize_state_all_stages_pending(self, tmp_path: Path):
        from src.accounts.state import initialize_state, PIPELINE_STAGES

        state = initialize_state(tmp_path)

        assert "stages" in state
        for stage in PIPELINE_STAGES:
            assert stage in state["stages"]
            assert state["stages"][stage]["status"] == "pending"

    def test_initialize_state_has_created_at(self, tmp_path: Path):
        from src.accounts.state import initialize_state

        state = initialize_state(tmp_path)

        assert "created_at" in state
        assert state["created_at"] is not None


class TestGetPipelineState:
    def test_get_pipeline_state_returns_correct_structure(self, tmp_path: Path):
        from src.accounts.state import initialize_state, get_pipeline_state

        initialize_state(tmp_path)
        state = get_pipeline_state(tmp_path)

        assert "stages" in state
        assert "created_at" in state

    def test_get_pipeline_state_missing_raises_file_not_found(self, tmp_path: Path):
        from src.accounts.state import get_pipeline_state

        with pytest.raises(FileNotFoundError, match="workflow_state.json"):
            get_pipeline_state(tmp_path)


class TestUpdateState:
    def test_update_state_persists_status(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, get_pipeline_state

        initialize_state(tmp_path)
        update_state(tmp_path, "intake", "completed")

        state = get_pipeline_state(tmp_path)
        assert state["stages"]["intake"]["status"] == "completed"

    def test_update_state_sets_updated_at(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, get_pipeline_state

        initialize_state(tmp_path)
        update_state(tmp_path, "intake", "completed")

        state = get_pipeline_state(tmp_path)
        assert state["stages"]["intake"]["updated_at"] is not None

    def test_update_state_invalid_stage_raises_value_error(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state

        initialize_state(tmp_path)
        with pytest.raises(ValueError, match="Unknown stage"):
            update_state(tmp_path, "nonexistent_stage", "completed")

    def test_update_state_with_metadata(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, get_pipeline_state

        initialize_state(tmp_path)
        update_state(tmp_path, "research", "completed", metadata={"duration_seconds": 42})

        state = get_pipeline_state(tmp_path)
        assert state["stages"]["research"]["metadata"]["duration_seconds"] == 42

    def test_update_state_multiple_stages(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, get_pipeline_state

        initialize_state(tmp_path)
        update_state(tmp_path, "intake", "completed")
        update_state(tmp_path, "research", "in_progress")

        state = get_pipeline_state(tmp_path)
        assert state["stages"]["intake"]["status"] == "completed"
        assert state["stages"]["research"]["status"] == "in_progress"
        assert state["stages"]["competitors"]["status"] == "pending"


class TestCheckPrerequisites:
    def test_check_prerequisites_intake_no_prereqs(self, tmp_path: Path):
        from src.accounts.state import initialize_state, check_prerequisites

        initialize_state(tmp_path)
        ok, missing = check_prerequisites(tmp_path, "intake")

        assert ok is True
        assert missing == []

    def test_check_prerequisites_keywords_both_missing(self, tmp_path: Path):
        from src.accounts.state import initialize_state, check_prerequisites

        initialize_state(tmp_path)
        # intake and research are still pending
        ok, missing = check_prerequisites(tmp_path, "keywords")

        assert ok is False
        assert "intake" in missing
        assert "research" in missing

    def test_check_prerequisites_keywords_partial(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, check_prerequisites

        initialize_state(tmp_path)
        update_state(tmp_path, "intake", "completed")
        # research still pending
        ok, missing = check_prerequisites(tmp_path, "keywords")

        assert ok is False
        assert missing == ["research"]

    def test_check_prerequisites_keywords_satisfied(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, check_prerequisites

        initialize_state(tmp_path)
        update_state(tmp_path, "intake", "completed")
        update_state(tmp_path, "research", "completed")
        ok, missing = check_prerequisites(tmp_path, "keywords")

        assert ok is True
        assert missing == []

    def test_check_prerequisites_invalid_stage(self, tmp_path: Path):
        from src.accounts.state import initialize_state, check_prerequisites

        initialize_state(tmp_path)
        with pytest.raises(ValueError, match="Unknown stage"):
            check_prerequisites(tmp_path, "invalid_stage")

    def test_check_prerequisites_competitors_requires_only_intake(self, tmp_path: Path):
        """competitors only needs intake, not research."""
        from src.accounts.state import initialize_state, update_state, check_prerequisites

        initialize_state(tmp_path)
        update_state(tmp_path, "intake", "completed")
        ok, missing = check_prerequisites(tmp_path, "competitors")

        assert ok is True
        assert missing == []


class TestGetNextStage:
    def test_get_next_stage_all_pending_returns_intake(self, tmp_path: Path):
        from src.accounts.state import initialize_state, get_next_stage

        initialize_state(tmp_path)
        next_stage = get_next_stage(tmp_path)

        assert next_stage == "intake"

    def test_get_next_stage_after_some_complete(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, get_next_stage

        initialize_state(tmp_path)
        update_state(tmp_path, "intake", "completed")
        update_state(tmp_path, "research", "completed")

        next_stage = get_next_stage(tmp_path)

        assert next_stage == "competitors"

    def test_get_next_stage_all_complete_returns_none(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, get_next_stage, PIPELINE_STAGES

        initialize_state(tmp_path)
        for stage in PIPELINE_STAGES:
            update_state(tmp_path, stage, "completed")

        next_stage = get_next_stage(tmp_path)

        assert next_stage is None

    def test_get_next_stage_skips_completed(self, tmp_path: Path):
        from src.accounts.state import initialize_state, update_state, get_next_stage

        initialize_state(tmp_path)
        update_state(tmp_path, "intake", "completed")

        next_stage = get_next_stage(tmp_path)

        assert next_stage == "research"
