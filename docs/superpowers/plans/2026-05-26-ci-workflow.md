# CI Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Actions CI that runs the pytest suite headless on ubuntu + windows × Python 3.11/3.13, and a CI status badge in the README.

**Architecture:** A single workflow file under `.github/workflows/`, plus one badge line in `README.md`. Purely additive — no application code changes. CI is configuration, so "verification" is YAML parse locally then a green Actions run after push (not pytest).

**Tech Stack:** GitHub Actions, `actions/checkout@v4`, `actions/setup-python@v5`, pip editable install with `dev`/`gui` extras, PySide6 headless (`QT_QPA_PLATFORM=offscreen`).

---

### Task 1: CI workflow file

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    name: tests (${{ matrix.os }}, py${{ matrix.python-version }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ["3.11", "3.13"]
    env:
      QT_QPA_PLATFORM: offscreen
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install Qt headless system libraries (Linux)
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libdbus-1-3

      - name: Install package with dev and gui extras
        run: |
          python -m pip install --upgrade pip
          pip install -e .[dev,gui]

      - name: Run tests
        run: python -m pytest -q
```

- [ ] **Step 2: Verify the YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8')); print('ci.yml OK')"`
Expected: `ci.yml OK` (no exception).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow (pytest, ubuntu+windows, py3.11/3.13)"
```

---

### Task 2: README CI badge

**Files:**
- Modify: `README.md:1` (insert a badge line just below the `# IntraMap` title)

- [ ] **Step 1: Insert the badge below the title**

Change the top of `README.md` from:

```markdown
# IntraMap

Scan a local IPv4 network, annotate the inventory with custom names and physical locations (floor / room / rack), then render the result as PlantUML and Graphviz diagrams. Optionally declare uplink wiring (switch / patch panel / PoE) to draw the cabling on the diagram.
```

to:

```markdown
# IntraMap

[![CI](https://github.com/Foxugly/IntraMap/actions/workflows/ci.yml/badge.svg)](https://github.com/Foxugly/IntraMap/actions/workflows/ci.yml)

Scan a local IPv4 network, annotate the inventory with custom names and physical locations (floor / room / rack), then render the result as PlantUML and Graphviz diagrams. Optionally declare uplink wiring (switch / patch panel / PoE) to draw the cabling on the diagram.
```

- [ ] **Step 2: Verify the badge line is present**

Run: `grep -F "actions/workflows/ci.yml/badge.svg" README.md`
Expected: the badge line is printed (one match).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add CI status badge to README"
```

---

### Task 3: Push and verify the CI run

**Files:** none (verification only).

- [ ] **Step 1: Confirm the local suite still passes**

Run: `python -m pytest -q`
Expected: `218 passed`.

- [ ] **Step 2: Push to main**

```bash
git push origin main
```

- [ ] **Step 3: Observe the Actions run**

Run: `gh run list --workflow=ci.yml --limit 1` (and optionally `gh run watch`)
Expected: a run appears for the latest commit; all 4 jobs (ubuntu/windows × 3.11/3.13) end green. If a Linux job fails on a missing Qt `.so`, add the named library to the `apt-get install` line in `ci.yml` and re-push.

- [ ] **Step 4: Confirm the badge renders**

Open the repo README on GitHub (or `gh repo view --web`) and confirm the CI badge shows and links to the workflow.

---

## Self-Review

**Spec coverage:**
- Workflow file (triggers, 4-job matrix, Linux Qt libs, install extras, pytest offscreen) → Task 1. ✓
- README badge below title → Task 2. ✓
- Success criteria (green Actions run, badge renders, no regression) → Task 3. ✓

**Placeholder scan:** No TBD/TODO; the workflow YAML and README diff are shown in full. ✓

**Type/name consistency:** Workflow filename `ci.yml` is consistent across the workflow path, the badge URL, and the `gh run list --workflow=ci.yml` command. ✓
