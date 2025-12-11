#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging functionality for API requests and responses.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from .types import PerformanceMetrics


class MarkdownLogger:
    """Logs API requests and responses to markdown files."""

    def __init__(self, log_dir: str = "logs"):
        """
        Initialize markdown logger.

        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

    def _generate_semantic_filename(
        self,
        request_type: str,
        image_path: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None,
        image_number: Optional[int] = None,
    ) -> str:
        """
        Generate a semantic filename based on file name and page information.

        Args:
            request_type: Type of request ("single_page", "batch", or recommendation step)
            image_path: Path to the image(s)
            additional_info: Additional information dictionary
            image_number: Image/page number

        Returns:
            Semantic filename for the log
        """
        if request_type == "batch":
            # For batch requests, use original filename from additional_info
            if additional_info and "Original Filename" in additional_info:
                base_name = additional_info["Original Filename"]
                # Remove file extension if present
                base_name = re.sub(r"\.[^.]+$", "", base_name)
                page_info = additional_info.get("Page Numbers", "unknown")
                if isinstance(page_info, list):
                    page_info = (
                        f"pages_{min(page_info)}-{max(page_info)}"
                        if page_info
                        else "unknown"
                    )
                base_filename = f"{base_name}_batch_{page_info}.md"
            else:
                base_filename = "batch_unknown.md"

        elif request_type.startswith("recommendation_step"):
            # For recommendation requests, use generic naming
            # Determine step number
            if "step1" in request_type:
                base_filename = "example_question_step1.md"
            elif "step2" in request_type:
                base_filename = "example_question_step2.md"
            else:
                base_filename = "example_question_unknown.md"

        else:  # single_page
            # For single page requests, extract from image_path
            if image_path:
                # Get just the filename from the path
                filename = Path(image_path).name
                # Remove extension
                filename_no_ext = re.sub(r"\.[^.]+$", "", filename)
                # Extract page number if present
                page_match = re.search(r"_page_(\d+)", filename_no_ext)
                if page_match:
                    page_num = int(page_match.group(1))
                    # Remove the page part to get base name
                    base_name = re.sub(r"_page_\d+", "", filename_no_ext)
                    base_filename = f"{base_name}_page_{page_num:03d}.md"
                else:
                    # Fallback to image_number if available
                    if image_number is not None:
                        base_filename = f"{filename_no_ext}_page_{image_number:03d}.md"
                    else:
                        base_filename = f"{filename_no_ext}.md"
            else:
                # Fallback to image_number
                if image_number is not None:
                    base_filename = f"page_{image_number:03d}.md"
                else:
                    base_filename = "unknown.md"

        # Ensure uniqueness by adding counter suffix if file already exists
        counter = 0
        final_filename = base_filename
        while (self.log_dir / final_filename).exists():
            counter += 1
            # Always apply counter to the original base filename, not to existing counter suffixes
            base_name_part = base_filename.rsplit(".", 1)[
                0
            ]  # Remove .md extension from original
            final_filename = f"{base_name_part}_{counter:03d}.md"

        return final_filename

    def log_request(
        self,
        request_type: str,
        prompt: str,
        content: str,
        metrics: PerformanceMetrics,
        model_name: str,
        image_path: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None,
        image_number: Optional[int] = None,
    ) -> None:
        """
        Log API request and response to a markdown file.

        Args:
            request_type: Type of request (e.g., "single_page", "batch")
            prompt: The prompt sent to the API
            content: The response content
            metrics: Performance metrics
            model_name: Name of the model used
            image_path: Optional path to the image(s) used
            additional_info: Optional dictionary with additional information
            image_number: Optional image number for filename (falls back to timestamp)
        """
        # Generate semantic filename based on file name and page information
        filename = self._generate_semantic_filename(
            request_type, image_path, additional_info, image_number
        )
        log_file = self.log_dir / filename

        with open(log_file, "w", encoding="utf-8") as f:
            # Header
            f.write("# PDF Description Generation Log\n\n")
            f.write(f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Request Type:** {request_type}\n")
            f.write(f"**Model:** {model_name}\n\n")

            # Request details
            f.write("## Request Details\n\n")
            if image_path:
                f.write(f"**Image Path:** `{image_path}`\n\n")

            f.write("### Prompt\n\n")
            f.write("```\n")
            f.write(prompt)
            f.write("\n```\n\n")

            if additional_info:
                f.write("### Additional Information\n\n")
                for key, value in additional_info.items():
                    f.write(f"- **{key}:** {value}\n")
                f.write("\n")

            # Response
            f.write("## Response\n\n")
            f.write("### Content\n\n")
            f.write("```json\n")
            try:
                parsed = json.loads(content)
                f.write(json.dumps(parsed, indent=2, ensure_ascii=False))
            except Exception:
                f.write(content)
            f.write("\n```\n\n")

            # Metrics table
            self._write_metrics_table(f, metrics)

    def _write_metrics_table(self, f, metrics: PerformanceMetrics) -> None:
        """
        Write metrics table to file.

        Args:
            f: File handle
            metrics: Performance metrics to write
        """
        f.write("## Token Usage & Metrics\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Prompt Tokens | {metrics.prompt_tokens} |\n")
        f.write(f"| Completion Tokens | {metrics.completion_tokens} |\n")
        f.write(f"| Total Tokens | {metrics.total_tokens} |\n")
        f.write(f"| Total Time (s) | {metrics.total_time:.3f} |\n")
        f.write(f"| Time to First Token (s) | {metrics.ttft:.3f} |\n")
        f.write(f"| Generation Time (s) | {metrics.generation_time:.3f} |\n")
        f.write(f"| Prompt Processing Rate (tokens/s) | {metrics.pp_per_sec:.2f} |\n")
        f.write(f"| Token Generation Rate (tokens/s) | {metrics.tg_per_sec:.2f} |\n")

        if metrics.total_cost is not None:
            f.write(f"| **Total Cost ($)** | **{metrics.total_cost:.6f}** |\n")
            f.write(f"| Input Cost ($) | {metrics.input_cost:.6f} |\n")
            f.write(f"| Output Cost ($) | {metrics.output_cost:.6f} |\n")

        f.write("\n")
