package main

import (
	"context"
	"fmt"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func registerInitializeJobsBatch(s *server.MCPServer) {
	batchTool := mcp.NewTool("initialize_jobs_batch",
		mcp.WithDescription("Batch initialize trackers from SQLite capture DB (status=new by default)"),
	)

	batchTool.InputSchema = mcp.ToolInputSchema{
		Type: "object",
		Properties: map[string]interface{}{
			"status":      map[string]interface{}{"type": "string", "description": "Filter jobs by status (default: new)"},
			"limit":       map[string]interface{}{"type": "integer", "description": "Max jobs to process (default: 50)"},
			"mark_status": map[string]interface{}{"type": "string", "description": "Status to set after initialization (default: tracked)"},
			"dry_run":     map[string]interface{}{"type": "boolean", "description": "If true, do not create files or update DB"},
			"db_path":     map[string]interface{}{"type": "string", "description": "Override DB path (optional)"},
		},
	}

	s.AddTool(batchTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, ok := request.Params.Arguments.(map[string]interface{})
		if !ok {
			return mcp.NewToolResultError("invalid arguments format"), nil
		}

		status := "new"
		if v, ok := args["status"].(string); ok && strings.TrimSpace(v) != "" {
			status = strings.TrimSpace(v)
		}
		limit := 50
		if v, ok := args["limit"].(float64); ok && v > 0 {
			limit = int(v)
		}
		markStatus := "tracked"
		if v, ok := args["mark_status"].(string); ok && strings.TrimSpace(v) != "" {
			markStatus = strings.TrimSpace(v)
		}
		dryRun := false
		if v, ok := args["dry_run"].(bool); ok {
			dryRun = v
		}
		dbPath := ""
		if v, ok := args["db_path"].(string); ok && strings.TrimSpace(v) != "" {
			dbPath = strings.TrimSpace(v)
		}

		db, err := openCaptureDB(dbPath)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to open capture DB: %v", err)), nil
		}
		defer db.Close()

		jobs, err := fetchJobsByStatus(db, status, limit)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to query jobs: %v", err)), nil
		}
		if len(jobs) == 0 {
			return mcp.NewToolResultText("No jobs found for batch initialization."), nil
		}

		var created []string
		var failed []string
		for _, job := range jobs {
			if dryRun {
				created = append(created, job.URL)
				continue
			}
			if _, err := runInitializationWithJob(job.Company, job.Title, job.URL, job.Description, job.JobID); err != nil {
				failed = append(failed, fmt.Sprintf("%s (%v)", job.URL, err))
				continue
			}
			if err := updateJobStatus(db, job.URL, markStatus); err != nil {
				failed = append(failed, fmt.Sprintf("%s (status update failed: %v)", job.URL, err))
				continue
			}
			created = append(created, job.URL)
		}

		var summary strings.Builder
		summary.WriteString(fmt.Sprintf("Processed %d jobs (status=%s, dry_run=%v).\n", len(jobs), status, dryRun))
		if len(created) > 0 {
			summary.WriteString(fmt.Sprintf("Initialized: %d\n", len(created)))
		}
		if len(failed) > 0 {
			summary.WriteString(fmt.Sprintf("Failed: %d\n", len(failed)))
		}
		return mcp.NewToolResultText(summary.String()), nil
	})
}
