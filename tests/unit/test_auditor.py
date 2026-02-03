"""Unit tests for auditor module."""

import pytest
from src.auditor.verifier import Auditor, EventStatus


class TestAuditor:
    """Test cases for Auditor."""
    
    @pytest.fixture
    def auditor(self):
        """Create auditor instance."""
        return Auditor()
    
    def test_auditor_initialization(self, auditor):
        """Test auditor initialization."""
        assert auditor.llm_client is None
        assert len(auditor.cost_indicators) > 0
    
    def test_verify_free_event(self, auditor):
        """Test verification of clearly free event."""
        description = "Free community jazz night! No tickets required. Everyone welcome."
        result = auditor.verify_event_free(description)
        
        assert result == EventStatus.FREE
    
    def test_verify_paid_event(self, auditor):
        """Test detection of paid events."""
        description = "Jazz night - $25 ticket required. Limited seating available."
        result = auditor.verify_event_free(description)
        
        assert result == EventStatus.PAID
    
    def test_verify_event_with_cover_charge(self, auditor):
        """Test detection of cover charge."""
        description = "Live band at the venue. $15 cover charge per person."
        result = auditor.verify_event_free(description)
        
        assert result == EventStatus.PAID
    
    def test_verify_event_with_drink_minimum(self, auditor):
        """Test detection of drink minimum."""
        description = "Happy hour event - $5 drink minimum per person."
        result = auditor.verify_event_free(description)
        
        assert result == EventStatus.PAID
    
    def test_verify_event_with_donation(self, auditor):
        """Test detection of suggested donation."""
        description = "Community fundraiser - suggested donation $10."
        result = auditor.verify_event_free(description)
        
        assert result == EventStatus.PAID
    
    def test_verify_empty_description(self, auditor):
        """Test handling of empty description."""
        result = auditor.verify_event_free("")
        
        assert result == EventStatus.UNKNOWN
    
    def test_get_warnings_for_donation(self, auditor):
        """Test warning detection for suggested donation."""
        description = "Community event - suggested donation $5."
        warnings = auditor.get_warnings(description)
        
        assert any("suggested donation" in w.lower() for w in warnings)
    
    def test_get_warnings_for_drink_minimum(self, auditor):
        """Test warning detection for drink minimum."""
        description = "Bar event - $5 drink minimum."
        warnings = auditor.get_warnings(description)
        
        assert any("drink minimum" in w.lower() for w in warnings)
    
    def test_get_warnings_for_cover_charge(self, auditor):
        """Test warning detection for cover charge."""
        description = "Live music venue - $10 cover charge."
        warnings = auditor.get_warnings(description)
        
        assert any("cover charge" in w.lower() for w in warnings)
    
    def test_get_no_warnings_for_free_event(self, auditor):
        """Test no warnings for free event."""
        description = "Free event! Open to public. No tickets required."
        warnings = auditor.get_warnings(description)
        
        assert len(warnings) == 0
    
    def test_cost_indicators_exist(self, auditor):
        """Test that cost indicators are defined."""
        assert "ticket" in auditor.cost_indicators
        assert "paid entry" in auditor.cost_indicators
        assert "cover charge" in auditor.cost_indicators
