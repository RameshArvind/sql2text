## Include/Exclude Sources (Linkup)
- Domain-level include/exclude controls

## Prefer Native-Language Sources
- Exclude English when local language differs
 - Faster, earlier local reporting and updates
 - Nuance: idioms, place names, micro-regions captured accurately
 - Better coverage of municipal/regional issues; less global noise
 - Terminology fidelity (official names, acronyms) improves search and synthesis

## Two-Step Local Sourcing
- Find local outlets
- Then search recent news scoped to them

## Continuous Discovery & Filtering
- Language filtering on new sources
- Deduplicate URLs

## Translation
- DeepL to EN-US
- Auto-detect source language

## Parallel Tooling & Budgets
- Run 3–5 tools concurrently
- Respect per-query tool-call budgets

## Tighten-and-Retry
- If English leaks in, add offenders to exclude and rerun

## Output Style
- Short blurbs with inline citations

## Streaming & Limits
- Live tool-call updates
- Soft cap ~20 tool-call turns

## Debugging & Observability
- Use OpenAI Traces / stream logs to refine prompts

## Evals via OpenAI Traces
- Monitor spans per message: tool calls, params, outputs, latency
- Diagnose prompt/flow issues; compare traces across runs to validate fixes
- Iterate prompts, domain filters, and concurrency/turn budgets based on findings