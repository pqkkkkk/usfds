@README.md

> Read this `README.md` to understand overall context and purpose of the project.

---

## 0. Before You Start: Document Map

Identify the domain and read the corresponding documentation before implementing any request. Never edit code from memory or assumption.

| Request touches... | Read first |
| --- | --- |
| Architecture of codebase | `docs/architecture.md` |
| Design system | `docs/design-system.md` |
| Use case specification | all sub items of Notion page [Đặc tả use case hệ thống](https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)

If a request does not clearly fall under any specific documentation row, ask me for document link in Notion or other relevant sources first.

---

# Coding Guidelines

Behavioral guidelines to ensure high-quality, maintainable, and minimalistic code. Bias toward caution over speed.

## 1. Development Workflow & Planning

* **Plan First:** Draft multi-step plans with verifiable success criteria in `.plan/<task_name>.md` prior to implementation. Loop until verified.
* **Think Before Coding:** State assumptions explicitly. Present multiple interpretations if they exist.
* **Proactive Minimal Payload:** Ship the minimal working version first for complex requests and question the complexity. If the user insists, build it without debate. Explicitly state omitted elements.
* **Clarify & Push Back:** Stop and ask if a request is ambiguous. Suggest simpler approaches.
* **Goal-Driven Execution:** Transform tasks into concrete, verifiable goals.

### 1.1 The Execution Ladder

Stop at the first true statement:

1. Does this need to be built at all? No? Skip it.
2. Does it already exist in this codebase? Reuse the helper, util, or pattern.
3. Does the standard library do it? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Do it.
7. Only then write the minimum code that works.

## 2. Simplicity & Minimalism

* **Minimum Viable Code:** Write only what is required to solve the problem. Default to the edge-case-correct option for ties.
* **No Speculation:** Zero unrequested features, single-use abstractions, or speculative flexibility.
* **Boundary Definition (When not to be lazy):** Never cut validation, error handling, security, accessibility, or data-loss protection. Never skip understanding; blind edits are prohibited.
* **Clean Logic:** Keep core logic linear and push implementation details to the edges. Boring beats clever.

## 3. Surgical & Iterative Changes

* **Iterate:** Implement step-by-step. Ban sweeping modifications. Touch the fewest files possible.
* **Minimal Footprint:** Every modified line must trace directly to the task. The shortest working diff wins.
* **Do not Fix Unbroken Things:** Never refactor adjacent code or reformat unrelated lines. Tag pre-existing issues with `TODO:`.
* **Preserve Code (Deprecate):** Never delete unused code outright. Comment it out and tag as `DEPRECATED`.
* **Debug:** Fix root causes, not symptoms. Grep every caller end-to-end before editing. Fix the routing bottleneck once.
* **Testing:** Non-trivial logic requires exactly one runnable check (a tripwire). No bloated suites. Trivial one-liners require zero tests.

## 4. Formatting & Naming Conventions

* **Strict Formatting:**
* **Indentation:** Tabs only.
* **Semicolons:** Mandatory.
* **Braces:** One True Brace Style (1TBS).

* **Naming Conventions:**
* `camelCase`: Variables and functions. Make them instantly readable for `usfds-web`
* `snake_case`: Variables and functions. Make them instantly readable for `usfds-core` and `usfds-infra`
* `UPPER_SNAKE_CASE`: Constants and globals.
* `_prefix`: Internal or private functions.

## 6. HTML & CSS Design Philosophy
Follow current design system guidelines for consistency in UI components, typography, spacing, and color schemes in `docs/design-system.md`.

---

## Documentation Location

All documentation are maintained in the Notion page [Task](https://app.notion.com/p/325b99c6a9508074ba72e26e509260bf?v=325b99c6a9508078acdc000cad8d9232). For any additional context or clarification, ask me a Notion link for rapid searching. Documentation in `docs/` serves as a local reference and should be kept in sync with Notion.

**Agent Modification Policy:** Request user approval before editing any file in `docs/`. Append a `[YY-MM-DD]` comment to all approved edits.

---

# CRITICAL IMPORTANT: MANDATORY AGENT DIRECTIVE

Before modifying codebase logic, databases, routes, or assets:

1. You MUST read this entire `/README.md` document first.
2. Ensure no custom UI for API keys is generated. Rely strictly on standard `.env.example` configurations.
3. Do not delete or rename this file. Maintain all architectural transparency to ensure subsequent agents scale the project with absolute consistency.
4. After receiving a task, always plan first and ask clarifying questions. Upon approval, draft the plan and to-do list into `TODO.md`, and prepare unit tests in `tests/`. Update `TODO.md` synchronously as items are finished.
5. After completing `TODO.md`, request final approval. Once verified, dump the completed items into a new section in `CHANGELOG.md` and wipe `TODO.md` clean.
6. **Communication Protocol:** You MUST adopt this exact concise, decisive, and fluff-free tone in all summaries, questions, and chat interactions with the user. Stop guessing; state the facts.
7. If request don't have corresponding documentation, always ask me for relevant Notion link before proceeding.
8. If cannot connect to Notion, ask me download necessary documentation into `docs`.

---
