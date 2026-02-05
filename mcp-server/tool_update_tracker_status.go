package main

import (
	"context"
	"fmt"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func registerUpdateTrackerStatus(s *server.MCPServer) {
	trackerStatusTool := mcp.NewTool("update_tracker_status",
		mcp.WithDescription("Update tracker frontmatter status (default: Resume Written)"),
	)
	trackerStatusTool.InputSchema = mcp.ToolInputSchema{
		Type: "object",
		Properties: map[string]interface{}{
			"tracker_path": map[string]interface{}{"type": "string", "description": "Path to tracker markdown file"},
			"status":       map[string]interface{}{"type": "string", "description": "New status value (default: Resume Written)"},
			"dry_run":      map[string]interface{}{"type": "boolean", "description": "If true, do not write file"},
		},
		Required: []string{"tracker_path"},
	}
	s.AddTool(trackerStatusTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, ok := request.Params.Arguments.(map[string]interface{})
		if !ok {
			return mcp.NewToolResultError("invalid arguments format"), nil
		}
		trackerPath, _ := args["tracker_path"].(string)
		if strings.TrimSpace(trackerPath) == "" {
			return mcp.NewToolResultError("tracker_path is required"), nil
		}
		status := "Resume Written"
		if v, ok := args["status"].(string); ok && strings.TrimSpace(v) != "" {
			status = strings.TrimSpace(v)
		}
		dryRun := false
		if v, ok := args["dry_run"].(bool); ok {
			dryRun = v
		}

		updatedPath, err := updateTrackerStatus(trackerPath, status, dryRun)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("update_tracker_status failed: %v", err)), nil
		}
		if dryRun {
			return mcp.NewToolResultText(fmt.Sprintf("Dry run: would update status to %q in %s", status, updatedPath)), nil
		}
		return mcp.NewToolResultText(fmt.Sprintf("Updated status to %q in %s", status, updatedPath)), nil
	})
}
