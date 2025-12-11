# Recommendation System Package

MCP-enabled package for recommending educational materials to students based on their misconceptions using OpenAI-compatible LLMs.

## Overview

This package provides an MCP-enabled recommendation system where the LLM directly queries the database and orchestrates all decisions in a single streaming session. Unlike traditional two-step approaches, this system gives the LLM direct access to the SQLite database via MCP tools, allowing it to:

1. Query the database to find student errors
2. Query available materials (files and pages)
3. For each error, select the best file and page range
4. Return structured recommendations

## Package Structure

```
recommendation_system/
├── __init__.py              # Package exports
├── mcp_recommender.py       # MCP-enabled recommendation system
├── mcp_api_client.py        # MCP-enabled API client with tool integration
├── database.py              # Database operations for loading materials
├── schemas.py               # JSON schemas for structured outputs
├── types.py                 # Type definitions
├── ARCHITECTURE.md          # Detailed architecture documentation
└── README.md               # This file
```
