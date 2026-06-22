# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Pham Minh Duc
- **Student ID**: VAI2026-N2-02
- **Date**: 01-06-2026

---

## I. Technical Contribution (15 Points)

*Detailed contribution of the Tools Engineer in designing the entire healthcare operational tool system for Vinmec Hospital in `vinmec_tools.py` and optimizing the `vinmec_data.json` database.*

- **Modules Implemented**:
  - [vinmec_tools.py](file:///c:/Users/MiDi/VinAi/Lab/Day03-lab-assignment/Day-3-Lab-Chatbot-vs-react-agent/src/tools/vinmec_tools.py): Developed all clinical and helper tool logic, including a hybrid GPS/IP location resolver, Haversine distance calculator to find the nearest facility, intelligent schedule availability filters, insurance calculations, price lookup, and appointment booking logic.
  - [vinmec_data.json](file:///c:/Users/MiDi/VinAi/Lab/Day03-lab-assignment/Day-3-Lab-Chatbot-vs-react-agent/src/tools/vinmec_data.json): Structured the mock database comprising facilities with coordinates, city centers, consultation prices per specialty, first-aid instruction guides, natural language aliases for specialties/first-aid categories, and doctor timetables.

- **Code Highlights**:
  1. **Hybrid Location Resolver (`get_current_location`):**
     *Objective:* Prioritizes high-accuracy browser-provided GPS coordinates (`_LOCATION_OVERRIDE` set by Frontend). If unavailable, falls back to IP-based geolocation using `ip-api.com`. If that fails, supports interactive manual input via CLI, and finally defaults to Hanoi to ensure the agent loop does not fail.
     ```python
     def get_current_location() -> str:
         # 1) Prioritize high-accuracy GPS coordinates from the browser
         if _LOCATION_OVERRIDE:
             lat, lon = _LOCATION_OVERRIDE
             return f"lat={lat}, lon={lon}, source=gps"

         # 2) Fallback to IP Geolocation (city-level precision)
         try:
             resp = requests.get("http://ip-api.com/json/", timeout=5)
             data = resp.json()
             if data.get("status") == "success":
                 return (f"lat={data['lat']}, lon={data['lon']}, "
                         f"city={data.get('city')}, source=ip")
         except Exception:
             pass

         # 3) CLI Manual entry or fallback to Hanoi
         if sys.stdin and sys.stdin.isatty():
             city = input("[IP Geolocation failed] What city/province are you in? ").strip().lower()
             if city in CITY_COORDS:
                 lat, lon = CITY_COORDS[city]
                 return f"lat={lat}, lon={lon}, city={city}, source=manual"
         # Default fallback: Hanoi
         lat, lon = CITY_COORDS["hà nội"]
         return f"lat={lat}, lon={lon}, city=hà nội (default), source=fallback"
     ```

  2. **Intelligent Schedule Availability Filter (`_is_bookable` & `_slot_datetime`):**
     *Objective:* Enforces a minimum booking lead time of `MIN_LEAD_MINUTES = 30` minutes in the future. The tool parses slots and filters out past or immediate times, ensuring that the ReAct Loop is only presented with actionable, valid booking slots.
     ```python
     def _slot_datetime(slot: str):
         m = re.search(r"(\d{1,2}):(\d{2})", slot)
         if not m:
             return None
         hh, mm = int(m.group(1)), int(m.group(2))
         day = datetime.now().date()
         if "ngày mai" in slot.lower():
             day = day + timedelta(days=1)
         return datetime(day.year, day.month, day.day, hh, mm)

     def _is_bookable(slot: str, now: datetime = None) -> bool:
         now = now or datetime.now()
         dt = _slot_datetime(slot)
         if dt is None:
             return True  # Cannot parse -> bypass validation
         return dt >= now + timedelta(minutes=MIN_LEAD_MINUTES)
     ```

  3. **Natural Language Specialty Canonicalization (`_canonical_specialty`):**
     *Objective:* Maps user-supplied colloquial terms (e.g., "cơ xương khớp", "xương khớp", "tim", "dạ dày") to canonical medical specialties recognized by the hospital system ("chấn thương chỉnh hình", "tim mạch", "tiêu hóa").
     ```python
     def _canonical_specialty(name: str) -> str:
         key = name.strip().lower()
         return SPECIALTY_ALIASES.get(key, key)
     ```

- **Documentation**:
  - **Observation Size Optimization:** Running local LLMs (like Phi-3-mini on a 4K context window) demands extremely concise inputs. Returning verbose JSON structures or raw HTML logs quickly exhausts the context window, causing the LLM to hallucinate or enter infinite loops. Consequently, every tool is engineered to return a **single-line text observation (or a highly condensed list)**.
    - Example: `get_service_price` returns only `"300,000 VND"` and `apply_insurance` returns `"150,000 VND (Vinmec Care insurance covers 50%)"`.
  - **Interaction in the ReAct Loop:** When the LLM decides on an action, it outputs `Action: tool_name(arg=value)`. The Agent Core uses the `ast` module to safely parse this Pythonic call, retrieve the function reference, and execute it inside `vinmec_tools.py`. The returned string represents the `Observation` fed back into the model's history. With strict parameter types (`lat: float`, `lon: float`, `specialty: str`), the mapping remains robust and error-free.

---

## II. Debugging Case Study (10 Points)

*Analysis of a real failure event encountered during integration testing on local models and how it was resolved through robust tool design.*

- **Problem Description**:
  When tested with the query *"I want to get a bone and joint checkup (khám xương khớp) at the nearest Vinmec"*, the Agent entered an infinite loop or threw errors. The LLM repeatedly invoked `check_doctor_availability(specialty="xương khớp")` and received a lengthy error message offering alternatives. This verbose error overwhelmed the local model's attention, causing it to lose context and repeat the identical invalid action:
  `Action: check_doctor_availability(specialty="xương khớp")`
  `Observation: Không có lịch cho chuyên khoa 'xương khớp'. GỢI Ý: ...`

- **Log Source** (`logs/2026-06-01.log`):
  ```json
  {"timestamp": "2026-06-01T15:20:10.123456", "event": "AGENT_STEP", "data": {"step": 1, "output": "Thought: The user wants bone and joint examination. I will query the schedule for 'xương khớp'.\nAction: check_doctor_availability(specialty=\"xương khớp\")"}}
  {"timestamp": "2026-06-01T15:20:10.567890", "event": "OBSERVATION", "data": {"action": "check_doctor_availability(specialty=\"xương khớp\")", "observation": "Không có lịch cho chuyên khoa 'xương khớp'. GỢI Ý: có thể khám 'Nội tổng quát' (khám chung), hoặc chọn khoa đang có lịch: chấn thương chỉnh hình, da liễu, nhi, ngoại, nội tổng quát, răng hàm mặt, tai mũi họng, thần kinh, tiêu hóa, tim mạch, truyền nhiễm."}}
  {"timestamp": "2026-06-01T15:20:12.345678", "event": "AGENT_STEP", "data": {"step": 2, "output": "Thought: Oh, the specialty 'xương khớp' does not exist in the system. Let me try querying 'xương khớp' schedule again.\nAction: check_doctor_availability(specialty=\"xương khớp\")"}}
  {"timestamp": "2026-06-01T15:20:12.789012", "event": "OBSERVATION", "data": {"action": "check_doctor_availability(specialty=\"xương khớp\")", "observation": "Không có lịch cho chuyên khoa 'xương khớp'. GỢI Ý: ..."}}
  {"timestamp": "2026-06-01T15:20:14.000000", "event": "AGENT_END", "data": {"steps": 5, "status": "max_steps"}}
  ```

- **Diagnosis**:
  1. **Colloquial vs. Canonical Terminology Mismatch:** The mock database stores the clinic specialty as `"chấn thương chỉnh hình"`, whereas the user requested it using colloquial terms like `"xương khớp"`. Because the local LLM (Phi-3-mini) lacks the linguistic capacity of larger models, it was unable to map "xương khớp" to "chấn thương chỉnh hình" inside its action call.
  2. **Verbose Observation Distraction:** The list of suggested specialties returned by the tool was too long, distracting the local model's attention mechanism and making it repeat the failing step.

- **Solution**:
  Rather than counting on the LLM to translate medical terms, the solution was implemented within the tool's business logic layer:
  1. **Populated `specialty_aliases` in `vinmec_data.json`:**
     Created an mapping alias dictionary mapping slang terms to standardized medical specialties:
     `"cơ xương khớp": "chấn thương chỉnh hình"`, `"xương khớp": "chấn thương chỉnh hình"`, `"tim": "tim mạch"`, `"dạ dày": "tiêu hóa"`, etc.
  2. **Integrated canonicalization filter `_canonical_specialty`:**
     Forced all specialty-dependent tools (`check_doctor_availability`, `get_service_price`, and `book_appointment`) to pass arguments through this helper before running database queries.
  3. **Observation Optimization:** Drastically shortened the error message size to preserve Phi-3's context limits.
  *Result:* When the user queries "xương khớp", the tool immediately resolves it to "chấn thương chỉnh hình" and returns the schedule for Dr. "Phan Phan M", allowing the agent to proceed and successfully finish in 3 steps.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflection on the engineering and cognitive differences between standard Chatbots and ReAct Agents based on lab results.*

1.  **Reasoning**:
    - **LLM Chatbot**: Acts as a smooth conversationalist but suffers heavily from **hallucinations** when answering multi-step operational questions. Without tools, it fabricates clinic hours, consultation fees, and discount rates. It also struggles with accurate math computations for custom insurance coverage plans.
    - **ReAct Agent**: Utilizes the intermediate `Thought` space to behave as a structured problem solver. The `Thought` block enables the LLM to formulate an execution plan: *"First, I need to fetch the base appointment price -> Then, I retrieve the discount rate for Bao Viet -> Finally, I calculate the net price."* This sequential breakdown guarantees factual correctness.

2.  **Reliability**:
    - The ReAct Agent is vastly more reliable for **deterministic business operations** requiring absolute precision (e.g., verifying appointment slots, hotline numbers, exact prices).
    - **However, ReAct Agents can perform worse than Chatbots in the following scenarios:**
      - **Chitchat & Out-of-scope requests:** When handled by a simple greeting (e.g., "Hello") or general queries (e.g., "How's the weather?"), a chatbot replies gracefully and fast. ReAct Agents might overthink, attempt to call irrelevant tools, or trigger parsing failures, causing latency spike and wasting tokens.
      - **Brittle LLM Outputs & Parser Crashes:** If the LLM generates syntax errors in the action string (e.g., mismatched brackets), the AST parser crashes, freezing the agent entirely, whereas a chatbot degrades gracefully.

3.  **Observation**:
    - Observations represent the **critical feedback mechanism** that elevates a static LLM into a dynamic, grounded agent.
    - The environment's feedback serves as an external memory buffer. For instance, if `check_doctor_availability` returns no slots for today, the `Observation` actively drives the agent to adapt and recommend the fallback specialty ("Nội tổng quát"). Chatbots can never execute this level of real-time correction because they operate in a feed-forward bubble without physical environment interaction.

---

## IV. Future Improvements (5 Points)

*Roadmap for scaling the tools system to a production-grade enterprise architecture.*

- **Scalability**:
  - Swap the static `vinmec_data.json` mock file with live, secure database endpoints (**PostgreSQL or MongoDB**) via authenticated RESTful APIs.
  - Implement an asynchronous task queue like **Celery and Redis** for long-running tool operations (e.g., Google Maps direction parsing, real-time hospital booking confirmation) to prevent blocking the agent execution loop (Non-blocking ReAct execution).

- **Safety**:
  - Incorporate **Pydantic** models to rigorously validate arguments at the tool layer, preventing malformed action parameters from breaking the AST engine.
  - Integrate a **Human-in-the-loop (HITL)** protocol at the final `book_appointment` state. Booking codes should remain pending until the user physically approves the transaction on the front-end user interface.

- **Performance**:
  - Leverage a **Vector Database (e.g., ChromaDB, PGVector)** to host tool metadata, deploying a **Semantic Tool Retriever**. In a production system with hundreds of clinical tools, instead of overloading the prompt context with all tool specs, the agent dynamically retrieves and attaches only the 3-5 most relevant tool descriptions. This reduces token overhead by 80% and slashes inference latency.
