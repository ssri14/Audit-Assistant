# Audit Assistant

A desktop prototype for locating possible audit leads in one PDF against up to five supplied reference PDFs. It uses your configured GPU servers for model inference. Results support human examination; they are not audit verdicts.

## Run

From this folder, run:

```sh
python3 launch.py
```

On this development Mac the launcher reuses the existing cached Python/Qt installation; no new environment is needed. On another machine, install `requirements.txt` in your chosen Python environment and run `python app.py`. Native EXE/DMG packaging and GitHub Actions are configured; see PACKAGING.md for build, verification and release steps.

For source runs, copy `.env.example` to `.env` and set the reasoning and vision base URLs and model IDs, or use **GPU server settings** in the app. Base URLs end in `/v1`; a pasted `/v1/models` URL is also accepted. GUI settings are saved in `~/.audit-assistant/servers.json`. Environment variables take precedence. API keys are optional. The development `.env` and runtime configuration are excluded from Git.

## Workflow

1. Choose one target PDF and 1–5 reference PDFs, or **Load demo packet**.
2. **Build Compliance Book**: inspect extracted rules, applicability, exceptions and their source quotations. Use Add rule, Edit selected rule (or double-click), and Remove selected rule to prepare the book before screening. Edits retain stable IDs and an original/before-and-after history; a rule may be user-added without a linked reference. At least one rule is required. Rules lock after screening completes.
3. **Screen target**: inspect candidate passages and the associated rule IDs.
4. **Review leads**: the model checks each candidate skeptically and can request source pages or bounded arithmetic. It returns retained, not retained, or insufficient evidence, plus qualitative confidence and a short note.
5. **Export review pack** saves completed phases, coverage, model responses and a highlighted target copy in one ZIP. Nothing asks for an output folder before analysis.

Click a rule, candidate or review row to inspect readable evidence details beneath its source PDF. The lower-left panel contains Live Activity; no JSON is shown in the interface. Unique quotations located in native PDF text can be highlighted. Scanned-page quotations refer to the vision model's reading; their original page must be checked visually. The original PDFs are preserved.

## Activity feedback

The live activity panel is driven by actual workflow events. Labels include extracted page headings, record identifiers, filenames, rule work, requested evidence and calculations—for example, checking an emergency purchase or reading its referenced approval. Working, completed and stopped tasks have elapsed times and a persistent session history. The panel can show multiple active tasks, while inference currently runs sequentially. It does not display private model reasoning or invent progress messages while a request is pending.

## Models and limits

The demo uses GPT-OSS 120B for compliance notes, screening and skeptical review; Nemotron Nano 12B VL reads scanned or image-bearing pages. Native text pages use local PDF extraction before reasoning. Both endpoints are configurable. Documents are sent to those servers; there is no cloud fallback.

Initial operational limits: target 30 pages; each reference 50 pages, combined references 100 pages; 15 MB per file and 60 MB combined; at most 20 image-bearing pages; 200 extracted rules; 80 inference calls; two evidence-expansion rounds per candidate. PDFs must be unlocked. A conservative request budget prevents silent context truncation. A limit or request failure pauses work and keeps completed results exportable.

Current chunking uses page windows of up to 7,000 characters with 700-character overlap. Structural chapter chunking and automatic cross-session resume are future work. Retry in the current session reuses completed model responses. Session files are temporary until exported; closing the app removes them.

## Demo and validation

The bundled packet is fictional workshop material, not government procurement rules or real transactions. It contains a threshold case, an emergency exception with approval on another page, an arithmetic discrepancy, a missing acceptance record and an embedded instruction that should be treated as document content. Its mixed PDF includes a scanned page to exercise both models. Evaluation expectations are kept separately and are not provided to inference.

`prepare_pilot.py` reproduces the demo PDFs. `PILOT_REVIEW.md` records early model behaviour and limitations. Automated tests run with `python -m unittest discover -s tests -q`; Qt tests require PyQt6 and can run with `QT_QPA_PLATFORM=offscreen`.

Model extractions can omit information; a second role using the same model is not independent assurance. Confidence describes model-reported support for its disposition, not a probability of a breach. Missing records are requests for evidence, not proof that the records never existed. Source validation concerns remain visible beside the model's output.

## Desktop downloads

Release builds provide a portable Windows x64 EXE and a macOS Apple Silicon DMG. Python and PDF tools are included; models and GPU servers are configured separately. Open GPU server settings on first launch. See RELEASE_NOTES.md for participant instructions and PACKAGING.md for release maintainers.
