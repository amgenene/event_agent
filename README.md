# EventFinder AI - Complete Technical Implementation

Multi-agent autonomous system for discovering free events using voice commands and natural language processing.

## Project Structure

```
event_searcher/
├── src/
│   ├── api.py                      # FastAPI application
│   ├── input_parser/
│   │   ├── __init__.py
│   │   └── parser.py               # Voice-to-intent conversion
│   ├── discovery_agent/
│   │   ├── __init__.py
│   │   └── searcher.py             # Event discovery via Tavily AI
│   ├── calendar_agent/
│   │   ├── __init__.py
│   │   └── scheduler.py            # Calendar integration & travel time
│   ├── auditor/
│   │   ├── __init__.py
│   │   └── verifier.py             # Free event verification
│   ├── resilience/
│   │   ├── __init__.py
│   │   └── edge_case_handler.py    # Edge case handling
│   └── orchestration/
│       ├── __init__.py
│       └── manager.py              # Workflow orchestration
├── tauri_frontend/                 # Desktop Application
│   ├── src-tauri/                  # Rust backend for Tauri
│   └── src/                        # React Frontend
├── tests/
│   ├── unit/
│   │   ├── test_input_parser.py
│   │   ├── test_discovery_agent.py
│   │   ├── test_calendar_agent.py
│   │   ├── test_auditor.py
│   │   ├── test_resilience.py
│   │   └── test_orchestration.py
│   └── integration/
│       └── test_complete_workflow.py
├── docs/
│   ├── input_parser/
│   ├── discovery_agent/
│   ├── calendar_agent/
│   ├── auditor/
│   ├── resilience/
│   ├── orchestration/
│   └── stack/
├── conftest.py                     # Pytest configuration
├── pyproject.toml                  # Project dependencies
├── requirements.txt                # Additional dependencies
└── README.md                       # This file
```

## Components

### 1. **Desktop App** (Frontend)
- **Tech**: Tauri + React + TypeScript
- **Role**: Voice command capture, displaying itineraries, and user feedback.

### 2. **Input Parser** (Whisper Layer)
Converts voice/text input to structured intent using:
- Speech-to-text (STT) via OpenAI Whisper or Deepgram
- LLM-powered intent mapping
- Default preferences for vague inputs

### 2. **Discovery Agent** (Live Search)
Searches for events using:
- Tavily AI (primary search engine)
- Domain-specific crawling strategies
- Site-specific searches (Eventbrite, Meetup, etc.)

### 3. **Calendar Agent** (Logic Gap)
Manages scheduling constraints:
- Nylas API for unified calendar access
- Travel time calculation via Google Maps
- Availability gap detection

### 4. **Auditor** (Verification)
Ensures events are truly free:
- LLM-powered description analysis
- Hidden cost detection
- Warnings for conditional pricing

### 5. **Resilience Handler** (Edge Cases)
Manages failures with relaxation strategies:
- Search radius expansion
- Category broadening
- API failover
- Drop-in event flexibility

### 6. **Manager** (Orchestration)
Coordinates the 5-step workflow:
1. Ingestion - Parse voice to intent
2. Constraint Check - Check calendar availability
3. Discovery - Search for events
4. Verification - Audit events
5. Relaxation - Handle edge cases

## Installation

```bash
# Clone repository
git clone <repo-url>
cd event_searcher

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or using poetry
poetry install
```

## Configuration

Create a `.env` file with required API keys:

```env
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
NYLAS_API_KEY=your_nylas_key
GOOGLE_MAPS_API_KEY=your_maps_key
DEEPGRAM_API_KEY=your_deepgram_key
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/unit/test_input_parser.py

# Run integration tests only
pytest tests/integration/

# Run with verbose output
pytest -v
```

## Running the API

```bash
# Start development server
uvicorn src.api:app --reload

# Or run directly
python src/api.py

# API will be available at http://localhost:8000
# API will be available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

## Running the Desktop App (Frontend)

Prerequisites: [Rust](https://www.rust-lang.org/tools/install) and Node.js installed.

```bash
cd tauri_frontend/event_agent_frontend

# Install dependencies
npm install

# Run in development mode
npm run tauri dev
```

## API Endpoints

### POST `/search`
Search for free events
```json
{
  "query": "Find jazz events",
  "preferences": {
    "home_city": "San Francisco",
    "favorite_genres": ["jazz", "music"],
    "radius_miles": 10,
    "max_transit_minutes": 45
  }
}
```

### POST `/verify`
Verify if an event is free
```json
{
  "description": "Live jazz performance. No cover charge."
}
```

### GET `/health`
Health check endpoint

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Orchestration** | LangGraph |
| **Frontend** | Tauri, React, TypeScript |
| **Web Framework** | FastAPI |
| **STT** | Deepgram Aura |
| **Calendar API** | Nylas |
| **Web Search** | Tavily AI |
| **Maps/Travel** | Google Maps API |
| **State Management** | Redis |
| **Testing** | Pytest |
| **Language** | Python 3.10+ |

## Development

### Code Style
Uses Black for formatting and isort for import sorting:
```bash
black src/ tests/
isort src/ tests/
```

### Type Checking
```bash
mypy src/
```

### Linting
```bash
flake8 src/ tests/
```

## Architecture Principles

- **State Graph Pattern** - Handles complex workflows with backtracking
- **Multi-Agent Design** - Specialized agents for specific tasks
- **Resilience-First** - Built-in relaxation and retry strategies
- **Domain-Specific Search** - Smart crawling for free events
- **Hidden Cost Detection** - LLM-powered verification

## Edge Case Handling

| Failure | Response | Strategy |
|---------|----------|----------|
| **Zero Results** | RelaxationNode | Expand radius or broaden categories |
| **Schedule Conflict** | CalendarNode | Accept drop-in events with grace period |
| **Hidden Costs** | AuditorNode | Warn user and exclude event |
| **API Timeout** | ManagerNode | Failover to secondary API |

## Future Enhancements

- [ ] Real API integrations (Tavily, Nylas, Google Maps)
- [ ] Deepgram STT integration
- [ ] Redis session management
- [ ] Advanced LLM prompting
- [ ] Event recommendations
- [ ] User feedback loop
- [ ] Analytics and metrics

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

For questions or issues, please open a GitHub issue or contact the development team.
