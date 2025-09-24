# test_request_logger.py
import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock

from codex_plus.request_logger import RequestLogger


class TestRequestLogger:
    """TDD test suite for RequestLogger fixes"""

    def test_log_request_payload_ignores_non_responses_path(self):
        """Test that non-responses paths are ignored"""
        body = b'{"test": "data"}'

        # Should not attempt any logging for non-responses paths
        with patch.object(RequestLogger, '_log_payload_to_file_async') as mock_async:
            RequestLogger.log_request_payload(body, "other_path")
            mock_async.assert_not_called()

    def test_log_request_payload_ignores_empty_body(self):
        """Test that empty bodies are ignored"""
        # Should not attempt any logging for empty bodies
        with patch.object(RequestLogger, '_log_payload_to_file_async') as mock_async:
            RequestLogger.log_request_payload(b'', "responses")
            RequestLogger.log_request_payload(None, "responses")
            mock_async.assert_not_called()

    def test_asyncio_event_loop_handling_with_running_loop(self):
        """Test asyncio event loop handling when loop is running"""
        body = b'{"test": "data"}'

        async_logger = AsyncMock(return_value=None)

        with patch.object(RequestLogger, '_log_payload_to_file_async', new=async_logger):
            with patch('asyncio.get_running_loop') as mock_get_running_loop:
                def consume_task(coro):
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(coro)
                    finally:
                        loop.close()
                    return Mock(name='task')

                mock_loop = Mock()
                mock_loop.create_task = Mock(side_effect=consume_task)
                mock_get_running_loop.return_value = mock_loop

                RequestLogger.log_request_payload(body, "responses")

                mock_get_running_loop.assert_called_once()
                mock_loop.create_task.assert_called_once()
                async_logger.assert_called_once_with(body)

    def test_asyncio_event_loop_handling_without_running_loop(self):
        """Test asyncio event loop handling when no loop is running"""
        body = b'{"test": "data"}'

        async_logger = AsyncMock(return_value=None)

        with patch.object(RequestLogger, '_log_payload_to_file_async', new=async_logger):
            with patch('asyncio.get_running_loop', side_effect=RuntimeError("No running loop")):
                def run_side_effect(coro):
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(coro)
                    finally:
                        loop.close()
                    return None

                with patch('asyncio.run', side_effect=run_side_effect) as mock_run:
                    RequestLogger.log_request_payload(body, "responses")

                mock_run.assert_called_once()
                async_logger.assert_called_once_with(body)

    @pytest.mark.asyncio
    async def test_json_parsing_with_valid_json(self):
        """Test JSON parsing with valid JSON data"""
        valid_json = b'{"key": "value", "instructions": "test instruction"}'

        async_to_thread = AsyncMock(return_value=None)
        with patch('asyncio.to_thread', new=async_to_thread):
            with patch('aiofiles.open') as mock_open:
                mock_file = AsyncMock()
                mock_open.return_value.__aenter__.return_value = mock_file

                await RequestLogger._log_payload_to_file_async(valid_json)

        assert async_to_thread.await_count >= 1
        assert mock_open.call_count >= 1

    @pytest.mark.asyncio
    async def test_json_parsing_with_invalid_json(self):
        """Test JSON parsing with invalid JSON data"""
        invalid_json = b'{"key": "value"'  # Malformed JSON

        with patch('codex_plus.request_logger.logger') as mock_logger:
            await RequestLogger._log_payload_to_file_async(invalid_json)

            # Should log warning about invalid JSON
            mock_logger.warning.assert_called_once()
            assert "Invalid JSON" in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_directory_creation_using_asyncio_to_thread(self):
        """Test that directory creation uses asyncio.to_thread"""
        valid_json = b'{"test": "data"}'

        async_to_thread = AsyncMock(return_value=None)
        with patch('asyncio.to_thread', new=async_to_thread):
            with patch('aiofiles.open') as mock_open:
                mock_file = AsyncMock()
                mock_open.return_value.__aenter__.return_value = mock_file

                await RequestLogger._log_payload_to_file_async(valid_json)

        assert async_to_thread.await_count >= 1

    @pytest.mark.asyncio
    async def test_file_writing_uses_aiofiles(self):
        """Test that file writing uses aiofiles instead of subprocess"""
        valid_json = b'{"test": "data", "instructions": "test instruction"}'

        async_to_thread = AsyncMock(return_value=None)
        with patch('asyncio.to_thread', new=async_to_thread):
            with patch('aiofiles.open') as mock_open:
                mock_file = AsyncMock()
                mock_open.return_value.__aenter__.return_value = mock_file

                await RequestLogger._log_payload_to_file_async(valid_json)

                assert mock_open.call_count >= 1
                mock_file.write.assert_called()

    @pytest.mark.asyncio
    async def test_instructions_file_creation_when_present(self):
        """Test that instructions file is created when instructions are present"""
        json_with_instructions = b'{"test": "data", "instructions": "test instruction"}'

        async_to_thread = AsyncMock(return_value=None)
        with patch('asyncio.to_thread', new=async_to_thread):
            with patch('aiofiles.open') as mock_open:
                mock_file = AsyncMock()
                mock_open.return_value.__aenter__.return_value = mock_file

                await RequestLogger._log_payload_to_file_async(json_with_instructions)

                assert mock_open.call_count == 2

    @pytest.mark.asyncio
    async def test_instructions_file_skipped_when_not_string(self):
        """Test that instructions file is skipped when instructions is not a string"""
        json_with_non_string_instructions = b'{"test": "data", "instructions": 123}'

        async_to_thread = AsyncMock(return_value=None)
        with patch('asyncio.to_thread', new=async_to_thread):
            with patch('aiofiles.open') as mock_open:
                mock_file = AsyncMock()
                mock_open.return_value.__aenter__.return_value = mock_file

                await RequestLogger._log_payload_to_file_async(json_with_non_string_instructions)

                assert mock_open.call_count == 1

    @pytest.mark.asyncio
    async def test_branch_name_validation_prevents_path_traversal(self):
        """Test that branch name validation prevents path traversal attacks"""
        valid_json = b'{"test": "data"}'

        # Test various malicious branch names
        malicious_branches = ["../../../etc", "branch/with/slashes", "branch..parent", ""]

        for malicious_branch in malicious_branches:
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (malicious_branch.encode(), b'')
                mock_subprocess.return_value = mock_proc

                async_to_thread = AsyncMock(return_value=None)
                with patch('asyncio.to_thread', new=async_to_thread):
                    await RequestLogger._log_payload_to_file_async(valid_json)

                if async_to_thread.await_count:
                    call_args = async_to_thread.call_args.args
                    assert "unknown" in str(call_args[0])

    @pytest.mark.asyncio
    async def test_error_handling_in_file_operations(self):
        """Test that file operation errors are handled gracefully"""
        valid_json = b'{"test": "data"}'

        async_to_thread = AsyncMock(return_value=None)
        with patch('asyncio.to_thread', new=async_to_thread):
            with patch('aiofiles.open', side_effect=IOError("File write error")):
                with patch('codex_plus.request_logger.logger') as mock_logger:
                    await RequestLogger._log_payload_to_file_async(valid_json)

                    mock_logger.debug.assert_called()
                    assert "Async file logging failed" in str(mock_logger.debug.call_args)

    @pytest.mark.asyncio
    async def test_git_command_timeout_handling(self):
        """Test that git command timeouts are handled gracefully"""
        valid_json = b'{"test": "data"}'

        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b'', b'')
            mock_subprocess.return_value = mock_process

            async def timeout_side_effect(coro, *_args, **_kwargs):
                try:
                    await coro
                finally:
                    raise asyncio.TimeoutError

            with patch('asyncio.wait_for', side_effect=timeout_side_effect):
                async_to_thread = AsyncMock(return_value=None)
                with patch('asyncio.to_thread', new=async_to_thread):
                    with patch('aiofiles.open') as mock_open:
                        mock_file = AsyncMock()
                        mock_open.return_value.__aenter__.return_value = mock_file

                        await RequestLogger._log_payload_to_file_async(valid_json)

                        mock_open.assert_called()

    def test_exception_handling_in_main_method(self):
        """Test that exceptions in main method are caught and logged"""
        body = b'{"test": "data"}'

        with patch('asyncio.get_running_loop', side_effect=Exception("Unexpected error")):
            with patch('codex_plus.request_logger.logger') as mock_logger:
                RequestLogger.log_request_payload(body, "responses")

                # Should log error
                mock_logger.error.assert_called_once()
                assert "Failed to log request payload" in str(mock_logger.error.call_args)


# Integration test with real file operations
class TestRequestLoggerIntegration:
    """Integration tests with real file operations"""

    @pytest.mark.asyncio
    async def test_real_file_operations(self):
        """Test actual file creation with temporary directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            valid_json = b'{"test": "data", "instructions": "test instruction"}'

            # Mock the log directory to use temp directory
            with patch('codex_plus.request_logger.Path') as mock_path:
                mock_log_dir = Path(temp_dir) / "test_branch"
                mock_path.return_value = mock_log_dir

                await RequestLogger._log_payload_to_file_async(valid_json)

                # Check that files were actually created
                payload_file = mock_log_dir / "request_payload.json"
                instructions_file = mock_log_dir / "instructions.txt"

                assert payload_file.exists()
                assert instructions_file.exists()

                # Check file contents
                with open(payload_file) as f:
                    saved_payload = json.load(f)
                assert saved_payload["test"] == "data"

                with open(instructions_file) as f:
                    saved_instructions = f.read()
                assert saved_instructions == "test instruction"