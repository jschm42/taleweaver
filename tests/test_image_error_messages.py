from backend.engine.media.image_error_messages import MAX_REASON_LENGTH, image_error_reason


def test_reason_includes_provider_message():
    # Arrange
    exc = RuntimeError("OpenRouter image generation failed: prompt rejected for keyword 'blood'")

    # Act
    reason = image_error_reason(exc)

    # Assert
    assert reason == (
        "Visual generation failed: OpenRouter image generation failed: "
        "prompt rejected for keyword 'blood'"
    )


def test_reason_redacts_secrets():
    # Arrange
    exc = RuntimeError(
        "401 for https://api.example.com/v1/images?key=abc123 with sk-proj-ABCDEFGHIJKLMNOP "
        "and Authorization: Bearer eyJhbGciOi.payload.sig"
    )

    # Act
    reason = image_error_reason(exc)

    # Assert
    assert "abc123" not in reason
    assert "sk-proj" not in reason
    assert "eyJhbGciOi" not in reason
    assert reason.count("[redacted]") == 3


def test_reason_is_clipped_and_falls_back_when_empty():
    # Act
    long_reason = image_error_reason(ValueError("word " * 500))
    empty_reason = image_error_reason(RuntimeError(""))

    # Assert
    assert long_reason.endswith("...")
    assert len(long_reason) <= MAX_REASON_LENGTH + len("Visual generation failed: ")
    assert empty_reason == "Visual generation failed."
