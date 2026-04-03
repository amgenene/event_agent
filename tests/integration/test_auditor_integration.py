"""Integration tests for the auditor with LLM-powered verification."""

import pytest
from unittest.mock import MagicMock, patch

from src.auditor.verifier import Auditor, EventStatus


class TestAuditorIntegration:
    """Integration tests for the auditor component."""

    def test_keyword_check_free_event(self):
        """Test keyword detection for free events."""
        auditor = Auditor()

        status = auditor.verify_event_free(
            "Free community event, open to the public. No tickets required."
        )
        assert status == EventStatus.FREE

    def test_keyword_check_paid_event(self):
        """Test keyword detection for paid events."""
        auditor = Auditor()

        status = auditor.verify_event_free(
            "Live music night. Cover charge $10. Drink minimum $20."
        )
        assert status == EventStatus.PAID

    def test_keyword_check_conditional(self):
        """Test keyword detection for conditional pricing."""
        auditor = Auditor()

        status = auditor.verify_event_free(
            "Suggested donation of $5. Membership required for entry."
        )
        assert status == EventStatus.PAID

    def test_keyword_check_free_with_ticket_mention(self):
        """Test that 'free tickets' doesn't trigger paid status."""
        auditor = Auditor()

        status = auditor.verify_event_free(
            "Free tickets available at the door. No cost to attend."
        )
        assert status == EventStatus.FREE

    def test_empty_description(self):
        """Test handling of empty description."""
        auditor = Auditor()

        status = auditor.verify_event_free("")
        assert status == EventStatus.UNKNOWN

    def test_get_warnings(self):
        """Test warning extraction from event description."""
        auditor = Auditor()

        description = (
            "Free event with suggested donation. "
            "Drink minimum of $15. Cover charge waived for members. "
            "RSVP required. Limited capacity."
        )

        warnings = auditor.get_warnings(description)

        assert len(warnings) >= 4
        assert any("suggested donation" in w for w in warnings)
        assert any("drink minimum" in w for w in warnings)
        assert any("cover charge" in w for w in warnings)
        assert any("RSVP" in w for w in warnings)

    def test_get_warnings_clean_event(self):
        """Test no warnings for clean event."""
        auditor = Auditor()

        description = "Free community gathering. Everyone welcome."
        warnings = auditor.get_warnings(description)

        assert warnings == []

    def test_llm_verification_success(self):
        """Test LLM-powered verification when client is available."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"status": "FREE", "reason": "No cost indicators found"}'
                    )
                )
            ]
        )

        auditor = Auditor(llm_client=mock_client)
        status = auditor.verify_event_free("Free outdoor concert in the park.")

        assert status == EventStatus.FREE
        mock_client.chat.completions.create.assert_called_once()

    def test_llm_verification_paid(self):
        """Test LLM detects paid events."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"status": "PAID", "reason": "Cover charge of $25 mentioned"}'
                    )
                )
            ]
        )

        auditor = Auditor(llm_client=mock_client)
        status = auditor.verify_event_free("Jazz night with $25 cover charge.")

        assert status == EventStatus.PAID

    def test_llm_verification_fallback_on_parse_error(self):
        """Test fallback to keyword check when LLM response is malformed."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json"))]
        )

        auditor = Auditor(llm_client=mock_client)
        status = auditor.verify_event_free("Free event, no cost.")

        assert status == EventStatus.FREE

    def test_llm_verification_fallback_on_exception(self):
        """Test fallback to keyword check when LLM call fails."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        auditor = Auditor(llm_client=mock_client)
        status = auditor.verify_event_free("Free community event.")

        assert status == EventStatus.FREE

    def test_llm_with_invoke_interface(self):
        """Test LLM client using invoke interface (LangChain-style)."""

        class InvokeClient:
            def invoke(self, prompt):
                return '{"status": "CONDITIONAL", "reason": "Suggested donation"}'

        auditor = Auditor(llm_client=InvokeClient())
        status = auditor.verify_event_free("Event with suggested donation.")

        assert status == EventStatus.CONDITIONAL

    def test_full_audit_pipeline(self):
        """Test complete audit pipeline: keyword check + LLM + warnings."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"status": "CONDITIONAL", "reason": "Suggested donation mentioned"}'
                    )
                )
            ]
        )

        auditor = Auditor(llm_client=mock_client)
        description = "Free art exhibition. Suggested donation $5. RSVP required."

        status = auditor.verify_event_free(description)
        warnings = auditor.get_warnings(description)

        assert status == EventStatus.CONDITIONAL
        assert len(warnings) >= 2
