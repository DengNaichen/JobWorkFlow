"""
Unit tests for artifact path resolution utilities.

Tests path parsing, wiki-link format support, and companion file resolution.
"""

import pytest
from utils.artifact_paths import (
    parse_resume_path,
    resolve_resume_tex_path,
    resolve_artifact_paths,
    ArtifactPathError
)


class TestParseResumePath:
    """Tests for parse_resume_path function."""
    
    def test_wiki_link_format(self):
        """Test parsing wiki-link format: [[path]]."""
        raw = "[[data/applications/amazon-352/resume/resume.pdf]]"
        result = parse_resume_path(raw)
        assert result == "data/applications/amazon-352/resume/resume.pdf"
    
    def test_plain_path_format(self):
        """Test parsing plain path format."""
        raw = "data/applications/amazon-352/resume/resume.pdf"
        result = parse_resume_path(raw)
        assert result == "data/applications/amazon-352/resume/resume.pdf"
    
    def test_wiki_link_with_whitespace(self):
        """Test wiki-link format with surrounding whitespace."""
        raw = "  [[data/applications/meta-100/resume/resume.pdf]]  "
        result = parse_resume_path(raw)
        assert result == "data/applications/meta-100/resume/resume.pdf"
    
    def test_plain_path_with_whitespace(self):
        """Test plain path format with surrounding whitespace."""
        raw = "  data/applications/meta-100/resume/resume.pdf  "
        result = parse_resume_path(raw)
        assert result == "data/applications/meta-100/resume/resume.pdf"
    
    def test_none_input(self):
        """Test that None input returns None."""
        result = parse_resume_path(None)
        assert result is None
    
    def test_empty_string(self):
        """Test that empty string raises error."""
        with pytest.raises(ArtifactPathError, match="resume_path is empty"):
            parse_resume_path("")
    
    def test_whitespace_only(self):
        """Test that whitespace-only string raises error."""
        with pytest.raises(ArtifactPathError, match="resume_path is empty"):
            parse_resume_path("   ")
    
    def test_empty_wiki_link(self):
        """Test that empty wiki-link raises error."""
        with pytest.raises(ArtifactPathError, match="wiki-link contains empty path"):
            parse_resume_path("[[]]")
    
    def test_wiki_link_with_only_whitespace(self):
        """Test that wiki-link with only whitespace raises error."""
        with pytest.raises(ArtifactPathError, match="wiki-link contains empty path"):
            parse_resume_path("[[   ]]")
    
    def test_non_string_input(self):
        """Test that non-string input raises error."""
        with pytest.raises(ArtifactPathError, match="must be a string"):
            parse_resume_path(123)
    
    def test_different_application_slugs(self):
        """Test parsing with various application slugs."""
        test_cases = [
            ("[[data/applications/google-500/resume/resume.pdf]]", 
             "data/applications/google-500/resume/resume.pdf"),
            ("[[data/applications/meta-100/resume/resume.pdf]]", 
             "data/applications/meta-100/resume/resume.pdf"),
            ("[[data/applications/general_motors-711/resume/resume.pdf]]", 
             "data/applications/general_motors-711/resume/resume.pdf"),
        ]
        
        for raw, expected in test_cases:
            result = parse_resume_path(raw)
            assert result == expected
    
    def test_determinism(self):
        """Test that same input produces same output (deterministic)."""
        raw = "[[data/applications/amazon-352/resume/resume.pdf]]"
        result1 = parse_resume_path(raw)
        result2 = parse_resume_path(raw)
        assert result1 == result2


class TestResolveResumeTexPath:
    """Tests for resolve_resume_tex_path function."""
    
    def test_basic_resolution(self):
        """Test basic resume.tex path resolution."""
        pdf_path = "data/applications/amazon-352/resume/resume.pdf"
        tex_path = resolve_resume_tex_path(pdf_path)
        assert tex_path == "data/applications/amazon-352/resume/resume.tex"
    
    def test_different_slugs(self):
        """Test resolution with various application slugs."""
        test_cases = [
            ("data/applications/meta-100/resume/resume.pdf",
             "data/applications/meta-100/resume/resume.tex"),
            ("data/applications/google-500/resume/resume.pdf",
             "data/applications/google-500/resume/resume.tex"),
            ("data/applications/general_motors-711/resume/resume.pdf",
             "data/applications/general_motors-711/resume/resume.tex"),
        ]
        
        for pdf_path, expected_tex in test_cases:
            result = resolve_resume_tex_path(pdf_path)
            assert result == expected_tex
    
    def test_empty_path(self):
        """Test that empty path raises error."""
        with pytest.raises(ArtifactPathError, match="cannot be empty"):
            resolve_resume_tex_path("")
    
    def test_determinism(self):
        """Test that same input produces same output (deterministic)."""
        pdf_path = "data/applications/amazon-352/resume/resume.pdf"
        result1 = resolve_resume_tex_path(pdf_path)
        result2 = resolve_resume_tex_path(pdf_path)
        assert result1 == result2
    
    def test_preserves_directory_structure(self):
        """Test that directory structure is preserved."""
        pdf_path = "data/applications/amazon-352/resume/resume.pdf"
        tex_path = resolve_resume_tex_path(pdf_path)
        
        # Both should be in the same directory
        import os
        assert os.path.dirname(pdf_path) == os.path.dirname(tex_path)


class TestResolveArtifactPaths:
    """Tests for resolve_artifact_paths convenience function."""
    
    def test_wiki_link_format(self):
        """Test resolving both paths from wiki-link format."""
        raw = "[[data/applications/amazon-352/resume/resume.pdf]]"
        pdf_path, tex_path = resolve_artifact_paths(raw)
        
        assert pdf_path == "data/applications/amazon-352/resume/resume.pdf"
        assert tex_path == "data/applications/amazon-352/resume/resume.tex"
    
    def test_plain_path_format(self):
        """Test resolving both paths from plain path format."""
        raw = "data/applications/meta-100/resume/resume.pdf"
        pdf_path, tex_path = resolve_artifact_paths(raw)
        
        assert pdf_path == "data/applications/meta-100/resume/resume.pdf"
        assert tex_path == "data/applications/meta-100/resume/resume.tex"
    
    def test_none_input(self):
        """Test that None input raises error."""
        with pytest.raises(ArtifactPathError, match="resume_path is required"):
            resolve_artifact_paths(None)
    
    def test_empty_string(self):
        """Test that empty string raises error."""
        with pytest.raises(ArtifactPathError, match="resume_path is empty"):
            resolve_artifact_paths("")
    
    def test_determinism(self):
        """Test that same input produces same output (deterministic)."""
        raw = "[[data/applications/amazon-352/resume/resume.pdf]]"
        
        pdf1, tex1 = resolve_artifact_paths(raw)
        pdf2, tex2 = resolve_artifact_paths(raw)
        
        assert pdf1 == pdf2
        assert tex1 == tex2
    
    def test_paths_in_same_directory(self):
        """Test that resolved PDF and TEX paths are in the same directory."""
        raw = "[[data/applications/google-500/resume/resume.pdf]]"
        pdf_path, tex_path = resolve_artifact_paths(raw)
        
        import os
        assert os.path.dirname(pdf_path) == os.path.dirname(tex_path)
    
    def test_multiple_slugs(self):
        """Test resolution with various application slugs."""
        test_cases = [
            "[[data/applications/amazon-352/resume/resume.pdf]]",
            "[[data/applications/meta-100/resume/resume.pdf]]",
            "[[data/applications/general_motors-711/resume/resume.pdf]]",
            "data/applications/google-500/resume/resume.pdf",
        ]
        
        for raw in test_cases:
            pdf_path, tex_path = resolve_artifact_paths(raw)
            
            # Verify both paths are non-empty
            assert pdf_path
            assert tex_path
            
            # Verify both end with expected filenames
            assert pdf_path.endswith("resume.pdf")
            assert tex_path.endswith("resume.tex")
            
            # Verify they're in the same directory
            import os
            assert os.path.dirname(pdf_path) == os.path.dirname(tex_path)


class TestRequirementTraceability:
    """Tests that verify specific requirements are met."""
    
    def test_requirement_6_1_resolve_pdf_from_frontmatter(self):
        """
        Requirement 6.1: Resolve resume.pdf path from tracker frontmatter resume_path.
        """
        # Simulate frontmatter value
        resume_path_raw = "[[data/applications/amazon-352/resume/resume.pdf]]"
        
        # Should successfully parse and return PDF path
        pdf_path = parse_resume_path(resume_path_raw)
        assert pdf_path == "data/applications/amazon-352/resume/resume.pdf"
    
    def test_requirement_6_2_support_both_formats(self):
        """
        Requirement 6.2: Support wiki-link path format ([[...]]) and plain path format.
        """
        wiki_link = "[[data/applications/amazon-352/resume/resume.pdf]]"
        plain_path = "data/applications/amazon-352/resume/resume.pdf"
        
        # Both formats should resolve to the same path
        result_wiki = parse_resume_path(wiki_link)
        result_plain = parse_resume_path(plain_path)
        
        assert result_wiki == "data/applications/amazon-352/resume/resume.pdf"
        assert result_plain == "data/applications/amazon-352/resume/resume.pdf"
        assert result_wiki == result_plain
    
    def test_requirement_6_3_derive_tex_from_workspace(self):
        """
        Requirement 6.3: Derive resume.tex from resolved resume workspace directory.
        """
        pdf_path = "data/applications/amazon-352/resume/resume.pdf"
        
        # Should derive tex path in same directory
        tex_path = resolve_resume_tex_path(pdf_path)
        assert tex_path == "data/applications/amazon-352/resume/resume.tex"
        
        # Verify same directory
        import os
        assert os.path.dirname(pdf_path) == os.path.dirname(tex_path)
    
    def test_requirement_6_4_error_on_missing_resume_path(self):
        """
        Requirement 6.4: Return VALIDATION_ERROR when resume_path is missing or unparsable.
        """
        # Missing (None)
        with pytest.raises(ArtifactPathError):
            resolve_artifact_paths(None)
        
        # Empty string
        with pytest.raises(ArtifactPathError):
            resolve_artifact_paths("")
        
        # Empty wiki-link
        with pytest.raises(ArtifactPathError):
            parse_resume_path("[[]]")
    
    def test_requirement_6_5_deterministic_resolution(self):
        """
        Requirement 6.5: Path resolution is deterministic for identical tracker content.
        """
        resume_path_raw = "[[data/applications/amazon-352/resume/resume.pdf]]"
        
        # Multiple calls with same input should produce identical results
        pdf1, tex1 = resolve_artifact_paths(resume_path_raw)
        pdf2, tex2 = resolve_artifact_paths(resume_path_raw)
        pdf3, tex3 = resolve_artifact_paths(resume_path_raw)
        
        assert pdf1 == pdf2 == pdf3
        assert tex1 == tex2 == tex3
