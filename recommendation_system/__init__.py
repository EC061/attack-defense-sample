#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recommendation System Package

MCP-enabled package for recommending educational materials
to students based on their misconceptions using OpenAI-compatible LLMs.
"""

from .mcp_recommender import MCPMaterialRecommendationSystem
from .mcp_api_client import MCPRecommendationAPIClient
from .database import MCPDatabaseClient
from .types import (
    FileInfo,
    PageInfo,
    FileData,
    FileSelectionResult,
    PageSelectionResult,
    RecommendationResult,
)
from .schemas import (
    get_file_selection_schema,
    get_page_selection_schema,
    prepare_structured_output,
)

__version__ = "2.0.0"

__all__ = [
    # Main MCP-enabled class
    "MCPMaterialRecommendationSystem",
    # MCP Components
    "MCPRecommendationAPIClient",
    "MCPDatabaseClient",
    # Types
    "FileInfo",
    "PageInfo",
    "FileData",
    "FileSelectionResult",
    "PageSelectionResult",
    "RecommendationResult",
    # Schemas
    "get_file_selection_schema",
    "get_page_selection_schema",
    "prepare_structured_output",
]
