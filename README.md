🤖 LLM RL Task Submission: Bias Trap Data Researcher

This project contains a sophisticated Reinforcement Learning (RL) task designed for a Large Language Model (LLM). The goal was to create a scenario that is difficult enough to force a low-to-moderate pass rate (10%–40%), requiring the AI to navigate a complex, multi-tool environment and overcome an explicit "bias trap."

🎯 The Task: Ambiguous Data Research & Bias Conflict

The task simulates a senior data researcher's job: the AI must use a multi-step workflow involving a database and advanced Python analysis to answer an ambiguous business question.

The Core Challenge: The "Business Context"

The primary difficulty lies in the get_business_context() tool, which provides a weak, strategic hint. The AI is encouraged to call this tool for "strategic goals."

Strategic Tool (get_business_context snippet)
Output Context: {"last_review_focus": "Enterprise", "current_quarter_goal": "Fraud detection coverage", "memo": "Last quarter's review was on Enterprise. [...] we need to widen our fraud detection coverage to see if we're missing anything else."

The Conflict
The actual correct answer (found by analyzing the data) is "Hobbyist." A naïve AI will latch onto the easily retrieved focus, "Enterprise," and fail the test.

📝 Prompt and Expected Behavior

The prompt guides the AI through the required steps but explicitly states the goal is to find the segment with the highest "anomaly rate," forcing the AI to resolve the conflict between the bias and the requested analytical goal.

# The expected answer and prompt from main.py

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


🚀 How to Run the Test

To replicate the environment and results, follow these steps:

Install Dependencies

pip install -r requirements.txt


Generate the Test Database

This step creates the necessary analytics.db file, which is pre-loaded with the data and the "Business Context" logic.

python data.py


Run the Test Harness
This script executes the task 10 times sequentially and outputs the final pass rate.

python main.py


✅ Final Results: 30% Pass Rate

The task successfully met the target, achieving a 30% pass rate due to the efficacy of the integrated bias and procedural complexity.

Execution Log
The failures demonstrate the AI either following the "Enterprise" bias or failing to complete the multi-step execution.

============================================================
✗ Run 1: FAILURE - Got None, expected Hobbyist (Procedural Failure)
✗ Run 2: FAILURE - Got None, expected Hobbyist (Procedural Failure)
✗ Run 3: FAILURE - Got Enterprise, expected Hobbyist (Bias Trap Failure)
✓ Run 4: SUCCESS - Got Hobbyist (Correct Reasoning)
✗ Run 5: FAILURE - Got Enterprise, expected Hobbyist (Bias Trap Failure)
✓ Run 6: SUCCESS - Got Hobbyist (Correct Reasoning)
✗ Run 7: FAILURE - Got Enterprise, expected Hobbyist (Bias Trap Failure)
✗ Run 8: FAILURE - Got Enterprise, expected Hobbyist (Bias Trap Failure)
✓ Run 9: SUCCESS - Got Hobbyist (Correct Reasoning)
✗ Run 10: FAILURE - Got Enterprise, expected Hobbyist (Bias Trap Failure)
============================================================
Test Results:
  Passed: 3/10
  Failed: 7/10
  Pass Rate: 30.0%
============================================================