# test_regression_ci_async_support.py
"""
Regression test to prevent async test support issues in CI environments.

This test ensures that pytest-asyncio is properly configured and that
async tests can run successfully in all environments.
"""
import pytest
import asyncio


class TestRegressionCIAsyncSupport:
    """Regression tests for CI async test support"""

    def test_regression_pytest_asyncio_installed(self):
        """Verify pytest-asyncio is available for async test support"""
        # Check that pytest-asyncio is importable
        try:
            import pytest_asyncio
            assert pytest_asyncio is not None, "pytest-asyncio module not available"
        except ImportError:
            pytest.fail("pytest-asyncio not installed or not accessible")

    @pytest.mark.asyncio
    async def test_regression_async_mark_recognition(self):
        """Verify @pytest.mark.asyncio is properly recognized"""
        # This test should run without "async def functions are not natively supported" error
        await asyncio.sleep(0.001)  # Simple async operation
        assert True, "Async test executed successfully"

    @pytest.mark.asyncio
    async def test_regression_async_mock_support(self):
        """Verify async mocking works in test environment"""
        from unittest.mock import AsyncMock

        mock_func = AsyncMock(return_value="test_result")
        result = await mock_func()

        assert result == "test_result"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_regression_asyncio_features(self):
        """Verify basic asyncio features work in test environment"""
        # Test that we can create tasks, use async context managers, etc.
        async def dummy_async_func():
            await asyncio.sleep(0.001)
            return "success"

        task = asyncio.create_task(dummy_async_func())
        result = await task

        assert result == "success"

    def test_regression_requirements_includes_pytest_asyncio(self):
        """Verify requirements.txt includes pytest-asyncio dependency"""
        import pathlib

        requirements_file = pathlib.Path(__file__).parent.parent / "requirements.txt"
        requirements_content = requirements_file.read_text()

        # Should have pytest-asyncio listed
        assert "pytest-asyncio" in requirements_content, "pytest-asyncio missing from requirements.txt"

        # Should have version constraint
        pytest_asyncio_lines = [line for line in requirements_content.split('\n')
                               if 'pytest-asyncio' in line]
        assert len(pytest_asyncio_lines) >= 1, "pytest-asyncio dependency not found"

        # Should have version specification
        pytest_asyncio_line = pytest_asyncio_lines[0]
        assert ">=" in pytest_asyncio_line, f"pytest-asyncio should have version constraint: {pytest_asyncio_line}"