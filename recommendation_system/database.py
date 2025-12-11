#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database operations for recommendation system using MCP.
"""

import json
import re
import ast
from pathlib import Path
from typing import Dict, Any, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .types import FileInfo, PageInfo, FileData


class MCPDatabaseClient:
    """Manages database operations for recommendation system using MCP."""

    def __init__(self, db_path: str):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = str(Path(db_path).absolute())
        self.server_params = StdioServerParameters(
            command="uvx",
            args=["mcp-server-sqlite", "--db-path", self.db_path],
            env=None,
        )

    @staticmethod
    def _extract_page_number(filename: str) -> int:
        """
        Extract page number from filename.
        Expected format: originalname_page_N.ext

        Args:
            filename: Filename to extract page number from

        Returns:
            Page number (0 if not found)
        """
        match = re.search(r"_page_(\d+)", filename)
        if match:
            return int(match.group(1))
        # Fallback: try to find any number in the filename
        match = re.search(r"(\d+)", filename)
        if match:
            return int(match.group(1))
        return 0

    async def _run_query(self, query: str) -> List[Any]:
        """
        Run a SQL query via MCP.

        Args:
            query: SQL query string

        Returns:
            List of rows
        """
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # List tools to find the query tool (usually 'read_query' or similar for sqlite server)
                # For mcp-server-sqlite, the tool is typically 'read_query' taking a 'query' argument
                # We can also just try calling it directly if we know the name.
                # Based on standard mcp-server-sqlite, it exposes `read_query(query: str)`.

                result = await session.call_tool(
                    "read_query", arguments={"query": query}
                )

                # The result content is usually a list of TextContent or similar.
                # For sqlite server, it returns a JSON string or list of dicts in the text content.
                # We need to parse it.

                # Assuming the result.content is a list of TextContent, and the first one contains the JSON data.
                if not result.content:
                    return []

                try:
                    data = json.loads(result.content[0].text)
                    return data
                except (json.JSONDecodeError, AttributeError, IndexError) as e:
                    # Try ast.literal_eval as fallback for single-quoted strings (Python repr)
                    try:
                        data = ast.literal_eval(result.content[0].text)
                        return data
                    except Exception as e2:
                        print(f"Error parsing MCP result: {e}")
                        print(f"Fallback parsing failed: {e2}")
                        print(f"Raw content: {result.content}")
                        return []

    async def load_materials(self) -> Dict[str, FileData]:
        """
        Load materials metadata via MCP.

        Returns:
            Dictionary mapping filename to FileData objects
        """
        query = """
            SELECT id, original_filename, current_filename, status, 
                   description, needed, key_concept 
            FROM materials
        """

        rows = await self._run_query(query)

        # Organize data by file
        files_data: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            # mcp-server-sqlite usually returns list of dicts
            if isinstance(row, dict):
                row_id = row.get("id")
                original_filename = row.get("original_filename")
                current_filename = row.get("current_filename")
                status = row.get("status")
                description = row.get("description")
                needed = row.get("needed")
                key_concept = row.get("key_concept")
            else:
                # Fallback if it returns tuples (unlikely for the standard server but possible)
                (
                    row_id,
                    original_filename,
                    current_filename,
                    status,
                    description,
                    needed,
                    key_concept,
                ) = row

            if original_filename not in files_data:
                files_data[original_filename] = {"file_info": None, "pages": []}

            # Check if this is a file-level summary (current_filename == 'all')
            if current_filename == "all":
                files_data[original_filename]["file_info"] = FileInfo(
                    id=row_id,
                    filename=original_filename,
                    description=description or "",
                    key_concepts=json.loads(key_concept) if key_concept else [],
                )
            else:
                # This is a page-level entry
                # Extract page number from current_filename
                try:
                    page_num = self._extract_page_number(current_filename)
                except Exception:
                    page_num = len(files_data[original_filename]["pages"]) + 1

                files_data[original_filename]["pages"].append(
                    PageInfo(
                        id=row_id,
                        page_number=page_num,
                        filename=current_filename,
                        needed=needed == 1 if needed is not None else None,
                        description=description or "",
                        key_concept=key_concept or "",
                    )
                )

        # Sort pages by page number for each file
        for filename in files_data:
            files_data[filename]["pages"].sort(key=lambda x: x.page_number)

        # Filter out files without valid file_info or without any needed pages
        # Convert to FileData objects
        valid_files_data: Dict[str, FileData] = {}

        for filename, data in files_data.items():
            if data["file_info"] and data["file_info"].description:
                # Check if there are any needed pages
                needed_pages = [p for p in data["pages"] if p.needed]
                if needed_pages:
                    valid_files_data[filename] = FileData(
                        file_info=data["file_info"], pages=data["pages"]
                    )

        return valid_files_data

    async def get_student_errors(self, student_id: str) -> List[Dict[str, Any]]:
        """
        Get questions where the student made an error.

        Args:
            student_id: The student ID

        Returns:
            List of dictionaries containing question details and student's wrong answer
        """
        query = f"""
            SELECT 
                q.question, 
                q.a, q.b, q.c, q.d, 
                q.correct_choice, 
                sc.student_choice
            FROM student_choices sc
            JOIN questions q ON sc.question_id = q.id
            WHERE sc.student_id = '{student_id}' 
            AND sc.student_choice != sc.correct_choice
        """

        rows = await self._run_query(query)
        return rows
