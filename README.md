# Beaver's Choice Multi-Agent System Project

Welcome to the starter code repository for the **Beaver's Choice Paper Company Multi-Agent System Project**! This repository contains the starter code and tools you will need to design, build, and test a multi-agent system that supports core business operations at a fictional paper manufacturing company.

## Project Context

You’ve been hired as an AI consultant by Beaver's Choice Paper Company, a fictional enterprise looking to modernize their workflows. They need a smart, modular **multi-agent system** to automate:

- **Inventory checks** and restocking decisions
- **Quote generation** for incoming sales inquiries
- **Order fulfillment** including supplier logistics and transactions

Your solution must use a maximum of **5 agents** and process inputs and outputs entirely via **text-based communication**.

This project challenges your ability to orchestrate agents using modern Python frameworks like `smolagents`, `pydantic-ai`, or `npcsh`, and combine that with real data tools like `sqlite3`, `pandas`, and LLM prompt engineering.

---

## What’s Included

From the `project.zip` starter archive, you will find:

- `project_starter.py`: Compatibility entrypoint exposing the original starter helper names
- `beavers_choice/`: Strict hexagonal implementation with domain, ports, adapters, and app wiring
- `quotes.csv`: Historical quote data used for reference by quoting agents
- `quote_requests.csv`: Incoming customer requests used to build quoting logic
- `quote_requests_sample.csv`: A set of simulated test cases to evaluate your system

---

## Workspace Instructions

All the files have been provided in the VS Code workspace on the Udacity platform. Please install the agent orchestration framework of your choice.

## Docker setup

No local Python installation is required. Docker installs all dependencies from
`requirements.txt` inside the image.

1. Create `.env`

Add your OpenAI-compatible API key:

`UDACITY_OPENAI_API_KEY=your_openai_key_here`

This project uses a custom OpenAI-compatible proxy hosted at https://openai.vocareum.com/v1.

2. Build the image

`docker compose build`

3. Run the application

`docker compose up`

## How to Run the Project

Docker Compose reads API configuration from the local `.env` file at runtime;
the file is excluded from the image. To run once and remove the stopped
container afterward:

`docker compose run --rm app`

The same application can also be started through the package entrypoint:

`docker compose run --rm app python -m beavers_choice`

Generated files such as `beaver_choice.db`, `test_results.csv`, and
`logfire.log` are written to this project directory through the bind mount.
`logfire.log` contains local Pydantic Logfire traces for agent runs, tool calls,
and scenario outcomes. It is excluded from Git and is not sent to Logfire
Cloud. Override its path with `LOGFIRE_LOG_FILE` if needed.

Rebuild after changing `requirements.txt`:

`docker compose build --no-cache`

Run the offline regression tests:

`docker compose run --rm app pytest -q`

## Architecture

The implementation uses a strict hexagonal architecture:

- `beavers_choice/domain`: framework-independent business models, catalog
  matching, inventory, quoting, fulfillment, discount, delivery, and response
  safety rules
- `beavers_choice/ports`: `typing.Protocol` interfaces for AI, persistence,
  telemetry, output, clock, and ID generation
- `beavers_choice/adapters`: Pydantic AI, SQLAlchemy/SQLite, Logfire,
  CSV/Pandas, UUID, and system-clock implementations of those ports
- `beavers_choice/app`: production container, workflow orchestration,
  evaluation runner, and CLI entrypoint

This keeps Pydantic AI, SQLite, Pandas, and Logfire replaceable. LangChain can
replace `PydanticAiAgentAdapter`, and PostgreSQL can be used by changing the
SQLAlchemy database URL or replacing the persistence adapter.

The Decision Orchestrator Agent extracts raw customer item phrases. The domain
`CatalogMatchingService` then performs exact-name matching, aliases, and fuzzy
matching above a confidence threshold before worker agents receive catalog
items.

Start by defining your agents in the `"YOUR MULTI AGENT STARTS HERE"` section inside `template.py`. Once your agent team is ready:

1. Run the `run_test_scenarios()` function at the bottom of the script.
2. This will simulate a series of customer requests.
3. Your system should respond by coordinating inventory checks, generating quotes, and processing orders.

Output will include:

- Agent responses
- Cash and inventory updates
- Final financial report
- A validation summary with row count, cash-balance changes, completed order
  references, and the first five CSV rows
- A `test_results.csv` file with all interaction logs

---

## Tips for Success

- Start by sketching a **flow diagram** to visualize agent responsibilities and interactions.
- Test individual agent tools before full orchestration.
- Always include **dates** in customer requests when passing data between agents.
- Ensure every quote includes **bulk discounts** and uses past data when available.
- Use the **exact item names** from the database to avoid transaction failures.

---

## Submission Checklist

Make sure to submit the following files:

1. Your completed `template.py` or `project_starter.py` with all agent logic
2. A **workflow diagram** describing your agent architecture and data flow
3. `design_notes.txt`, containing the architecture explanation, evaluation
   reflection, and future improvements
4. Outputs from your test run (like `test_results.csv`)

---
