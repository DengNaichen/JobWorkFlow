package main

import (
	"context"
	"fmt"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func registerAutoFilterJobs(s *server.MCPServer) {
	filterTool := mcp.NewTool("auto_filter_jobs",
		mcp.WithDescription("Auto-filter jobs (AI-focused) and update DB status; optionally write Obsidian trackers for shortlist"),
	)
	filterTool.InputSchema = mcp.ToolInputSchema{
		Type: "object",
		Properties: map[string]interface{}{
			"source_status":      map[string]interface{}{"type": "string", "description": "Only process jobs with this status (default: new)"},
			"limit":              map[string]interface{}{"type": "integer", "description": "Max jobs to process (default: 50)"},
			"dry_run":            map[string]interface{}{"type": "boolean", "description": "If true, do not update DB or create trackers"},
			"write_trackers":     map[string]interface{}{"type": "boolean", "description": "If true, write Obsidian trackers for shortlist (default: true)"},
			"shortlist_status":   map[string]interface{}{"type": "string", "description": "Status for shortlist (default: shortlist)"},
			"reviewed_status":    map[string]interface{}{"type": "string", "description": "Status for reviewed (default: reviewed)"},
			"reject_status":      map[string]interface{}{"type": "string", "description": "Status for rejected (default: reject)"},
			"db_path":            map[string]interface{}{"type": "string", "description": "Override DB path (optional)"},
			"require_location":   map[string]interface{}{"type": "boolean", "description": "If true, downgrade non-Ontario/remote to reviewed (default: false)"},
			"require_production": map[string]interface{}{"type": "boolean", "description": "If true, require production/deployment signals (default: true)"},
		},
	}
	s.AddTool(filterTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, ok := request.Params.Arguments.(map[string]interface{})
		if !ok {
			return mcp.NewToolResultError("invalid arguments format"), nil
		}

		sourceStatus := "new"
		if v, ok := args["source_status"].(string); ok && strings.TrimSpace(v) != "" {
			sourceStatus = strings.TrimSpace(v)
		}
		limit := 50
		if v, ok := args["limit"].(float64); ok && v > 0 {
			limit = int(v)
		}
		dryRun := false
		if v, ok := args["dry_run"].(bool); ok {
			dryRun = v
		}
		writeTrackers := true
		if v, ok := args["write_trackers"].(bool); ok {
			writeTrackers = v
		}
		shortlistStatus := "shortlist"
		if v, ok := args["shortlist_status"].(string); ok && strings.TrimSpace(v) != "" {
			shortlistStatus = strings.TrimSpace(v)
		}
		reviewedStatus := "reviewed"
		if v, ok := args["reviewed_status"].(string); ok && strings.TrimSpace(v) != "" {
			reviewedStatus = strings.TrimSpace(v)
		}
		rejectStatus := "reject"
		if v, ok := args["reject_status"].(string); ok && strings.TrimSpace(v) != "" {
			rejectStatus = strings.TrimSpace(v)
		}
		dbPath := ""
		if v, ok := args["db_path"].(string); ok && strings.TrimSpace(v) != "" {
			dbPath = strings.TrimSpace(v)
		}
		requireLocation := false
		if v, ok := args["require_location"].(bool); ok {
			requireLocation = v
		}
		requireProduction := true
		if v, ok := args["require_production"].(bool); ok {
			requireProduction = v
		}

		db, err := openCaptureDB(dbPath)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to open capture DB: %v", err)), nil
		}
		defer db.Close()

		jobs, err := fetchJobsByStatus(db, sourceStatus, limit)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to query jobs: %v", err)), nil
		}
		if len(jobs) == 0 {
			return mcp.NewToolResultText("No jobs found to filter."), nil
		}

		var shortlisted int
		var reviewed int
		var rejected int
		var failed int

		for _, job := range jobs {
			decision := classifyJob(job, requireLocation, requireProduction)
			if dryRun {
				switch decision {
				case "shortlist":
					shortlisted++
				case "reviewed":
					reviewed++
				default:
					rejected++
				}
				continue
			}

			switch decision {
			case "shortlist":
				if writeTrackers {
					if _, err := runInitializationWithJob(job.Company, job.Title, job.URL, job.Description, job.JobID); err != nil {
						failed++
						continue
					}
				}
				if err := updateJobStatus(db, job.URL, shortlistStatus); err != nil {
					failed++
					continue
				}
				shortlisted++
			case "reviewed":
				if err := updateJobStatus(db, job.URL, reviewedStatus); err != nil {
					failed++
					continue
				}
				reviewed++
			default:
				if err := updateJobStatus(db, job.URL, rejectStatus); err != nil {
					failed++
					continue
				}
				rejected++
			}
		}

		var summary strings.Builder
		summary.WriteString(fmt.Sprintf("Filtered %d jobs (status=%s, dry_run=%v).\n", len(jobs), sourceStatus, dryRun))
		summary.WriteString(fmt.Sprintf("Shortlist: %d | Reviewed: %d | Reject: %d\n", shortlisted, reviewed, rejected))
		if failed > 0 {
			summary.WriteString(fmt.Sprintf("Failed: %d\n", failed))
		}
		return mcp.NewToolResultText(summary.String()), nil
	})
}
