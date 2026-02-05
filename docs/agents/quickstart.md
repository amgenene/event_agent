# Deep Agents Quickstart (Lean)

This quickstart shows how to stand up a minimal Deep Agents workflow, then points to the next steps.

## What Deep Agents Are
Deep Agents is an agent harness built on LangChain and LangGraph. It includes built-in planning helpers (like task list creation), a filesystem backend, and support for subagents so you can scale from a single agent to a multi-agent workflow as complexity grows.

`create_deep_agent` returns a compiled LangGraph graph and requires a model that supports tool calling.

## Prereqs
- A model API key for any LangChain-compatible provider (e.g., Anthropic, OpenAI, Google).
- A search provider key if you want web search (Tavily is used in the example below).

## Install
```bash
pip install deepagents
# optional, only if you want Tavily in the example below
pip install tavily-python
```

## Set Environment Variables
```bash
export TAVILY_API_KEY=your_tavily_key
# also set your model key, e.g.
export ANTHROPIC_API_KEY=your_anthropic_key
```

## Minimal Example
```python
import os
from tavily import TavilyClient
from deepagents import create_deep_agent

tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def internet_search(query: str, max_results: int = 5):
    return tavily.search(query, max_results=max_results)

agent = create_deep_agent(
    tools=[internet_search],
    system_prompt="You are a helpful research assistant.",
)

result = agent.invoke({
    "messages": [
        {"role": "user", "content": "Find free jazz events in Chicago this week."}
    ]
})

print(result["messages"][-1].content)
```

## What The Agent Does (Typical Flow)
1. Builds a plan or task list.
2. Uses tools (like search) to gather evidence.
3. Optionally spins up subagents for focused subtasks.
4. Synthesizes a final response and returns messages.

## References
- Deep Agents README (overview, features, and examples)
- LangGraph and LangChain documentation

## Next Steps
- Add tools for calendars, maps, or internal APIs.
- Add subagents for specialized tasks (e.g., “events extractor”, “price verifier”).
- Add guardrails and structured output schemas for safety and consistency.

## Notes For This Repo
If you want to integrate Deep Agents into `event_searcher`, consider using it as a higher-level orchestration layer that calls the existing `DiscoveryAgent`, `Auditor`, and `CalendarAgent` tools, while keeping provider keys and PII isolated per agent.
