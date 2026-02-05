package main

type JobRecord struct {
	URL         string
	Title       string
	Description string
	Company     string
	JobID       string
	Location    string
}

type TrackerData struct {
	Company       string
	Position      string
	ResumePath    string
	ReferenceLink string
	JobDesc       string
}
