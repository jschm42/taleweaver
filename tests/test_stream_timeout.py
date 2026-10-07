import asyncio
import pytest
from backend.core.llm_router import GameMasterLLM


class MockChunk:
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


class MockChoice:
    def __init__(self, content: str):
        self.delta = MockDelta(content)


class MockDelta:
    def __init__(self, content: str):
        self.content = content


@pytest.mark.asyncio
async def test_stream_timeout_normal_completion() -> None:
    """Test that a healthy stream yields all chunks without interruption."""
    # Arrange
    async def sample_stream():
        for token in ["Hello", " brave", " hero", "!"]:
            await asyncio.sleep(0.01)
            yield MockChunk(token)

    # Act
    collected = []
    async for chunk in GameMasterLLM._with_stream_timeout(sample_stream(), initial_timeout=1.0, chunk_timeout=0.2):
        collected.append(chunk.choices[0].delta.content)

    # Assert
    assert "".join(collected) == "Hello brave hero!"


@pytest.mark.asyncio
async def test_stream_timeout_graceful_recovery_after_tokens() -> None:
    """Test that an LLM stream stalling after generating tokens terminates gracefully without losing narrative."""
    # Arrange
    async def stalled_stream():
        yield MockChunk("The ancient gate creaks open.")
        yield MockChunk(" Cold wind rushes past.")
        # Simulates provider keeping socket open indefinitely after finishing generation
        await asyncio.sleep(5.0)
        yield MockChunk("Should not be reached")

    # Act
    collected = []
    async for chunk in GameMasterLLM._with_stream_timeout(stalled_stream(), initial_timeout=1.0, chunk_timeout=0.1):
        collected.append(chunk.choices[0].delta.content)

    # Assert
    assert "".join(collected) == "The ancient gate creaks open. Cold wind rushes past."


@pytest.mark.asyncio
async def test_stream_timeout_raises_when_no_content_generated() -> None:
    """Test that an LLM stream stalling before emitting any tokens raises a TimeoutError."""
    # Arrange
    async def unresponsive_stream():
        await asyncio.sleep(5.0)
        yield MockChunk("Never produced")

    # Act & Assert
    with pytest.raises(TimeoutError, match="The AI model did not respond in time"):
        async for _ in GameMasterLLM._with_stream_timeout(unresponsive_stream(), initial_timeout=0.1, chunk_timeout=0.05):
            pass


@pytest.mark.asyncio
async def test_stream_timeout_preserves_narrative_on_connection_error() -> None:
    """Test that network connection drops mid-stream preserve all narrative received so far."""
    # Arrange
    async def dropping_stream():
        yield MockChunk("You draw your blade.")
        await asyncio.sleep(0.01)
        raise ConnectionResetError("Remote server closed connection")

    # Act
    collected = []
    async for chunk in GameMasterLLM._with_stream_timeout(dropping_stream(), initial_timeout=1.0, chunk_timeout=0.2):
        collected.append(chunk.choices[0].delta.content)

    # Assert
    assert "".join(collected) == "You draw your blade."
