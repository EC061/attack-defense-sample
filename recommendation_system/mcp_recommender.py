#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP-enabled recommender that lets the LLM orchestrate all database queries.
"""

import os
import json
from typing import Dict, Any, Optional, List
from openai import OpenAI
from dotenv import load_dotenv
from config_loader import load_config
from pdf_description_gen.logger import MarkdownLogger
from .mcp_api_client import MCPRecommendationAPIClient
from .prompt_injection_filter import PromptInjectionFilter
from .pii_filter import PIIFilter

# Global toggle for prompt injection filter
PROMPT_INJECTION_FILTER_ENABLED = True
# Global toggle for PII filter
PII_FILTER_ENABLED = True

# Load environment variables from .env file
load_dotenv()


class MCPMaterialRecommendationSystem:
    """
    MCP-enabled recommendation system where the LLM directly queries the database.

    Unlike the original system that manually fetches data and makes two separate
    LLM calls (file selection, then page selection), this system gives the LLM
    direct access to the MCP SQLite server and lets it orchestrate all queries
    and decisions in a single streaming session.
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
        db_path: Optional[str] = None,
        enable_filter: bool = True,
        enable_pii_filter: bool = True,
    ):
        """
        Initialize the MCP-enabled recommendation system.

        Args:
            api_base: Base URL for the OpenAI-compatible API (defaults from config.yml)
            api_key: API key (defaults from config.yml)
            model_name: Name of the LLM model to use (defaults from config.yml)
            timeout: Request timeout in seconds (defaults from config.yml)
            db_path: Path to SQLite database (defaults from config.yml)
            enable_filter: Whether to enable prompt injection filtering (defaults to True)
            enable_pii_filter: Whether to enable PII filtering (defaults to True)
        """
        # Read configuration from YAML
        cfg = load_config()
        self.platform = cfg.get("api", {}).get("platform", "openai").lower()
        self.cfg = cfg

        # Get platform-specific API configuration
        api_config = cfg.get("api", {}).get(self.platform, {})

        # Determine optional service tier for OpenAI platform
        service_tier = api_config.get("service_tier")
        if isinstance(service_tier, str):
            service_tier = service_tier.strip().lower()
        self.service_tier = service_tier or None

        # Get values from YAML or use provided values or fallback defaults
        if api_base is None:
            api_base = (api_config.get("base_url") or "").strip()
            if not api_base:
                api_base = "https://api.openai.com/v1"

        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY", api_config.get("key", ""))

        if model_name is None:
            model_name = api_config.get("llm_model", "gpt-5")

        if timeout is None:
            timeout = int(cfg.get("api", {}).get("timeout", 3600))

        if db_path is None:
            db_path = cfg.get("paths", {}).get(
                "materials_db_path", "materials/processed_materials.db"
            )

        # Make db_path absolute
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)

        self.db_path = db_path
        self.model_name = model_name
        self.enable_filter = enable_filter and PROMPT_INJECTION_FILTER_ENABLED
        self.enable_pii_filter = enable_pii_filter and PII_FILTER_ENABLED

        # Initialize OpenAI client
        client = OpenAI(api_key=api_key, base_url=api_base, timeout=timeout)

        # Initialize MCP-enabled API client
        self.api_client = MCPRecommendationAPIClient(
            client, model_name, db_path, self.service_tier
        )
        self.logger = MarkdownLogger(log_dir="logs")

        # Initialize Prompt Injection Filter
        self.filter = PromptInjectionFilter(client, model_name)

        # Initialize PII Filter
        self.pii_filter = PIIFilter(client, model_name)

    def recommend_for_student(
        self,
        student_id: str,
        student_question: Optional[str] = None,
        system_instruction: Optional[str] = None,
        verbose: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations for a student by letting the LLM orchestrate everything.

        The LLM will:
        1. Query the database to find the student's errors
        2. Query available materials
        3. For each error, select the best file and page range
        4. Return structured recommendations

        Args:
            student_id: The student ID
            student_question: Optional question/context from the student
            system_instruction: Optional custom system instruction (for testing/attacks)
            verbose: If True, print progress information

        Returns:
            List of recommendation dictionaries
        """
        if verbose:
            print("\n" + "=" * 80)
            print("MCP-ENABLED EDUCATIONAL MATERIAL RECOMMENDATION SYSTEM")
            print("=" * 80)
            print(f"Student ID: {student_id}")
            if student_question:
                print(f"Student Question: {student_question}")
            print("=" * 80 + "\n")

        # Apply prompt injection filter if enabled and input is present
        effective_student_question = student_question

        if self.enable_filter and student_question:
            if verbose:
                print("Analyzing input for prompt injection...")

            analysis = self.filter.analyze(student_question)

            if verbose:
                print("\n" + "-" * 40)
                print("PROMPT INJECTION ANALYSIS")
                print("-" * 40)
                print(json.dumps(analysis, indent=2))
                print("-" * 40 + "\n")

            # Use cleaned prompt if provided
            if analysis.get("cleaned_prompt") is not None:
                effective_student_question = analysis["cleaned_prompt"]
                if effective_student_question != student_question and verbose:
                    print(f"Using sanitized prompt: {effective_student_question}")

        # Let the LLM orchestrate all queries and decisions
        result = self.api_client.generate_recommendation(
            student_id=student_id,
            student_question=effective_student_question,
            system_instruction=system_instruction,
            verbose=verbose,
        )

        # Log the complete interaction
        self.logger.log_request(
            request_type="mcp_recommendation_full_flow",
            prompt=f"Student ID: {student_id}\nStudent Question: {student_question or 'None'}",
            content=result["raw_content"],
            metrics=result["metrics"],
            model_name=self.model_name,
            additional_info={
                "Student ID": student_id,
                "Student Question": student_question or "None",
                "Tool Calls": len(result.get("tool_calls", [])),
                "Tool Call Details": result.get("tool_calls", []),
            },
        )

        # Extract recommendations from the response
        recommendations = result["content"]

        # Ensure it's a list
        if isinstance(recommendations, dict):
            if "recommendations" in recommendations:
                recommendations = recommendations["recommendations"]
            elif "error" not in recommendations:
                # Single recommendation, wrap in list
                recommendations = [recommendations]
            else:
                # Error case
                recommendations = []

        # Apply PII filter if enabled
        if self.enable_pii_filter:
            if verbose:
                print("Analyzing response for PII...")

            # Analyze using PII filter
            pii_analysis = self.pii_filter.analyze_and_redact(
                recommendations, student_id
            )

            if verbose:
                print("\n" + "-" * 40)
                print("PII ANALYSIS")
                print("-" * 40)
                print(json.dumps(pii_analysis, indent=2))
                print("-" * 40 + "\n")

            # Update recommendations with sanitized version if available
            if pii_analysis.get("sanitized_response") is not None:
                recommendations = pii_analysis["sanitized_response"]

            # Re-ensure list structure as the filter might return what we passed it
            # The structure of recommendations passed to filter is already a list (or dict)
            # The sanitized response should preserve that structure.

        if verbose:
            print("\n" + "=" * 80)
            print("RECOMMENDATION SUMMARY")
            print("=" * 80)
            print(f"Generated {len(recommendations)} recommendation(s)")

            for i, rec in enumerate(recommendations, 1):
                print(f"\n--- Recommendation {i} ---")
                print(f"Question: {rec.get('question', 'N/A')[:80]}...")
                print(f"Wrong Answer: {rec.get('wrong_answer', 'N/A')}")
                print(f"Selected File: {rec.get('selected_file', 'N/A')}")
                print(
                    f"Pages: {rec.get('start_page', 'N/A')} - {rec.get('end_page', 'N/A')}"
                )
                print(f"File Reasoning: {rec.get('file_reasoning', 'N/A')[:100]}...")
                print(f"Page Reasoning: {rec.get('page_reasoning', 'N/A')[:100]}...")

            print("\n" + "=" * 80)
            print("PERFORMANCE SUMMARY")
            print("=" * 80)
            metrics = result["metrics"]
            print(
                f"Total Tokens: {metrics.total_tokens} "
                f"(Prompt: {metrics.prompt_tokens}, Completion: {metrics.completion_tokens})"
            )
            if metrics.total_cost is not None:
                print(
                    f"Total Cost: ${metrics.total_cost:.6f} "
                    f"(Input: ${metrics.input_cost:.6f}, Output: ${metrics.output_cost:.6f})"
                )
            print(f"Total Time: {metrics.total_time:.3f}s")
            print(f"Tool Calls: {len(result.get('tool_calls', []))}")
            print(f"Total Retries: {result.get('total_retries', 0)}")
            print("=" * 80 + "\n")

        return recommendations

    def recommend(
        self,
        question: str,
        wrong_answer: str,
        choices: Dict[str, str],
        correct_answer: Optional[str] = None,
        student_question: Optional[str] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a recommendation for a single question (legacy interface).

        Note: This method creates a temporary student entry for compatibility
        with the original interface. For production use, prefer recommend_for_student.

        Args:
            question: The multiple choice question text
            wrong_answer: The incorrect answer the student selected
            choices: Dictionary of choices
            correct_answer: The correct answer (optional)
            student_question: Optional question/context from the student
            verbose: If True, print progress information

        Returns:
            Dictionary with recommendation result
        """
        # This is a compatibility method - the MCP system works best when
        # querying actual student data from the database
        print(
            "Warning: Using legacy interface. For best results, use recommend_for_student "
            "with actual student IDs in the database."
        )

        # Format a prompt that mimics a single-question scenario
        single_question_prompt = f"""
Generate a recommendation for this single question:

Question: {question}
Choices: {choices}
Wrong Answer: {wrong_answer}
Correct Answer: {correct_answer or "Not provided"}
"""
        if student_question:
            single_question_prompt += f"\nStudent Context: {student_question}"

        single_question_prompt += """

Query the materials database to find the best file and page range to help
understand the correct concept. Return a single recommendation with the format:
{
  "question": "...",
  "wrong_answer": "...",
  "correct_answer": "...",
  "selected_file": "filename.pdf",
  "file_reasoning": "why this file",
  "start_page": N,
  "end_page": M,
  "page_reasoning": "why this range"
}
"""

        # Use a dummy student ID
        result = self.api_client.generate_recommendation(
            student_id="single_question",
            student_question=single_question_prompt,
            verbose=verbose,
        )

        recommendations = result["content"]
        if isinstance(recommendations, list) and len(recommendations) > 0:
            return recommendations[0]
        elif isinstance(recommendations, dict) and "error" not in recommendations:
            return recommendations
        else:
            raise ValueError(f"Failed to generate recommendation: {recommendations}")
