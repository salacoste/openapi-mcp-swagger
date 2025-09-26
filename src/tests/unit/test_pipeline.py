"""Unit tests for pipeline components."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass
from typing import Dict, Any, List

from swagger_mcp_server.pipeline import (
    ProcessingStage, PipelineContext, StageResult, ProcessingMetrics,
    ProcessingResult, BatchProcessingResult, SwaggerProcessingPipeline
)


@dataclass
class MockStageResult:
    """Mock stage result for testing."""
    success: bool
    data: Any = None
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class MockStage(ProcessingStage):
    """Mock processing stage for testing."""

    def __init__(self, name: str, should_succeed: bool = True, result_data: Any = None):
        super().__init__(name)
        self.should_succeed = should_succeed
        self.result_data = result_data
        self.execute_called = False
        self.rollback_called = False

    async def execute(self, input_data: Any, context: PipelineContext) -> StageResult:
        """Mock execute method."""
        self.execute_called = True

        if self.should_succeed:
            return StageResult(
                success=True,
                data=self.result_data or f"{self.name}_output",
                stage_name=self.name
            )
        else:
            return StageResult(
                success=False,
                stage_name=self.name,
                errors=[f"{self.name} failed"]
            )

    async def rollback(self, context: PipelineContext) -> None:
        """Mock rollback method."""
        self.rollback_called = True


class TestPipelineComponents:
    """Test pipeline component functionality."""

    def test_processing_metrics_initialization(self):
        """Test ProcessingMetrics initialization."""
        metrics = ProcessingMetrics()

        assert metrics.parsing_duration == 0.0
        assert metrics.normalization_duration == 0.0
        assert metrics.storage_duration == 0.0
        assert metrics.endpoints_processed == 0
        assert metrics.schemas_processed == 0
        assert metrics.errors_count == 0

    def test_pipeline_context_initialization(self):
        """Test PipelineContext initialization."""
        context = PipelineContext(file_path="test.json")

        assert context.file_path == "test.json"
        assert context.api_id is None
        assert isinstance(context.metrics, ProcessingMetrics)
        assert isinstance(context.stage_results, dict)

    def test_stage_result_creation(self):
        """Test StageResult creation."""
        result = StageResult(
            success=True,
            data="test_data",
            stage_name="test_stage",
            errors=["error1"],
            warnings=["warning1"]
        )

        assert result.success is True
        assert result.data == "test_data"
        assert result.stage_name == "test_stage"
        assert result.errors == ["error1"]
        assert result.warnings == ["warning1"]

    @pytest.mark.asyncio
    async def test_successful_pipeline_execution(self):
        """Test successful pipeline execution with mock stages."""
        # Create mock stages
        stage1 = MockStage("stage1", should_succeed=True, result_data="stage1_output")
        stage2 = MockStage("stage2", should_succeed=True, result_data="stage2_output")
        stage3 = MockStage("stage3", should_succeed=True, result_data="final_output")

        # Create pipeline with mock stages
        with patch('swagger_mcp_server.pipeline.get_db_manager'):
            pipeline = SwaggerProcessingPipeline()
            pipeline.stages = [stage1, stage2, stage3]

            # Mock the file hash calculation
            with patch.object(pipeline, '_calculate_file_hash', return_value="mock_hash"):
                result = await pipeline.process_file("test_file.json")

            # Verify all stages were executed
            assert stage1.execute_called
            assert stage2.execute_called
            assert stage3.execute_called

            # Verify no rollbacks were called
            assert not stage1.rollback_called
            assert not stage2.rollback_called
            assert not stage3.rollback_called

            # Verify successful result
            assert result.success is True
            assert result.file_path == "test_file.json"

    @pytest.mark.asyncio
    async def test_failed_stage_triggers_rollback(self):
        """Test that a failed stage triggers rollback of previous stages."""
        # Create stages where stage2 fails
        stage1 = MockStage("stage1", should_succeed=True)
        stage2 = MockStage("stage2", should_succeed=False)  # This will fail
        stage3 = MockStage("stage3", should_succeed=True)

        # Create pipeline with mock stages
        with patch('swagger_mcp_server.pipeline.get_db_manager'):
            pipeline = SwaggerProcessingPipeline()
            pipeline.stages = [stage1, stage2, stage3]

            # Mock the file hash calculation
            with patch.object(pipeline, '_calculate_file_hash', return_value="mock_hash"):
                result = await pipeline.process_file("test_file.json")

            # Verify execution pattern
            assert stage1.execute_called  # Stage1 should execute
            assert stage2.execute_called  # Stage2 should execute and fail
            assert not stage3.execute_called  # Stage3 should not execute

            # Verify rollback pattern
            assert stage1.rollback_called  # Stage1 should rollback
            assert stage2.rollback_called  # Stage2 should rollback
            assert not stage3.rollback_called  # Stage3 should not rollback

            # Verify failed result
            assert result.success is False
            assert "stage2 failed" in result.errors

    @pytest.mark.asyncio
    async def test_batch_processing_success(self):
        """Test successful batch processing."""
        # Create a successful stage
        mock_stage = MockStage("mock_stage", should_succeed=True)

        with patch('swagger_mcp_server.pipeline.get_db_manager'):
            pipeline = SwaggerProcessingPipeline()
            pipeline.stages = [mock_stage]

            # Mock individual file processing
            async def mock_process_file(file_path):
                return ProcessingResult(
                    success=True,
                    file_path=file_path,
                    api_id=1
                )

            with patch.object(pipeline, 'process_file', side_effect=mock_process_file):
                result = await pipeline.process_batch(["file1.json", "file2.json"])

            assert result.total_files == 2
            assert result.successful_files == 2
            assert result.failed_files == 0
            assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_batch_processing_with_failures(self):
        """Test batch processing with some file failures."""
        with patch('swagger_mcp_server.pipeline.get_db_manager'):
            pipeline = SwaggerProcessingPipeline()

            # Mock individual file processing with mixed results
            async def mock_process_file(file_path):
                if "fail" in file_path:
                    return ProcessingResult(
                        success=False,
                        file_path=file_path,
                        errors=["Mock failure"]
                    )
                return ProcessingResult(
                    success=True,
                    file_path=file_path,
                    api_id=1
                )

            with patch.object(pipeline, 'process_file', side_effect=mock_process_file):
                result = await pipeline.process_batch(["success.json", "fail.json"])

            assert result.total_files == 2
            assert result.successful_files == 1
            assert result.failed_files == 1

    @pytest.mark.asyncio
    async def test_integrity_validation(self):
        """Test data integrity validation."""
        with patch('swagger_mcp_server.pipeline.get_db_manager'):
            pipeline = SwaggerProcessingPipeline()

            # Test integrity validation
            report = await pipeline.validate_integrity(api_id=1)

            assert "api_id" in report
            assert report["api_id"] == 1
            assert "checks" in report
            assert "score" in report

    def test_processing_result_creation(self):
        """Test ProcessingResult creation and properties."""
        metrics = ProcessingMetrics()
        metrics.total_duration = 5.0
        metrics.endpoints_processed = 10

        result = ProcessingResult(
            success=True,
            api_id=123,
            file_path="test.json",
            metrics=metrics,
            errors=[],
            warnings=["test warning"]
        )

        assert result.success is True
        assert result.api_id == 123
        assert result.file_path == "test.json"
        assert result.metrics.total_duration == 5.0
        assert result.warnings == ["test warning"]

    def test_batch_processing_result_creation(self):
        """Test BatchProcessingResult creation and aggregation."""
        individual_results = [
            ProcessingResult(success=True, file_path="file1.json", api_id=1),
            ProcessingResult(success=False, file_path="file2.json", errors=["error"])
        ]

        batch_result = BatchProcessingResult(
            total_files=2,
            successful_files=1,
            failed_files=1,
            results=individual_results
        )

        assert batch_result.total_files == 2
        assert batch_result.successful_files == 1
        assert batch_result.failed_files == 1
        assert len(batch_result.results) == 2


class TestPipelineEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_file_path(self):
        """Test pipeline with empty file path."""
        with patch('swagger_mcp_server.pipeline.get_db_manager'):
            pipeline = SwaggerProcessingPipeline()

            with patch.object(pipeline, '_calculate_file_hash', side_effect=FileNotFoundError):
                result = await pipeline.process_file("")

            assert result.success is False
            assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_batch_processing_empty_list(self):
        """Test batch processing with empty file list."""
        with patch('swagger_mcp_server.pipeline.get_db_manager'):
            pipeline = SwaggerProcessingPipeline()

            result = await pipeline.process_batch([])

            assert result.total_files == 0
            assert result.successful_files == 0
            assert result.failed_files == 0

    @pytest.mark.asyncio
    async def test_pipeline_with_exception_in_stage(self):
        """Test pipeline handling of unexpected exceptions in stages."""
        class ExceptionStage(ProcessingStage):
            def __init__(self):
                super().__init__("exception_stage")

            async def execute(self, input_data, context):
                raise ValueError("Unexpected error in stage")

            async def rollback(self, context):
                pass

        with patch('swagger_mcp_server.pipeline.get_db_manager'):
            pipeline = SwaggerProcessingPipeline()
            pipeline.stages = [ExceptionStage()]

            with patch.object(pipeline, '_calculate_file_hash', return_value="hash"):
                result = await pipeline.process_file("test.json")

            assert result.success is False
            assert any("Pipeline failed" in error for error in result.errors)


if __name__ == "__main__":
    # Simple test runner for development
    import sys
    pytest.main([__file__] + sys.argv[1:])