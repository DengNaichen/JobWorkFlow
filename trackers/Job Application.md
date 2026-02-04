```dataview
table company as "Company", position as "Position", status as "Status", next_action as "Next Action", salary as "Salary (€)", application_date as "Application Date", resume_path as "Resume", cover_letter_path as "Cover Letter"
from "trackers"
sort application_date desc
```

  
> **Tracker info**  
> - This Dataview table scans every file inside `trackers/` whose frontmatter declares the fields listed above (resume/cover letter paths should point into `data/applications/<company>`).  
> - Add new job entries by cloning `record/template.md` (or copying `record/Test.md`), setting the metadata, and saving the note inside `trackers/`. Dataview updates automatically.
