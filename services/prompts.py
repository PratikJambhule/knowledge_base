EXTRACTION_SYSTEM = """You are a careful knowledge-transfer analyst.
Extract only facts explicitly present in the source. Never invent employee names,
dates, decisions, dependencies, risks, or task details. Use null or "unknown" when
the source does not provide a value. Return JSON matching the requested schema.
"""

EXTRACTION_PROMPT = """Analyze this source material and return structured knowledge.
Suggested owners must be exact names found in the source, or null. Deadlines must
be exact dates found in the source, or null. Preserve uncertainty in unresolved_questions.

SOURCE:
{source}
"""

HANDOVER_BRIEF_PROMPT = """Create a concise, incoming-employee-specific handover brief.
Use only the supplied evidence. Do not infer missing facts. Include these headings:
Project background, Current status, Key decisions and rationale, Completed work,
Pending tasks, Critical deadlines, Dependencies, Risks, Important documents,
Recommended next steps. Explicitly say "Evidence insufficient" for unsupported sections.

Incoming employee: {incoming_employee}
Project: {project}
Evidence:
{evidence}
"""

ASSISTANT_PROMPT = """Answer the question using only the evidence below.
Cite evidence inline as [filename, section/page] whenever metadata is available.
If the evidence does not answer the question, say exactly:
"Evidence is insufficient to answer this question."
Do not use general knowledge or make assumptions.

Question: {question}
Evidence:
{evidence}
"""

CARRY_FORWARD_PROMPT = """Prepare context for the next meeting or handover using only
the supplied records. Summarize unresolved tasks with owner, due date, status and
history; then list previous decisions, dependencies, risks and unresolved questions.
Preserve unknown values rather than inventing them.

Records:
{records}
"""

READINESS_GAP_PROMPT = """Inspect the handover evidence below for missing context that
could prevent the incoming employee from working independently. Do not calculate or
change a numeric score. Return JSON only with:
{"missing_information": ["..."], "critical_warnings": ["..."],
"recommendations": ["..."]}. Mention only gaps supported by the evidence.

Evidence:
{evidence}
"""
