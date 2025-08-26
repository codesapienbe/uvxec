#!/usr/bin/env python3
"""
GUI Launcher for UV Cross-Platform Installer.

This provides a simple launcher interface to start installations for any repository.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import subprocess
from pathlib import Path
import urllib.parse
import re


class InstallerLauncher:
    """Simple launcher GUI for the installer."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.create_widgets()
    
    def setup_window(self):
        """Set up the launcher window."""
        self.root.title("UV Cross-Platform Installer Launcher")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        
        # Center the window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.root.winfo_screenheight() // 2) - (400 // 2)
        self.root.geometry(f"600x400+{x}+{y}")
    
    def create_widgets(self):
        """Create the launcher widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="UV Cross-Platform Installer", 
                               font=("Segoe UI", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        subtitle_label = ttk.Label(main_frame, text="Install Python applications with ease", 
                                  font=("Segoe UI", 10))
        subtitle_label.pack(pady=(0, 30))
        
        # Repository URL input
        url_frame = ttk.LabelFrame(main_frame, text="Repository Information", padding="15")
        url_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(url_frame, text="Repository URL:").pack(anchor=tk.W)
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, font=("Consolas", 10))
        self.url_entry.pack(fill=tk.X, pady=(5, 10))
        
        # URL examples
        examples_text = ("Examples:\n"
                        "• https://github.com/user/repo.git\n"
                        "• https://github.com/user/repo\n"
                        "• git@github.com:user/repo.git")
        ttk.Label(url_frame, text=examples_text, font=("Segoe UI", 9), foreground="gray").pack(anchor=tk.W)
        
        # App name input
        ttk.Label(url_frame, text="Application Name:").pack(anchor=tk.W, pady=(15, 0))
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(url_frame, textvariable=self.name_var, font=("Consolas", 10))
        self.name_entry.pack(fill=tk.X, pady=(5, 10))
        
        # Auto-fill button
        auto_button = ttk.Button(url_frame, text="Auto-fill from URL", command=self.auto_fill_name)
        auto_button.pack(anchor=tk.W)
        
        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Installation Options", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Python version
        version_frame = ttk.Frame(options_frame)
        version_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(version_frame, text="Python Version:").pack(side=tk.LEFT)
        self.version_var = tk.StringVar(value="3.9")
        version_combo = ttk.Combobox(version_frame, textvariable=self.version_var, 
                                    values=["3.8", "3.9", "3.10", "3.11", "3.12"], 
                                    state="readonly", width=10)
        version_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        # Installation mode
        mode_frame = ttk.Frame(options_frame)
        mode_frame.pack(fill=tk.X)
        
        ttk.Label(mode_frame, text="Installation Mode:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="gui")
        
        gui_radio = ttk.Radiobutton(mode_frame, text="GUI Wizard", variable=self.mode_var, 
                                   value="gui")
        gui_radio.pack(side=tk.LEFT, padx=(10, 0))
        
        cli_radio = ttk.Radiobutton(mode_frame, text="Command Line", variable=self.mode_var, 
                                   value="cli")
        cli_radio.pack(side=tk.LEFT, padx=(10, 0))
        
        # Quick start section
        quick_frame = ttk.LabelFrame(main_frame, text="Quick Start", padding="15")
        quick_frame.pack(fill=tk.X, pady=(0, 20))
        
        quick_text = ("1. Enter the GitHub repository URL\n"
                     "2. Specify an application name\n"
                     "3. Choose your preferred Python version\n"
                     "4. Click 'Start Installation' to begin")
        ttk.Label(quick_frame, text=quick_text).pack(anchor=tk.W)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.install_button = ttk.Button(button_frame, text="Start Installation", 
                                        command=self.start_installation, 
                                        style="Accent.TButton" if hasattr(ttk.Style(), 'theme_use') else "TButton")
        self.install_button.pack(side=tk.RIGHT)
        
        validate_button = ttk.Button(button_frame, text="Validate URL", 
                                    command=self.validate_url)
        validate_button.pack(side=tk.RIGHT, padx=(0, 10))
        
        # Bind URL changes to auto-validation
        self.url_var.trace('w', self.on_url_changed)
        self.name_var.trace('w', self.on_name_changed)
        
        # Initial state
        self.update_button_state()
    
    def auto_fill_name(self):
        """Auto-fill application name from repository URL."""
        url = self.url_var.get().strip()
        if url:
            try:
                # Extract repo name from URL
                if url.endswith('.git'):
                    url = url[:-4]
                
                # Handle different URL formats
                if 'github.com' in url:
                    parts = url.split('/')
                    if len(parts) >= 2:
                        repo_name = parts[-1]
                        # Clean up the name
                        repo_name = re.sub(r'[^a-zA-Z0-9_-]', '', repo_name)
                        if repo_name:
                            self.name_var.set(repo_name)
            except:
                pass
    
    def validate_url(self):
        """Validate the repository URL."""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Validation", "Please enter a repository URL.")
            return
        
        try:
            parsed = urllib.parse.urlparse(url)
            
            if not parsed.scheme:
                messagebox.showwarning("Validation", "URL must include a scheme (https:// or git://)")
                return
            
            if parsed.scheme not in ['https', 'http', 'git', 'ssh']:
                messagebox.showwarning("Validation", f"Unsupported URL scheme: {parsed.scheme}")
                return
            
            if not parsed.netloc:
                messagebox.showwarning("Validation", "URL must include a hostname")
                return
            
            messagebox.showinfo("Validation", "✓ URL appears to be valid!")
            
        except Exception as e:
            messagebox.showerror("Validation Error", f"Invalid URL: {e}")
    
    def on_url_changed(self, *args):
        """Handle URL field changes."""
        self.update_button_state()
    
    def on_name_changed(self, *args):
        """Handle name field changes."""
        self.update_button_state()
    
    def update_button_state(self):
        """Update the install button state based on input validation."""
        url = self.url_var.get().strip()
        name = self.name_var.get().strip()
        
        # Basic validation
        valid = bool(url and name and len(name) >= 2)
        
        if valid:
            try:
                parsed = urllib.parse.urlparse(url)
                valid = bool(parsed.scheme and parsed.netloc)
            except:
                valid = False
        
        self.install_button.config(state=tk.NORMAL if valid else tk.DISABLED)
    
    def start_installation(self):
        """Start the installation process."""
        url = self.url_var.get().strip()
        name = self.name_var.get().strip()
        version = self.version_var.get()
        mode = self.mode_var.get()
        
        if not url or not name:
            messagebox.showwarning("Input Error", "Please fill in all required fields.")
            return
        
        # Validate app name
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            messagebox.showwarning("Input Error", "App name can only contain letters, numbers, hyphens, and underscores.")
            return
        
        try:
            # Build command
            cmd = [sys.executable, "-m", "uv_cross_installer", url, name]
            cmd.extend(["--python-version", version])
            
            if mode == "gui":
                cmd.append("--gui")
            
            # Ask for confirmation
            message = (f"Ready to install {name}!\n\n"
                      f"Repository: {url}\n"
                      f"Python Version: {version}+\n"
                      f"Mode: {'GUI Wizard' if mode == 'gui' else 'Command Line'}\n\n"
                      f"Continue with installation?")
            
            if messagebox.askyesno("Confirm Installation", message):
                # Hide launcher window
                self.root.withdraw()
                
                try:
                    # Start installation
                    if mode == "gui":
                        # Import and run GUI directly
                        from .gui import create_installation_wizard
                        from . import CrossPlatformInstaller
                        
                        create_installation_wizard(
                            installer_class=CrossPlatformInstaller,
                            repo_url=url,
                            app_name=name,
                            python_version=version
                        )
                    else:
                        # Run CLI in subprocess
                        result = subprocess.run(cmd, capture_output=False)
                        if result.returncode != 0:
                            messagebox.showerror("Installation Failed", 
                                               "The installation process failed. Check the console for details.")
                
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to start installation: {e}")
                
                finally:
                    # Show launcher again
                    self.root.deiconify()
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start installation: {e}")
    
    def run(self):
        """Run the launcher."""
        self.root.mainloop()


def main():
    """Main entry point for the launcher."""
    try:
        launcher = InstallerLauncher()
        launcher.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Launcher error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 