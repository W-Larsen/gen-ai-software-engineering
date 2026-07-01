# Top AI Agents, Skills & Agentic Pipelines for Dev / PM / QA

> Research compiled May 2026. Focus: Claude Code ecosystem + cross-agent tools.

---

## 🏗️ DEVELOPMENT

### 1. Feature-Dev Plugin (Anthropic Official)
**What it does:** Replaces ad-hoc feature coding with a structured 7-phase agentic workflow: Discovery → Codebase Exploration → Clarifying Questions → Architecture Design (3+ options) → Implementation → Quality Review → Summary.

**Pros:** Prevents misunderstandings upfront; enforces architecture review before coding; parallel agent execution for speed; ensures consistency with existing codebase patterns.  
**Cons:** Overkill for trivial fixes or hotfixes; slower on large codebases; requires an existing codebase to learn from.

**Install:**
```bash
# In Claude Code
/plugin install anthropics/feature-dev
# Then use via:
/feature-dev Add user authentication with OAuth
```
**Links:** [GitHub](https://github.com/anthropics/claude-code/tree/main/plugins/feature-dev)

---

### 2. Superpowers (obra/superpowers)
**What it does:** A cross-platform agentic skills framework with 20+ battle-tested skills covering the full dev lifecycle: TDD (red-green-refactor), design brainstorming, implementation planning, parallel subagent task execution, debugging, code review, and git worktree management. Works with Claude Code, Cursor, Gemini CLI, Codex, GitHub Copilot.

**Pros:** Platform-agnostic; enforces TDD & YAGNI principles automatically; reduces ad-hoc decision-making; supports autonomous agent work for extended periods; active community.  
**Cons:** Steeper learning curve for custom skill creation; primarily benefits larger, longer-running projects.

**Install:**
```bash
# Claude Code
/plugin install superpowers@claude-plugins-official

# Gemini CLI
gemini extensions install https://github.com/obra/superpowers

# Cursor
/add-plugin superpowers
```
**Links:** [GitHub](https://github.com/obra/superpowers) · [Discord](https://discord.gg/35wsABTejz)

---

### 3. wshobson/agents — Multi-Agent Orchestration
**What it does:** 182 specialized agents across 77 focused plugins in 24 categories. Language experts (Python, TypeScript, JVM), infra specialists (Kubernetes, CI/CD, cloud), domain experts (security, backend, frontend, AI/ML), plus debugging, deployment, and documentation roles. Uses a three-tier model strategy: Opus 4.6 for critical decisions, flexible models for complex work, Haiku for support tasks.

**Pros:** Progressive disclosure keeps context lean; deep domain specialization per plugin; clean install (only loads what you need).  
**Cons:** Large surface area — takes time to know what's available.

**Install:**
```bash
/plugin marketplace add wshobson/agents
/plugin install python-development   # or any of 77 plugins
```
**Links:** [GitHub](https://github.com/wshobson/agents)

---

### 4. RIPER Workflow (Community)
**What it does:** Structured 5-phase workflow enforcing separation of concerns in AI-assisted development: **R**esearch → **I**nnovate → **P**lan → **E**xecute → **R**eview. Prevents Claude from jumping straight to implementation before understanding the problem.

**Pros:** Dramatically reduces hallucinated solutions; forces explicit planning before coding; easy to customize per project.  
**Cons:** Requires discipline to not skip phases under time pressure; adds overhead for simple tasks.

**Install:** Add the RIPER prompt/skill to your `CLAUDE.md` project config or as a slash command.  
**Links:** [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)

---

### 5. VoltAgent Subagents — fullstack-developer & code-reviewer
**What it does:** Curated 100+ specialized subagents. Key ones for dev: `fullstack-developer` (end-to-end feature work across FE/BE), `code-reviewer` (quality guardian for PRs), `refactoring-specialist` (modernize codebases, reduce complexity).

**Pros:** Plug-and-play domain specialists; minimal setup.  
**Cons:** Quality varies across agents; less opinionated than feature-dev.

**Install:**
```bash
claude plugin install voltagent-core-dev
```
**Links:** [GitHub](https://github.com/VoltAgent/awesome-claude-code-subagents)

---

## 📋 PRODUCT MANAGEMENT

### 6. Claude Code PM Plugin
**What it does:** Full PM workflow: feature scoping, stakeholder updates, sprint planning, roadmap management, and backlog grooming — all via slash commands with specialized PM agents.

**Pros:** Keeps PM artifacts (specs, updates, decisions) co-located with code; integrates Jira/Confluence context.  
**Cons:** Works best when code and PM tooling are connected; limited value without integration.

**Install:** Available via [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) curated list.

---

### 7. VoltAgent product-manager + business-analyst Subagents
**What it does:** `product-manager` — product strategy, roadmap decisions, feature prioritization, release planning. `business-analyst` — translates stakeholder needs into technical specs, clarifies scope, documents requirements.

**Pros:** Forces structured thinking before building; bridges biz ↔ eng communication.  
**Cons:** Context-dependent; works best with a well-defined project brief to start.

**Install:**
```bash
claude plugin install voltagent-core-dev
```
**Links:** [GitHub](https://github.com/VoltAgent/awesome-claude-code-subagents)

---

## 🧪 QA & TESTING

### 8. Trail of Bits Security Skills
**What it does:** Professional security-focused skills for code auditing, vulnerability detection, static analysis (CodeQL/Semgrep), and variant analysis. Designed for teams with security review requirements.

**Pros:** Production-grade, battle-tested by security professionals; systematic coverage of vulnerability classes.  
**Cons:** Requires some security domain knowledge to interpret results; setup for CodeQL/Semgrep adds overhead.

**Install:** Via [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) (Trail of Bits Security Skills entry).

---

### 9. VoltAgent qa-expert Subagent
**What it does:** Test automation specialist agent — designs test strategies, builds test frameworks, creates comprehensive test coverage plans, automates QA pipelines.

**Pros:** Opinionated test structure; reduces time writing boilerplate test scaffolding.  
**Cons:** Generic output by default — needs project-specific context for best results.

**Install:**
```bash
claude plugin install voltagent-core-dev
```
**Links:** [GitHub](https://github.com/VoltAgent/awesome-claude-code-subagents)

---

### 10. webapp-testing (travisvn/awesome-claude-skills)
**What it does:** Tests local web applications via Playwright for automated UI verification. Integrates with your dev environment to run end-to-end UI tests on demand.

**Pros:** Direct integration with local dev server; no separate test infrastructure needed.  
**Cons:** Playwright setup required; currently best for web-only apps.

**Install:** From [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) repository.

---

## 🤖 MULTI-AGENT ORCHESTRATION

### 11. Claude Squad
**What it does:** Terminal app that manages multiple Claude Code (and Codex, Aider) agents in separate workspaces simultaneously. Enables parallel agent work on different tasks/branches with a kanban-style interface.

**Pros:** True parallelism across tasks; agents coordinate via git; great for large feature work.  
**Cons:** Resource-intensive; requires good task decomposition upfront.

**Links:** [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)

### 12. Auto-Claude (Multi-Agent SDLC)
**What it does:** Integrates a full Software Development Life Cycle pipeline — from requirement intake through design, implementation, testing, and deployment review — with multiple agents handling each phase autonomously.

**Pros:** End-to-end automation of the SDLC; minimal human intervention for routine features.  
**Cons:** Needs careful guardrails; best for well-understood problem domains.

**Links:** [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)

---

## 📦 DISCOVERY & CURATED LISTS

| Resource | What's inside | Link |
|---|---|---|
| **awesome-claude-code** | Skills, hooks, slash-commands, orchestrators, plugins — community curated | [GitHub](https://github.com/hesreallyhim/awesome-claude-code) |
| **awesome-claude-skills** | 100+ skills by category, install guides | [GitHub](https://github.com/travisvn/awesome-claude-skills) |
| **claude-code-ultimate-guide** | Beginner→power-user guide, workflow templates, agent teams patterns | [GitHub](https://github.com/FlorianBruniaux/claude-code-ultimate-guide) |
| **claude-skills (alirezarezvani)** | 232+ skills across 11 AI coding platforms | [GitHub](https://github.com/alirezarezvani/claude-skills) |
| **claude-code-plugins-plus-skills** | 340 plugins + 1367 skills, open-source marketplace | [GitHub](https://github.com/jeremylongshore/claude-code-plugins-plus-skills) |

---

---

## 🧠 MEMORY & CONTEXT

### 13. claude-mem (thedotmack) ⭐ 58k
**What it does:** Persistent memory compression system for Claude Code. Auto-captures all tool usage and observations during sessions, compresses with AI, injects relevant context into future sessions via RAG (Chroma vector DB + SQLite). Provides a web viewer UI at `localhost:37777`, MCP search tools with 3-layer query pattern (search → timeline → get_observations), and `<private>` tags to exclude sensitive info.

**Pros:** Zero manual intervention — fully automatic; ~10x token savings via progressive disclosure before fetching full context; cross-session project continuity; supports modes (code, chill, investigation) and multilingual.  
**Cons:** Requires Bun + Node 18+; AGPL-3.0 license (commercial use restrictions); occasional sync issues on large projects.

**Install:**
```bash
npx claude-mem install
# or via plugin marketplace:
/plugin marketplace add thedotmack/claude-mem && /plugin install claude-mem
```
**Links:** [GitHub](https://github.com/thedotmack/claude-mem) · [Docs](https://docs.claude-mem.ai) · [Discord](https://discord.com/invite/J4wttp9vDu)

---

## ⚡ TOKEN & COST OPTIMIZATION

### 14. RTK — Rust Token Killer ⭐ 19.5k
**What it does:** CLI proxy that intercepts shell commands before they reach the LLM and compresses outputs by 60–90%. Rewrites `git status`, `ls`, `cat`, `cargo test`, `pytest`, `docker ps`, `aws` etc. to token-efficient equivalents. Single Rust binary, <10ms overhead, zero dependencies. Works via PreToolUse hook — transparent to Claude.

**Typical savings in a 30-min session:** ~118k tokens → ~24k tokens (**-80%**).

**Pros:** Transparent — Claude never knows it's happening; saves real money at scale; supports 10 AI tools (Claude Code, Cursor, Gemini CLI, Codex, Copilot, Windsurf, Cline, OpenCode); analytics dashboard (`rtk gain`).  
**Cons:** Only intercepts Bash tool calls — built-in `Read`/`Grep`/`Glob` tools bypass it; some command filtering needs tuning per project.

**Install:**
```bash
brew install rtk          # macOS
# or
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
# Then hook into Claude Code:
rtk init -g
# Restart Claude Code — done.
```
**Links:** [GitHub](https://github.com/rtk-ai/rtk) · [Website](https://www.rtk-ai.app) · [Discord](https://discord.gg/RySmvNF5kF)

> **+1 Recommendation:** Pair RTK with `CLAUDE.md` context trimming — keep your project instructions under 500 tokens, load sub-context via `@file` references only when needed. Together with RTK this can cut total session costs by 85%+.

---

## 🏛️ ARCHITECTURE & CODE QUALITY

### 15. vladikk/modularity
**What it does:** Claude Code plugin for software architecture quality. Two skills: `/modularity:review` analyzes an existing codebase for coupling imbalances (what's leaking across component boundaries, where cascading changes are waiting); `/modularity:high-level-design` designs modular architectures from functional requirements, producing module docs with integration contracts, test specs, and full coupling assessment. Grounded in the **Balanced Coupling** model: evaluates coupling across Integration Strength × Distance × Volatility.

**Pros:** Operates at architectural level (not just code-level); every recommendation traces to a concrete coupling dimension; produces HTML + Markdown review docs; forces approval at each step.  
**Cons:** Requires Claude Opus 4.5+ for nuanced reasoning; CC BY-NC-SA license (non-commercial only free); most valuable on large codebases with complex boundaries.

**Install:**
```bash
/plugin marketplace add vladikk/modularity
/plugin install modularity@vladikk-modularity
# or clone directly:
git clone https://github.com/vladikk/modularity.git
claude --plugin-dir ./modularity
```
**Links:** [GitHub](https://github.com/vladikk/modularity) · [coupling.dev](https://coupling.dev)

---

## 🎨 DESIGN & UI/UX

### 16. UI/UX Pro Max
**What it does:** Design intelligence skill for building professional UI/UX across platforms. Includes a searchable design database: 50+ UI styles, 97 color palettes, 57 font pairings, 99 UX guidelines, 25 chart types across 9 tech stacks (React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind, shadcn/ui). v2.0 flagship: **Design System Generator** — analyzes project requirements and generates a complete tailored design system in seconds.

**Pros:** Eliminates generic AI aesthetics; auto-activates on UI/UX requests; cross-platform (Claude Code, Cursor, Windsurf, Antigravity); massive curated design reference.  
**Cons:** Large install size due to reference database; opinionated style choices may conflict with existing brand.

**Install:**
```bash
uipro init --ai claude --global   # installs to ~/.claude/skills/
# or via plugin:
/plugin install nextlevelbuilder/ui-ux-pro-max-skill
```
**Links:** [GitHub](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) · [Site](https://ui-ux-pro-max-skill.nextlevelbuilder.io)

---

## 📓 KNOWLEDGE BASE & SECOND BRAIN

### 17. kepano/obsidian-skills + json-canvas
**What it does:** Official skills from Obsidian's creator (Steph Lechanski) teaching agents to interact with Obsidian vaults. Skills cover: Markdown notes, Bases (structured data), **JSON Canvas** (programmatic `.canvas` file creation for visual flowcharts, architecture diagrams, knowledge graphs), CLI operations, full-text search, tags, links, and plugin management. The `json-canvas` sub-skill alone enables generating entire visual architecture diagrams from a natural language description.

**Pros:** Official, well-maintained; works with any SKILL.md-compatible agent; vault files are plain text so Claude can read/write directly; great for knowledge workers using Obsidian as a second brain.  
**Cons:** Requires Obsidian + CLI setup; vault context can grow large; generated content should stay in `~/.claude/` not pollute the vault.

**Install:**
```bash
/plugin marketplace add kepano/obsidian-skills
/plugin install obsidian-skills
# or add skills/ folder to /.claude in your vault root
```
**Links:** [GitHub](https://github.com/kepano/obsidian-skills) · [axton visual skills](https://github.com/axtonliu/axton-obsidian-visual-skills) · [Claudian (embed Claude in vault)](https://github.com/YishenTu/claudian)

---

## 🔬 LLM OBSERVABILITY & EVALUATION

### 18. LangSmith Observability Skill
**What it does:** Traces every Claude Code session into LangSmith — captures LLM interactions (model, tokens, cache), all tool executions (Bash, Read, Edit, Grep), subagent runs, compaction events. Groups turns by `thread_id` for session-level visibility. Supports custom metadata tagging (PR URL, author, environment). Enables comparing model/prompt changes over time.

**Pros:** Production-grade LLM observability; essential for teams optimizing prompt quality or auditing agent behavior; integrates with LangChain ecosystem; enables A/B testing prompts with real metrics.  
**Cons:** Requires LangSmith account; trace data sent to LangSmith cloud; adds slight latency overhead.

**Install:**
```bash
# Set env vars:
export LANGSMITH_API_KEY=your_key
export TRACE_TO_LANGSMITH=true
# Install plugin:
/plugin install langsmith-observability
```
**Links:** [LangSmith Docs](https://docs.langchain.com/langsmith/trace-claude-code) · [agent-observability](https://github.com/nexus-labs-automation/agent-observability) · [davila7 skill](https://playbooks.com/skills/davila7/claude-code-templates/observability-langsmith)

---

### 19. DeepEval — LLM Testing Framework
**What it does:** Pytest-style evaluation framework for LLM outputs. Claude Code skill that writes and runs eval suites measuring: answer relevancy, hallucination rate, faithfulness, task completion, G-Eval scores, RAG quality. Works like unit tests but for AI behavior — run in CI to catch regressions when prompts or models change.

**Pros:** Open-source; runs locally (no cloud required for basic metrics); integrates with pytest; supports RAGAS, Braintrust, Phoenix too; essential for teams shipping AI features.  
**Cons:** Requires Python setup; LLM-as-judge metrics add API cost; meaningful evals require good test dataset curation.

**Install:**
```bash
pip install deepeval
# Claude Code skill:
/plugin install deepeval-llm-testing
```
**Links:** [GitHub](https://github.com/confident-ai/deepeval) · [Claude Code Skill](https://mcpmarket.com/tools/skills/deepeval-llm-testing)

---

## 🤖 AUTONOMOUS & SELF-IMPROVING AGENTS

### 20. Self-Improving Agent Skill
**What it does:** Establishes a systematic loop for AI agents to learn from experience. Creates a dedicated `.self-improvement/` directory where Claude documents: unexpected failures, user-provided corrections, missing capabilities, and recurring solutions — then promotes proven patterns to enforced rules and extracts solutions into reusable skills. Inspired by Karpathy's autoresearch methodology.

**Pros:** Compounds value over time — agent gets better the longer it runs; zero external dependencies; works alongside claude-mem.  
**Cons:** Requires consistent feedback discipline from the user; early iterations produce low-signal; need to periodically review and curate what gets promoted.

**Install:**
```bash
/plugin marketplace add alirezarezvani/claude-skills
/plugin install self-improving-agent
# or: github.com/miles990/self-evolving-agent
```
**Links:** [claude-skills repo](https://github.com/alirezarezvani/claude-skills/tree/main/engineering-team/self-improving-agent) · [self-evolving-agent](https://github.com/miles990/self-evolving-agent)

---

### 21. ARIS — Auto-Research-In-Sleep
**What it does:** Autonomous ML research agent that runs overnight. Skills: cross-model review loops, idea discovery, experiment automation, paper scoring, LaTeX rewriting. Zero dependencies — pure Markdown SKILL.md files. Pairs Claude Code with GPU-optional compute (Modal serverless at ~$30/month free tier). Codex fallback: when experiments fail, `/codex:rescue` auto-invokes GPT to diagnose before Claude retries.

**Pros:** Radically lightweight — no frameworks, no lock-in; platform-agnostic (works with Codex, Cursor, OpenClaw); wakes up to scored, improved experiments; Modal integration means no local GPU needed.  
**Cons:** ML-research focused (niche); requires structured experiment scripts to iterate on; overnight runs need robust error handling.

**Install:**
```bash
git clone https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
# Add skills/ to your /.claude folder
```
**Links:** [ARIS GitHub](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) · [autoresearch](https://github.com/uditgoenka/autoresearch)

---

## 🧪 TESTING & BROWSER AUTOMATION

### 22. Playwright Skill (lackeyjb + willmarple)
**What it does:** Claude autonomously writes and executes Playwright automation for browser testing and validation. Describe what you want tested in natural language → Claude generates, runs, and returns results with screenshots and console output. v2026 enhancement: three built-in specialized agents (planner, generator, healer) that explore apps autonomously and self-fix failing tests.

**Pros:** No boilerplate — Claude writes all test code; handles complex multi-step flows; healer agent fixes flaky tests automatically; supports both unit and E2E flows.  
**Cons:** Requires Playwright + Node setup; browser tests are inherently slower; healer agent can mask underlying UI bugs.

**Install:**
```bash
/plugin install lackeyjb/playwright-skill
# or official Anthropic plugin:
# claude.com/plugins/playwright
```
**Links:** [lackeyjb/playwright-skill](https://github.com/lackeyjb/playwright-skill) · [willmarple/playwright-skill](https://github.com/willmarple/playwright-skill) · [Playwright MCP guide](https://testomat.io/blog/playwright-mcp-claude-code/)

---

## 🔗 INTEGRATIONS & TOOLING

---

### 23. skill-creator (Anthropic official)
**What it does:** Meta-skill for creating, improving, and benchmarking other skills. Generates SKILL.md files from scratch, optimizes descriptions for trigger accuracy, runs evals to validate skills activate correctly (trigger precision vs output quality), and measures performance with variance analysis. Includes a Python eval system for automated skill testing in CI.

**Pros:** Closes the loop on skill quality — not just "does it produce good output" but "does it activate when it should"; official Anthropic support; essential for teams building custom skills at scale.  
**Cons:** Requires existing skills to improve; eval design takes thoughtful test case creation.

**Use:**
```bash
/skill-creator    # in Claude Code or Cowork
```
**Links:** Built-in to Claude Code + Cowork · [Skill evals guide](https://www.mager.co/blog/2026-03-08-claude-code-eval-loop/)

---

## 💡 Best Practices Summary

- **Context is king** — a skill tuned to your project's specific patterns beats a generic one every time. Customize `CLAUDE.md` per repo.
- **Decompose before delegating** — multi-agent work only scales if tasks are well-scoped upfront. Use RIPER or feature-dev's discovery phase.
- **Progressive disclosure** — load agents/skills on-demand rather than all upfront to keep context windows efficient.
- **Agentic workflow pattern** — all mature pipelines converge on: Research → Plan → Execute → Review → Ship. Enforce this, don't skip phases.
- **Use git worktrees** — superpowers and claude-squad both leverage git worktrees for safe parallel agent work without branch conflicts.
