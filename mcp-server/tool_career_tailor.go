package main

import (
	"context"
	"fmt"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func registerCareerTailor(s *server.MCPServer) {
	careerTool := mcp.NewTool("career_tailor",
		mcp.WithDescription("Create per-job resume workspace from a tracker and optionally compile LaTeX"),
	)
	careerTool.InputSchema = mcp.ToolInputSchema{
		Type: "object",
		Properties: map[string]interface{}{
			"tracker_path": map[string]interface{}{"type": "string", "description": "Path to tracker markdown file"},
			"compile":      map[string]interface{}{"type": "boolean", "description": "Compile resume.tex (default: false)"},
			"force":        map[string]interface{}{"type": "boolean", "description": "Overwrite resume.tex if it exists"},
			"pdflatex":     map[string]interface{}{"type": "string", "description": "Override pdflatex path (optional)"},
		},
		Required: []string{"tracker_path"},
	}
	s.AddTool(careerTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, ok := request.Params.Arguments.(map[string]interface{})
		if !ok {
			return mcp.NewToolResultError("invalid arguments format"), nil
		}
		trackerPath, _ := args["tracker_path"].(string)
		if strings.TrimSpace(trackerPath) == "" {
			return mcp.NewToolResultError("tracker_path is required"), nil
		}

		compile := false
		if v, ok := args["compile"].(bool); ok {
			compile = v
		}
		force := false
		if v, ok := args["force"].(bool); ok {
			force = v
		}
		pdflatex := ""
		if v, ok := args["pdflatex"].(string); ok && strings.TrimSpace(v) != "" {
			pdflatex = strings.TrimSpace(v)
		}

		result, err := runCareerTailor(trackerPath, compile, force, pdflatex)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("career_tailor failed: %v", err)), nil
		}
		return mcp.NewToolResultText(result), nil
	})
}
