import asyncio
import json
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, Callable, TypedDict, List
import google.generativeai as genai
from dotenv import load_dotenv
import os
import sqlite3
import pandas as pd

load_dotenv()
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Create a model instance
# model = genai.GenerativeModel('models/gemini-2.5-flash')

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolUnionParam

class PythonExpressionToolResult(TypedDict):
    result: Any
    error: str | None


class SubmitAnswerToolResult(TypedDict):
    answer: Any
    submitted: bool


class SqlQueryToolResult(TypedDict):
    """Return type for the sql_query_tool."""
    result_json: str | None
    error: str | None

class BusinessContextToolResult(TypedDict):
    """Return type for the get_business_context tool."""
    context: dict | None
    error: str | None


def sql_query_tool(query: str) -> SqlQueryToolResult:
    """
    Executes a read-only SQL query against the 'analytics.db' database
    and returns the result as a JSON string.
    """
    try:
        conn = sqlite3.connect('analytics.db')
        df = pd.read_sql_query(query, conn)
        conn.close()
        return {"result_json": df.to_json(orient='records'), "error": None}
    except Exception as e:
        return {"result_json": None, "error": f"Error executing query: {str(e)}"}

def get_business_context() -> BusinessContextToolResult:
    """Provides strategic business context from leadership."""
    try:
        context = {
            "last_review_focus": "Enterprise",
            "current_quarter_goal": "Fraud detection coverage",
            "memo": "Last quarter's review was on Enterprise. For this quarter, we need to widen our fraud detection coverage to see if we're missing anything else."
        }
        return {"context": context, "error": None}
    except Exception as e:
        return {"context": None, "error": f"Error getting context: {str(e)}"}
    
def python_expression_tool(expression: str) -> PythonExpressionToolResult:
    """
    Tool that evaluates Python expressions using exec.
    Use print(...) to emit output; stdout will be captured and returned.
    """
    try:
        namespace = {}
        stdout = StringIO()
        with redirect_stdout(stdout):
            exec(expression, namespace, namespace)
        return {"result": stdout.getvalue(), "error": None}
    except KeyboardInterrupt:
        raise
    except Exception as e:
        return {"result": None, "error": str(e)}


def submit_answer_tool(answer: Any) -> SubmitAnswerToolResult:
    """
    Tool for submitting the final answer.
    """
    return {"answer": answer, "submitted": True}


async def run_agent_loop(
    prompt: str,
    tools: list[ToolUnionParam],
    tool_handlers: dict[str, Callable[..., Any]],
    max_steps: int = 10,
    model: str = "claude-3-5-haiku-latest",
    # model: str = 'models/gemini-2.5-flash',
    verbose: bool = True,
) -> Any | None:
    """
    Runs an agent loop with the given prompt and tools.

    Args:
        prompt: The initial prompt for the agent
        tools: List of tool definitions for Anthropic API
        tool_handlers: Dictionary mapping tool names to their handler functions
        max_steps: Maximum number of steps before stopping (default 5)
        model: The Anthropic model to use
        verbose: Whether to print detailed output (default True)

    Returns:
        The submitted answer if submit_answer was called, otherwise None
    """
    client = AsyncAnthropic()
    messages: list[MessageParam] = [{"role": "user", "content": prompt}]

    for step in range(max_steps):
        if verbose:
            print(f"\n=== Step {step + 1}/{max_steps} ===")

        response = await client.messages.create(
            model=model, max_tokens=1000, tools=tools, messages=messages
        )

        # Track if we need to continue
        has_tool_use = False
        # tool_results = []
        tool_results_dict = {}
        submitted_answer = None

        # Process the response
        for content in response.content:
            if content.type == "text":
                if verbose:
                    print(f"Assistant: {content.text}")
            elif content.type == "tool_use":
                has_tool_use = True
                tool_name = content.name
                tool_input = content.input
                tool_use_id = content.id

                if tool_name in tool_handlers:
                    if verbose:
                        print(f"Using tool: {tool_name}")

                    # Extract arguments based on tool
                    handler = tool_handlers[tool_name]
                    tool_input = content.input

                    # Call the appropriate tool handler
                    if tool_name == "python_expression":
                        # We replace the brittle 'assert' with a robust if/else check
                        if isinstance(tool_input, dict) and "expression" in tool_input:
                            # HAPPY PATH: The AI called the tool correctly
                            expression = tool_input["expression"]
                            if verbose:
                                print("\nInput (Python Expression):")
                                print("```")
                                for line in expression.split("\n"):
                                    print(f"{line}")
                                print("```")
                            
                            # Call the handler (which is python_expression_tool)
                            result = handler(expression)
                            
                            if verbose:
                                print("\nOutput:")
                                print("```")
                                print(result)
                                print("```")
                        else:
                            # SAD PATH: The AI called the tool with bad arguments
                            if verbose:
                                print(f"\nError: AI called 'python_expression' with invalid input: {tool_input}")
                            
                            # We MUST provide an error 'result' to avoid a crash
                            result = {"result": None, "error": f"Invalid tool input. Expected a JSON object with an 'expression' key."}

                    elif tool_name == "sql_query_tool":
                        assert isinstance(tool_input, dict) and "query" in tool_input
                        if verbose:
                            print("\nInput (SQL Query):")
                            print("```sql")
                            for line in tool_input["query"].split("\n"):
                                print(f"{line}")
                            print("```")
                        result = handler(tool_input["query"])
                        if verbose:
                            print("\nOutput:")
                            print("```")
                            print(result)
                            print("```")
                        
                    elif tool_name == "submit_answer":
                        assert isinstance(tool_input, dict) and "answer" in tool_input
                        result = handler(tool_input["answer"])
                        submitted_answer = result["answer"]
                    else:
                        # Generic handler call
                        result = (
                            handler(**tool_input)
                            if isinstance(tool_input, dict)
                            else handler(tool_input)
                        )

                    # tool_results.append(
                    #     {
                    #         "type": "tool_result",
                    #         "tool_use_id": content.id,
                    #         "content": json.dumps(result),
                    #     }
                    # )
                    tool_results_dict[content.id] = {
                    "type": "tool_result",
                    "tool_use_id": content.id,
                    "content": json.dumps(result),
                    }
                else:
                    # The AI called a tool we don't have. We MUST provide an error result.
                    if verbose:
                        print(f"Error: Unknown tool '{tool_name}' called by AI.")
                    
                    tool_results_dict[tool_use_id] = {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps({"result": None, "error": f"Unknown tool name: {tool_name}"}),
                    }
        # If we have tool uses, add them to the conversation
        if has_tool_use:
            messages.append({"role": "assistant", "content": response.content})
            
            # Convert our dict of unique results back into a list
            final_tool_results = list(tool_results_dict.values())
            
            if final_tool_results: # Check the new list
                messages.append({"role": "user", "content": final_tool_results})
            
            # If an answer was submitted, return it
            if submitted_answer is not None:
                if verbose:
                    print(f"\nAgent submitted answer: {submitted_answer}")
                return submitted_answer
        else:
            # No tool use, conversation might be complete
            if verbose:
                print("\nNo tool use in response, ending loop.")
            break

    if verbose:
        print(f"\nReached maximum steps ({max_steps}) without submitting answer.")
    return None


async def run_single_test(
    run_id: int,
    num_runs: int,
    prompt: str,
    tools: list[ToolUnionParam],
    tool_handlers: dict[str, Callable[..., Any]],
    expected_answer: Any,
    verbose: bool = True,
) -> tuple[int, bool, Any]:
    if verbose:
        print(f"\n\n{'=' * 20} RUN {run_id}/{num_runs} {'=' * 20}")

    result = await run_agent_loop(
        prompt=prompt,
        tools=tools,
        tool_handlers=tool_handlers,
        max_steps=10,
        verbose=verbose,
    )

    success = result == expected_answer

    if success:
        print(f"✓ Run {run_id}: SUCCESS - Got {result}")
    else:
        print(f"✗ Run {run_id}: FAILURE - Got {result}, expected {expected_answer}")

    return run_id, success, result


async def main(concurrent: bool = True):
    tools: list[ToolUnionParam] = [
        {
            "name": "python_expression",
            "description": "Evaluates a Python expression",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Will be passed to exec(). Use print() to output something. Returns stdout. ",
                    }
                },
                "required": ["expression"],
            },
        },
        {
            "name": "submit_answer",
            "description": "Submit the final answer",
            "input_schema": {
                "type": "object",
                "properties": {"answer": {"description": "The final answer to submit"}},
                "required": ["answer"],
            },
        },
        {
            "name": "sql_query_tool",
            "description": "Executes a read-only SQL query against the 'analytics.db' database and returns the result as a JSON string.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute."
                    }
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_business_context",
            "description": "Provides strategic business context and goals from leadership.",
            "input_schema": {"type": "object", "properties": {}}, # No inputs
        }
    ]

    tool_handlers = {
        "python_expression": python_expression_tool,
        "submit_answer": submit_answer_tool,
        "sql_query_tool": sql_query_tool,
        "get_business_context": get_business_context,
    }

    # Run the test 10 times and track success rate
    num_runs = 10
    expected_answer = "Hobbyist"
    prompt = """
    Your task is to act as a senior data researcher. A business leader needs a definitive answer on where to focus fraud review efforts.

    You have access to several tools:
    1.  `sql_query_tool(query)`: Queries the company's 'analytics.db' (which has 'users' and 'transactions' tables).
    2.  `get_business_context()`: Provides strategic goals from leadership.
    3.  `python_expression_tool(expression)`: For any final data analysis using libraries like pandas or scikit-learn.

    **The Business Request:**
    "I need to know which user segment is showing the most *problematic* transaction behavior... We need to know which single segment has the highest **anomaly rate** so we can focus our manual review team there."

    **Your Recommended Workflow:**
    1.  Call `get_business_context()` to understand the strategic goals.
    2.  Use `sql_query_tool` to explore the database tables ('users', 'transactions') and then write a JOIN query to fetch all necessary data.
    3.  Pass the retrieved data to the `python_expression_tool`.
    4.  Inside Python, use anomaly detection methods to analyze the data, and find the segment with the highest anomaly *rate*.
    5.  Submit the name of that single segment (e.g., "Hobbyist").
    """

    execution_mode = "concurrently" if concurrent else "sequentially"
    print(f"Running {num_runs} test iterations {execution_mode}...")
    print("=" * 60)

    # Create all test coroutines
    tasks = [
        run_single_test(
            run_id=i + 1,
            num_runs=num_runs,
            prompt=prompt,
            tools=tools,
            tool_handlers=tool_handlers,
            expected_answer=expected_answer,
            verbose=False,
        )
        for i in range(num_runs)
    ]

    # Run concurrently or sequentially based on the flag
    if concurrent:
        # Process results as they complete
        results = []
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
    else:
        # Run sequentially by awaiting each task in order
        results = []
        for task in tasks:
            result = await task
            results.append(result)

    # Count successes
    # successes = sum(1 for _, success, _ in results)
    successes = sum(success for _, success, _ in results)

    # Calculate and display pass rate
    pass_rate = (successes / num_runs) * 100
    print(f"\n{'=' * 60}")
    print("Test Results:")
    print(f"  Passed: {successes}/{num_runs}")
    print(f"  Failed: {num_runs - successes}/{num_runs}")
    print(f"  Pass Rate: {pass_rate:.1f}%")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    # Set to True for concurrent execution, False for sequential execution
    asyncio.run(main(concurrent=False))
