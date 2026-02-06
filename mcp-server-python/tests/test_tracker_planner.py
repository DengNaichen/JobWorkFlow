"""
Unit tests for tracker planning utilities.

Tests deterministic slug generation, filename generation, and path computation.
"""


from pathlib import Path
from utils.tracker_planner import (
    normalize_company_name,
    generate_application_slug,
    generate_tracker_filename,
    compute_tracker_path,
    compute_resume_path,
    compute_cover_letter_path,
    compute_workspace_directories,
    plan_tracker
)


class TestNormalizeCompanyName:
    """Tests for company name normalization."""
    
    def test_simple_company_name(self):
        """Test normalization of simple company names."""
        assert normalize_company_name("Amazon") == "amazon"
        assert normalize_company_name("Meta") == "meta"
        assert normalize_company_name("Google") == "google"
    
    def test_company_name_with_spaces(self):
        """Test normalization of company names with spaces."""
        assert normalize_company_name("General Motors") == "general_motors"
        assert normalize_company_name("JP Morgan") == "jp_morgan"
    
    def test_company_name_with_special_chars(self):
        """Test normalization of company names with special characters."""
        assert normalize_company_name("L'Oréal") == "l_or_al"
        assert normalize_company_name("AT&T Inc.") == "at_t_inc"
        assert normalize_company_name("Procter & Gamble") == "procter_gamble"
    
    def test_company_name_with_multiple_spaces(self):
        """Test that consecutive spaces collapse to single underscore."""
        assert normalize_company_name("Company  Name") == "company_name"
        assert normalize_company_name("A   B   C") == "a_b_c"
    
    def test_company_name_with_leading_trailing_special(self):
        """Test that leading/trailing special chars are stripped."""
        assert normalize_company_name("_Company_") == "company"
        assert normalize_company_name("...Company...") == "company"


class TestGenerateApplicationSlug:
    """Tests for application slug generation."""
    
    def test_slug_format(self):
        """Test that slug follows <company>-<id> format."""
        slug = generate_application_slug("Amazon", 3629)
        assert slug == "amazon-3629"
        
        slug = generate_application_slug("General Motors", 3711)
        assert slug == "general_motors-3711"
    
    def test_slug_uniqueness_same_company(self):
        """Test that different IDs produce different slugs for same company."""
        slug1 = generate_application_slug("Amazon", 100)
        slug2 = generate_application_slug("Amazon", 200)
        assert slug1 != slug2
        assert slug1 == "amazon-100"
        assert slug2 == "amazon-200"
    
    def test_slug_determinism(self):
        """Test that same inputs always produce same slug."""
        slug1 = generate_application_slug("Meta", 3630)
        slug2 = generate_application_slug("Meta", 3630)
        assert slug1 == slug2


class TestGenerateTrackerFilename:
    """Tests for tracker filename generation."""
    
    def test_filename_format(self):
        """Test that filename follows <date>-<company>-<id>.md format."""
        filename = generate_tracker_filename("Amazon", 3629, "2026-02-04T15:30:00")
        assert filename == "2026-02-04-amazon-3629.md"
        
        filename = generate_tracker_filename("General Motors", 3711, "2026-02-04T10:00:00")
        assert filename == "2026-02-04-general_motors-3711.md"
    
    def test_filename_with_space_separator(self):
        """Test that filename works with space-separated timestamp."""
        filename = generate_tracker_filename("Meta", 3630, "2026-02-04 16:00:00")
        assert filename == "2026-02-04-meta-3630.md"
    
    def test_filename_determinism(self):
        """Test that same inputs always produce same filename."""
        filename1 = generate_tracker_filename("Amazon", 3629, "2026-02-04T15:30:00")
        filename2 = generate_tracker_filename("Amazon", 3629, "2026-02-04T15:30:00")
        assert filename1 == filename2
    
    def test_filename_date_extraction(self):
        """Test that date is correctly extracted from timestamp."""
        # ISO format with T
        filename = generate_tracker_filename("Test", 1, "2026-02-04T15:30:00")
        assert filename.startswith("2026-02-04-")
        
        # Format with space
        filename = generate_tracker_filename("Test", 1, "2026-02-04 15:30:00")
        assert filename.startswith("2026-02-04-")


class TestComputeTrackerPath:
    """Tests for tracker path computation."""
    
    def test_default_trackers_dir(self):
        """Test path computation with default trackers directory."""
        path = compute_tracker_path("Amazon", 3629, "2026-02-04T15:30:00")
        assert path == Path("trackers/2026-02-04-amazon-3629.md")
    
    def test_custom_trackers_dir(self):
        """Test path computation with custom trackers directory."""
        path = compute_tracker_path("Meta", 3630, "2026-02-04T16:00:00", "custom/trackers")
        assert path == Path("custom/trackers/2026-02-04-meta-3630.md")
    
    def test_path_is_path_object(self):
        """Test that returned value is a Path object."""
        path = compute_tracker_path("Amazon", 3629, "2026-02-04T15:30:00")
        assert isinstance(path, Path)


class TestComputeResumePath:
    """Tests for resume path computation."""

    def test_resume_path_format(self):
        """Test that resume path follows wiki-link format."""
        path = compute_resume_path("amazon-3629")
        assert path == "[[data/applications/amazon-3629/resume/resume.pdf]]"

    def test_resume_path_with_different_slugs(self):
        """Test resume path with various application slugs."""
        assert compute_resume_path("meta-3630") == "[[data/applications/meta-3630/resume/resume.pdf]]"
        assert compute_resume_path("general_motors-3711") == "[[data/applications/general_motors-3711/resume/resume.pdf]]"

    def test_resume_path_determinism(self):
        """Test that same slug produces same path."""
        path1 = compute_resume_path("amazon-3629")
        path2 = compute_resume_path("amazon-3629")
        assert path1 == path2


class TestComputeCoverLetterPath:
    """Tests for cover letter path computation."""

    def test_cover_letter_path_format(self):
        """Test that cover letter path follows wiki-link format."""
        path = compute_cover_letter_path("amazon-3629")
        assert path == "[[data/applications/amazon-3629/cover/cover-letter.pdf]]"

    def test_cover_letter_path_with_different_slugs(self):
        """Test cover letter path with various application slugs."""
        assert compute_cover_letter_path("meta-3630") == "[[data/applications/meta-3630/cover/cover-letter.pdf]]"
        assert compute_cover_letter_path("general_motors-3711") == "[[data/applications/general_motors-3711/cover/cover-letter.pdf]]"

    def test_cover_letter_path_determinism(self):
        """Test that same slug produces same path."""
        path1 = compute_cover_letter_path("amazon-3629")
        path2 = compute_cover_letter_path("amazon-3629")
        assert path1 == path2


class TestComputeWorkspaceDirectories:
    """Tests for workspace directory computation."""

    def test_workspace_directories_structure(self):
        """Test that all required directories are computed."""
        dirs = compute_workspace_directories("amazon-3629")
        assert "workspace_root" in dirs
        assert "resume_dir" in dirs
        assert "cover_dir" in dirs

    def test_workspace_directories_paths(self):
        """Test that directory paths are correct."""
        dirs = compute_workspace_directories("amazon-3629")
        assert dirs["workspace_root"] == Path("data/applications/amazon-3629")
        assert dirs["resume_dir"] == Path("data/applications/amazon-3629/resume")
        assert dirs["cover_dir"] == Path("data/applications/amazon-3629/cover")

    def test_workspace_directories_with_custom_base(self):
        """Test workspace directories with custom base directory."""
        dirs = compute_workspace_directories("meta-3630", base_dir="custom/apps")
        assert dirs["workspace_root"] == Path("custom/apps/meta-3630")
        assert dirs["resume_dir"] == Path("custom/apps/meta-3630/resume")
        assert dirs["cover_dir"] == Path("custom/apps/meta-3630/cover")

    def test_workspace_directories_are_path_objects(self):
        """Test that all directory values are Path objects."""
        dirs = compute_workspace_directories("amazon-3629")
        assert isinstance(dirs["workspace_root"], Path)
        assert isinstance(dirs["resume_dir"], Path)
        assert isinstance(dirs["cover_dir"], Path)


class TestPlanTracker:
    """Tests for complete tracker planning."""
    
    def test_plan_includes_all_components(self):
        """Test that plan includes all required components."""
        job = {
            "id": 3629,
            "company": "Amazon",
            "captured_at": "2026-02-04T15:30:00"
        }
        plan = plan_tracker(job)
        
        assert "application_slug" in plan
        assert "tracker_filename" in plan
        assert "tracker_path" in plan
        assert "exists" in plan
        assert "resume_path" in plan
        assert "cover_letter_path" in plan
        assert "workspace_dirs" in plan
    
    def test_plan_values_correct(self):
        """Test that plan values are correctly computed."""
        job = {
            "id": 3629,
            "company": "Amazon",
            "captured_at": "2026-02-04T15:30:00"
        }
        plan = plan_tracker(job)
        
        assert plan["application_slug"] == "amazon-3629"
        assert plan["tracker_filename"] == "2026-02-04-amazon-3629.md"
        assert plan["tracker_path"] == Path("trackers/2026-02-04-amazon-3629.md")
        assert isinstance(plan["exists"], bool)
        assert plan["resume_path"] == "[[data/applications/amazon-3629/resume/resume.pdf]]"
        assert plan["cover_letter_path"] == "[[data/applications/amazon-3629/cover/cover-letter.pdf]]"
        assert plan["workspace_dirs"]["resume_dir"] == Path("data/applications/amazon-3629/resume")
        assert plan["workspace_dirs"]["cover_dir"] == Path("data/applications/amazon-3629/cover")
    
    def test_plan_with_custom_trackers_dir(self):
        """Test planning with custom trackers directory."""
        job = {
            "id": 3630,
            "company": "Meta",
            "captured_at": "2026-02-04T16:00:00"
        }
        plan = plan_tracker(job, trackers_dir="custom/trackers")
        
        assert plan["tracker_path"] == Path("custom/trackers/2026-02-04-meta-3630.md")
    
    def test_plan_determinism(self):
        """Test that same job produces same plan."""
        job = {
            "id": 3629,
            "company": "Amazon",
            "captured_at": "2026-02-04T15:30:00"
        }
        plan1 = plan_tracker(job)
        plan2 = plan_tracker(job)
        
        assert plan1["application_slug"] == plan2["application_slug"]
        assert plan1["tracker_filename"] == plan2["tracker_filename"]
        assert plan1["tracker_path"] == plan2["tracker_path"]
