# Graph Report - .  (2026-06-25)

## Corpus Check
- Corpus is ~10,809 words - fits in a single context window. You may not need a graph.

## Summary
- 303 nodes · 639 edges · 24 communities (20 shown, 4 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 24 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Graph Extraction Engine|Graph Extraction Engine]]
- [[_COMMUNITY_Ingest & Graph Construction|Ingest & Graph Construction]]
- [[_COMMUNITY_Render Pipeline & Base Classes|Render Pipeline & Base Classes]]
- [[_COMMUNITY_Graph Store & Persistence|Graph Store & Persistence]]
- [[_COMMUNITY_Slide Schema & Judge Tests|Slide Schema & Judge Tests]]
- [[_COMMUNITY_Graph Query API|Graph Query API]]
- [[_COMMUNITY_Frontend TypeScript Config|Frontend TypeScript Config]]
- [[_COMMUNITY_FastAPI Backend Endpoints|FastAPI Backend Endpoints]]
- [[_COMMUNITY_Project Concepts & Docs|Project Concepts & Docs]]
- [[_COMMUNITY_Frontend Dependencies|Frontend Dependencies]]
- [[_COMMUNITY_Shared Data Models|Shared Data Models]]
- [[_COMMUNITY_LLM Client & Utilities|LLM Client & Utilities]]
- [[_COMMUNITY_Graph ID Namespace|Graph ID Namespace]]
- [[_COMMUNITY_Frontend UI Pages|Frontend UI Pages]]
- [[_COMMUNITY_App Layout & Metadata|App Layout & Metadata]]
- [[_COMMUNITY_Next.js Configuration|Next.js Configuration]]
- [[_COMMUNITY_Package Root|Package Root]]
- [[_COMMUNITY_Slide Agent Root|Slide Agent Root]]

## God Nodes (most connected - your core abstractions)
1. `GraphStore` - 67 edges
2. `Node` - 26 edges
3. `GraphQuery` - 24 edges
4. `Deck` - 23 edges
5. `Edge` - 20 edges
6. `DesignPhilosophy` - 18 edges
7. `compilerOptions` - 16 edges
8. `load_text()` - 16 edges
9. `Document` - 16 edges
10. `Block` - 15 edges

## Surprising Connections (you probably didn't know these)
- `_graph_store()` --calls--> `build_graph()`  [EXTRACTED]
  tests/test_judge_and_inbox.py → services/pipeline/graph/builder.py
- `_store()` --calls--> `build_graph()`  [EXTRACTED]
  tests/test_validate.py → services/pipeline/graph/builder.py
- `tmp_store()` --calls--> `GraphStore`  [EXTRACTED]
  tests/conftest.py → services/pipeline/graph/store.py
- `_build()` --calls--> `GraphStore`  [EXTRACTED]
  tests/test_graph.py → services/pipeline/graph/store.py
- `_graph_store()` --calls--> `GraphStore`  [EXTRACTED]
  tests/test_judge_and_inbox.py → services/pipeline/graph/store.py

## Import Cycles
- 3-file cycle: `services/pipeline/graph/__init__.py -> services/pipeline/graph/builder.py -> services/pipeline/graph/extract_agent.py -> services/pipeline/graph/__init__.py`
- 3-file cycle: `services/pipeline/graph/__init__.py -> services/pipeline/graph/builder.py -> services/pipeline/graph/deterministic.py -> services/pipeline/graph/__init__.py`

## Hyperedges (group relationships)
- **Slide Agent End-to-End Pipeline Flow** — slide_agent_readme_ingest, slide_agent_readme_knowledge_graph, slide_agent_readme_query_tool, slide_agent_readme_researcher, slide_agent_readme_designer, slide_agent_readme_judge, slide_agent_readme_render [EXTRACTED 1.00]
- **Trustworthiness Enforcement Triad** — slide_agent_readme_judge, slide_agent_readme_design_philosophy, slide_agent_readme_provenance_tracking [EXTRACTED 0.95]
- **Graph Integrity Constraint System** — slide_agent_readme_closed_ontology, slide_agent_readme_deterministic_validator, slide_agent_readme_knowledge_graph [EXTRACTED 0.95]

## Communities (24 total, 4 thin omitted)

### Community 0 - "Graph Extraction Engine"
Cohesion: 0.08
Nodes (34): Knowledge-graph builder: orchestrates the deterministic + agent-assisted passes, _claims_from_block(), extract(), _find_concepts(), _find_metrics(), _mentions_from_text(), Deterministic, rule-based graph extraction (no LLM).  Given documents, produce a, _blocks_payload() (+26 more)

### Community 1 - "Ingest & Graph Construction"
Cohesion: 0.11
Nodes (25): build_graph(), _doc_id(), load_document(), load_text(), File loaders. Normalize uploaded files into a canonical Document.  Document ids, Build a Document from in-memory text (used by API uploads and tests)., _title_from(), _block_id() (+17 more)

### Community 2 - "Render Pipeline & Base Classes"
Cohesion: 0.15
Nodes (18): ABC, BaseModel, Renderer interface. reveal.js is the first implementation; a PPTX adapter (pytho, Return the rendered artifact (HTML string for reveal.js)., Renderer, reveal.js HTML renderer.  Turns the renderer-agnostic Deck into a self-contained, RevealRenderer, DesignPhilosophy (+10 more)

### Community 3 - "Graph Store & Persistence"
Cohesion: 0.12
Nodes (7): GraphStore, Question, GraphManifest, ResearchNote, tmp_store(), Researcher agent.  Reads the graph (top concepts) and gathers ADDITIONAL externa, research()

### Community 4 - "Slide Schema & Judge Tests"
Cohesion: 0.19
Nodes (21): AskUser, Citation, ContentElement, Backs a content element to either graph provenance or an external note., Slide, _graph_store(), Judge veracity/design enforcement and the async question inbox., test_judge_flags_fabricated_metric() (+13 more)

### Community 5 - "Graph Query API"
Cohesion: 0.12
Nodes (9): MultiDiGraph, GraphQuery, Typed query API over the knowledge graph.  This is the ONLY way agents learn fac, Return the source blocks backing a node or edge id., True if `text` appears verbatim (case-insensitive) in any source block., BFS out to `depth`; returns {nodes, edges} dicts for the reachable region., Claims that are `about` the given concept, or `supported by` a metric/event., dispatch() (+1 more)

### Community 6 - "Frontend TypeScript Config"
Cohesion: 0.10
Nodes (19): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+11 more)

### Community 7 - "FastAPI Backend Endpoints"
Cohesion: 0.15
Nodes (15): answer(), AnswerBody, build(), BuildOpts, create_project(), deck_json(), graph(), list_questions() (+7 more)

### Community 8 - "Project Concepts & Docs"
Cohesion: 0.15
Nodes (16): Project Helios Sample Fixture, Async Question Inbox, Closed Ontology, Design Philosophy, Designer Agent, Deterministic Validator, FastAPI Backend, Ingest Component (+8 more)

### Community 9 - "Frontend Dependencies"
Cohesion: 0.12
Nodes (15): dependencies, next, react, react-dom, devDependencies, @types/node, @types/react, typescript (+7 more)

### Community 10 - "Shared Data Models"
Cohesion: 0.23
Nodes (11): Enum, Question, QuestionStatus, Shared pydantic models used across ingest, graph, query, workflow, render, api., RunEvent, Stage, str, ask_user() (+3 more)

### Community 11 - "LLM Client & Utilities"
Cohesion: 0.29
Nodes (10): Any, RuntimeError, available(), _cli_path(), complete_json(), _extract_json(), LLMUnavailable, Claude CLI wrapper.  All agentic steps go through here. Instead of calling the A (+2 more)

### Community 12 - "Graph ID Namespace"
Cohesion: 0.39
Nodes (6): claim_id(), concept_id(), edge_id(), Deterministic id helpers.  Node ids are derived from stable, content-based slugs, section_id(), slug()

### Community 13 - "Frontend UI Pages"
Cohesion: 0.40
Nodes (3): Question, RunState, STAGES

## Knowledge Gaps
- **41 isolated node(s):** `metadata`, `RunState`, `Question`, `STAGES`, `nextConfig` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GraphStore` connect `Graph Store & Persistence` to `Graph Extraction Engine`, `Ingest & Graph Construction`, `Render Pipeline & Base Classes`, `Slide Schema & Judge Tests`, `Graph Query API`, `FastAPI Backend Endpoints`, `Shared Data Models`?**
  _High betweenness centrality (0.252) - this node is a cross-community bridge._
- **Why does `GraphQuery` connect `Graph Query API` to `Graph Extraction Engine`, `Render Pipeline & Base Classes`, `Graph Store & Persistence`, `Slide Schema & Judge Tests`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `Node` connect `Graph Extraction Engine` to `Render Pipeline & Base Classes`, `Shared Data Models`, `Graph Store & Persistence`, `Graph Query API`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `GraphStore` (e.g. with `AnswerBody` and `BuildOpts`) actually correct?**
  _`GraphStore` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `Node` (e.g. with `GraphStore` and `GraphQuery`) actually correct?**
  _`Node` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `GraphQuery` (e.g. with `Block` and `Edge`) actually correct?**
  _`GraphQuery` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Deck` (e.g. with `GraphStore` and `Renderer`) actually correct?**
  _`Deck` has 3 INFERRED edges - model-reasoned connections that need verification._