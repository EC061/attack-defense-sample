#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP-enabled API client for recommendation system.
Uses OpenAI responses API to let the LLM directly call MCP tools.
"""

import json
import time
import asyncio
from typing import Dict, Any, Optional
from openai import OpenAI, APIError, APIConnectionError, APITimeoutError
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from pdf_description_gen.types import PerformanceMetrics
from pdf_description_gen.pricing_calculator import calculate_cost


class MCPRecommendationAPIClient:
    """Handles API communication with MCP tool integration and retry logic."""

    # Retry configuration
    INITIAL_BACKOFF = 0.001  # 1 millisecond
    MAX_BACKOFF_DELAY = 5.0  # 5 seconds

    def __init__(
        self,
        client: OpenAI,
        model_name: str,
        db_path: str,
        service_tier: Optional[str] = None,
    ):
        """
        Initialize MCP-enabled API client.

        Args:
            client: OpenAI client instance
            model_name: Name of the model to use
            db_path: Path to SQLite database for MCP server
            service_tier: Optional service tier for API requests
        """
        self.client = client
        self.model_name = model_name
        self.db_path = db_path
        self.service_tier = service_tier

    async def _run_mcp_flow(
        self, system_instruction: str, user_message: str, verbose: bool
    ) -> Dict[str, Any]:
        """
        Async implementation of the MCP flow.
        """
        # Configure MCP server
        server_params = StdioServerParameters(
            command="uvx",
            args=["mcp-server-sqlite", "--db-path", self.db_path],
            env=None,
        )

        tool_calls_log = []
        start_time = time.time()
        first_token_time = None
        prompt_tokens = 0
        completion_tokens = 0
        total_retries = 0  # Track total retries across all API calls

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message},
        ]

        final_content = ""

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Get available tools
                mcp_tools = await session.list_tools()
                openai_tools = []
                for tool in mcp_tools.tools:
                    openai_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema,
                            },
                        }
                    )

                if verbose:
                    print(f"Loaded {len(openai_tools)} tools from MCP server.")

                # Loop for tool execution
                while True:
                    if verbose:
                        print("\nCalling LLM...")

                    # Prepare request args
                    create_kwargs = {
                        "model": self.model_name,
                        "messages": messages,
                        "tools": openai_tools,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    }
                    if self.service_tier:
                        create_kwargs["service_tier"] = self.service_tier

                    # Call OpenAI with retry logic
                    retry_count = 0

                    while True:
                        try:
                            stream = self.client.chat.completions.create(
                                **create_kwargs
                            )
                            total_retries += retry_count  # Add retries from this call
                            break  # Success, exit retry loop
                        except (APIError, APIConnectionError, APITimeoutError) as e:
                            # Check if it's a retriable error
                            is_retriable = False
                            if isinstance(e, APIError):
                                status_code = getattr(e, "status_code", None)
                                if status_code in [500, 502, 503, 504]:
                                    is_retriable = True
                            elif isinstance(e, (APIConnectionError, APITimeoutError)):
                                is_retriable = True

                            if is_retriable:
                                # Calculate delay with exponential backoff
                                delay = min(
                                    self.MAX_BACKOFF_DELAY,
                                    self.INITIAL_BACKOFF * (2**retry_count),
                                )
                                retry_count += 1
                                if verbose:
                                    print(
                                        f"\n[Retry {retry_count}] Retrying after {delay:.3f}s due to: {e}"
                                    )
                                await asyncio.sleep(delay)
                                continue
                            else:
                                # Not retriable - fail immediately
                                raise
                        except Exception:
                            # Non-retriable errors should not be retried
                            raise

                    current_content = ""
                    current_tool_calls = {}  # Index -> ToolCall object builder

                    for chunk in stream:
                        if chunk.usage:
                            prompt_tokens += chunk.usage.prompt_tokens
                            completion_tokens += chunk.usage.completion_tokens

                        delta = chunk.choices[0].delta if chunk.choices else None

                        if delta:
                            # Track TTFT
                            if first_token_time is None and delta.content:
                                first_token_time = time.time()

                            if delta.content:
                                current_content += delta.content
                                if verbose:
                                    print(delta.content, end="", flush=True)

                            if delta.tool_calls:
                                for tc in delta.tool_calls:
                                    if tc.index not in current_tool_calls:
                                        current_tool_calls[tc.index] = {
                                            "id": tc.id,
                                            "name": tc.function.name,
                                            "arguments": "",
                                        }
                                    if tc.id:
                                        current_tool_calls[tc.index]["id"] = tc.id
                                    if tc.function.name:
                                        current_tool_calls[tc.index]["name"] = (
                                            tc.function.name
                                        )
                                    if tc.function.arguments:
                                        current_tool_calls[tc.index]["arguments"] += (
                                            tc.function.arguments
                                        )

                    # Check if we have tool calls
                    if current_tool_calls:
                        # Append assistant message with tool calls
                        assistant_msg = {
                            "role": "assistant",
                            "content": current_content if current_content else None,
                            "tool_calls": [],
                        }

                        for idx in sorted(current_tool_calls.keys()):
                            tc_data = current_tool_calls[idx]
                            assistant_msg["tool_calls"].append(
                                {
                                    "id": tc_data["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc_data["name"],
                                        "arguments": tc_data["arguments"],
                                    },
                                }
                            )

                            tool_calls_log.append(
                                {
                                    "name": tc_data["name"],
                                    "arguments": tc_data["arguments"],
                                }
                            )

                            if verbose:
                                print(f"\n[Tool Call: {tc_data['name']}]")
                                print(f"Arguments: {tc_data['arguments']}")

                        messages.append(assistant_msg)

                        # Execute tools
                        for tc in assistant_msg["tool_calls"]:
                            tool_name = tc["function"]["name"]
                            tool_args_str = tc["function"]["arguments"]
                            try:
                                tool_args = json.loads(tool_args_str)
                                result = await session.call_tool(
                                    tool_name, arguments=tool_args
                                )
                                # Convert result to string (handling TextContent/ImageContent)
                                result_text = ""
                                for content_item in result.content:
                                    if content_item.type == "text":
                                        result_text += content_item.text
                                    elif content_item.type == "image":
                                        result_text += "[Image]"

                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc["id"],
                                        "content": result_text,
                                    }
                                )
                                if verbose:
                                    print(f"[Tool Result] Length: {len(result_text)}")

                            except Exception as e:
                                error_msg = (
                                    f"Error executing tool {tool_name}: {str(e)}"
                                )
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc["id"],
                                        "content": error_msg,
                                    }
                                )
                                if verbose:
                                    print(f"[Tool Error] {error_msg}")

                        # Continue loop to send tool results back to LLM
                        continue

                    else:
                        # No tool calls, this is the final response
                        final_content = current_content
                        break

        end_time = time.time()
        total_time = end_time - start_time
        ttft = first_token_time - start_time if first_token_time else 0
        generation_time = (
            end_time - first_token_time if first_token_time else total_time
        )

        # Estimate tokens if not provided in chunks (older models/API versions)
        if prompt_tokens == 0 and completion_tokens == 0:
            # Very rough estimate
            pass

        # Calculate cost
        cost_details = None
        if prompt_tokens > 0 or completion_tokens > 0:
            try:
                cost_details = calculate_cost(
                    model_name=self.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cached_tokens=0,
                    service_tier=self.service_tier,
                )
            except Exception as e:
                if verbose:
                    print(f"Warning: Could not calculate cost: {e}")

        # Create PerformanceMetrics object
        metrics = PerformanceMetrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            total_time=total_time,
            ttft=ttft,
            generation_time=generation_time,
            pp_per_sec=prompt_tokens / ttft if ttft > 0 else 0,
            tg_per_sec=completion_tokens / generation_time
            if generation_time > 0
            else 0,
            input_cost=cost_details["input_cost"] if cost_details else None,
            output_cost=cost_details["output_cost"] if cost_details else None,
            total_cost=cost_details["total_cost"] if cost_details else None,
        )

        # Parse JSON response
        try:
            content_str = final_content
            # Try to extract JSON from markdown code blocks if present
            if "```json" in content_str:
                json_start = content_str.find("```json") + 7
                json_end = content_str.find("```", json_start)
                content_str = content_str[json_start:json_end].strip()
            elif "```" in content_str:
                json_start = content_str.find("```") + 3
                json_end = content_str.find("```", json_start)
                content_str = content_str[json_start:json_end].strip()

            parsed_content = json.loads(content_str)
        except json.JSONDecodeError as e:
            if verbose:
                print(f"Warning: Failed to parse JSON response: {e}")
            # Return raw content if parsing fails
            parsed_content = {"raw_response": final_content, "error": str(e)}

        if verbose:
            print(f"\nTotal retries: {total_retries}")

        return {
            "content": parsed_content,
            "raw_content": final_content,
            "metrics": metrics,
            "tool_calls": tool_calls_log,
            "total_retries": total_retries,
        }

    def generate_recommendation(
        self,
        student_id: str,
        student_question: Optional[str] = None,
        system_instruction: Optional[str] = None,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate recommendations by letting the LLM orchestrate MCP queries.

        Args:
            student_id: The student ID to generate recommendations for
            student_question: Optional question/context from the student
            system_instruction: Optional custom system instruction (for testing/attacks)
            verbose: If True, print detailed information

        Returns:
            Dictionary with recommendations and metrics
        """
        # Build the system instruction
        if system_instruction is None:
            system_instruction = """You are an educational assistant that helps students learn from their mistakes.

Step by step process:
1. Query the database to find questions where the student made errors
2. For each error, start by querying the materials table to get all files, their summaries and key concepts using specific SQL: "SELECT * FROM materials WHERE current_filename = 'all'"
3. Select one most relevant file that addresses the student's misconception based on the file's summary and key concepts, do not query any other files in the next step other than the selected file
4. Query the materials table to get the pages within the selected file that are relevant to the student's misconception using specific SQL: "SELECT * FROM materials WHERE original_filename = 'selected_file' AND needed = 1"
5. Select a focused page range (3-5 pages) within that file that covers the concept
6. Return a structured JSON response with all recommendations

Database schema:
- materials: id, original_filename, current_filename, status, description, needed, key_concept
  * current_filename='all' indicates file-level summary with key_concepts as JSON array
  * current_filename with '_page_N' indicates page-level entry (needed=1 means relevant)
- student_choices: student_id, question_id, student_choice, correct_choice
- questions: id, question, a, b, c, d, correct_choice
- students: id, name, gender, email, address, phone_number

Return JSON array of recommendations, each with:
{
  "question": "...",
  "wrong_answer": "...",
  "correct_answer": "...",
  "selected_file": "file name",
  "file_reasoning": "why this file",
  "start_page": page number,
  "end_page": page number,
  "page_reasoning": "why this range"
}

Be thorough in your reasoning. Use the database queries to make informed decisions."""

        user_message = f"Generate recommendations for student ID: {student_id}"
        if student_question:
            user_message += f"\\n\\nStudent's question/context: {student_question}"

        if verbose:
            print("\\n" + "=" * 80)
            print("STARTING MCP-ENABLED RECOMMENDATION GENERATION")
            print("=" * 80)
            print(f"Model: {self.model_name}")
            print(f"Student ID: {student_id}")
            print(f"Database: {self.db_path}")
            print("=" * 80 + "\\n")

        try:
            return asyncio.run(
                self._run_mcp_flow(system_instruction, user_message, verbose)
            )
        except Exception as e:
            print(f"Error generating recommendation: {e}")
            raise
