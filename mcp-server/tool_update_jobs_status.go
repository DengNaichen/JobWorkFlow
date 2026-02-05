package main

import (
	"context"
	"fmt"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func registerUpdateJobsStatus(s *server.MCPServer) {
	statusTool := mcp.NewTool("update_jobs_status",
		mcp.WithDescription("Update job status in SQLite (defaults: new -> review)"),
	)
	statusTool.InputSchema = mcp.ToolInputSchema{
		Type: "object",
		Properties: map[string]interface{}{
			"from_status": map[string]interface{}{"type": "string", "description": "Current status to match (default: new)"},
			"to_status":   map[string]interface{}{"type": "string", "description": "New status to set (default: review)"},
			"limit":       map[string]interface{}{"type": "integer", "description": "Max rows to update (optional)"},
			"dry_run":     map[string]interface{}{"type": "boolean", "description": "If true, do not update DB"},
			"db_path":     map[string]interface{}{"type": "string", "description": "Override DB path (optional)"},
		},
	}
	s.AddTool(statusTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, ok := request.Params.Arguments.(map[string]interface{})
		if !ok {
			return mcp.NewToolResultError("invalid arguments format"), nil
		}

		fromStatus := "new"
		if v, ok := args["from_status"].(string); ok && strings.TrimSpace(v) != "" {
			fromStatus = strings.TrimSpace(v)
		}
		toStatus := "reviewed"
		if v, ok := args["to_status"].(string); ok && strings.TrimSpace(v) != "" {
			toStatus = strings.TrimSpace(v)
		}
		limit := 0
		if v, ok := args["limit"].(float64); ok && v > 0 {
			limit = int(v)
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

		count, err := updateJobsStatus(db, fromStatus, toStatus, limit, dryRun)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to update jobs: %v", err)), nil
		}
		return mcp.NewToolResultText(fmt.Sprintf("Updated %d jobs (%s -> %s, dry_run=%v).", count, fromStatus, toStatus, dryRun)), nil
	})
}
