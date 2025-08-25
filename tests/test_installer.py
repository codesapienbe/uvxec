#!/usr/bin/env python3
"""
Test suite for the CrossPlatformInstaller class.
"""

import pytest
import tempfile
import shutil
import subprocess
import logging
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import sys
import os

from uv_cross_installer import (
    CrossPlatformInstaller, 
    SecurityValidator,
    ProcessManager,
    InstallationError,
    SecurityError,
    ValidationError,
    InstallationStatus,
    setup_logging
)


class TestSecurityValidator:
    """Test cases for SecurityValidator."""
    
    def test_validate_repository_url_valid_https(self):
        """Test valid HTTPS repository URL."""
        url = "https://github.com/user/repo.git"
        assert SecurityValidator.validate_repository_url(url) is True
    
    def test_validate_repository_url_invalid_scheme(self):
        """Test invalid URL scheme."""
        url = "http://github.com/user/repo.git"
        with pytest.raises(SecurityError, match="Unsafe URL scheme"):
            SecurityValidator.validate_repository_url(url)
    
    def test_validate_repository_url_localhost(self):
        """Test localhost URL rejection."""
        url = "https://localhost/repo.git"
        with pytest.raises(SecurityError, match="Local URLs not allowed"):
            SecurityValidator.validate_repository_url(url)
    
    def test_validate_repository_url_private_ip(self):
        """Test private IP rejection."""
        url = "https://192.168.1.1/repo.git"
        with pytest.raises(SecurityError, match="Private IP addresses not allowed"):
            SecurityValidator.validate_repository_url(url)
    
    def test_validate_app_name_valid(self):
        """Test valid application name."""
        app_name = "MyApp-123"
        assert SecurityValidator.validate_app_name(app_name) is True
    
    def test_validate_app_name_invalid_characters(self):
        """Test invalid characters in app name."""
        app_name = "My App!"
        with pytest.raises(ValidationError, match="App name contains invalid characters"):
            SecurityValidator.validate_app_name(app_name)
    
    def test_validate_app_name_too_long(self):
        """Test app name too long."""
        app_name = "a" * 65
        with pytest.raises(ValidationError, match="App name too long"):
            SecurityValidator.validate_app_name(app_name)
    
    def test_validate_app_name_dangerous_pattern(self):
        """Test dangerous pattern in app name."""
        app_name = "../malicious"
        with pytest.raises(SecurityError, match="App name contains dangerous pattern"):
            SecurityValidator.validate_app_name(app_name)
    
    def test_validate_install_path_valid(self):
        """Test valid installation path."""
        path = Path("/opt/myapp")
        assert SecurityValidator.validate_install_path(path) is True
    
    def test_validate_install_path_dangerous_pattern(self):
        """Test dangerous pattern in install path."""
        path = Path("/opt/../etc/passwd")
        with pytest.raises(SecurityError, match="Install path contains dangerous pattern"):
            SecurityValidator.validate_install_path(path)


class TestProcessManager:
    """Test cases for ProcessManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger('test')
        self.process_manager = ProcessManager(self.logger)
    
    @patch('subprocess.Popen')
    def test_run_secure_success(self, mock_popen):
        """Test successful secure command execution."""
        mock_process = Mock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = self.process_manager.run_secure(
            ["echo", "test"], 
            correlation_id="test123"
        )
        
        assert result.returncode == 0
        assert result.stdout == "output"
        mock_popen.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_run_secure_timeout(self, mock_popen):
        """Test command timeout handling."""
        mock_process = Mock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(["echo"], 1)
        mock_popen.return_value = mock_process
        
        with pytest.raises(InstallationError, match="Command timed out"):
            self.process_manager.run_secure(
                ["echo", "test"], 
                timeout=1,
                correlation_id="test123"
            )
        
        mock_process.kill.assert_called_once()
    
    def test_run_secure_invalid_command(self):
        """Test invalid command validation."""
        with pytest.raises(ValidationError, match="Command must be a non-empty list"):
            self.process_manager.run_secure([], correlation_id="test123")
    
    @patch('subprocess.Popen')
    def test_cleanup_processes(self, mock_popen):
        """Test process cleanup."""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process still running
        mock_popen.return_value = mock_process
        
        # Simulate adding a process
        with patch.object(self.process_manager, '_active_processes', [mock_process]):
            self.process_manager.cleanup_processes()
        
        mock_process.terminate.assert_called_once()


class TestLogging:
    """Test cases for logging setup."""
    
    def test_setup_logging_creates_logger(self):
        """Test that logging setup creates proper logger."""
        logger = setup_logging()
        assert logger.name == 'uv_cross_installer'
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 2  # File and console handlers
    
    def test_json_logging_format(self):
        """Test JSON logging format."""
        logger = setup_logging()
        
        # Test log record with correlation_id
        with patch('builtins.open', mock_open()):
            logger.info("Test message", extra={'correlation_id': 'test123'})
        
        # Check that handler processes the record
        assert len(logger.handlers) >= 1


class TestCrossPlatformInstaller:
    """Test cases for CrossPlatformInstaller."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.repo_url = "https://github.com/test/repo.git"
        self.app_name = "TestApp"
        
        # Mock security validation to avoid actual validation during setup
        with patch.object(SecurityValidator, 'validate_repository_url', return_value=True), \
             patch.object(SecurityValidator, 'validate_app_name', return_value=True), \
             patch.object(SecurityValidator, 'validate_install_path', return_value=True), \
             patch('signal.signal'):
            self.installer = CrossPlatformInstaller(
                repo_url=self.repo_url,
                app_name=self.app_name,
                python_version="3.9",
                correlation_id="test123"
            )
    
    def test_init_with_correlation_id(self):
        """Test installer initialization with correlation ID."""
        assert self.installer.repo_url == self.repo_url
        assert self.installer.app_name == self.app_name
        assert self.installer.python_version == "3.9"
        assert self.installer.context.correlation_id == "test123"
        assert self.installer.context.status == InstallationStatus.PENDING
        assert self.installer.install_dir is not None
    
    def test_generate_correlation_id(self):
        """Test correlation ID generation."""
        with patch.object(SecurityValidator, 'validate_repository_url', return_value=True), \
             patch.object(SecurityValidator, 'validate_app_name', return_value=True), \
             patch.object(SecurityValidator, 'validate_install_path', return_value=True), \
             patch('signal.signal'):
            installer = CrossPlatformInstaller(self.repo_url, self.app_name)
            assert len(installer.context.correlation_id) == 16
    
    @patch('platform.system')
    def test_get_default_install_dir_linux(self, mock_system):
        """Test default installation directory on Linux."""
        mock_system.return_value = 'Linux'
        
        with patch.object(SecurityValidator, 'validate_repository_url', return_value=True), \
             patch.object(SecurityValidator, 'validate_app_name', return_value=True), \
             patch.object(SecurityValidator, 'validate_install_path', return_value=True), \
             patch('signal.signal'):
            installer = CrossPlatformInstaller(self.repo_url, self.app_name)
            install_dir = installer._get_default_install_dir()
            assert self.app_name in str(install_dir)
    
    @patch('platform.system')
    def test_get_default_install_dir_windows(self, mock_system):
        """Test default installation directory on Windows."""
        mock_system.return_value = 'Windows'
        
        with patch.dict(os.environ, {'PROGRAMFILES': 'C:\\Program Files'}), \
             patch.object(SecurityValidator, 'validate_repository_url', return_value=True), \
             patch.object(SecurityValidator, 'validate_app_name', return_value=True), \
             patch.object(SecurityValidator, 'validate_install_path', return_value=True), \
             patch('signal.signal'):
            installer = CrossPlatformInstaller(self.repo_url, self.app_name)
            install_dir = installer._get_default_install_dir()
            assert "Program Files" in str(install_dir)
            assert self.app_name in str(install_dir)
    
    def test_check_python_version_compatible(self):
        """Test Python version check with compatible version."""
        assert self.installer.check_python_version() is True
    
    def test_check_python_version_incompatible(self):
        """Test Python version check with incompatible version."""
        self.installer.python_version = "3.20"  # Future version
        assert self.installer.check_python_version() is False
    
    def test_check_python_version_invalid_format(self):
        """Test Python version check with invalid format."""
        self.installer.python_version = "invalid"
        assert self.installer.check_python_version() is False
    
    @patch.object(ProcessManager, 'run_secure')
    def test_update_pip_success(self, mock_run):
        """Test successful pip update."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        assert self.installer.update_pip() is True
        mock_run.assert_called_once()
    
    @patch.object(ProcessManager, 'run_secure')
    def test_update_pip_failure(self, mock_run):
        """Test failed pip update."""
        mock_run.return_value = Mock(returncode=1, stderr="Error message")
        assert self.installer.update_pip() is False
    
    @patch.object(ProcessManager, 'run_secure')
    def test_install_uv_success(self, mock_run):
        """Test successful uv installation."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        assert self.installer.install_uv() is True
        mock_run.assert_called_once()
    
    @patch.object(ProcessManager, 'run_secure')
    def test_install_uv_failure(self, mock_run):
        """Test failed uv installation."""
        mock_run.return_value = Mock(returncode=1, stderr="Error message")
        assert self.installer.install_uv() is False
    
    @patch('tempfile.mkdtemp')
    @patch.object(ProcessManager, 'run_secure')
    def test_clone_repository_success_subprocess(self, mock_run, mock_mkdtemp):
        """Test successful repository cloning using subprocess."""
        mock_mkdtemp.return_value = "/tmp/test"
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        # Mock git module not available
        with patch.dict('sys.modules', {'git': None}):
            assert self.installer.clone_repository() is True
        
        assert str(self.installer.temp_dir) == "/tmp/test"
        assert str(self.installer.cloned_repo_path) == "/tmp/test/repo"
    
    @patch('tempfile.mkdtemp')
    def test_clone_repository_success_gitpython(self, mock_mkdtemp):
        """Test successful repository cloning using GitPython."""
        mock_mkdtemp.return_value = "/tmp/test"
        
        with patch('git.Repo.clone_from') as mock_clone, \
             patch.object(Path, 'exists', return_value=True):
            mock_clone.return_value = Mock()
            assert self.installer.clone_repository() is True
        
        assert str(self.installer.temp_dir) == "/tmp/test"
        assert str(self.installer.cloned_repo_path) == "/tmp/test/repo"
    
    @patch('tempfile.mkdtemp')
    def test_clone_repository_security_verification_failure(self, mock_mkdtemp):
        """Test repository security verification failure."""
        mock_mkdtemp.return_value = "/tmp/test"
        
        with patch('git.Repo.clone_from') as mock_clone, \
             patch.object(Path, 'exists', return_value=False):
            mock_clone.return_value = Mock()
            assert self.installer.clone_repository() is False
    
    def test_build_project_no_repository(self):
        """Test build project when no repository is cloned."""
        self.installer.cloned_repo_path = None
        assert self.installer.build_project() is False
    
    @patch.object(ProcessManager, 'run_secure')
    def test_build_project_success(self, mock_run):
        """Test successful project build."""
        # Set up cloned repo path
        with tempfile.TemporaryDirectory() as temp_dir:
            self.installer.cloned_repo_path = Path(temp_dir)
            (self.installer.cloned_repo_path / 'pyproject.toml').touch()
            
            mock_run.return_value = Mock(returncode=0, stderr="")
            assert self.installer.build_project() is True
            
            # Should call uv sync and uv pip install
            assert mock_run.call_count == 2
    
    @patch.object(ProcessManager, 'run_secure')
    def test_build_project_uv_sync_failure(self, mock_run):
        """Test project build with uv sync failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.installer.cloned_repo_path = Path(temp_dir)
            
            mock_run.return_value = Mock(returncode=1, stderr="Sync failed")
            assert self.installer.build_project() is False
    
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
    
    @patch.object(ProcessManager, 'cleanup_processes')
    @patch('shutil.rmtree')
    def test_cleanup_success(self, mock_rmtree, mock_cleanup):
        """Test successful cleanup of temporary files and processes."""
        self.installer.temp_dir = Path("/tmp/test")
        
        with patch.object(Path, 'exists', return_value=True):
            self.installer.cleanup()
        
        mock_cleanup.assert_called_once()
        mock_rmtree.assert_called_once_with(Path("/tmp/test"))
    
    def test_cleanup_no_temp_dir(self):
        """Test cleanup when no temp directory exists."""
        self.installer.temp_dir = None
        
        with patch.object(self.installer.process_manager, 'cleanup_processes') as mock_cleanup:
            self.installer.cleanup()
        
        mock_cleanup.assert_called_once()


class TestIntegration:
    """Integration tests for the installer."""
    
    def test_full_install_process_mock(self):
        """Test the full installation process with mocked components."""
        with patch.object(SecurityValidator, 'validate_repository_url', return_value=True), \
             patch.object(SecurityValidator, 'validate_app_name', return_value=True), \
             patch.object(SecurityValidator, 'validate_install_path', return_value=True), \
             patch('signal.signal'):
            
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
                assert installer.context.status == InstallationStatus.SUCCESS
    
    def test_install_failure_handling(self):
        """Test installation failure handling."""
        with patch.object(SecurityValidator, 'validate_repository_url', return_value=True), \
             patch.object(SecurityValidator, 'validate_app_name', return_value=True), \
             patch.object(SecurityValidator, 'validate_install_path', return_value=True), \
             patch('signal.signal'):
            
            installer = CrossPlatformInstaller(
                "https://github.com/test/repo.git",
                "TestApp",
                "3.9"
            )
            
            # Mock first step to fail
            with patch.object(installer, 'check_python_version', return_value=False), \
                 patch.object(installer, 'cleanup'):
                
                result = installer.install()
                assert result is False
                assert installer.context.status == InstallationStatus.FAILED


if __name__ == "__main__":
    pytest.main([__file__]) 