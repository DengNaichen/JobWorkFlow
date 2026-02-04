---
name: job-scout-patrol
description: Periodically search for relevant AI and Backend engineering jobs in target locations, extract details, and initialize trackers in Obsidian. Use for proactive job scouting and automated application pipeline entry.
metadata:
  {
    "openclaw": { "emoji": "🕵️" }
  }
---

# Job Scout Patrol

This skill formalizes the process of autonomously finding new job opportunities and handing them off to the initialization pipeline.

## Objectives
- Automate the discovery of high-quality AI/Backend roles.
- Ensure all relevant data (Company, Position, URL, JD) is captured.
- Seamlessly trigger the `kaka-job-scout` MCP tool for Obsidian tracking.

## Workflow

### 1. Scouting Phase
- **Target Keywords**: "AI Engineer", "Machine Learning Engineer", "Backend Engineer (Python/Go)", "HPC Researcher".
- **Target Location**: "Ontario, Canada" or "Remote".
- **Action**: 
    - **Step 0**: Use the clawdbot browser relay to verify active connections.
    - Primarily use the clawdbot browser tool via Chrome Extension Relay (profile: "chrome").
    - Navigate to the designated LinkedIn search URLs (Machine Learning & Backend).
    - If the browser is unreachable or the tab is not attached, proceed to the **Human Intervention Protocol**.
- **Frequency**: Managed by clawdbot scheduler (e.g., every 2 hours during 09:00 - 18:00). Document the actual schedule in clawdbot, not here.

### 2. Human Intervention Protocol
- If the browser relay reports "no tab is connected" or "tab not found":
    - **IMMEDIATELY** notify the configured contact via the configured channel.
    - **Message Template**: "Browser relay is detached. Please open the search page and click 'Attach' so scouting can continue."
    - Pause the current patrol until the connection is restored.

### 3. Filtering & Selection
- Match findings against the user's profile in `data/templates/full_resume.md`.
- Prioritize roles involving:
    - **FastAPI / Python**
    - **CUDA / High-Performance Computing**
    - **RAG / Knowledge Graphs**
- Exclude: "Junior" or purely "Frontend" roles unless specifically asked.

### 4. Handoff Phase
- Once a candidate job is identified, extract:
    - `company_name`
    - `job_title`
    - `job_url`
    - `full_description` (via clawdbot browser snapshot or web fetch)
- **Execute**: Call the MCP tool via clawdbot:
  ```bash
  clawdbot mcp call kaka-job-scout.initialize_job company="..." position="..." url="..." jd="..."
  ```

### 5. Reporting
- Notify the user on Telegram with a brief summary of the new find.
- Mention that the Obsidian tracker has been created.

## Guidelines
- **Live Vision Only**: Before reporting any findings, **ALWAYS** verify the required tabs are open and accessible. Never report from memory or cached data if a tab has been closed.
- **Avoid Duplicates**: Before initializing, run the local checker:
  ```bash
  ./scripts/check_job.sh "<job_url>" "<Company Name>" "<Position Name>"
  ```
  Only proceed when it returns `NEW: No matching job found.`
- **Quality over Quantity**: Aim for 1-3 high-quality matches per patrol rather than dumping dozens of low-relevance links.
