"""Performance tests for pipeline processing."""

import asyncio
import time
from pathlib import Path

import pytest

from swagger_mcp_server.pipeline import (
    PipelineFactory,
    ProcessingResult,
    SwaggerProcessingPipeline,
)
from swagger_mcp_server.storage import DatabaseConfig


class TestPipelinePerformance:
    """Performance tests for the pipeline."""

    @pytest.fixture
    def test_swagger_file(self):
        """Path to the test Swagger file."""
        project_root = Path(__file__).parent.parent.parent.parent
        swagger_file = project_root / "swagger-openapi-data" / "swagger.json"
        assert (
            swagger_file.exists()
        ), f"Test swagger file not found: {swagger_file}"
        return str(swagger_file)

    @pytest.fixture
    def temp_db_config(self, tmp_path):
        """Temporary database configuration for testing."""
        db_path = tmp_path / "test_performance.db"
        return DatabaseConfig(
            database_path=str(db_path), enable_wal=True, max_connections=10
        )

    @pytest.mark.asyncio
    async def test_ozon_api_processing_within_60_seconds(
        self, test_swagger_file, temp_db_config
    ):
        """Test that 262KB Ozon API processes within 60 seconds (AC: 2)."""
        # Create high-performance pipeline
        pipeline = PipelineFactory.create_high_performance_pipeline()
        pipeline.db_config = temp_db_config
        pipeline.db_manager = None  # Force recreation with new config

        start_time = time.time()

        # Process the file
        result = await pipeline.process_file(test_swagger_file)

        processing_time = time.time() - start_time

        # Verify processing completed successfully
        assert result.success, f"Processing failed: {result.errors}"
        assert (
            result.api_id is not None
        ), "API ID should be set on successful processing"

        # Verify performance requirement (60 seconds)
        assert (
            processing_time < 60.0
        ), f"Processing took {processing_time:.2f}s, exceeding 60s requirement"

        # Verify metrics are populated
        assert result.metrics.total_duration > 0
        assert result.metrics.parsing_duration > 0
        assert result.metrics.normalization_duration > 0
        assert result.metrics.storage_duration > 0

        # Verify data was processed
        assert result.metrics.endpoints_processed > 0
        assert result.metrics.schemas_processed > 0

        print(f"✅ Ozon API processed successfully in {processing_time:.2f}s")
        print(
            f"📊 Metrics: {result.metrics.endpoints_processed} endpoints, "
            f"{result.metrics.schemas_processed} schemas"
        )

    @pytest.mark.asyncio
    async def test_pipeline_memory_efficiency(
        self, test_swagger_file, temp_db_config
    ):
        """Test that pipeline processes large files without excessive memory usage."""
        pipeline = PipelineFactory.create_high_performance_pipeline()
        pipeline.db_config = temp_db_config
        pipeline.db_manager = None

        # Get file size
        file_size = Path(test_swagger_file).stat().st_size

        result = await pipeline.process_file(test_swagger_file)

        assert result.success, f"Processing failed: {result.errors}"

        # Verify memory usage is reasonable (should not exceed file size by more than 10x)
        if result.metrics.memory_peak_mb > 0:
            file_size_mb = file_size / (1024 * 1024)
            memory_ratio = result.metrics.memory_peak_mb / file_size_mb

            assert memory_ratio < 10.0, (
                f"Memory usage ({result.metrics.memory_peak_mb:.1f}MB) is {memory_ratio:.1f}x "
                f"file size ({file_size_mb:.1f}MB), indicating possible memory leak"
            )

        print(f"✅ Memory efficiency test passed")
        print(f"📁 File size: {file_size / (1024 * 1024):.1f}MB")
        if result.metrics.memory_peak_mb > 0:
            print(f"🧠 Peak memory: {result.metrics.memory_peak_mb:.1f}MB")

    @pytest.mark.asyncio
    async def test_batch_processing_performance(
        self, test_swagger_file, temp_db_config
    ):
        """Test batch processing performance with multiple files."""
        pipeline = PipelineFactory.create_high_performance_pipeline()
        pipeline.db_config = temp_db_config
        pipeline.db_manager = None

        # Process the same file 3 times to simulate batch processing
        file_paths = [test_swagger_file] * 3

        start_time = time.time()
        batch_result = await pipeline.process_batch(
            file_paths, max_concurrent=2
        )
        batch_time = time.time() - start_time

        # Verify all files processed successfully
        assert (
            batch_result.successful_files == 3
        ), f"Expected 3 successful files, got {batch_result.successful_files}"
        assert (
            batch_result.failed_files == 0
        ), f"No files should fail, got {batch_result.failed_files}"

        # Verify batch processing is more efficient than sequential
        # Should take less than 3x single file time due to concurrency
        single_file_time = batch_result.results[0].metrics.total_duration
        max_expected_time = single_file_time * 2.5  # Allow some overhead

        assert (
            batch_time < max_expected_time
        ), f"Batch processing took {batch_time:.2f}s, should be less than {max_expected_time:.2f}s"

        print(f"✅ Batch processing completed in {batch_time:.2f}s")
        print(
            f"📊 Throughput: {batch_result.batch_metrics['throughput']:.1f} files/second"
        )


@pytest.mark.asyncio
async def test_pipeline_factory_configurations():
    """Test different pipeline factory configurations."""

    # Test default pipeline creation
    default_pipeline = PipelineFactory.create_default_pipeline()
    assert default_pipeline is not None
    assert len(default_pipeline.stages) == 3

    # Test high-performance pipeline creation
    high_perf_pipeline = PipelineFactory.create_high_performance_pipeline()
    assert high_perf_pipeline is not None
    assert high_perf_pipeline.parser_config.strict_mode is False

    # Test strict pipeline creation
    strict_pipeline = PipelineFactory.create_strict_pipeline()
    assert strict_pipeline is not None
    assert strict_pipeline.parser_config.strict_mode is True
    assert strict_pipeline.parser_config.max_errors == 0

    print("✅ All pipeline factory configurations created successfully")


if __name__ == "__main__":
    # Run the main performance test
    async def main():
        # Simple test runner for development
        test_file = (
            Path(__file__).parent.parent.parent.parent
            / "swagger-openapi-data"
            / "swagger.json"
        )
        if test_file.exists():
            print(f"🚀 Running performance test with {test_file}")
            pipeline = PipelineFactory.create_high_performance_pipeline()

            start = time.time()
            try:
                result = await pipeline.process_file(str(test_file))
                duration = time.time() - start

                if result.success:
                    print(
                        f"✅ SUCCESS: Processed in {duration:.2f}s (target: <60s)"
                    )
                    print(
                        f"📊 {result.metrics.endpoints_processed} endpoints, {result.metrics.schemas_processed} schemas"
                    )
                else:
                    print(f"❌ FAILED: {result.errors}")
            except Exception as e:
                print(f"💥 ERROR: {str(e)}")
                import traceback

                traceback.print_exc()
        else:
            print(f"❌ Test file not found: {test_file}")

    asyncio.run(main())
