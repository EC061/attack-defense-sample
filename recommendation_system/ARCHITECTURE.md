# Architecture Overview

## System Architecture Comparison

### Original System: Manual Orchestration

```
┌─────────────────────────────────────────────────────────────────┐
│                         Python Application                       │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  MaterialRecommendationSystem                           │    │
│  │                                                          │    │
│  │  1. Load materials from DB                              │    │
│  │  2. Get student errors from DB                          │    │
│  │  3. Call LLM for file selection                         │    │
│  │  4. Call LLM for page selection                         │    │
│  │  5. Return recommendations                              │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│         ↓ SQL Queries              ↓ Prompts + Data             │
│                                                                  │
└─────────┼──────────────────────────┼───────────────────────────┘
          │                          │
          ↓                          ↓
┌─────────────────────┐    ┌─────────────────────┐
│   MCP SQLite Server │    │   OpenAI API        │
│                     │    │                     │
│  - read_query tool  │    │  - chat.completions │
│  - Returns JSON     │    │  - Streaming        │
└─────────────────────┘    └─────────────────────┘
          ↓
┌─────────────────────┐
│  SQLite Database    │
│                     │
│  - materials        │
│  - students         │
│  - questions        │
│  - student_choices  │
└─────────────────────┘
```

**Flow**:
1. Python → MCP: `SELECT * FROM student_choices WHERE student_id=?`
2. MCP → Python: Student errors (JSON)
3. Python → MCP: `SELECT * FROM materials WHERE current_filename='all'`
4. MCP → Python: Materials list (JSON)
5. Python → OpenAI: "Select best file for error X" + materials data
6. OpenAI → Python: File selection (JSON)
7. Python → OpenAI: "Select best pages from file Y" + pages data
8. OpenAI → Python: Page selection (JSON)

**Total Round-Trips**: 4 (2 DB queries + 2 LLM calls)

---

### MCP-Enabled System: LLM Orchestration

```
┌─────────────────────────────────────────────────────────────────┐
│                         Python Application                       │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  MCPMaterialRecommendationSystem                        │    │
│  │                                                          │    │
│  │  1. Initialize MCP tool config                          │    │
│  │  2. Send system instruction + student ID                │    │
│  │  3. Stream response (LLM orchestrates everything)       │    │
│  │  4. Return recommendations                              │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│         ↓ Prompt + MCP Tool Config                              │
│         ↑ Streaming Response                                    │
│                                                                  │
└─────────┼──────────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────────┐
│                         OpenAI API                               │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  LLM (gpt-5)                                            │    │
│  │                                                          │    │
│  │  1. Analyze task: "Get recommendations for student X"   │    │
│  │  2. Plan: "Query student errors"                        │    │
│  │  3. Execute: Call MCP tool with SQL                     │    │
│  │  4. Analyze: "Student got question Y wrong"             │    │
│  │  5. Plan: "Query available materials"                   │    │
│  │  6. Execute: Call MCP tool with SQL                     │    │
│  │  7. Reason: "File Z best matches misconception"         │    │
│  │  8. Plan: "Query pages for file Z"                      │    │
│  │  9. Execute: Call MCP tool with SQL                     │    │
│  │ 10. Reason: "Pages 15-18 cover the concept"             │    │
│  │ 11. Generate: Return structured recommendation          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│         ↓ Tool Calls (SQL)                                      │
│         ↑ Tool Results (JSON)                                   │
│                                                                  │
└─────────┼──────────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────┐
│   MCP SQLite Server │
│                     │
│  - read_query tool  │
│  - Returns JSON     │
└─────────────────────┘
          ↓
┌─────────────────────┐
│  SQLite Database    │
│                     │
│  - materials        │
│  - students         │
│  - questions        │
│  - student_choices  │
└─────────────────────┘
```

**Flow**:
1. Python → OpenAI: System instruction + student ID + MCP tool config
2. OpenAI → MCP: `SELECT ... FROM student_choices WHERE student_id=?` (LLM-generated)
3. MCP → OpenAI: Student errors (JSON)
4. OpenAI → MCP: `SELECT ... FROM materials WHERE ...` (LLM-generated)
5. MCP → OpenAI: Materials (JSON)
6. OpenAI → MCP: `SELECT ... FROM materials WHERE original_filename=? AND needed=1` (LLM-generated)
7. MCP → OpenAI: Pages (JSON)
8. OpenAI → Python: Complete recommendations (streamed JSON)

**Total Round-Trips**: 1 (single streaming session with embedded tool calls)

---

## Component Architecture

### Original System Components

```
recommendation_system/
├── recommender.py              # MaterialRecommendationSystem
│   ├── load_materials_from_db()   # Manual MCP query
│   ├── step1_select_file()        # LLM call #1
│   └── step2_select_pages()       # LLM call #2
│
├── api_client.py               # RecommendationAPIClient
│   └── generate_completion()      # chat.completions.create()
│
├── database.py                 # MCPDatabaseClient
│   ├── _run_query()               # MCP tool invocation
│   ├── load_materials()           # Query materials table
│   └── get_student_errors()       # Query student_choices table
│
└── schemas.py                  # JSON schemas for structured output
    ├── get_file_selection_schema()
    └── get_page_selection_schema()
```

### MCP-Enabled System Components

```
recommendation_system/
├── mcp_recommender.py          # MCPMaterialRecommendationSystem
│   └── recommend_for_student()    # Single call, LLM orchestrates
│
├── mcp_api_client.py           # MCPRecommendationAPIClient
│   ├── _get_mcp_tool_config()     # MCP tool configuration
│   └── generate_recommendation()  # responses.stream() with tools
│
└── (reuses existing)
    ├── database.py                # For manual queries if needed
    ├── schemas.py                 # For reference (not used directly)
    └── types.py                   # Data structures
```

---

## Data Flow Diagrams

### Original: Two-Step Process

```
┌──────────┐
│ Student  │
│   ID     │
└────┬─────┘
     │
     ↓
┌────────────────────┐
│ Load Materials     │ ← MCP Query #1
│ (all files)        │
└────┬───────────────┘
     │
     ↓
┌────────────────────┐
│ Get Student Errors │ ← MCP Query #2
│ (wrong answers)    │
└────┬───────────────┘
     │
     ↓
┌────────────────────┐
│ Step 1: File       │ ← LLM Call #1
│ Selection          │   (with all materials)
│                    │
│ Input:             │
│ - Question         │
│ - Wrong answer     │
│ - All materials    │
│                    │
│ Output:            │
│ - Selected file    │
│ - Reasoning        │
└────┬───────────────┘
     │
     ↓
┌────────────────────┐
│ Step 2: Page       │ ← LLM Call #2
│ Selection          │   (with file's pages)
│                    │
│ Input:             │
│ - Question         │
│ - Wrong answer     │
│ - Selected file    │
│ - File's pages     │
│                    │
│ Output:            │
│ - Start page       │
│ - End page         │
│ - Reasoning        │
└────┬───────────────┘
     │
     ↓
┌────────────────────┐
│ Recommendation     │
│ Result             │
└────────────────────┘
```

### MCP-Enabled: Single Streaming Session

```
┌──────────┐
│ Student  │
│   ID     │
└────┬─────┘
     │
     ↓
┌────────────────────────────────────────────────────────┐
│ Single LLM Streaming Session                           │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │ LLM Reasoning & Tool Orchestration              │  │
│  │                                                  │  │
│  │ 1. "I need to find student's errors"            │  │
│  │    → Tool Call: read_query(SELECT ...)          │  │ ← MCP
│  │    ← Tool Result: [errors]                      │  │
│  │                                                  │  │
│  │ 2. "I need to see available materials"          │  │
│  │    → Tool Call: read_query(SELECT ...)          │  │ ← MCP
│  │    ← Tool Result: [materials]                   │  │
│  │                                                  │  │
│  │ 3. "File X best matches error Y because..."     │  │
│  │                                                  │  │
│  │ 4. "I need pages for file X"                    │  │
│  │    → Tool Call: read_query(SELECT ...)          │  │ ← MCP
│  │    ← Tool Result: [pages]                       │  │
│  │                                                  │  │
│  │ 5. "Pages 15-18 cover the concept because..."   │  │
│  │                                                  │  │
│  │ 6. Generate structured recommendation           │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
└────┬────────────────────────────────────────────────────┘
     │
     ↓
┌────────────────────┐
│ Recommendation     │
│ Result             │
└────────────────────┘
```

---

## Token Flow Analysis

### Original System

**Request #1 (File Selection)**:
```
System: "You are an educational assistant..."
User: "Question: [Q], Wrong: [W], Materials: [M1, M2, ..., Mn]"

Tokens: ~500 (system) + ~100 (question) + ~2000 (materials) = 2600 input
Response: ~100 tokens (file + reasoning)
```

**Request #2 (Page Selection)**:
```
System: "You are an educational assistant..."
User: "Question: [Q], Wrong: [W], File: [F], Pages: [P1, P2, ..., Pk]"

Tokens: ~500 (system) + ~100 (question) + ~800 (pages) = 1400 input
Response: ~100 tokens (pages + reasoning)
```

**Total**: ~4000 input tokens, ~200 output tokens

---

### MCP-Enabled System

**Single Request**:
```
System: "You are an educational assistant... [database schema]"
User: "Generate recommendations for student S001"

Initial tokens: ~800 (system) + ~50 (user) = 850 input

Tool Call #1: SELECT ... FROM student_choices
Tool Result: [errors] → ~200 tokens added to context

Tool Call #2: SELECT ... FROM materials
Tool Result: [materials] → ~2000 tokens added to context

Tool Call #3: SELECT ... FROM materials WHERE ...
Tool Result: [pages] → ~800 tokens added to context

Response: ~300 tokens (recommendations + reasoning)
```

**Total**: ~3850 input tokens, ~300 output tokens

**Note**: Slightly fewer input tokens (no duplicate system prompts), but more output tokens (includes reasoning for tool calls).

---

## Latency Analysis

### Original System

```
┌─────────────┐  50ms   ┌─────────────┐
│ MCP Query 1 │ ───────→│             │
└─────────────┘         │             │
                        │             │
┌─────────────┐  50ms   │   Python    │
│ MCP Query 2 │ ───────→│   Waits     │
└─────────────┘         │             │
                        │             │
┌─────────────┐ 2-4s    │             │
│ LLM Call 1  │ ───────→│             │
└─────────────┘         │             │
                        │             │
┌─────────────┐ 2-4s    │             │
│ LLM Call 2  │ ───────→│             │
└─────────────┘         └─────────────┘

Total: 4-8 seconds (sequential)
```

### MCP-Enabled System

```
┌──────────────────────────────────────────────────────┐
│         Single Streaming Session                     │
│                                                       │
│  ┌──────────┐  50ms  ┌──────────┐  50ms  ┌────────┐ │
│  │ MCP Call │ ─────→ │ MCP Call │ ─────→ │  MCP   │ │
│  │    1     │        │    2     │        │ Call 3 │ │
│  └──────────┘        └──────────┘        └────────┘ │
│                                                       │
│  LLM reasoning happens in parallel with tool calls   │
│  Streaming starts as soon as first token is ready    │
│                                                       │
└──────────────────────────────────────────────────────┘

Total: 3-6 seconds (parallel + streaming)
```

**Speedup**: 25-40% faster due to:
- Parallel processing
- Single connection overhead
- Streaming starts earlier

---

## Error Handling

### Original System

```python
try:
    materials = await db.load_materials()
except Exception as e:
    # Handle DB error
    
try:
    step1 = await recommender.step1_select_file(...)
except Exception as e:
    # Handle LLM error
    
try:
    step2 = await recommender.step2_select_pages(...)
except Exception as e:
    # Handle LLM error
```

**Granular**: Each step can be caught and handled separately.

### MCP-Enabled System

```python
try:
    recommendations = recommender.recommend_for_student(...)
except Exception as e:
    # Handle any error (DB or LLM)
    # Less granular, but simpler
```

**Coarse**: Single try-catch for entire flow. Tool errors are handled internally by the LLM or SDK.

---

## Extensibility

### Original System

**Adding a new step**:
1. Create `step3_...()` method
2. Add manual DB queries if needed
3. Create new schema
4. Update `recommend()` to call step3
5. Update logging

**Adding a new data source**:
1. Add methods to `MCPDatabaseClient`
2. Update `load_materials_from_db()`
3. Update prompts to include new data

### MCP-Enabled System

**Adding a new step**:
1. Update system instruction to describe new step
2. LLM automatically adapts its reasoning
3. No code changes needed!

**Adding a new data source**:
1. Add table to database
2. Update MCP tool description with new schema
3. LLM automatically discovers and uses it

**Winner**: MCP-Enabled (more flexible, less code)

---

## Summary

| Aspect | Original | MCP-Enabled |
|--------|----------|-------------|
| **Architecture** | Manual orchestration | LLM orchestration |
| **API Calls** | 2+ separate | 1 streaming |
| **Latency** | 4-8s | 3-6s |
| **Token Usage** | ~4000 in, ~200 out | ~3850 in, ~300 out |
| **Flexibility** | Fixed workflow | Adaptive workflow |
| **Error Handling** | Granular | Coarse |
| **Extensibility** | Code changes | Prompt changes |
| **Debugging** | Easier | Harder |
| **Best For** | Production | Exploration |

