```
---
company: <Company name>
position: <Role>
status: <Applied | Interviewed | Offer | Rejected | Accepted>
next_action:
  - <Optional multi-select values like Follow up, Prepare Interview>
salary: <Number>
application_date: YYYY-MM-DD
website: https://...
reference_link: https://...
resume_path: data/applications/<company>/resume/resume.pdf
cover_letter_path: data/applications/<company>/cover/cover-letter.pdf
---

## Recruiter Details
- 📧 Email address
- 📞 Phone number

## Notes
Describe what happened during the outreach, interview, or follow up.
```

Copy this template into any file under `trackers/` (filenames can follow `YYYY-Company.md`). Dataview reads the frontmatter and populates the table automatically, so you do not need to edit the dataview note itself.
