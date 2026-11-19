# Audit Assistant v0.1.0 — workshop pre-release

Upload one target PDF and up to five reference PDFs. Build and edit a Compliance Book, screen the target for possible review locations, then request a skeptical review. Inspect source pages, readable evidence details and live contextual activity. Export completed work, rule-change history and supported PDF highlights in a review ZIP.

## Downloads

- Windows x64: download the `.exe` and open it. This is a portable application, not an installation wizard.
- macOS Apple Silicon: download the `macOS-arm64.dmg`, open it, and drag AuditAssistant to Applications. Requires macOS 14 or newer. This download does not support Intel Macs.
- Python, Qt and PDF tools are included. No Python installation or Ollama is needed on the participant's computer.

## Before analysing

Configure reachable in-house GPU servers using **GPU server settings**, then **Test servers**. Provide OpenAI-compatible `/v1` endpoints, model IDs and optional API keys. The workshop uses GPT-OSS 120B for reasoning and Nemotron Nano 12B VL for scanned pages. Model weights and GPU servers are not included. Documents are processed by the servers you configure. No demo IP address or credentials are included in the download.

Use **Load demo packet** for fictional workshop documents. These are not real procurement rules or transactions.

## Limits and interpretation

PDF only: target up to 30 pages, references up to 100 pages combined (50 each), 15 MB per file / 60 MB total, up to 20 image-bearing pages. The first version also caps extracted rules and model requests. Results are possible leads for human examination; model confidence is qualitative, not a probability of a breach. Models may misread evidence, miss rules or fail to retrieve relevant context. Scanned-page excerpts need visual checking; precise highlights are available only for uniquely located native text.

These initial packages are unsigned and the macOS package is not notarized. Operating systems may show an unknown-publisher or unverified-app message. Normal publisher signing can be added in a later release. Check the SHA-256 file when validating a download.
