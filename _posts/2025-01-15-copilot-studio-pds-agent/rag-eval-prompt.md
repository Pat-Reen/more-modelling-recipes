# RAG Evaluation Prompt

Use this prompt when passing the golden queries to either the Copilot Studio agent or the custom RAG system for evaluation. Paste the prompt first, then a single query object from the JSON.

---

## Prompt

You are evaluating a RAG system built over Australian life insurance Product Disclosure Statements (PDSs).

I will give you a query and a set of evaluation criteria. Your task is to answer the query as the RAG system would — strictly grounded in the PDS documents you have been given as knowledge — and then self-assess your response against the criteria.

**Evaluation criteria:**

1. **Grounding** — Is every claim in your response explicitly stated in the PDS? Do not infer, extrapolate, or describe system behaviour or administrative practice unless explicitly stated in the PDS.
2. **Directness** — If the PDS provides specific values (options, formulas, timeframes, amounts), state them directly. Do not describe where they can be found or reference them abstractly.
3. **Silence** — If the PDS does not address the query, say so clearly and specifically. Do not surface adjacent content and present it as responsive.
4. **Attribution** — Attribute each claim to the specific insurer and document. Do not blend insurers in a way that makes the source of a claim ambiguous.
5. **Brevity** — Give the minimal necessary response. Over-explaining is a failure mode.
6. **Boundaries** — Do not provide financial, tax, or legal advice. If a query requires judgement beyond what the PDS states, set that boundary explicitly.

**After your response**, score yourself on each criterion: Pass / Partial / Fail, with one sentence of reasoning. Then check your response against the `must_contain` and `must_not_contain` constraints in the query.

**Query:**

```json
{PASTE QUERY OBJECT HERE}
```

---

## Usage notes

- Run each query independently. Do not carry context between queries.
- For cross-insurer queries (`expected_docs` lists more than one document), the agent must retrieve from all listed documents and label each insurer's answer separately.
- For queries with `difficulty: "hard"` and `answer_type: "pds_silent"`, the correct answer is a confident statement that the PDS does not address this — not a hedged partial answer.
- Compare responses between the Copilot Studio agent and the custom RAG system using the same query set. Differences in grounding, directness, and silence handling are the meaningful signal.
