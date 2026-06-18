# Resource Reference Model

## Purpose

This note defines the canonical resource model for knowledge ingestion and retrieval.

The goal is to stop reasoning in terms of file-type-specific workflows such as "PDF support" and
instead reason in terms of:

- canonical resource identity
- source origin
- acquisition mode
- extraction need
- indexing contract

This model is required for WS3 because knowledge preparation, dataprep, retrieval, and future
knowledge-base reuse all depend on a single consistent notion of "resource".

## Problem Being Solved

The current behavior is confusing because some resources can acquire multiple visible identities.

Example:

- external reference: https://arxiv.org/pdf/2306.02171.pdf
- source display name: 2306.02171.pdf
- extracted artifact name: 2306.02171.pdf.md

If the workflow reasons about the source name while the backend exposes the extracted artifact
name, retrieval becomes inconsistent and failure analysis becomes misleading.

The system must expose one canonical identity for a resource, regardless of whether the content was
downloaded, extracted, cached, or derived from another source.

## Canonical Identity

Every resource must be identified by a stable canonical URI.

Examples:

- file:///absolute/path/to/doc.pdf
- https://arxiv.org/pdf/2306.02171.pdf
- evernote://note/<id>
- notion://page/<id>
- ag://report/<id>
- kb://2306.02171.pdf

Rules:

- The canonical URI is the only identity used by the workflow.
- Display names are user-facing labels, not identities.
- Cache files, extracted text files, and backend-specific ids are implementation details.

## URI Roles

### External Resource URIs

These identify a source of truth outside the internal knowledge base.

Examples:

- file:// for local files
- https:// for web resources
- evernote:// for Evernote notes
- notion:// for Notion pages

These URIs answer the question: where does this resource come from originally?

### kb:// URIs

kb:// identifies the canonical internal reference inside the knowledge base, regardless of the
original source.

Example flow:

- external source: https://arxiv.org/pdf/2306.02171.pdf
- internal reference after ingestion: kb://2306.02171.pdf

This URI answers the question: how do I refer to this resource consistently once it exists in the
knowledge base?

This is useful because later workflows should not need to care whether the original source came
from the web, local disk, Evernote, or Notion.

### ag:// URIs

ag:// identifies content produced by agentic-research itself.

Examples:

- ag://report/<id>
- ag://analysis/<id>

These are not raw external sources. They are generated artifacts that may later become reusable
knowledge inputs.

Relation to kb://:

- ag:// refers to provenance and production context
- kb:// refers to the canonical internal knowledge-base identity

In practice, an ag:// artifact may also be ingested into the knowledge base and then referenced as
kb://...

## Unified Workflow

The ingestion and retrieval workflow should be the same for every resource type.

1. A report references resources through canonical URIs.
2. The knowledge preparation agent resolves each URI.
3. If the resource already exists in the knowledge base and is still valid, reuse it.
4. Otherwise dataprep ingests it.
5. If the resource needs extraction, dataprep produces indexable text.
6. The backend indexes the resource under its canonical internal identity.
7. Retrieval always returns the canonical resource identity, never a cache or extraction artifact
   identity.

## Source Dimensions

The system should model these dimensions explicitly.

### Source Origin

- local disk
- web
- MCP external source
- agentic-research generated artifact

### Content Mode

- text-native
- extraction-required

Examples:

- text-native: md, txt, some html
- extraction-required: pdf, docx, pptx, complex web pages

### Persistence Mode

- source of truth
- local cache or snapshot
- extracted text for indexing
- derived content

These are different concepts and must not share the same field name.

## Recommended Data Model

Each knowledge entry should expose fields conceptually equivalent to:

- resource_uri
- resource_scheme
- display_name
- source_kind
- content_kind
- source_version
- cache_path
- extracted_text_path
- index_document_id
- openai_file_id
- last_ingested_at

Important rule:

- extracted_text_path is not a second document identity

## Naming Rules

The term normalized_filename should be removed from this workflow vocabulary.

Why:

- it is ambiguous
- it suggests cleaned or semantically normalized content
- it conflicts with future notions of normalized or refined knowledge artifacts

Prefer explicit names:

- cache_path
- extracted_text_path
- derived_content_path

## Workflow Contract

### User Contract

The user always references a resource the same way:

- file://...
- https://...
- evernote://...
- notion://...
- kb://...
- ag://...

The user should not need to know whether extraction or caching is required.

### Agent Contract

The knowledge preparation agent is responsible for:

- detecting resource references
- checking whether they already exist in the knowledge base
- asking dataprep to ingest missing resources
- never bypassing the retrieval contract by trying to directly open source files as a fallback

### Dataprep Contract

Dataprep is responsible for:

- acquiring the source
- extracting text if needed
- managing cache or snapshot details
- indexing the resource under the canonical internal identity

### Retrieval Contract

Retrieval must:

- accept canonical resource identifiers
- return canonical resource identifiers
- never leak cache or extracted artifact identities as if they were the source identity

## Failure Handling

If retrieval returns zero hits for a selected canonical resource:

- the workflow must fail fast
- the failure must be reported as a retrieval or indexing problem
- the system must not attempt direct filesystem access to the source path as a fallback

This is essential for making failures diagnosable.

## Why This Matters

This model prevents:

- PDF-specific behavior that diverges from other resource types
- identity split between source file and extracted artifact
- confusing failures where the model reports access errors instead of retrieval failures
- future inconsistencies when MCP sources and generated reports become first-class knowledge inputs

It also creates a path to support:

- local files
- web documents
- Evernote
- Notion
- internal agentic-research outputs
- future knowledge-base-native references

with one consistent mental model.
