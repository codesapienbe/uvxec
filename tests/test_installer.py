#!/usr/bin/env python3
"""
Test suite for the CrossPlatformInstaller class.
"""

import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

from uv_cross_installer import CrossPlatformInstaller


class TestCrossPlatformInstaller:
    """Test cases for CrossPlatformInstaller."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.repo_url = "https://github.com/test/repo.git"
        self.app_name = "TestApp"
        self.installer = CrossPlatformInstaller(
            repo_url=self.repo_url,
            app_name=self.app_name,
            python_version="3.9"
        )
    
    def test_init(self):
        """Test installer initialization."""
        assert self.installer.repo_url == self.repo_url
        assert self.installer.app_name == self.app_name
        assert self.installer.python_version == "3.9"
        assert self.installer.install_dir is not None
        assert self.installer.temp_dir is None
        assert self.installer.cloned_repo_path is None
    
    def test_get_default_install_dir_linux(self):
        """Test default installation directory on Linux."""
        with patch('platform.system', return_value='Linux'):
            installer = CrossPlatformInstaller(self.repo_url, self.app_name)
            install_dir = installer._get_default_install_dir()
            assert self.app_name in str(install_dir)
    
    def test_get_default_install_dir_windows(self):
        """Test default installation directory on Windows."""
        with patch('platform.system', return_value='Windows'):
            with patch.dict(os.environ, {'PROGRAMFILES': 'C:\\Program Files'}):
                installer = CrossPlatformInstaller(self.repo_url, self.app_name)
                install_dir = installer._get_default_install_dir()
                assert "Program Files" in str(install_dir)
                assert self.app_name in str(install_dir)
    
    def test_get_default_install_dir_macos(self):
        """Test default installation directory on macOS."""
        with patch('platform.system', return_value='Darwin'):
            installer = CrossPlatformInstaller(self.repo_url, self.app_name)
            install_dir = installer._get_default_install_dir()
            assert "Applications" in str(install_dir)
            assert self.app_name in str(install_dir)
    
    def test_check_python_version_compatible(self):
        """Test Python version check with compatible version."""
        installer = CrossPlatformInstaller(
            self.repo_url, 
            self.app_name, 
            python_version="3.8"
        )
        assert installer.check_python_version() is True
    
    def test_check_python_version_incompatible(self):
        """Test Python version check with incompatible version."""
        installer = CrossPlatformInstaller(
            self.repo_url, 
            self.app_name, 
            python_version="3.20"  # Future version
        )
        assert installer.check_python_version() is False
    
    @patch('subprocess.run')
    def test_update_pip_success(self, mock_run):
        """Test successful pip update."""
        mock_run.return_value = Mock(returncode=0)
        assert self.installer.update_pip() is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_update_pip_failure(self, mock_run):
        """Test failed pip update."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'pip')
        mock_run.return_value.stderr = "Error message"
        assert self.installer.update_pip() is False
    
    @patch('subprocess.run')
    def test_install_uv_success(self, mock_run):
        """Test successful uv installation."""
        mock_run.return_value = Mock(returncode=0)
        assert self.installer.install_uv() is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_install_uv_failure(self, mock_run):
        """Test failed uv installation."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'pip')
        mock_run.return_value.stderr = "Error message"
        assert self.installer.install_uv() is False
    
    @patch('tempfile.mkdtemp')
    @patch('subprocess.run')
    def test_clone_repository_success_subprocess(self, mock_run, mock_mkdtemp):
        """Test successful repository cloning using subprocess."""
        mock_mkdtemp.return_value = "/tmp/test"
        mock_run.return_value = Mock(returncode=0)
        
        # Mock git module not available
        with patch.dict('sys.modules', {'git': None}):
            assert self.installer.clone_repository() is True
        
        assert self.installer.temp_dir == "/tmp/test"
        assert str(self.installer.cloned_repo_path) == "/tmp/test/repo"
    
    @patch('tempfile.mkdtemp')
    def test_clone_repository_success_gitpython(self, mock_mkdtemp):
        """Test successful repository cloning using GitPython."""
        mock_mkdtemp.return_value = "/tmp/test"
        
        with patch('git.Repo.clone_from') as mock_clone:
            mock_clone.return_value = Mock()
            assert self.installer.clone_repository() is True
        
        assert self.installer.temp_dir == "/tmp/test"
        assert str(self.installer.cloned_repo_path) == "/tmp/test/repo"
    
    def test_find_main_executable_existing_files(self):
        """Test finding main executable when files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.installer.install_dir = Path(temp_dir)
            
            # Create a main.py file
            main_py = self.installer.install_dir / "main.py"
            main_py.touch()
            
            result = self.installer._find_main_executable()
            assert result == main_py
    
    def test_find_main_executable_fallback(self):
        """Test finding main executable fallback behavior."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.installer.install_dir = Path(temp_dir)
            
            result = self.installer._find_main_executable()
            expected = self.installer.install_dir / "main.py"
            assert result == expected
    
    @patch('shutil.rmtree')
    def test_cleanup_success(self, mock_rmtree):
        """Test successful cleanup of temporary files."""
        self.installer.temp_dir = "/tmp/test"
        with patch('os.path.exists', return_value=True):
            self.installer.cleanup()
        mock_rmtree.assert_called_once_with("/tmp/test")
    
    @patch('shutil.rmtree')
    def test_cleanup_no_temp_dir(self, mock_rmtree):
        """Test cleanup when no temp directory exists."""
        self.installer.temp_dir = None
        self.installer.cleanup()
        mock_rmtree.assert_not_called()
    
    def test_move_to_install_directory_success(self):
        """Test successful move to installation directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up source and destination
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()
            (source_dir / "test_file.txt").touch()
            
            dest_dir = Path(temp_dir) / "dest"
            
            self.installer.cloned_repo_path = source_dir
            self.installer.install_dir = dest_dir
            
            assert self.installer.move_to_install_directory() is True
            assert dest_dir.exists()
            assert (dest_dir / "test_file.txt").exists()
    
    @patch('platform.system')
    def test_create_shortcuts_linux(self, mock_system):
        """Test shortcut creation on Linux."""
        mock_system.return_value = 'Linux'
        
        with patch.object(self.installer, '_create_linux_shortcuts', return_value=True) as mock_create:
            assert self.installer.create_shortcuts() is True
            mock_create.assert_called_once()
    
    @patch('platform.system')
    def test_create_shortcuts_windows(self, mock_system):
        """Test shortcut creation on Windows."""
        mock_system.return_value = 'Windows'
        
        with patch.object(self.installer, '_create_windows_shortcuts', return_value=True) as mock_create:
            assert self.installer.create_shortcuts() is True
            mock_create.assert_called_once()
    
    @patch('platform.system')
    def test_create_shortcuts_macos(self, mock_system):
        """Test shortcut creation on macOS."""
        mock_system.return_value = 'Darwin'
        
        with patch.object(self.installer, '_create_macos_shortcuts', return_value=True) as mock_create:
            assert self.installer.create_shortcuts() is True
            mock_create.assert_called_once()


class TestIntegration:
    """Integration tests for the installer."""
    
    def test_full_install_process_mock(self):
        """Test the full installation process with mocked components."""
        installer = CrossPlatformInstaller(
            "https://github.com/test/repo.git",
            "TestApp",
            "3.9"
        )
        
        # Mock all the methods to return success
        with patch.object(installer, 'check_python_version', return_value=True), \
             patch.object(installer, 'update_pip', return_value=True), \
             patch.object(installer, 'install_uv', return_value=True), \
             patch.object(installer, 'clone_repository', return_value=True), \
             patch.object(installer, 'build_project', return_value=True), \
             patch.object(installer, 'choose_install_directory', return_value=True), \
             patch.object(installer, 'move_to_install_directory', return_value=True), \
             patch.object(installer, 'create_shortcuts', return_value=True), \
             patch.object(installer, 'show_completion_message'), \
             patch.object(installer, 'cleanup'):
            
            result = installer.install()
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__]) 