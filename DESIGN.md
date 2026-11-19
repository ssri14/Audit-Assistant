# Audit Assistant - design and implementation notes

## Purpose and status

Help an auditor locate passages worth examining against supplied reference/rule documents. Outputs are review leads and their evidence, never audit verdicts or a compliance certificate. The first desktop prototype is implemented. See README.md for its actual controls, limits and launch instructions. The detailed sections below retain design intentions; structural chapter chunking and cross-session resume remain future work.

Endpoints were queried successfully on 19 November 2026. Port 8000 lists `openai/gpt-oss-120b`, configured context 32768 tokens. Port 8002 lists `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16`, configured context 131072 tokens. Both model-list access and pilot task calls have been exercised. The pilot exposed quotation and disposition errors; PILOT_REVIEW.md records these limitations. Published model limits do not override deployed server limits.

## Model roles and configuration

- Nemotron vision: free reading of scanned or image-bearing pages, preserving page identity, tables, uncertain text and amounts. Native text/coordinates come from a local PDF parser where reliable. Model reading and subsequent structuring remain separate calls when required.
- GPT-OSS 120B: atomic rule extraction from supplied page text, consolidation, chunk screening, follow-up evidence requests and skeptical review. Reviewing in a fresh role/context using the same model is not independent assurance.
- Separate configurable reading and reasoning endpoint/model roles; GUI can discover models and test each connection. `.env` supplies demo defaults. Users can configure the same host with different ports or different servers, and optional API keys. Keep `.env` ignored, and never embed it or demo host addresses in distributed binaries.
- Use OpenAI-compatible `/v1` base URLs; accept a pasted `/v1/models` URL and normalize it. Probe installed serving features rather than assuming all vLLM versions expose the same extras. No external cloud fallback or model downloads.
- Document requests go to the configured GPU servers. Do not reuse OPAH's claim that all processing stays on the laptop. Processing sends the selected document text or page images to the configured servers.

## Proposed starting limits (validate against pilot)

- PDF only, one target and one to five references; no embedded attachment execution, spreadsheets or nested archives.
- Target: up to 30 pages / 15 MB. References: up to 50 pages / 15 MB each, at most 100 reference pages combined. Total upload cap 60 MB.
- At most 20 image/scanned pages across the job for the initial pilot. Flag unreadable pages and exclude them from any completeness claim.
- For a short workshop demonstration, use a 5-10-page target and 1-3 short reference extracts, rather than whole manuals.
- Structural chunks target 2000-3000 tokens; bounded adjacent overlap about 250 tokens. Dense pages can split into multiple fragments while preserving page and text offsets. Tables retain headers/units; cross-page continuations are linked.
- Reasoning calls target no more than 24000 tokens including prompts, rule evidence, source context and reserved output, below the currently deployed 32768 limit. Validate actual token counts using the server tokenizer if available; otherwise use a conservative budget and fail visibly rather than silently truncate.
- Start with a 200-atomic-rule cap, 80-call job budget and at most two context-expansion passes per candidate. These are proposed operational guardrails, not accuracy thresholds. If a limit is reached, retain completed work, mark coverage incomplete and offer a smaller scope; never silently discard rules or candidates.
- Process requests sequentially by default per model. Enable only bounded concurrency after measuring server behaviour. Support cancellation and checkpoint/resume; show actual progress rather than fabricated ETA.

## Intake and source ledger

Fingerprint each source file. Record original filename, role, page count, page numbers, any printed page labels, text offsets and available text geometry. Detect extraction gaps, rotated pages and tables. Keep native text and visual readings distinct. Record model ID, serving settings and extraction lineage. An unread page is a coverage gap.

Ask for an optional audit focus/period. Reference metadata includes document title, issuing authority as stated, edition/date, effective dates, section/clause IDs and applicability limits. Missing version information and unresolved conflicts remain visible. Do not invent a hierarchy or treat a generic recommendation as a mandatory rule.

## Phase 1 - Consolidated Compliance Book

1. Read every selected reference fragment; maintain a fragment coverage ledger.
2. Extract atomic obligations, prohibitions, thresholds, required records, exceptions and applicability conditions.
3. Assign stable rule IDs. Preserve exact supporting source excerpts, document/page/section pointers, qualifications, amounts/units and version metadata.
4. Consolidate duplicates without losing their source links or exceptions. Keep conflicting rules separately and identify the unresolved conflict.
5. Check source grounding and extraction coverage. A title/summary is not a substitute for the original clause.
6. Present the Consolidated Compliance Book with editable scope/applicability and a review checkpoint before screening. Users may explicitly choose an automatic full run for a demo; agent checkpoints still persist.

Deliverable 1: rule table/readable book plus structured JSON with provenance, uncertainty and coverage. Unsupported or unreadable clauses are flagged rather than converted into invented rules.

## Phase 2 - Candidate locations

1. Build structural or page-window target chunks, each with stable IDs and source spans.
2. Route potentially applicable rules using their full compact inventory; retrieve original clauses, exceptions and related chunks. Local lexical search requires no additional hosted embedding model. Retrieval confidence is not compliance confidence.
3. The screening role identifies plausible locations and may request neighbouring text, definitions, table headers or reference clauses through bounded read/search tools.
4. Candidate records contain target quote/location, cited rule IDs and excerpts, an applicability explanation, possible concern, missing evidence and related candidates.
5. Merge duplicates from overlapping windows while retaining every source location. Log chunks processed, rules considered/retrieved, unread content and unresolved applicability. A retrieval omission is not a reviewed-and-compliant rule.

Deliverable 2: candidate ledger for every chunk, including chunks with no candidate, explicit coverage gaps and unresolved cases. No candidate is not proof of compliance.

## Phase 3 - Skeptical review

Review each candidate with the actual target text and reference clauses, including exceptions and nearby context. A fresh reviewer prompt checks applicability, factual support, alternative readings, duplicate accounting and missing evidence; it does not merely polish the screening note. It may request up to two extra evidence passes.

Use three dispositions:

- Retained for auditor review: short draft audit note and confidence rationale.
- Not retained: supplied evidence does not support this candidate, with reasons. Do not label the whole document compliant.
- Insufficient evidence: say what additional record/context or better reading is needed.

Confidence is Low/Medium/High as an evidence-strength label, not a calibrated probability of a breach:

- High: a clearly applicable cited rule and a clear supporting source passage, with no material unresolved reading or exception.
- Medium: a plausible supported concern with a stated applicability/context limitation.
- Low: weak/ambiguous extraction, uncertain applicability or material missing context; often belongs under Insufficient evidence.

Confidence in the auditor-review lead is distinct from text-reading quality. Retain both and their reasons. Keep rejected candidates accessible with reasons.

Deliverable 3: reviewed lead register, rejected-candidate log and insufficient-evidence list, with source citations and suggested follow-up records. Record coverage and avoid an overall compliance score or approval badge.

## Highlighting and evidence validation

For native-text PDFs, verify the quoted text against source text and map unique matches to text rectangles/quads. Display highlights and export an annotated copy. Repeated/ambiguous matches require disambiguation; never highlight a guessed location.

For scans, match an extracted quote to OCR/vision-derived geometry only when reliable coordinates exist. Otherwise provide original PDF page, excerpt and source preview. Agreement with OCR establishes agreement with the reading, not fidelity to the printed image; preserve that distinction. Printed page label and physical PDF page are both shown when known.

Source spans must be validated in code. Retain original and normalized text; only documented whitespace/ligature normalization is allowed when matching excerpts. Do not silently repair digits, relocate an excerpt to a different section, or fabricate a quotation.

## Agent controller and storage

This is a bounded workflow with model-selected read/search/calculate requests, persisted task state and evidence-led refinement. It is more than a single long prompt, and does not require multiple distinct LLMs for every role. Uploaded text is evidence rather than executable agent instructions. Tools may read only the selected documents/indices and perform arithmetic; no arbitrary shell execution, internet search or external messages.

Keep phase artifacts, prompts, responses, candidate revisions and source hashes in a local job folder. Allow explicit save/resume and deletion of a job. Sessions/reference books should be reused only when source hashes, scope, model/settings and versions match. Exports may include a readable Compliance Book, candidate/review tables, structured JSON and an annotated target PDF where grounding supports it. Model prose remains marked as assistant-generated.

## Pilot before UI implementation

Use a short raw procurement/administrative document and selected reference extracts with assistant-reviewed expected leads, exceptions and no-issue controls. Include an ambiguous OCR number, a missing supporting record, a rule exception, a cross-page dependency and a misleading instruction inside document text. Never supply the key to inference.

Measure grounding and applicability, coverage, retained/rejected/insufficient outcomes, false positives on controls, handling of missing evidence, reading-versus-formatting changes, tokens/calls, server latency and recovery from cancellation. Do not choose a confidence rubric or limits from model self-report alone. Confirm native-text and scanned routes separately. Build the first UI around observed behaviour rather than claim general audit accuracy.

Primary model/serving references:

- https://huggingface.co/openai/gpt-oss-120b
- https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16
- https://docs.vllm.ai/en/latest/serving/openai_compatible_server/
