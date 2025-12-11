#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON schemas for structured output in recommendation system.
"""

from typing import Dict, Any, Optional, Tuple


def get_file_selection_schema() -> Dict[str, Any]:
    """
    Get JSON schema for file selection structured output.

    Returns:
        JSON schema dictionary for file selection
    """
    return {
        "type": "object",
        "title": "file_selection",
        "additionalProperties": False,
        "properties": {
            "selected_file": {
                "type": "string",
                "description": "The filename of the selected material",
            },
            "reasoning": {
                "type": "string",
                "description": "Explanation for why this file was selected",
            },
        },
        "required": ["selected_file", "reasoning"],
    }


def get_page_selection_schema() -> Dict[str, Any]:
    """
    Get JSON schema for page selection structured output.

    Returns:
        JSON schema dictionary for page selection
    """
    return {
        "type": "object",
        "title": "page_selection",
        "additionalProperties": False,
        "properties": {
            "start_page": {
                "type": "integer",
                "description": "Starting page number of the recommended range",
            },
            "end_page": {
                "type": "integer",
                "description": "Ending page number of the recommended range",
            },
            "reasoning": {
                "type": "string",
                "description": "Explanation for why this page range was selected",
            },
        },
        "required": ["start_page", "end_page", "reasoning"],
    }


def prepare_structured_output(
    schema: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Prepare structured output parameters for OpenAI API.

    Args:
        schema: JSON schema dictionary

    Returns:
        Tuple of (extra_body, response_format) where extra_body is None for OpenAI
    """
    # OpenAI format: use response_format parameter
    schema_name = schema.get("title", "structured_output")

    response_format = {
        "type": "json_schema",
        "json_schema": {"name": schema_name, "schema": schema, "strict": True},
    }

    return None, response_format
