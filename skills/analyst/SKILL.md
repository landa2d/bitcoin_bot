# Analyst Agent Skills

## Task Processing

You receive tasks from the `agent_tasks` Supabase table.
Poll for tasks where `assigned_to = 'analyst'` and `status = 'pending'`.
Process in priority order (1 = highest).

## Task Types

### extract_problems
- Input: `{hours_back: 48, batch_size: 100}`
- Read unprocessed posts from `moltbook_posts`
- Extract problems using the analysis prompt
- Store in `problems` table, mark posts as processed

### cluster_problems
- Input: `{min_problems: 3}`
- Read unclustered problems from `problems` table
- Group by semantic similarity using the clustering prompt
- Store clusters in `problem_clusters` table

### generate_opportunities
- Input: `{min_frequency: 1, limit: 5}`
- Read top problem clusters
- Generate opportunity briefs
- Store in `opportunities` table
- Save markdown briefs to `workspace/agentpulse/opportunities/`

### review_opportunity
- Input: `{opportunity_id: "uuid"}`
- Re-evaluate an existing opportunity with fresh data
- Update confidence score and reasoning

## Output Protocol

For every completed task:
1. Update `agent_tasks` row: status='completed', output_data={...}
2. Write detailed results to Supabase tables
3. Write summary to `workspace/agentpulse/queue/responses/` (for Gato file-based reads)
