# Pipeline 1: Opportunity Finder

## Purpose

Discover business opportunities by analyzing what agents complain about, struggle with, or wish existed.

## Pipeline Steps

### Step 1: Problem Extraction

**Input:** Recent Moltbook posts (from Supabase)

**Process:**
- Scan for signal phrases: "I wish...", "why is there no...", "struggling with...", "anyone know how to...", "frustrated that...", "would pay for..."
- Extract the underlying problem
- Categorize: tools, infrastructure, communication, payments, security, data, other

**Output:** List of raw problems with source posts

### Step 2: Problem Clustering

**Input:** Extracted problems

**Process:**
- Group similar problems using semantic similarity
- Merge near-duplicates
- Calculate frequency (how many unique mentions)
- Calculate recency (when was it last mentioned)

**Output:** Problem clusters with scores

### Step 3: Market Validation

**Input:** Top problem clusters

**Process:**
- Check if agents indicated willingness to pay
- Look for existing solutions mentioned (and why they're inadequate)
- Estimate market size based on engagement/frequency
- Score validation strength

**Output:** Validated problems with market signals

### Step 4: Opportunity Generation

**Input:** Validated problem clusters

**Process:**
- Generate 1-2 business model ideas per cluster
- Consider: pricing model, distribution channel, competitive moat
- Write mini pitch brief

**Output:** Opportunity briefs

## Categories

Use these categories for problem classification:

| Category | Examples |
|----------|----------|
| `tools` | IDEs, debugging, testing frameworks |
| `infrastructure` | Hosting, deployment, scaling |
| `communication` | Agent-to-agent messaging, protocols |
| `payments` | Invoicing, wallets, settlements |
| `security` | Authentication, encryption, trust |
| `data` | Storage, retrieval, sharing |
| `coordination` | Task management, scheduling |
| `identity` | Verification, reputation |
| `other` | Anything else |

## Scoring

**Opportunity Score Formula:**
```
score = (frequency_weight * 0.3) + 
        (recency_weight * 0.2) + 
        (willingness_to_pay * 0.3) + 
        (solution_gap * 0.2)
```

Where:
- `frequency_weight`: log(mention_count) / log(max_mentions)
- `recency_weight`: 1 if <7 days, 0.7 if <30 days, 0.3 otherwise
- `willingness_to_pay`: 1 if explicit, 0.5 if implied, 0 if none
- `solution_gap`: 1 if no solutions, 0.5 if inadequate solutions, 0 if solved
