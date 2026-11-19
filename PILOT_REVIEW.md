# Audit Assistant feasibility pilot

Synthetic sources: a four-page procurement dossier and two reference PDFs totalling three pages. Six fictional records, five fictional clauses. All seven pages were rendered and visually checked. Keys were excluded from inference.

## Original run

7 server calls; 26.49 seconds of recorded request time (not a large-document throughput benchmark).
Five rules were extracted; all five supporting quotes match the supplied native reference text. Five screening candidates were produced; their five target quotes match native source text.
The first batch review retained an unsupported payment-document concern and labelled missing-record requests as retained/high confidence. These results are preserved; no baseline answers were replaced.

## Revised per-candidate review

6 additional server calls; 16.45 seconds of request time.
A stricter applicability/missing-evidence prompt and separate candidate contexts yielded two retained leads (quotation shortfall and invoice arithmetic discrepancy), two not-retained candidates, and one insufficient-evidence request for an acceptance certificate.
For the emergency purchase, the reviewer requested target page 3, read the dated supervisor approval, and rejected the initial quotation concern. The other rejected candidate lacked evidence of the payment event required by its cited rule.
The control records below the quotation threshold did not produce a supported compliance concern. The embedded supplier instruction did not override the workflow.

## Remaining limitations

This is one tiny assistant-authored synthetic packet, with assistant-reviewed expectations, not independent validation or general audit accuracy.
The model still used verdict-like wording (“no breach”) in a rejection note. It mentioned R003 in its rationale but omitted that rule from its structured rule-ID list. Some applicability_quote fields contain a rule quotation rather than evidence of the triggering target event. These need explicit validation/repair in the product, not silent acceptance.
Confidence values are self-reported, qualitative and uncalibrated. A second role using the same model does not provide independent assurance. Native-text screening and one separate vision diagnostic do not establish performance on dense real-world scans.

## PDF highlighting

5/5 candidate passages uniquely located and highlighted on a separate PDF copy using PDFium character ranges and pypdf quad annotations. Original PDF hash is unchanged.
All Phase 2 candidates remain highlighted, including rejected and insufficient-evidence candidates; their annotation notes contain the Phase 3 disposition. Highlights are review locations, not confirmed violations.

## Architecture implication

Proceed with three persisted phases, source-grounding checks, per-candidate skeptical review, bounded requests for original pages, explicit insufficient-evidence outcomes, and a human-review checkpoint. GUI/.env server configuration is required; request text goes to configured in-house GPU endpoints. Proposed size/token limits remain in DESIGN.md and require real-document pilot testing.

## Desktop workflow verification — 19 November 2026

The implemented engine completed all three phases on the mixed native/scanned demo PDF using the configured GPT-OSS and Nemotron endpoints: 14 inference calls, five extracted rules and five candidate passages. The activity stream included actual procurement headings, record identifiers, quote checks and review passages. Completed output was exported to a ZIP and loaded into the desktop UI for visual inspection.

This run is a workflow test, not an accuracy pass. It retained the invoice arithmetic lead and treated the missing acceptance certificate as insufficient evidence. It also mislabelled the explicit one-quotation ordinary purchase as insufficient evidence and failed to request Appendix A for two emergency-purchase candidates, leaving them unresolved even though the approval was present in the uploaded dossier. This differs from the earlier per-candidate pilot that requested the appendix. The app now flags insufficient-evidence results with no follow-up page requests, and preserves the model output and source preview for human checking. These results must not be presented as a completed audit or a validated detection benchmark.

Native candidate quotations were located in an annotated copy; the scanned-page lead remains page/excerpt only and is explicitly marked for visual review. Fifteen local tests pass, including multiple simultaneous activity entries, genuine completion events from a background Qt worker, PDF routing, bounded arithmetic, cancellation/retry intake state and request budgets. The Qt worker test caught and fixed a signal name that shadowed QObject.event.
