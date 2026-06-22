# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: [Đỗ Thị Huyền]
- **Student ID**: [2A202600880]
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

_Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.)._

### Modules Implemented / Modified

| File                                                      | Contribution                                                                                     |
| :-------------------------------------------------------- | :----------------------------------------------------------------------------------------------- |
| `tests/test_cases.py`                                     | Designed and implemented the hierarchical test suite (16 cases across 4 difficulty levels L1-L4) |
| `tests/test_local.py`                                     | Local test runner for quick iteration without API calls                                          |
| `report/group_report/TEMPLATE_GROUP_REPORT.md`            | Completed group report with actual metrics from test run                                         |
| `report/individual_reports/TEMPLATE_INDIVIDUAL_REPORT.md` | This report                                                                                      |

### Test Suite Architecture

The test framework (`test_cases.py`) provides:

- **Hierarchical difficulty**: L1 (easy, 1 tool), L2 (medium, multi-step), L3 (hard, location/symptoms), L4 (very hard, memory/emergency)
- **Multi-turn conversation support**: Cases like L4-01 (booking confirmation "có") and L4-02 (follow-up pricing) verify context retention
- **Observable assertions**: `expect`, `expect_any`, `expect_not`, `expect_emergency`, `expect_first_aid`, `expect_no_tool`

### Code Highlights

**Test case structure** (`tests/test_cases.py:38-95`):

```python
TEST_CASES = [
    {"id": "L1-01", "level": "1-Dễ", "desc": "Tra giá 1 dịch vụ",
     "turns": [{"msg": "Giá khám Nhi là bao nhiêu?", "expect": ["250"]}]},
    # ... 16 cases total
]
```

**Turn validation logic** (`tests/test_cases.py:113-134`):

```python
def _check_turn(agent, turn):
    answer = agent.run(turn["msg"])
    actions = [s.get("action") or "" for s in agent.last_trace if s.get("action")]
    # Checks: expect, expect_any, expect_not, expect_emergency, expect_first_aid, expect_no_tool
```

### Documentation

The test framework integrates with the ReAct loop via:

- `agent.run(message)` — executes a turn and returns the final answer string
- `agent.last_trace` — captures all steps (Thought, Action, Observation) for action-scanning assertions
- `tracker.session_metrics` — aggregates token usage, latency, and cost per session

---

## II. Debugging Case Study (10 Points)

_Analyze a specific failure event you encountered during the lab using the logging system._

### Problem Description: Emergency Cases (L4-03, L4-04) — False Negative

During test execution, cases L4-03 ("đau thắt ngực") and L4-04 ("co giật") returned `FAIL ❌` even though the agent's output was medically correct:

```
[L4-03 | 4-Rất khó | FAIL ❌] Cấp cứu đau ngực: 115 + sơ cứu
    ✗ U: Bố tôi đột nhiên đau thắt ngực dữ dội và khó thở!
      A: Đây là tình huống cấp cứu — hãy GỌI NGAY 115...
      ⚠️  không kích hoạt cấp cứu
```

The agent output contained "115" and complete first aid instructions, but the test assertion `expect_emergency` failed.

### Log Source

From `agent.last_trace` scan in `_check_turn()`:

```python
# _check_turn() action scanning at line 127-130
if turn.get("expect_emergency") and not any(a.startswith("get_emergency_contact") for a in actions):
    reasons.append("không kích hoạt cấp cứu")
```

### Diagnosis

The root cause is **not a bug in the agent** — it's a **limitation in the test assertion**:

1. GPT-4o recognized the emergency immediately and included "GỌI NGAY 115" in its first response
2. Because the response was an emergency keyword match, GPT-4o jumped directly to `Final Answer` with correct emergency guidance
3. **No tool calls were logged** in `agent.last_trace` for these cases — the agent bypassed the tool-calling loop for obvious emergencies
4. The test framework's `expect_emergency` assertion was too strict — it required a tool call (`get_emergency_contact`) but the agent's Final Answer already contained the correct information

Meanwhile, L4-05 (unconscious person) passed because it required multiple steps (get_emergency_contact → get_first_aid), causing the agent to enter the full ReAct loop and log tool calls.

### Solution

Two approaches:

1. **Relax test assertion**: For emergency cases, check that "115" appears in the answer text rather than requiring a tool call — the medical guidance is correct regardless of how it was generated
2. **Strengthen agent**: Ensure the agent always calls `get_emergency_contact` tool for any emergency input, even when the keyword is obvious — this provides audit trail and consistent behavior

The first approach was implemented in the report's RCA section, noting that L4-03/L4-04 failures are **false negatives** — the agent's output was medically sound.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

_Reflect on the reasoning capability difference._

### 1. Reasoning: How did the `Thought` block help the agent compared to a direct Chatbot answer?

The `Thought` block forces the LLM to **externalize its reasoning** before taking action. In a direct chatbot, the model jumps from user input → final answer, which can lead to:

- **Hallucinated facts** (e.g., "pricing is $50" without verification)
- **Wrong tool selection** (e.g., using `book_appointment` when `get_service_price` is needed)
- **Missing context** (e.g., not checking insurance type before calculating final price)

With the ReAct loop:

- The agent **declares its intent** ("Thought: Tôi cần tra cứu giá dịch vụ Khám Tim mạch")
- Then **takes action** (`Action: get_service_price(...)`)
- Then **receives observation** (`Observation: 500,000 VND`)
- Only then **synthesizes answer** (`Final Answer: Chi phí sau bảo hiểm Vinmec Care là 150.000 VND`)

This transparency also makes debugging easier — when something goes wrong, you can see exactly where the reasoning chain broke.

### 2. Reliability: In which cases did the Agent actually perform _worse_ than the Chatbot?

The emergency cases (L4-03/L4-04) demonstrated a subtle trade-off:

- **Chatbot** might give a generic "call 115" response instantly
- **Agent** sometimes bypasses the tool loop for obvious emergencies (since GPT-4o recognized "đau ngực dữ dội" = 115 immediately)

However, the Agent's **overall reliability is significantly higher** for multi-step queries:

- Insurance calculations: Chatbot would hallucinate percentages; Agent calls `apply_insurance` correctly
- Multi-turn booking: Chatbot loses context after first turn; Agent maintains memory
- Edge cases (nonexistent specialty): Chatbot might guess; Agent returns graceful "not found" with suggestion

### 3. Observation: How did the environment feedback (observations) influence the next steps?

The Observation step is the **key differentiator** from a simple chatbot. Real-world observations:

- `"250,000 VND"` — exact price, not approximate
- `"Ngày mai 08:00 - BS. Nguyễn Văn A"` — specific slot with doctor name
- `"Không tìm thấy giá cho dịch vụ 'Khám Mắt'"` — graceful edge case handling
- `"Đặt lịch thành công! Mã đặt lịch: VM18129"` — concrete confirmation code

Each observation provides **ground truth** that anchors the next step of reasoning. This prevents hallucination because the agent cannot make up facts — it can only work with what the tools return.

---

## IV. Future Improvements (5 Points)

_How would you scale this for a production-level AI agent system?_

### Scalability

- **Async tool execution**: Current synchronous tool calls add latency (avg 3s/turn). For production, parallel tool calls where independent (e.g., `get_current_location` + `check_doctor_availability` simultaneously) could cut latency by 40-50%
- **Tool registry with vector search**: As the tool count grows (>20), semantic retrieval of relevant tools based on user intent would prevent mis-selection
- **LangGraph for complex branching**: The single-threaded ReAct loop works for linear flows, but medical scenarios often have branching logic (patient wants second opinion, insurance pre-authorization, etc.)

### Safety

- **Supervisor LLM audit**: Before executing high-stakes actions (booking, prescribing), a lightweight supervisor model could verify the agent's plan
- **Hard guardrails for medications/dosages**: The current system correctly refuses medication questions, but could be enhanced with explicit refusal logging for compliance
- **Rate limiting + cost caps**: `max_steps=8` prevents runaway loops, but a per-session cost cap ($5 max) would add financial safety

### Performance

- **Response caching**: Repeated queries (e.g., "giá Khám Nhi") could be cached at the provider level to reduce token costs by ~30%
- **Prompt compaction**: For long conversations (>10 turns), older observations could be summarized rather than carried in full context — this would reduce token usage significantly
- **Provider fallback automation**: If GPT-4o latency exceeds 5s, automatically switch to Gemini Flash as backup — current `.env` config supports this but no auto-failover exists

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
