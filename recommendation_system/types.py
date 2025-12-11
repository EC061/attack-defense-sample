#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Type definitions for recommendation system.
"""

from dataclasses import dataclass
from typing import List, Optional
from pdf_description_gen.types import PerformanceMetrics


@dataclass
class FileInfo:
    """Information about a file in the materials database."""

    id: int
    filename: str
    description: str
    key_concepts: List[str]


@dataclass
class PageInfo:
    """Information about a page in the materials database."""

    id: int
    page_number: int
    filename: str
    needed: Optional[bool]
    description: str
    key_concept: str


@dataclass
class FileData:
    """Combined file and page data."""

    file_info: FileInfo
    pages: List[PageInfo]


@dataclass
class FileSelectionResult:
    """Result of file selection step."""

    selected_file: str
    reasoning: str
    file_data: FileData
    metrics: Optional[PerformanceMetrics] = None


@dataclass
class PageSelectionResult:
    """Result of page selection step."""

    start_page: int
    end_page: int
    num_pages: int
    pages: List[PageInfo]
    reasoning: str
    metrics: Optional[PerformanceMetrics] = None


@dataclass
class RecommendationResult:
    """Complete recommendation result."""

    question: str
    wrong_answer: str
    correct_answer: Optional[str]
    selected_file: str
    file_reasoning: str
    start_page: int
    end_page: int
    num_pages: int
    page_reasoning: str
