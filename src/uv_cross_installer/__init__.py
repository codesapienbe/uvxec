#!/usr/bin/env python3
"""
Cross-platform installer for uv-based Python applications.

This module provides a secure, enterprise-grade installer with comprehensive
logging, input validation, and error handling.
"""

import os
import sys
import subprocess
import shutil
import platform
import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import tkinter as tk
from tkinter import filedialog, messagebox
import tempfile
import hashlib
from dataclasses import dataclass
from enum import Enum
import signal
import threading
import time

try:
    import git
except ImportError:
    git = None

try:
    import platformdirs
except ImportError:
    platformdirs = None

try:
    import winshell
except ImportError:
    winshell = None


# Configure structured logging
def setup_logging() -> logging.Logger:
    """Set up structured logging for the installer."""
    logger = logging.getLogger('uv_cross_installer')
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create file handler for application.log
    log_file = Path.cwd() / 'application.log'
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Create JSON formatter for structured logging
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                'timestamp': self.formatTime(record, '%Y-%m-%d %H:%M:%S'),
                'level': record.levelname,
                'component': 'uv_cross_installer',
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Add correlation_id if available
            if hasattr(record, 'correlation_id'):
                log_entry['correlation_id'] = record.correlation_id
            
            # Add user_id if available
            if hasattr(record, 'user_id'):
                log_entry['user_id'] = record.user_id
                
            # Add request_id if available
            if hasattr(record, 'request_id'):
                log_entry['request_id'] = record.request_id
            
            return json.dumps(log_entry)
    
    # Set formatters
    file_handler.setFormatter(JSONFormatter())
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


class InstallationError(Exception):
    """Custom exception for installation failures."""
    pass


class SecurityError(Exception):
    """Custom exception for security-related issues."""
    pass


class ValidationError(Exception):
    """Custom exception for input validation failures."""
    pass


class InstallationStatus(Enum):
    """Installation status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class InstallationContext:
    """Installation context with correlation tracking."""
    correlation_id: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    start_time: float = 0.0
    status: InstallationStatus = InstallationStatus.PENDING


class SecurityValidator:
    """Security validation utilities."""
    
    # Allowed URL schemes
    ALLOWED_SCHEMES = {'https', 'git+https', 'ssh', 'git+ssh'}
    
    # Dangerous path patterns
    DANGEROUS_PATTERNS = [
        r'\.\./',  # Path traversal
        r'~/',     # Home directory access
        r'/etc/',  # System config access
        r'/proc/', # Process info access
        r'/sys/',  # System info access
    ]
    
    @classmethod
    def validate_repository_url(cls, url: str) -> bool:
        """Validate repository URL for security."""
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Check scheme
            if parsed.scheme not in cls.ALLOWED_SCHEMES:
                raise SecurityError(f"Unsafe URL scheme: {parsed.scheme}")
            
            # Check for localhost/private IPs
            if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
                raise SecurityError("Local URLs not allowed")
            
            # Check for private IP ranges (basic check)
            if parsed.hostname and (
                parsed.hostname.startswith('192.168.') or
                parsed.hostname.startswith('10.') or
                parsed.hostname.startswith('172.')
            ):
                raise SecurityError("Private IP addresses not allowed")
            
            return True
            
        except urllib.parse.ParseError as e:
            raise ValidationError(f"Invalid URL format: {e}")
    
    @classmethod
    def validate_app_name(cls, app_name: str) -> bool:
        """Validate application name for security."""
        # Check for dangerous characters
        if not re.match(r'^[a-zA-Z0-9_-]+$', app_name):
            raise ValidationError("App name contains invalid characters")
        
        # Check length
        if len(app_name) > 64:
            raise ValidationError("App name too long")
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, app_name):
                raise SecurityError(f"App name contains dangerous pattern: {pattern}")
        
        return True
    
    @classmethod
    def validate_install_path(cls, path: Path) -> bool:
        """Validate installation path for security."""
        path_str = str(path.resolve())
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, path_str):
                raise SecurityError(f"Install path contains dangerous pattern: {pattern}")
        
        # Ensure path is within reasonable bounds
        if not path.is_absolute():
            raise ValidationError("Install path must be absolute")
        
        return True


class ProcessManager:
    """Secure process execution manager."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._active_processes: List[subprocess.Popen] = []
        self._lock = threading.Lock()
    
    def run_secure(
        self, 
        cmd: List[str], 
        cwd: Optional[Path] = None,
        timeout: int = 300,
        correlation_id: str = ""
    ) -> subprocess.CompletedProcess:
        """Run command with security constraints."""
        
        # Validate command
        if not cmd or not isinstance(cmd, list):
            raise ValidationError("Command must be a non-empty list")
        
        # Sanitize environment
        safe_env = {
            'PATH': os.environ.get('PATH', ''),
            'HOME': os.environ.get('HOME', ''),
            'USER': os.environ.get('USER', ''),
            'PYTHONPATH': '',  # Clear PYTHONPATH for security
        }
        
        # Add system-specific environment variables
        if platform.system() == 'Windows':
            safe_env.update({
                'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
                'TEMP': os.environ.get('TEMP', ''),
                'TMP': os.environ.get('TMP', ''),
            })
        
        self.logger.info(
            "Executing command",
            extra={
                'correlation_id': correlation_id,
                'command': ' '.join(cmd),
                'cwd': str(cwd) if cwd else None,
                'timeout': timeout
            }
        )
        
        try:
            # Create process with security constraints
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=safe_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,  # Never use shell=True for security
                preexec_fn=None,  # Don't allow custom preexec functions
            )
            
            with self._lock:
                self._active_processes.append(process)
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                returncode = process.returncode
                
                # Log execution result
                if returncode == 0:
                    self.logger.info(
                        "Command executed successfully",
                        extra={'correlation_id': correlation_id, 'returncode': returncode}
                    )
                else:
                    self.logger.error(
                        "Command execution failed",
                        extra={
                            'correlation_id': correlation_id, 
                            'returncode': returncode,
                            'stderr': stderr[:500]  # Limit error output
                        }
                    )
                
                return subprocess.CompletedProcess(
                    cmd, returncode, stdout, stderr
                )
                
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise InstallationError(f"Command timed out after {timeout} seconds")
                
        except FileNotFoundError:
            raise InstallationError(f"Command not found: {cmd[0]}")
        except PermissionError:
            raise InstallationError(f"Permission denied executing: {cmd[0]}")
        finally:
            with self._lock:
                if process in self._active_processes:
                    self._active_processes.remove(process)
    
    def cleanup_processes(self):
        """Clean up any remaining processes."""
        with self._lock:
            for process in self._active_processes[:]:
                try:
                    if process.poll() is None:  # Process still running
                        process.terminate()
                        process.wait(timeout=5)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                self._active_processes.remove(process)


class CrossPlatformInstaller:
    """Secure cross-platform installer for uv-based Python applications."""
    
    def __init__(
        self, 
        repo_url: str, 
        app_name: str, 
        python_version: str = "3.9",
        correlation_id: Optional[str] = None
    ):
        # Set up logging
        self.logger = setup_logging()
        
        # Generate correlation ID for tracking
        self.context = InstallationContext(
            correlation_id=correlation_id or self._generate_correlation_id(),
            start_time=time.time()
        )
        
        # Validate inputs
        SecurityValidator.validate_repository_url(repo_url)
        SecurityValidator.validate_app_name(app_name)
        
        self.repo_url = repo_url
        self.app_name = app_name
        self.python_version = python_version
        self.install_dir = self._get_default_install_dir()
        self.temp_dir: Optional[Path] = None
        self.cloned_repo_path: Optional[Path] = None
        
        # Initialize process manager
        self.process_manager = ProcessManager(self.logger)
        
        # Set up signal handlers for cleanup
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(
            "Installer initialized",
            extra={
                'correlation_id': self.context.correlation_id,
                'repo_url': repo_url,
                'app_name': app_name,
                'python_version': python_version
            }
        )
    
    def _generate_correlation_id(self) -> str:
        """Generate a unique correlation ID."""
        return hashlib.sha256(
            f"{time.time()}{os.getpid()}{id(self)}".encode()
        ).hexdigest()[:16]
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully."""
        self.logger.warn(
            f"Received signal {signum}, cleaning up...",
            extra={'correlation_id': self.context.correlation_id}
        )
        self.context.status = InstallationStatus.CANCELLED
        self.cleanup()
        sys.exit(1)
    
    def _get_default_install_dir(self) -> Path:
        """Get OS-appropriate default installation directory."""
        system = platform.system()
        
        if system == "Windows":
            base_dir = Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
        elif system == "Darwin":  # macOS
            base_dir = Path("/Applications")
        else:  # Linux and others
            if platformdirs:
                base_dir = Path(platformdirs.user_data_dir())
            else:
                base_dir = Path.home() / ".local" / "share"
        
        install_dir = base_dir / self.app_name
        SecurityValidator.validate_install_path(install_dir)
        
        return install_dir
    
    def check_python_version(self) -> bool:
        """Check if required Python version is available."""
        self.logger.info(
            f"Checking Python {self.python_version} availability",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        try:
            current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            required_parts = self.python_version.split('.')
            
            if len(required_parts) != 2:
                raise ValidationError("Invalid Python version format")
            
            required_major, required_minor = map(int, required_parts)
            current_major, current_minor = sys.version_info.major, sys.version_info.minor
            
            compatible = (current_major > required_major or 
                         (current_major == required_major and current_minor >= required_minor))
            
            if compatible:
                self.logger.info(
                    f"Python {current_version} meets requirement (>= {self.python_version})",
                    extra={'correlation_id': self.context.correlation_id}
                )
                return True
            else:
                self.logger.error(
                    f"Python {current_version} does not meet requirement (>= {self.python_version})",
                    extra={'correlation_id': self.context.correlation_id}
                )
                return False
                
        except Exception as e:
            self.logger.error(
                f"Error checking Python version: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def update_pip(self) -> bool:
        """Update pip to latest stable version."""
        self.logger.info(
            "Updating pip to latest version",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        try:
            result = self.process_manager.run_secure(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                correlation_id=self.context.correlation_id
            )
            
            if result.returncode == 0:
                self.logger.info(
                    "pip updated successfully",
                    extra={'correlation_id': self.context.correlation_id}
                )
                return True
            else:
                raise InstallationError(f"pip update failed: {result.stderr}")
                
        except Exception as e:
            self.logger.error(
                f"Failed to update pip: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def install_uv(self) -> bool:
        """Install uv package manager."""
        self.logger.info(
            "Installing uv package manager",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        try:
            result = self.process_manager.run_secure(
                [sys.executable, "-m", "pip", "install", "uv"],
                correlation_id=self.context.correlation_id
            )
            
            if result.returncode == 0:
                self.logger.info(
                    "uv installed successfully",
                    extra={'correlation_id': self.context.correlation_id}
                )
                return True
            else:
                raise InstallationError(f"uv installation failed: {result.stderr}")
                
        except Exception as e:
            self.logger.error(
                f"Failed to install uv: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def clone_repository(self) -> bool:
        """Clone the repository securely."""
        self.logger.info(
            f"Cloning repository: {self.repo_url}",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        try:
            self.temp_dir = Path(tempfile.mkdtemp(prefix='uv_installer_'))
            self.cloned_repo_path = self.temp_dir / "repo"
            
            if git:
                # Use GitPython with security constraints
                repo = git.Repo.clone_from(
                    self.repo_url, 
                    str(self.cloned_repo_path),
                    depth=1,  # Shallow clone for security
                    single_branch=True
                )
                
                # Verify repository integrity
                if not (self.cloned_repo_path / '.git').exists():
                    raise SecurityError("Repository verification failed")
                    
            else:
                # Fallback to subprocess with security constraints
                result = self.process_manager.run_secure(
                    ["git", "clone", "--depth", "1", self.repo_url, str(self.cloned_repo_path)],
                    correlation_id=self.context.correlation_id,
                    timeout=600  # 10 minute timeout for clone
                )
                
                if result.returncode != 0:
                    raise InstallationError(f"Git clone failed: {result.stderr}")
            
            self.logger.info(
                "Repository cloned successfully",
                extra={'correlation_id': self.context.correlation_id}
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"Failed to clone repository: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def build_project(self) -> bool:
        """Build the project using uv."""
        self.logger.info(
            "Building project with uv",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        if not self.cloned_repo_path or not self.cloned_repo_path.exists():
            self.logger.error(
                "No cloned repository found",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
        
        try:
            # Verify project structure
            if not (self.cloned_repo_path / 'pyproject.toml').exists():
                self.logger.warn(
                    "No pyproject.toml found, project may not be uv-compatible",
                    extra={'correlation_id': self.context.correlation_id}
                )
            
            # Run uv sync
            self.logger.debug(
                "Running uv sync",
                extra={'correlation_id': self.context.correlation_id}
            )
            
            result = self.process_manager.run_secure(
                ["uv", "sync"],
                cwd=self.cloned_repo_path,
                correlation_id=self.context.correlation_id,
                timeout=600
            )
            
            if result.returncode != 0:
                raise InstallationError(f"uv sync failed: {result.stderr}")
            
            # Run uv pip install -e .
            self.logger.debug(
                "Installing package in development mode",
                extra={'correlation_id': self.context.correlation_id}
            )
            
            result = self.process_manager.run_secure(
                ["uv", "pip", "install", "-e", "."],
                cwd=self.cloned_repo_path,
                correlation_id=self.context.correlation_id,
                timeout=600
            )
            
            if result.returncode != 0:
                raise InstallationError(f"uv pip install failed: {result.stderr}")
            
            self.logger.info(
                "Project built successfully",
                extra={'correlation_id': self.context.correlation_id}
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"Failed to build project: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def choose_install_directory(self) -> bool:
        """Let user choose installation directory via file dialog."""
        try:
            self.logger.info(
                "Presenting directory selection dialog",
                extra={'correlation_id': self.context.correlation_id}
            )
            
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            
            selected_dir = filedialog.askdirectory(
                title=f"Choose installation directory for {self.app_name}",
                initialdir=str(self.install_dir.parent)
            )
            
            if selected_dir:
                proposed_dir = Path(selected_dir) / self.app_name
                SecurityValidator.validate_install_path(proposed_dir)
                self.install_dir = proposed_dir
                
                self.logger.info(
                    f"Installation directory set to: {self.install_dir}",
                    extra={'correlation_id': self.context.correlation_id}
                )
            else:
                self.logger.info(
                    f"Using default installation directory: {self.install_dir}",
                    extra={'correlation_id': self.context.correlation_id}
                )
            
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error with directory selection: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return True  # Continue with default
    
    def move_to_install_directory(self) -> bool:
        """Move cloned repository to installation directory."""
        self.logger.info(
            f"Moving application to: {self.install_dir}",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        try:
            # Create parent directory if it doesn't exist
            self.install_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # Remove existing installation if it exists
            if self.install_dir.exists():
                self.logger.warn(
                    f"Removing existing installation at {self.install_dir}",
                    extra={'correlation_id': self.context.correlation_id}
                )
                shutil.rmtree(self.install_dir)
            
            # Move the cloned repository
            shutil.move(str(self.cloned_repo_path), str(self.install_dir))
            
            self.logger.info(
                "Application moved to installation directory successfully",
                extra={'correlation_id': self.context.correlation_id}
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"Failed to move application: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def create_shortcuts(self) -> bool:
        """Create OS-appropriate shortcuts."""
        self.logger.info(
            "Creating application shortcuts",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        system = platform.system()
        
        try:
            if system == "Windows":
                return self._create_windows_shortcuts()
            elif system == "Darwin":
                return self._create_macos_shortcuts()
            else:
                return self._create_linux_shortcuts()
                
        except Exception as e:
            self.logger.error(
                f"Failed to create shortcuts: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def _create_windows_shortcuts(self) -> bool:
        """Create Windows shortcuts."""
        try:
            main_script = self._find_main_executable()
            if not main_script:
                self.logger.warn(
                    "Could not find main executable for shortcuts",
                    extra={'correlation_id': self.context.correlation_id}
                )
                return False
            
            if winshell:
                # Create desktop shortcut
                desktop = winshell.desktop()
                shortcut_path = os.path.join(desktop, f"{self.app_name}.lnk")
                with winshell.shortcut(shortcut_path) as shortcut:
                    shortcut.path = sys.executable
                    shortcut.arguments = str(main_script)
                    shortcut.working_directory = str(self.install_dir)
                
                # Create start menu shortcut
                start_menu = winshell.start_menu()
                start_shortcut_path = os.path.join(start_menu, f"{self.app_name}.lnk")
                with winshell.shortcut(start_shortcut_path) as shortcut:
                    shortcut.path = sys.executable
                    shortcut.arguments = str(main_script)
                    shortcut.working_directory = str(self.install_dir)
                
                self.logger.info(
                    "Windows shortcuts created successfully",
                    extra={'correlation_id': self.context.correlation_id}
                )
                return True
            else:
                self.logger.warn(
                    "winshell not available, skipping shortcut creation",
                    extra={'correlation_id': self.context.correlation_id}
                )
                return True
                
        except Exception as e:
            self.logger.error(
                f"Error creating Windows shortcuts: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def _create_macos_shortcuts(self) -> bool:
        """Create macOS app bundle."""
        try:
            main_script = self._find_main_executable()
            if not main_script:
                return False
            
            # Create app bundle
            apps_dir = Path.home() / "Applications"
            apps_dir.mkdir(exist_ok=True)
            
            app_path = apps_dir / f"{self.app_name}.app"
            if app_path.exists():
                shutil.rmtree(app_path)
            
            # Create app bundle structure
            contents_dir = app_path / "Contents"
            macos_dir = contents_dir / "MacOS"
            macos_dir.mkdir(parents=True)
            
            # Create executable script
            executable_path = macos_dir / self.app_name
            with open(executable_path, 'w') as f:
                f.write(f"""#!/bin/bash
cd "{self.install_dir}"
"{sys.executable}" "{main_script}"
""")
            executable_path.chmod(0o755)
            
            # Create Info.plist
            info_plist = contents_dir / "Info.plist"
            with open(info_plist, 'w') as f:
                f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>{self.app_name}</string>
    <key>CFBundleIdentifier</key>
    <string>com.{self.app_name.lower()}.app</string>
    <key>CFBundleName</key>
    <string>{self.app_name}</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>""")
            
            self.logger.info(
                "macOS app bundle created successfully",
                extra={'correlation_id': self.context.correlation_id}
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error creating macOS shortcuts: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def _create_linux_shortcuts(self) -> bool:
        """Create Linux desktop shortcuts."""
        try:
            main_script = self._find_main_executable()
            if not main_script:
                return False
            
            # Create .desktop file content
            desktop_content = f"""[Desktop Entry]
Name={self.app_name}
Comment=Installed via uv installer
Exec={sys.executable} {main_script}
Path={self.install_dir}
Terminal=false
Type=Application
Categories=Utility;
"""
            
            # Save to user's applications directory
            apps_dir = Path.home() / ".local" / "share" / "applications"
            apps_dir.mkdir(parents=True, exist_ok=True)
            
            desktop_file_path = apps_dir / f"{self.app_name.lower()}.desktop"
            with open(desktop_file_path, 'w') as f:
                f.write(desktop_content)
            desktop_file_path.chmod(0o755)
            
            # Also create on desktop if Desktop directory exists
            desktop_dir = Path.home() / "Desktop"
            if desktop_dir.exists():
                desktop_shortcut = desktop_dir / f"{self.app_name}.desktop"
                with open(desktop_shortcut, 'w') as f:
                    f.write(desktop_content)
                desktop_shortcut.chmod(0o755)
            
            self.logger.info(
                "Linux shortcuts created successfully",
                extra={'correlation_id': self.context.correlation_id}
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error creating Linux shortcuts: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
    
    def _find_main_executable(self) -> Optional[Path]:
        """Find the main executable or entry point."""
        # Look for common entry point patterns
        possible_mains = [
            self.install_dir / "main.py",
            self.install_dir / f"{self.app_name}.py",
            self.install_dir / "__main__.py",
            self.install_dir / "src" / "main.py",
            self.install_dir / "src" / f"{self.app_name}" / "__main__.py",
        ]
        
        for main_file in possible_mains:
            if main_file.exists():
                self.logger.debug(
                    f"Found main executable: {main_file}",
                    extra={'correlation_id': self.context.correlation_id}
                )
                return main_file
        
        # Try to parse pyproject.toml for entry points
        pyproject_file = self.install_dir / "pyproject.toml"
        if pyproject_file.exists():
            try:
                import tomllib
                with open(pyproject_file, 'rb') as f:
                    data = tomllib.load(f)
                    scripts = data.get('project', {}).get('scripts', {})
                    if scripts:
                        # Return a default main.py as fallback
                        return self.install_dir / "main.py"
            except Exception as e:
                self.logger.debug(
                    f"Could not parse pyproject.toml: {e}",
                    extra={'correlation_id': self.context.correlation_id}
                )
        
        # Default fallback
        return self.install_dir / "main.py"
    
    def show_completion_message(self):
        """Show installation completion message."""
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                "Installation Complete",
                f"{self.app_name} has been successfully installed!\n\n"
                f"Installation directory: {self.install_dir}\n"
                f"Shortcuts have been created for easy access."
            )
        except Exception as e:
            self.logger.info(
                f"Installation completed successfully! Directory: {self.install_dir}",
                extra={'correlation_id': self.context.correlation_id}
            )
    
    def cleanup(self):
        """Clean up temporary files and processes."""
        self.logger.info(
            "Performing cleanup",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        # Clean up processes
        self.process_manager.cleanup_processes()
        
        # Clean up temporary directory
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                self.logger.debug(
                    "Temporary directory cleaned up",
                    extra={'correlation_id': self.context.correlation_id}
                )
            except Exception as e:
                self.logger.warn(
                    f"Could not clean up temporary directory: {e}",
                    extra={'correlation_id': self.context.correlation_id}
                )
    
    def install(self) -> bool:
        """Run the complete installation process."""
        self.context.status = InstallationStatus.RUNNING
        
        self.logger.info(
            f"Starting installation of {self.app_name}",
            extra={'correlation_id': self.context.correlation_id}
        )
        
        try:
            installation_steps = [
                ("Checking Python version", self.check_python_version),
                ("Updating pip", self.update_pip),
                ("Installing uv", self.install_uv),
                ("Cloning repository", self.clone_repository),
                ("Building project", self.build_project),
                ("Choosing install directory", self.choose_install_directory),
                ("Moving to install directory", self.move_to_install_directory),
                ("Creating shortcuts", self.create_shortcuts),
            ]
            
            for step_name, step_func in installation_steps:
                self.logger.info(
                    f"Executing step: {step_name}",
                    extra={'correlation_id': self.context.correlation_id}
                )
                
                if not step_func():
                    self.context.status = InstallationStatus.FAILED
                    self.logger.error(
                        f"Installation failed at step: {step_name}",
                        extra={'correlation_id': self.context.correlation_id}
                    )
                    return False
            
            self.context.status = InstallationStatus.SUCCESS
            
            # Calculate installation time
            install_time = time.time() - self.context.start_time
            
            self.logger.info(
                f"Installation completed successfully in {install_time:.2f} seconds",
                extra={
                    'correlation_id': self.context.correlation_id,
                    'install_time_seconds': install_time,
                    'status': self.context.status.value
                }
            )
            
            self.show_completion_message()
            return True
            
        except Exception as e:
            self.context.status = InstallationStatus.FAILED
            self.logger.error(
                f"Unexpected error during installation: {e}",
                extra={'correlation_id': self.context.correlation_id}
            )
            return False
            
        finally:
            self.cleanup()


def main():
    """Main entry point for the installer."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Secure cross-platform installer for uv-based Python applications"
    )
    parser.add_argument("repo_url", help="Repository URL to clone and install")
    parser.add_argument("app_name", help="Name of the application")
    parser.add_argument("--python-version", default="3.9", help="Minimum required Python version")
    parser.add_argument("--correlation-id", help="Correlation ID for tracking")
    parser.add_argument("--log-level", choices=['DEBUG', 'INFO', 'WARN', 'ERROR'], 
                       default='INFO', help="Logging level")
    parser.add_argument("--gui", action="store_true", help="Launch graphical installation wizard")
    parser.add_argument("--install-dir", help="Custom installation directory")
    parser.add_argument("--no-shortcuts", action="store_true", help="Skip creating shortcuts")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger('uv_cross_installer').setLevel(getattr(logging, args.log_level))
    
    try:
        if args.gui:
            # Launch GUI wizard
            try:
                from .gui import create_installation_wizard
                create_installation_wizard(
                    installer_class=CrossPlatformInstaller,
                    repo_url=args.repo_url,
                    app_name=args.app_name,
                    python_version=args.python_version
                )
                sys.exit(0)
            except ImportError as e:
                print(f"GUI mode not available: {e}", file=sys.stderr)
                print("Falling back to command-line mode...", file=sys.stderr)
                # Fall through to command-line mode
        
        # Command-line installation
        installer = CrossPlatformInstaller(
            repo_url=args.repo_url,
            app_name=args.app_name,
            python_version=args.python_version,
            correlation_id=args.correlation_id
        )
        
        # Apply command-line options
        if args.install_dir:
            try:
                SecurityValidator.validate_install_path(Path(args.install_dir))
                installer.install_dir = Path(args.install_dir)
            except (ValidationError, SecurityError) as e:
                print(f"Invalid install directory: {e}", file=sys.stderr)
                sys.exit(2)
        
        # Override shortcut creation if requested
        if args.no_shortcuts:
            installer._create_shortcuts_original = installer.create_shortcuts
            installer.create_shortcuts = lambda: True  # Skip shortcuts
        
        # Show installation summary
        print(f"\n{installer.app_name} Installation")
        print("=" * 50)
        print(f"Repository: {installer.repo_url}")
        print(f"Install Directory: {installer.install_dir}")
        print(f"Python Version: {installer.python_version}+")
        print(f"Create Shortcuts: {'No' if args.no_shortcuts else 'Yes'}")
        print("=" * 50)
        
        # Ask for confirmation in interactive mode
        if sys.stdin.isatty():
            response = input("\nProceed with installation? [Y/n]: ").strip().lower()
            if response and response not in ['y', 'yes']:
                print("Installation cancelled by user.")
                sys.exit(0)
        
        success = installer.install()
        sys.exit(0 if success else 1)
        
    except (ValidationError, SecurityError) as e:
        print(f"Validation/Security Error: {e}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nInstallation cancelled by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 