package main

import (
	"database/sql"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

func openCaptureDB(dbPath string) (*sql.DB, error) {
	if dbPath == "" {
		if env := os.Getenv("JOBWORKFLOW_DB"); env != "" {
			dbPath = env
		} else {
			baseDir := resolveBaseDir()
			dbPath = filepath.Join(baseDir, "data", "capture", "jobs.db")
		}
	}
	if err := os.MkdirAll(filepath.Dir(dbPath), 0755); err != nil {
		return nil, err
	}
	return sql.Open("sqlite", dbPath)
}

func fetchJobsByStatus(db *sql.DB, status string, limit int) ([]JobRecord, error) {
	rows, err := db.Query(`
		SELECT url, title, description, company, job_id, location
		FROM jobs
		WHERE status = ?
		ORDER BY created_at DESC
		LIMIT ?
	`, status, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var jobs []JobRecord
	for rows.Next() {
		var job JobRecord
		if err := rows.Scan(&job.URL, &job.Title, &job.Description, &job.Company, &job.JobID, &job.Location); err != nil {
			continue
		}
		jobs = append(jobs, job)
	}
	return jobs, nil
}

func updateJobStatus(db *sql.DB, url, status string) error {
	_, err := db.Exec(`UPDATE jobs SET status = ? WHERE url = ?`, status, url)
	return err
}

func updateJobsStatus(db *sql.DB, fromStatus, toStatus string, limit int, dryRun bool) (int64, error) {
	if limit > 0 {
		if dryRun {
			row := db.QueryRow(`SELECT COUNT(1) FROM (
				SELECT 1 FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?
			)`, fromStatus, limit)
			var count int64
			if err := row.Scan(&count); err != nil {
				return 0, err
			}
			return count, nil
		}
		result, err := db.Exec(`
			UPDATE jobs SET status = ?
			WHERE url IN (
				SELECT url FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?
			)
		`, toStatus, fromStatus, limit)
		if err != nil {
			return 0, err
		}
		return result.RowsAffected()
	}

	if dryRun {
		row := db.QueryRow(`SELECT COUNT(1) FROM jobs WHERE status = ?`, fromStatus)
		var count int64
		if err := row.Scan(&count); err != nil {
			return 0, err
		}
		return count, nil
	}
	result, err := db.Exec(`UPDATE jobs SET status = ? WHERE status = ?`, toStatus, fromStatus)
	if err != nil {
		return 0, err
	}
	return result.RowsAffected()
}
