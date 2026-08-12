"""Regression tests for CREATE operations with directory grants."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from forgeai.core.workspace_manager import WorkspaceManager
from forgeai.core.workspace_database import WorkspaceDatabase
from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem


@pytest.fixture
def temp_project():
    """Create a temporary project directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        src_dir = project_root / "src"
        src_dir.mkdir()
        
        # Create one existing file for testing
        existing_file = project_root / "existing.py"
        existing_file.write_text("# existing file")
        
        yield project_root


@pytest.fixture
def workspace_manager(temp_project):
    """Create a workspace manager with a mock database."""
    database = MagicMock(spec=WorkspaceDatabase)
    database.fetchall.return_value = []
    database.fetchone.return_value = None
    
    # Track AI grants in memory
    grants = []
    
    def execute(query, params=None):
        if "INSERT INTO ai_access_grants" in query:
            grants.append({
                "relative_path": params[1],
                "grant_type": params[2],
            })
        elif "DELETE FROM ai_access_grants" in query:
            grants = [g for g in grants if not (g["relative_path"] == params[1])]
    
    def fetchall_grants(query, params=None):
        if "ai_access_grants" in query:
            return grants
        return []
    
    database.execute = execute
    database.fetchall = fetchall_grants
    
    filesystem = FileSystem()
    indexer = MagicMock(spec=FileIndexer)
    indexer.filesystem = filesystem
    
    manager = WorkspaceManager(database, indexer)
    manager.open_project(temp_project)
    
    # Store grants reference for testing
    manager._test_grants = grants
    
    return manager


class TestCreateGrantAuthorization:
    """Test CREATE operation authorization with directory grants."""
    
    def test_directory_root_grant_allows_root_file_create(self, workspace_manager):
        """Test 1: Directory "." granted → create("tessto1.txt") allowed."""
        # Grant root directory
        workspace_manager._test_grants.append({
            "relative_path": ".",
            "grant_type": "directory",
        })
        
        # Should allow creating file in root
        assert workspace_manager.is_ai_path_granted("tessto1.txt") is True
    
    def test_directory_grant_allows_child_file_create(self, workspace_manager):
        """Test 2: Directory "src" granted → create("src/tessto1.txt") allowed."""
        # Grant src directory
        workspace_manager._test_grants.append({
            "relative_path": "src",
            "grant_type": "directory",
        })
        
        # Should allow creating file in src
        assert workspace_manager.is_ai_path_granted("src/tessto1.txt") is True
    
    def test_directory_grant_denies_sibling_file_create(self, workspace_manager):
        """Test 3: Directory "src" granted → create("tessto1.txt") denied."""
        # Grant only src directory
        workspace_manager._test_grants.append({
            "relative_path": "src",
            "grant_type": "directory",
        })
        
        # Should deny creating file in root (only src is granted)
        assert workspace_manager.is_ai_path_granted("tessto1.txt") is False
    
    def test_file_grant_denies_new_file_create(self, workspace_manager):
        """Test 4: Only File grant → create("new.py") denied."""
        # Grant only a single file
        workspace_manager._test_grants.append({
            "relative_path": "existing.py",
            "grant_type": "file",
        })
        
        # Should deny creating new file (file grant doesn't cover new files)
        assert workspace_manager.is_ai_path_granted("new.py") is False
    
    def test_directory_grant_allows_existing_file_edit(self, workspace_manager):
        """Test 5: Directory grant → existing file edit allowed."""
        # Grant root directory
        workspace_manager._test_grants.append({
            "relative_path": ".",
            "grant_type": "directory",
        })
        
        # Should allow editing existing file
        assert workspace_manager.is_ai_path_granted("existing.py") is True
    
    def test_path_outside_project_denied(self, workspace_manager):
        """Test 6: Path outside project → denied."""
        # Grant root directory
        workspace_manager._test_grants.append({
            "relative_path": ".",
            "grant_type": "directory",
        })
        
        # Try to access path outside project (security boundary)
        outside_path = workspace_manager.active_project.parent / "outside.txt"
        assert workspace_manager.is_ai_path_granted(outside_path) is False
    
    def test_nested_directory_grant_allows_nested_create(self, workspace_manager):
        """Test 7: Nested directory grant allows nested file creation."""
        # Grant a nested directory
        workspace_manager._test_grants.append({
            "relative_path": "src",
            "grant_type": "directory",
        })
        
        # Should allow creating nested file
        assert workspace_manager.is_ai_path_granted("src/utils/helper.py") is True
    
    def test_file_grant_allows_exact_file_edit(self, workspace_manager):
        """Test 8: File grant allows editing exact file."""
        # Grant only existing.py
        workspace_manager._test_grants.append({
            "relative_path": "existing.py",
            "grant_type": "file",
        })
        
        # Should allow editing that specific file
        assert workspace_manager.is_ai_path_granted("existing.py") is True
    
    def test_file_grant_denies_other_file_access(self, workspace_manager):
        """Test 9: File grant doesn't grant access to other files."""
        # Grant only existing.py
        workspace_manager._test_grants.append({
            "relative_path": "existing.py",
            "grant_type": "file",
        })
        
        # Should deny access to different file
        assert workspace_manager.is_ai_path_granted("other.py") is False
    
    def test_multiple_directory_grants_union(self, workspace_manager):
        """Test 10: Multiple directory grants work together (union)."""
        # Grant two directories
        workspace_manager._test_grants.append({
            "relative_path": "src",
            "grant_type": "directory",
        })
        workspace_manager._test_grants.append({
            "relative_path": "tests",
            "grant_type": "directory",
        })
        
        # Should allow in both directories
        assert workspace_manager.is_ai_path_granted("src/new.py") is True
        assert workspace_manager.is_ai_path_granted("tests/new.py") is True
        # But not in root
        assert workspace_manager.is_ai_path_granted("root.py") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
