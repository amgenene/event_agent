"""Integration tests for input parser with LLM and rule-based modes."""

import pytest
from unittest.mock import MagicMock, patch
import json

from src.input_parser.parser import InputParser, ParsedIntent


class TestInputParserIntegration:
    """Integration tests for the input parser."""

    def test_rule_based_basic_query(self):
        """Test rule-based parsing of basic query."""
        parser = InputParser()

        intent = parser.parse_input("Find free jazz events in San Francisco")

        assert intent.query == "Find free jazz events in San Francisco"
        assert intent.genres == ["music", "arts", "tech"]
        assert isinstance(intent.genres, list)

    def test_rule_based_with_preferences(self):
        """Test rule-based parsing with user preferences."""
        parser = InputParser()
        preferences = {
            "home_city": "Austin",
            "favorite_genres": ["tech", "music"],
            "radius_miles": 15,
            "max_transit_minutes": 45,
            "time_window_days": 14,
        }

        intent = parser.parse_input("Find events", preferences)

        assert intent.location == "Austin"
        assert intent.genres == ["tech", "music"]
        assert intent.radius_miles == 15
        assert intent.max_transit_minutes == 45
        assert intent.time_window_days == 14

    def test_rule_based_date_extraction(self):
        """Test date pattern extraction."""
        parser = InputParser()

        intent = parser.parse_input("Find events tonight")
        assert intent.date is not None

        intent = parser.parse_input("Find events this weekend")
        assert intent.date is not None

        intent = parser.parse_input("Find events next week")
        assert intent.date is not None

    def test_rule_based_time_window_extraction(self):
        """Test time window extraction from natural language."""
        parser = InputParser()

        assert parser._extract_time_window("Find events tonight") == 1
        assert parser._extract_time_window("Find events today") == 1
        assert parser._extract_time_window("Find events this week") == 7
        assert parser._extract_time_window("Find events this weekend") == 7
        assert parser._extract_time_window("Find events next week") == 14
        assert parser._extract_time_window("Find events this month") == 30

    def test_rule_based_participant_extraction(self):
        """Test participant extraction from input."""
        parser = InputParser()

        intent = parser.parse_input("Find events with Alice and Bob")
        assert len(intent.participants) >= 1

        intent = parser.parse_input("Find events for me and Charlie")
        assert len(intent.participants) >= 1

    def test_llm_parsing_success(self):
        """Test LLM-powered parsing when client is available."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {
                                "query": "jazz concerts",
                                "location": "San Francisco",
                                "genres": ["jazz", "music"],
                                "date": None,
                                "radius_miles": 10,
                                "max_transit_minutes": 30,
                                "time_window_days": 7,
                                "participants": ["alice@example.com"],
                            }
                        )
                    )
                )
            ]
        )

        parser = InputParser(llm_client=mock_client)
        intent = parser.parse_input("Find jazz concerts in SF with alice@example.com")

        assert intent.query == "jazz concerts"
        assert intent.location == "San Francisco"
        assert "jazz" in intent.genres
        assert "alice@example.com" in intent.participants

    def test_llm_parsing_fallback_on_error(self):
        """Test fallback to rule-based when LLM fails."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        parser = InputParser(llm_client=mock_client)
        intent = parser.parse_input("Find events in Austin", {"home_city": "Austin"})

        assert intent is not None
        assert intent.location == "Austin"

    def test_llm_parsing_fallback_on_invalid_json(self):
        """Test fallback to rule-based when LLM returns invalid JSON."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not valid json"))]
        )

        parser = InputParser(llm_client=mock_client)
        intent = parser.parse_input("Find events in Austin")

        assert intent is not None

    def test_parsed_intent_defaults(self):
        """Test ParsedIntent default values."""
        intent = ParsedIntent(query="test")

        assert intent.genres == []
        assert intent.participants == []
        assert intent.location is None
        assert intent.date is None
        assert intent.radius_miles == 5
        assert intent.max_transit_minutes == 30
        assert intent.time_window_days == 7

    def test_parsed_intent_with_participants(self):
        """Test ParsedIntent with participants list."""
        intent = ParsedIntent(
            query="group event",
            participants=["alice@example.com", "bob@example.com"],
        )

        assert len(intent.participants) == 2
        assert "alice@example.com" in intent.participants

    def test_full_pipeline_with_llm_and_preferences(self):
        """Test full parsing pipeline with LLM and user preferences."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {
                                "query": "outdoor concerts",
                                "location": "Austin",
                                "genres": ["music", "outdoor"],
                                "date": "2026-04-15",
                                "radius_miles": 20,
                                "max_transit_minutes": 45,
                                "time_window_days": 14,
                                "participants": [],
                            }
                        )
                    )
                )
            ]
        )

        parser = InputParser(llm_client=mock_client)
        preferences = {
            "home_city": "Austin",
            "favorite_genres": ["music"],
            "latitude": 30.2672,
            "longitude": -97.7431,
        }

        intent = parser.parse_input(
            "Find outdoor concerts in Austin next week", preferences
        )

        assert intent.query == "outdoor concerts"
        assert intent.location == "Austin"
        assert intent.radius_miles == 20
        assert intent.max_transit_minutes == 45
