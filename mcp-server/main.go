package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func main() {
	s := server.NewMCPServer("kaka-job-scout", "1.0.0")

	tool := mcp.NewTool("initialize_job",
		mcp.WithDescription("Initialize a new job application by creating an Obsidian tracker and folder structure"),
	)
	
	tool.InputSchema = mcp.ToolInputSchema{
		Type: "object",
		Properties: map[string]interface{}{
			"company":  map[string]interface{}{"type": "string", "description": "The name of the company"},
			"position": map[string]interface{}{"type": "string", "description": "The job title/position"},
			"url":      map[string]interface{}{"type": "string", "description": "The job posting URL"},
			"jd":       map[string]interface{}{"type": "string", "description": "The full job description content"},
		},
		Required: []string{"company", "position", "url", "jd"},
	}

	s.AddTool(tool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		// Type assert request.Params.Arguments to the expected map type
		args, ok := request.Params.Arguments.(map[string]interface{})
		if !ok {
			return mcp.NewToolResultError("invalid arguments format"), nil
		}
		
		company, _ := args["company"].(string)
		position, _ := args["position"].(string)
		url, _ := args["url"].(string)
		jd, _ := args["jd"].(string)

		if company == "" || position == "" || url == "" || jd == "" {
			return mcp.NewToolResultError("missing required fields"), nil
		}

		err := runInitialization(company, position, url, jd)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to initialize job: %v", err)), nil
		}

		return mcp.NewToolResultText(fmt.Sprintf("Successfully initialized job application for %s as %s", company, position)), nil
	})

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "Server error: %v\n", err)
		os.Exit(1)
	}
}

func runInitialization(company, position, url, jd string) error {
	baseDir := resolveBaseDir()
	trackersDir := filepath.Join(baseDir, "trackers")
	appDir := filepath.Join(baseDir, "data", "applications", strings.ToLower(strings.ReplaceAll(company, " ", "_")))

	dirs := []string{trackersDir, filepath.Join(appDir, "resume"), filepath.Join(appDir, "cover")}
	for _, d := range dirs {
		if err := os.MkdirAll(d, 0755); err != nil {
			return err
		}
	}

	dateStr := time.Now().Format("2006-01-02")
	fileName := fmt.Sprintf("%s-%s.md", dateStr, strings.ReplaceAll(company, " ", "_"))
	filePath := filepath.Join(trackersDir, fileName)

	content := fmt.Sprintf(`---
company: %s
position: %s
status: Applied
next_action:
  - Wait for feedback
salary: 0
application_date: %s
website: 
reference_link: %s
resume_path: data/applications/%s/resume/resume.pdf
cover_letter_path: data/applications/%s/cover/cover-letter.pdf
---

## Job Description
%s

## Notes
- Created via Kaka Go MCP Tool
`, company, position, dateStr, url, filepath.Base(appDir), filepath.Base(appDir), jd)

	return os.WriteFile(filePath, []byte(content), 0644)
}

func resolveBaseDir() string {
	if env := os.Getenv("JOBWORKFLOW_ROOT"); env != "" {
		return env
	}

	cwd, err := os.Getwd()
	if err != nil {
		return "."
	}
	if hasRepoLayout(cwd) {
		return cwd
	}
	parent := filepath.Dir(cwd)
	if hasRepoLayout(parent) {
		return parent
	}

	return cwd
}

func hasRepoLayout(dir string) bool {
	if _, err := os.Stat(filepath.Join(dir, "trackers")); err != nil {
		return false
	}
	if _, err := os.Stat(filepath.Join(dir, "data")); err != nil {
		return false
	}
	return true
}
