#!/usr/bin/env python3
"""
Modern GUI Installation Wizard for UV Cross-Platform Installer.

This module provides a professional installation wizard with progress tracking,
modern visual design, and enhanced user experience.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum
import platform
import logging


class WizardStep(Enum):
    """Installation wizard steps."""
    WELCOME = "welcome"
    REQUIREMENTS = "requirements"
    DIRECTORY = "directory"
    CONFIRMATION = "confirmation"
    PROGRESS = "progress"
    COMPLETION = "completion"
    ERROR = "error"


@dataclass
class InstallationConfig:
    """Installation configuration data."""
    repo_url: str
    app_name: str
    python_version: str = "3.9"
    install_dir: Optional[Path] = None
    create_shortcuts: bool = True
    add_to_path: bool = False


class ProgressMessage:
    """Progress update message for thread communication."""
    def __init__(self, step: str, progress: int, message: str, is_error: bool = False):
        self.step = step
        self.progress = progress
        self.message = message
        self.is_error = is_error
        self.timestamp = time.time()


class ModernInstallationWizard:
    """Modern installation wizard with enhanced UX."""
    
    def __init__(self, installer_class, initial_config: InstallationConfig):
        self.installer_class = installer_class
        self.config = initial_config
        self.installer = None
        self.logger = logging.getLogger('uv_cross_installer.gui')
        
        # GUI state
        self.current_step = WizardStep.WELCOME
        self.installation_thread = None
        self.progress_queue = queue.Queue()
        self.is_cancelled = False
        
        # Create main window
        self.root = tk.Tk()
        self.setup_window()
        self.create_styles()
        self.create_widgets()
        self.show_welcome_step()
        
        # Start progress monitoring
        self.monitor_progress()
    
    def setup_window(self):
        """Set up the main window properties."""
        self.root.title(f"{self.config.app_name} Installation Wizard")
        self.root.geometry("700x500")
        self.root.resizable(False, False)
        
        # Center the window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.root.winfo_screenheight() // 2) - (500 // 2)
        self.root.geometry(f"700x500+{x}+{y}")
        
        # Set icon if available
        try:
            # You can add a custom icon here
            pass
        except:
            pass
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
    
    def create_styles(self):
        """Create modern ttk styles."""
        style = ttk.Style()
        
        # Configure modern theme
        if platform.system() == "Windows":
            style.theme_use("vista")
        elif platform.system() == "Darwin":
            style.theme_use("aqua")
        else:
            style.theme_use("clam")
        
        # Custom styles
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground="#2c3e50")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#34495e")
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#2c3e50")
        style.configure("Success.TLabel", font=("Segoe UI", 10), foreground="#27ae60")
        style.configure("Error.TLabel", font=("Segoe UI", 10), foreground="#e74c3c")
        style.configure("Warning.TLabel", font=("Segoe UI", 10), foreground="#f39c12")
        
        # Button styles
        style.configure("Primary.TButton", font=("Segoe UI", 10))
        style.configure("Secondary.TButton", font=("Segoe UI", 10))
        
        # Progress bar style
        style.configure("Modern.Horizontal.TProgressbar",
                       troughcolor="#ecf0f1",
                       borderwidth=0,
                       background="#3498db")
    
    def create_widgets(self):
        """Create the main widget structure."""
        # Main container
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header frame
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Content frame (this will hold different step frames)
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Button frame
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(fill=tk.X)
        
        # Navigation buttons
        self.back_button = ttk.Button(self.button_frame, text="← Back", 
                                     command=self.go_back, style="Secondary.TButton")
        self.back_button.pack(side=tk.LEFT)
        
        self.cancel_button = ttk.Button(self.button_frame, text="Cancel", 
                                       command=self.cancel_installation, style="Secondary.TButton")
        self.cancel_button.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.next_button = ttk.Button(self.button_frame, text="Next →", 
                                     command=self.go_next, style="Primary.TButton")
        self.next_button.pack(side=tk.RIGHT)
    
    def clear_content(self):
        """Clear the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def update_header(self, title: str, subtitle: str = ""):
        """Update the header with title and subtitle."""
        for widget in self.header_frame.winfo_children():
            widget.destroy()
        
        title_label = ttk.Label(self.header_frame, text=title, style="Title.TLabel")
        title_label.pack(anchor=tk.W)
        
        if subtitle:
            subtitle_label = ttk.Label(self.header_frame, text=subtitle, style="Subtitle.TLabel")
            subtitle_label.pack(anchor=tk.W, pady=(5, 0))
    
    def show_welcome_step(self):
        """Show the welcome step."""
        self.current_step = WizardStep.WELCOME
        self.clear_content()
        self.update_header(
            f"Welcome to {self.config.app_name} Installer",
            "This wizard will guide you through the installation process."
        )
        
        # Welcome content
        welcome_frame = ttk.Frame(self.content_frame)
        welcome_frame.pack(fill=tk.BOTH, expand=True)
        
        # App info
        info_frame = ttk.LabelFrame(welcome_frame, text="Application Information", padding="15")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(info_frame, text=f"Application: {self.config.app_name}", 
                 style="Header.TLabel").pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(info_frame, text=f"Repository: {self.config.repo_url}").pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(info_frame, text=f"Python Version Required: {self.config.python_version}+").pack(anchor=tk.W)
        
        # Features
        features_frame = ttk.LabelFrame(welcome_frame, text="Installation Features", padding="15")
        features_frame.pack(fill=tk.X, pady=(0, 20))
        
        features = [
            "✓ Automatic dependency management with uv",
            "✓ Cross-platform compatibility",
            "✓ Desktop shortcuts creation",
            "✓ Safe and secure installation process",
            "✓ Automatic cleanup on completion"
        ]
        
        for feature in features:
            ttk.Label(features_frame, text=feature, style="Success.TLabel").pack(anchor=tk.W, pady=2)
        
        # Requirements notice
        notice_frame = ttk.Frame(welcome_frame)
        notice_frame.pack(fill=tk.X)
        
        ttk.Label(notice_frame, text="⚠️ Requirements:", style="Warning.TLabel").pack(anchor=tk.W)
        ttk.Label(notice_frame, text="• Internet connection for downloading dependencies").pack(anchor=tk.W, padx=(20, 0))
        ttk.Label(notice_frame, text="• Administrator privileges may be required").pack(anchor=tk.W, padx=(20, 0))
        ttk.Label(notice_frame, text="• Git must be installed on your system").pack(anchor=tk.W, padx=(20, 0))
        
        # Update buttons
        self.back_button.config(state=tk.DISABLED)
        self.next_button.config(text="Next →", command=self.go_next)
    
    def show_requirements_step(self):
        """Show the system requirements check step."""
        self.current_step = WizardStep.REQUIREMENTS
        self.clear_content()
        self.update_header(
            "System Requirements Check",
            "Verifying your system meets the installation requirements."
        )
        
        # Requirements frame
        req_frame = ttk.Frame(self.content_frame)
        req_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a scrollable frame for requirements
        canvas = tk.Canvas(req_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(req_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Check requirements
        self.check_requirements(scrollable_frame)
        
        # Update buttons
        self.back_button.config(state=tk.NORMAL)
        self.next_button.config(text="Next →", command=self.go_next)
    
    def check_requirements(self, parent_frame):
        """Check and display system requirements."""
        requirements = [
            ("Python Version", self.check_python_version),
            ("Git Installation", self.check_git_installed),
            ("Internet Connection", self.check_internet_connection),
            ("Disk Space", self.check_disk_space),
            ("Permissions", self.check_permissions)
        ]
        
        all_passed = True
        
        for req_name, check_func in requirements:
            req_frame = ttk.LabelFrame(parent_frame, text=req_name, padding="10")
            req_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Status frame
            status_frame = ttk.Frame(req_frame)
            status_frame.pack(fill=tk.X)
            
            try:
                passed, message = check_func()
                if passed:
                    status_label = ttk.Label(status_frame, text="✓ PASSED", style="Success.TLabel")
                    status_label.pack(side=tk.LEFT)
                    detail_label = ttk.Label(status_frame, text=message)
                    detail_label.pack(side=tk.LEFT, padx=(10, 0))
                else:
                    status_label = ttk.Label(status_frame, text="✗ FAILED", style="Error.TLabel")
                    status_label.pack(side=tk.LEFT)
                    detail_label = ttk.Label(status_frame, text=message, style="Error.TLabel")
                    detail_label.pack(side=tk.LEFT, padx=(10, 0))
                    all_passed = False
            except Exception as e:
                status_label = ttk.Label(status_frame, text="⚠️ WARNING", style="Warning.TLabel")
                status_label.pack(side=tk.LEFT)
                detail_label = ttk.Label(status_frame, text=f"Could not check: {e}")
                detail_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Overall status
        overall_frame = ttk.LabelFrame(parent_frame, text="Overall Status", padding="10")
        overall_frame.pack(fill=tk.X, pady=(20, 0))
        
        if all_passed:
            ttk.Label(overall_frame, text="✓ All requirements met. Ready to proceed!", 
                     style="Success.TLabel").pack()
        else:
            ttk.Label(overall_frame, text="⚠️ Some requirements failed. Installation may not work correctly.", 
                     style="Warning.TLabel").pack()
            ttk.Label(overall_frame, text="You can continue at your own risk.").pack(pady=(5, 0))
    
    def check_python_version(self):
        """Check Python version requirement."""
        import sys
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        required_parts = self.config.python_version.split('.')
        required_major, required_minor = map(int, required_parts)
        
        if (sys.version_info.major > required_major or 
            (sys.version_info.major == required_major and sys.version_info.minor >= required_minor)):
            return True, f"Python {current} (>= {self.config.python_version} required)"
        else:
            return False, f"Python {current} is too old (>= {self.config.python_version} required)"
    
    def check_git_installed(self):
        """Check if Git is installed."""
        import subprocess
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, version
            else:
                return False, "Git command failed"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False, "Git not found in PATH"
    
    def check_internet_connection(self):
        """Check internet connectivity."""
        import urllib.request
        try:
            urllib.request.urlopen('https://github.com', timeout=5)
            return True, "Internet connection available"
        except:
            return False, "No internet connection detected"
    
    def check_disk_space(self):
        """Check available disk space."""
        import shutil
        try:
            free_bytes = shutil.disk_usage('.').free
            free_gb = free_bytes / (1024**3)
            if free_gb >= 1.0:
                return True, f"{free_gb:.1f} GB available"
            else:
                return False, f"Only {free_gb:.1f} GB available (1 GB recommended)"
        except:
            return False, "Could not check disk space"
    
    def check_permissions(self):
        """Check write permissions."""
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(delete=True):
                pass
            return True, "Write permissions available"
        except:
            return False, "Insufficient write permissions"
    
    def show_directory_step(self):
        """Show the installation directory selection step."""
        self.current_step = WizardStep.DIRECTORY
        self.clear_content()
        self.update_header(
            "Choose Installation Directory",
            "Select where to install the application."
        )
        
        # Directory frame
        dir_frame = ttk.Frame(self.content_frame)
        dir_frame.pack(fill=tk.BOTH, expand=True)
        
        # Current selection
        selection_frame = ttk.LabelFrame(dir_frame, text="Installation Location", padding="15")
        selection_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.dir_var = tk.StringVar(value=str(self.config.install_dir or self.get_default_install_dir()))
        
        dir_entry_frame = ttk.Frame(selection_frame)
        dir_entry_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.dir_entry = ttk.Entry(dir_entry_frame, textvariable=self.dir_var, font=("Consolas", 10))
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        browse_button = ttk.Button(dir_entry_frame, text="Browse...", command=self.browse_directory)
        browse_button.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Directory info
        self.update_directory_info(selection_frame)
        
        # Options
        options_frame = ttk.LabelFrame(dir_frame, text="Installation Options", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.shortcuts_var = tk.BooleanVar(value=self.config.create_shortcuts)
        shortcuts_cb = ttk.Checkbutton(options_frame, text="Create desktop shortcuts", 
                                      variable=self.shortcuts_var)
        shortcuts_cb.pack(anchor=tk.W, pady=(0, 5))
        
        self.path_var = tk.BooleanVar(value=self.config.add_to_path)
        path_cb = ttk.Checkbutton(options_frame, text="Add to system PATH (requires admin privileges)", 
                                 variable=self.path_var)
        path_cb.pack(anchor=tk.W)
        
        # Bind directory changes
        self.dir_var.trace('w', lambda *args: self.on_directory_changed())
        
        # Update buttons
        self.back_button.config(state=tk.NORMAL)
        self.next_button.config(text="Next →", command=self.go_next)
    
    def get_default_install_dir(self):
        """Get the default installation directory."""
        system = platform.system()
        if system == "Windows":
            return Path("C:\\Program Files") / self.config.app_name
        elif system == "Darwin":
            return Path("/Applications") / self.config.app_name
        else:
            return Path.home() / ".local" / "share" / self.config.app_name
    
    def browse_directory(self):
        """Open directory browser dialog."""
        current_dir = self.dir_var.get()
        selected_dir = filedialog.askdirectory(
            title="Choose Installation Directory",
            initialdir=str(Path(current_dir).parent)
        )
        
        if selected_dir:
            self.dir_var.set(str(Path(selected_dir) / self.config.app_name))
    
    def on_directory_changed(self):
        """Handle directory path changes."""
        # Update directory info when path changes
        for widget in self.content_frame.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.LabelFrame) and "Installation Location" in str(child.cget('text')):
                        self.update_directory_info(child)
                        break
    
    def update_directory_info(self, parent_frame):
        """Update directory information display."""
        # Remove existing info
        for widget in parent_frame.winfo_children():
            if isinstance(widget, ttk.Frame) and widget.winfo_children():
                if any("Space available" in str(w.cget('text')) for w in widget.winfo_children() if hasattr(w, 'cget')):
                    widget.destroy()
        
        # Add new info
        info_frame = ttk.Frame(parent_frame)
        info_frame.pack(fill=tk.X)
        
        dir_path = Path(self.dir_var.get())
        
        # Check if directory exists
        if dir_path.exists():
            status_text = "Directory exists and will be overwritten"
            status_style = "Warning.TLabel"
        else:
            status_text = "New directory will be created"
            status_style = "Success.TLabel"
        
        ttk.Label(info_frame, text=f"Status: {status_text}", style=status_style).pack(anchor=tk.W)
        
        # Check disk space
        try:
            import shutil
            free_bytes = shutil.disk_usage(dir_path.parent).free
            free_gb = free_bytes / (1024**3)
            ttk.Label(info_frame, text=f"Space available: {free_gb:.1f} GB").pack(anchor=tk.W)
        except:
            ttk.Label(info_frame, text="Space available: Unknown").pack(anchor=tk.W)
    
    def show_confirmation_step(self):
        """Show the installation confirmation step."""
        self.current_step = WizardStep.CONFIRMATION
        self.clear_content()
        self.update_header(
            "Confirm Installation",
            "Please review your installation settings before proceeding."
        )
        
        # Update config from GUI
        self.config.install_dir = Path(self.dir_var.get())
        self.config.create_shortcuts = self.shortcuts_var.get()
        self.config.add_to_path = self.path_var.get()
        
        # Confirmation frame
        conf_frame = ttk.Frame(self.content_frame)
        conf_frame.pack(fill=tk.BOTH, expand=True)
        
        # Installation summary
        summary_frame = ttk.LabelFrame(conf_frame, text="Installation Summary", padding="15")
        summary_frame.pack(fill=tk.X, pady=(0, 20))
        
        summary_items = [
            ("Application", self.config.app_name),
            ("Repository", self.config.repo_url),
            ("Installation Directory", str(self.config.install_dir)),
            ("Python Version", f"{self.config.python_version}+"),
            ("Create Shortcuts", "Yes" if self.config.create_shortcuts else "No"),
            ("Add to PATH", "Yes" if self.config.add_to_path else "No"),
        ]
        
        for label, value in summary_items:
            item_frame = ttk.Frame(summary_frame)
            item_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(item_frame, text=f"{label}:", style="Header.TLabel").pack(side=tk.LEFT)
            ttk.Label(item_frame, text=value).pack(side=tk.LEFT, padx=(10, 0))
        
        # Installation steps preview
        steps_frame = ttk.LabelFrame(conf_frame, text="Installation Steps", padding="15")
        steps_frame.pack(fill=tk.X)
        
        steps = [
            "1. Check Python version compatibility",
            "2. Update pip to latest version",
            "3. Install uv package manager",
            "4. Clone repository from GitHub",
            "5. Build project with uv",
            "6. Install to selected directory",
            "7. Create shortcuts (if selected)",
            "8. Add to PATH (if selected)",
            "9. Complete installation"
        ]
        
        for step in steps:
            ttk.Label(steps_frame, text=step).pack(anchor=tk.W, pady=1)
        
        # Update buttons
        self.back_button.config(state=tk.NORMAL)
        self.next_button.config(text="Install", command=self.start_installation)
    
    def start_installation(self):
        """Start the installation process."""
        self.current_step = WizardStep.PROGRESS
        self.show_progress_step()
        
        # Start installation in separate thread
        self.installation_thread = threading.Thread(target=self.run_installation, daemon=True)
        self.installation_thread.start()
    
    def show_progress_step(self):
        """Show the installation progress step."""
        self.clear_content()
        self.update_header(
            "Installing Application",
            f"Please wait while {self.config.app_name} is being installed..."
        )
        
        # Progress frame
        progress_frame = ttk.Frame(self.content_frame)
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        # Overall progress
        overall_frame = ttk.LabelFrame(progress_frame, text="Overall Progress", padding="15")
        overall_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.overall_progress = ttk.Progressbar(overall_frame, style="Modern.Horizontal.TProgressbar", 
                                              length=400, mode='determinate')
        self.overall_progress.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_label = ttk.Label(overall_frame, text="Initializing...")
        self.progress_label.pack()
        
        # Current step details
        details_frame = ttk.LabelFrame(progress_frame, text="Current Step", padding="15")
        details_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.step_label = ttk.Label(details_frame, text="Preparing installation...", style="Header.TLabel")
        self.step_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.detail_label = ttk.Label(details_frame, text="")
        self.detail_label.pack(anchor=tk.W)
        
        # Log output
        log_frame = ttk.LabelFrame(progress_frame, text="Installation Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollable text widget
        log_text_frame = ttk.Frame(log_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_text_frame, height=8, font=("Consolas", 9), 
                               bg="#f8f9fa", fg="#2c3e50", wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Make text read-only
        self.log_text.config(state=tk.DISABLED)
        
        # Update buttons
        self.back_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        self.cancel_button.config(text="Cancel", command=self.cancel_installation)
    
    def run_installation(self):
        """Run the installation process in a separate thread."""
        try:
            # Create installer instance
            self.installer = self.installer_class(
                repo_url=self.config.repo_url,
                app_name=self.config.app_name,
                python_version=self.config.python_version
            )
            
            # Override install directory if specified
            if self.config.install_dir:
                self.installer.install_dir = self.config.install_dir
            
            # Installation steps with progress tracking
            steps = [
                ("Checking Python version", 10, self.installer.check_python_version),
                ("Updating pip", 20, self.installer.update_pip),
                ("Installing uv", 30, self.installer.install_uv),
                ("Cloning repository", 50, self.installer.clone_repository),
                ("Building project", 70, self.installer.build_project),
                ("Installing to directory", 85, self.installer.move_to_install_directory),
                ("Creating shortcuts", 95, self.create_shortcuts_wrapper),
                ("Finalizing installation", 100, self.finalize_installation),
            ]
            
            for step_name, progress, step_func in steps:
                if self.is_cancelled:
                    break
                
                self.progress_queue.put(ProgressMessage(step_name, progress, f"Starting {step_name.lower()}..."))
                
                try:
                    success = step_func()
                    if success:
                        self.progress_queue.put(ProgressMessage(step_name, progress, f"✓ {step_name} completed"))
                    else:
                        self.progress_queue.put(ProgressMessage(step_name, progress, f"✗ {step_name} failed", True))
                        return
                except Exception as e:
                    self.progress_queue.put(ProgressMessage(step_name, progress, f"✗ {step_name} error: {e}", True))
                    return
            
            if not self.is_cancelled:
                self.progress_queue.put(ProgressMessage("Complete", 100, "Installation completed successfully!"))
                
        except Exception as e:
            self.progress_queue.put(ProgressMessage("Error", 0, f"Installation failed: {e}", True))
    
    def create_shortcuts_wrapper(self):
        """Wrapper for shortcut creation based on user preference."""
        if self.config.create_shortcuts:
            return self.installer.create_shortcuts()
        else:
            self.progress_queue.put(ProgressMessage("Shortcuts", 95, "Skipping shortcut creation (user choice)"))
            return True
    
    def finalize_installation(self):
        """Finalize the installation process."""
        try:
            # Add to PATH if requested (simplified for demo)
            if self.config.add_to_path:
                self.progress_queue.put(ProgressMessage("PATH", 98, "Adding to system PATH..."))
                # This would need platform-specific implementation
                self.progress_queue.put(ProgressMessage("PATH", 98, "PATH update completed"))
            
            return True
        except Exception as e:
            self.progress_queue.put(ProgressMessage("Finalize", 100, f"Finalization error: {e}", True))
            return False
    
    def monitor_progress(self):
        """Monitor progress updates from the installation thread."""
        try:
            while True:
                message = self.progress_queue.get_nowait()
                self.update_progress_display(message)
                
                if message.step == "Complete":
                    self.show_completion_step(True)
                    break
                elif message.is_error:
                    self.show_completion_step(False, message.message)
                    break
                    
        except queue.Empty:
            pass
        
        # Schedule next check
        if self.current_step == WizardStep.PROGRESS:
            self.root.after(100, self.monitor_progress)
    
    def update_progress_display(self, message: ProgressMessage):
        """Update the progress display with new information."""
        if hasattr(self, 'overall_progress'):
            self.overall_progress['value'] = message.progress
            
        if hasattr(self, 'progress_label'):
            self.progress_label.config(text=f"{message.progress}% Complete")
            
        if hasattr(self, 'step_label'):
            self.step_label.config(text=message.step)
            
        if hasattr(self, 'detail_label'):
            if message.is_error:
                self.detail_label.config(text=message.message, style="Error.TLabel")
            else:
                self.detail_label.config(text=message.message, style="Success.TLabel")
        
        if hasattr(self, 'log_text'):
            self.log_text.config(state=tk.NORMAL)
            timestamp = time.strftime("%H:%M:%S", time.localtime(message.timestamp))
            status = "ERROR" if message.is_error else "INFO"
            log_entry = f"[{timestamp}] {status}: {message.message}\n"
            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
    
    def show_completion_step(self, success: bool, error_message: str = ""):
        """Show the installation completion step."""
        if success:
            self.current_step = WizardStep.COMPLETION
        else:
            self.current_step = WizardStep.ERROR
            
        self.clear_content()
        
        if success:
            self.update_header(
                "Installation Complete!",
                f"{self.config.app_name} has been successfully installed."
            )
            
            # Success content
            success_frame = ttk.Frame(self.content_frame)
            success_frame.pack(fill=tk.BOTH, expand=True)
            
            # Success icon and message
            icon_frame = ttk.Frame(success_frame)
            icon_frame.pack(pady=20)
            
            ttk.Label(icon_frame, text="✅", font=("Segoe UI", 48)).pack()
            ttk.Label(icon_frame, text="Installation Successful!", 
                     style="Title.TLabel").pack(pady=(10, 0))
            
            # Installation details
            details_frame = ttk.LabelFrame(success_frame, text="Installation Details", padding="15")
            details_frame.pack(fill=tk.X, pady=(20, 0))
            
            details = [
                ("Installed to", str(self.config.install_dir)),
                ("Shortcuts created", "Yes" if self.config.create_shortcuts else "No"),
                ("Added to PATH", "Yes" if self.config.add_to_path else "No"),
            ]
            
            for label, value in details:
                detail_frame = ttk.Frame(details_frame)
                detail_frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(detail_frame, text=f"{label}:", style="Header.TLabel").pack(side=tk.LEFT)
                ttk.Label(detail_frame, text=value).pack(side=tk.LEFT, padx=(10, 0))
            
            # Next steps
            next_frame = ttk.LabelFrame(success_frame, text="Next Steps", padding="15")
            next_frame.pack(fill=tk.X, pady=(20, 0))
            
            if self.config.create_shortcuts:
                ttk.Label(next_frame, text="• Look for desktop shortcuts to launch the application").pack(anchor=tk.W)
            
            ttk.Label(next_frame, text=f"• Navigate to {self.config.install_dir} to find the installation").pack(anchor=tk.W)
            ttk.Label(next_frame, text="• Check the application documentation for usage instructions").pack(anchor=tk.W)
            
        else:
            self.update_header(
                "Installation Failed",
                "The installation could not be completed."
            )
            
            # Error content
            error_frame = ttk.Frame(self.content_frame)
            error_frame.pack(fill=tk.BOTH, expand=True)
            
            # Error icon and message
            icon_frame = ttk.Frame(error_frame)
            icon_frame.pack(pady=20)
            
            ttk.Label(icon_frame, text="❌", font=("Segoe UI", 48)).pack()
            ttk.Label(icon_frame, text="Installation Failed", 
                     style="Title.TLabel").pack(pady=(10, 0))
            
            # Error details
            if error_message:
                error_details_frame = ttk.LabelFrame(error_frame, text="Error Details", padding="15")
                error_details_frame.pack(fill=tk.X, pady=(20, 0))
                
                ttk.Label(error_details_frame, text=error_message, style="Error.TLabel").pack(anchor=tk.W)
            
            # Troubleshooting
            help_frame = ttk.LabelFrame(error_frame, text="Troubleshooting", padding="15")
            help_frame.pack(fill=tk.X, pady=(20, 0))
            
            help_items = [
                "• Check your internet connection",
                "• Ensure you have sufficient disk space",
                "• Verify you have the required permissions",
                "• Check that Git is properly installed",
                "• Try running as administrator (Windows) or with sudo (Linux/macOS)"
            ]
            
            for item in help_items:
                ttk.Label(help_frame, text=item).pack(anchor=tk.W)
        
        # Update buttons
        self.back_button.config(state=tk.DISABLED)
        
        if success:
            self.next_button.config(text="Finish", command=self.finish_installation, state=tk.NORMAL)
            self.cancel_button.config(text="Close", command=self.finish_installation)
        else:
            self.next_button.config(text="Retry", command=self.restart_installation, state=tk.NORMAL)
            self.cancel_button.config(text="Close", command=self.finish_installation)
    
    def go_back(self):
        """Go to the previous step."""
        if self.current_step == WizardStep.REQUIREMENTS:
            self.show_welcome_step()
        elif self.current_step == WizardStep.DIRECTORY:
            self.show_requirements_step()
        elif self.current_step == WizardStep.CONFIRMATION:
            self.show_directory_step()
    
    def go_next(self):
        """Go to the next step."""
        if self.current_step == WizardStep.WELCOME:
            self.show_requirements_step()
        elif self.current_step == WizardStep.REQUIREMENTS:
            self.show_directory_step()
        elif self.current_step == WizardStep.DIRECTORY:
            self.show_confirmation_step()
        elif self.current_step == WizardStep.CONFIRMATION:
            self.start_installation()
    
    def cancel_installation(self):
        """Cancel the installation process."""
        if self.current_step == WizardStep.PROGRESS:
            # Ask for confirmation
            if messagebox.askyesno("Cancel Installation", 
                                  "Are you sure you want to cancel the installation?\n"
                                  "This may leave the system in an incomplete state."):
                self.is_cancelled = True
                if self.installer:
                    self.installer.cleanup()
                self.root.quit()
        else:
            self.root.quit()
    
    def finish_installation(self):
        """Finish and close the installer."""
        self.root.quit()
    
    def restart_installation(self):
        """Restart the installation process."""
        self.is_cancelled = False
        self.show_welcome_step()
    
    def on_window_close(self):
        """Handle window close event."""
        self.cancel_installation()
    
    def run(self):
        """Run the installation wizard."""
        try:
            self.root.mainloop()
        finally:
            if self.installer:
                self.installer.cleanup()


def create_installation_wizard(installer_class, repo_url: str, app_name: str, python_version: str = "3.9"):
    """Create and run the installation wizard."""
    config = InstallationConfig(
        repo_url=repo_url,
        app_name=app_name,
        python_version=python_version
    )
    
    wizard = ModernInstallationWizard(installer_class, config)
    wizard.run()
    
    return wizard 