#!/usr/bin/env python3
"""
Cross-platform installer for uv-based Python applications.
"""

import os
import sys
import subprocess
import shutil
import platform
import json
from pathlib import Path
from typing import Optional, Dict, Any
import tkinter as tk
from tkinter import filedialog, messagebox
import tempfile
import urllib.request
import zipfile

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


class CrossPlatformInstaller:
    """Cross-platform installer for uv-based Python applications."""
    
    def __init__(self, repo_url: str, app_name: str, python_version: str = "3.8"):
        self.repo_url = repo_url
        self.app_name = app_name
        self.python_version = python_version
        self.install_dir = self._get_default_install_dir()
        self.temp_dir = None
        self.cloned_repo_path = None
        
    def _get_default_install_dir(self) -> Path:
        """Get OS-appropriate default installation directory."""
        system = platform.system()
        if system == "Windows":
            return Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / self.app_name
        elif system == "Darwin":  # macOS
            return Path("/Applications") / self.app_name
        else:  # Linux and others
            if platformdirs:
                return Path(platformdirs.user_data_dir()) / self.app_name
            return Path.home() / ".local" / "share" / self.app_name
    
    def check_python_version(self) -> bool:
        """Check if required Python version is available."""
        print(f"Checking Python {self.python_version} availability...")
        try:
            current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            required_major, required_minor = map(int, self.python_version.split('.'))
            current_major, current_minor = sys.version_info.major, sys.version_info.minor
            
            if current_major > required_major or (current_major == required_major and current_minor >= required_minor):
                print(f"✓ Python {current_version} meets requirement (>= {self.python_version})")
                return True
            else:
                print(f"✗ Python {current_version} does not meet requirement (>= {self.python_version})")
                return False
        except Exception as e:
            print(f"Error checking Python version: {e}")
            return False
    
    def update_pip(self) -> bool:
        """Update pip to latest stable version."""
        print("Updating pip to latest version...")
        try:
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "--upgrade", "pip"
            ], capture_output=True, text=True, check=True)
            print("✓ pip updated successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to update pip: {e}")
            print(f"Error output: {e.stderr}")
            return False
    
    def install_uv(self) -> bool:
        """Install uv package manager."""
        print("Installing uv package manager...")
        try:
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "uv"
            ], capture_output=True, text=True, check=True)
            print("✓ uv installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install uv: {e}")
            print(f"Error output: {e.stderr}")
            return False
    
    def clone_repository(self) -> bool:
        """Clone the GitHub repository."""
        print(f"Cloning repository: {self.repo_url}")
        try:
            self.temp_dir = tempfile.mkdtemp()
            self.cloned_repo_path = Path(self.temp_dir) / "repo"
            
            if git:
                # Use GitPython SDK
                git.Repo.clone_from(self.repo_url, str(self.cloned_repo_path))
            else:
                # Fallback to subprocess
                result = subprocess.run([
                    "git", "clone", self.repo_url, str(self.cloned_repo_path)
                ], capture_output=True, text=True, check=True)
            
            print("✓ Repository cloned successfully")
            return True
        except Exception as e:
            print(f"✗ Failed to clone repository: {e}")
            return False
    
    def build_project(self) -> bool:
        """Build the project using uv."""
        print("Building project with uv...")
        try:
            # Change to repo directory
            original_cwd = os.getcwd()
            os.chdir(self.cloned_repo_path)
            
            # Run uv sync
            print("Running uv sync...")
            result = subprocess.run(["uv", "sync"], capture_output=True, text=True, check=True)
            print("✓ uv sync completed")
            
            # Run uv pip install -e .
            print("Running uv pip install -e .")
            result = subprocess.run(["uv", "pip", "install", "-e", "."], capture_output=True, text=True, check=True)
            print("✓ Package installed in development mode")
            
            os.chdir(original_cwd)
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to build project: {e}")
            print(f"Error output: {e.stderr}")
            os.chdir(original_cwd)
            return False
        except Exception as e:
            print(f"✗ Unexpected error during build: {e}")
            os.chdir(original_cwd)
            return False
    
    def choose_install_directory(self) -> bool:
        """Let user choose installation directory via file dialog."""
        try:
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            
            selected_dir = filedialog.askdirectory(
                title=f"Choose installation directory for {self.app_name}",
                initialdir=str(self.install_dir.parent)
            )
            
            if selected_dir:
                self.install_dir = Path(selected_dir) / self.app_name
                print(f"Installation directory set to: {self.install_dir}")
                return True
            else:
                print(f"Using default installation directory: {self.install_dir}")
                return True
                
        except Exception as e:
            print(f"Error with file dialog: {e}")
            print(f"Using default installation directory: {self.install_dir}")
            return True
    
    def move_to_install_directory(self) -> bool:
        """Move cloned repository to installation directory."""
        print(f"Moving application to: {self.install_dir}")
        try:
            # Create parent directory if it doesn't exist
            self.install_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # Remove existing installation if it exists
            if self.install_dir.exists():
                shutil.rmtree(self.install_dir)
            
            # Move the cloned repository
            shutil.move(str(self.cloned_repo_path), str(self.install_dir))
            print("✓ Application moved to installation directory")
            return True
        except Exception as e:
            print(f"✗ Failed to move application: {e}")
            return False
    
    def create_shortcuts(self) -> bool:
        """Create shortcuts for the application."""
        print("Creating shortcuts...")
        system = platform.system()
        
        try:
            if system == "Windows":
                return self._create_windows_shortcuts()
            elif system == "Darwin":
                return self._create_macos_shortcuts()
            else:
                return self._create_linux_shortcuts()
        except Exception as e:
            print(f"✗ Failed to create shortcuts: {e}")
            return False
    
    def _create_windows_shortcuts(self) -> bool:
        """Create Windows shortcuts."""
        try:
            # Find the main executable or script
            main_script = self._find_main_executable()
            if not main_script:
                print("Could not find main executable")
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
                
                print("✓ Windows shortcuts created")
                return True
            else:
                print("winshell not available, skipping shortcut creation")
                return True
                
        except Exception as e:
            print(f"Error creating Windows shortcuts: {e}")
            return False
    
    def _create_macos_shortcuts(self) -> bool:
        """Create macOS shortcuts."""
        try:
            main_script = self._find_main_executable()
            if not main_script:
                return False
            
            # Create an app bundle or alias
            apps_dir = Path.home() / "Applications"
            apps_dir.mkdir(exist_ok=True)
            
            app_path = apps_dir / f"{self.app_name}.app"
            if app_path.exists():
                shutil.rmtree(app_path)
            
            # Create basic app bundle structure
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
            
            print("✓ macOS app bundle created")
            return True
            
        except Exception as e:
            print(f"Error creating macOS shortcuts: {e}")
            return False
    
    def _create_linux_shortcuts(self) -> bool:
        """Create Linux desktop shortcuts."""
        try:
            main_script = self._find_main_executable()
            if not main_script:
                return False
            
            # Create .desktop file
            desktop_file_content = f"""[Desktop Entry]
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
                f.write(desktop_file_content)
            desktop_file_path.chmod(0o755)
            
            # Also create on desktop if Desktop directory exists
            desktop_dir = Path.home() / "Desktop"
            if desktop_dir.exists():
                desktop_shortcut = desktop_dir / f"{self.app_name}.desktop"
                with open(desktop_shortcut, 'w') as f:
                    f.write(desktop_file_content)
                desktop_shortcut.chmod(0o755)
            
            print("✓ Linux shortcuts created")
            return True
            
        except Exception as e:
            print(f"Error creating Linux shortcuts: {e}")
            return False
    
    def _find_main_executable(self) -> Optional[Path]:
        """Find the main executable or entry point."""
        # Look for common patterns
        possible_mains = [
            self.install_dir / "main.py",
            self.install_dir / f"{self.app_name}.py",
            self.install_dir / "__main__.py",
        ]
        
        for main_file in possible_mains:
            if main_file.exists():
                return main_file
        
        # Look for setup.py or pyproject.toml to find entry points
        setup_py = self.install_dir / "setup.py"
        pyproject_toml = self.install_dir / "pyproject.toml"
        
        if pyproject_toml.exists():
            # Try to parse pyproject.toml for entry points
            try:
                import tomllib
                with open(pyproject_toml, 'rb') as f:
                    data = tomllib.load(f)
                    scripts = data.get('project', {}).get('scripts', {})
                    if scripts:
                        # Return the first script found
                        return self.install_dir / "main.py"  # Fallback
            except:
                pass
        
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
                f"Shortcuts have been created on your desktop and start menu."
            )
        except Exception as e:
            print(f"✓ Installation completed successfully!")
            print(f"Installation directory: {self.install_dir}")
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"Warning: Could not clean up temporary directory: {e}")
    
    def install(self) -> bool:
        """Run the complete installation process."""
        print(f"Starting installation of {self.app_name}...")
        
        try:
            steps = [
                ("Checking Python version", self.check_python_version),
                ("Updating pip", self.update_pip),
                ("Installing uv", self.install_uv),
                ("Cloning repository", self.clone_repository),
                ("Building project", self.build_project),
                ("Choosing install directory", self.choose_install_directory),
                ("Moving to install directory", self.move_to_install_directory),
                ("Creating shortcuts", self.create_shortcuts),
            ]
            
            for step_name, step_func in steps:
                print(f"\n--- {step_name} ---")
                if not step_func():
                    print(f"Installation failed at step: {step_name}")
                    return False
            
            self.show_completion_message()
            print(f"\n🎉 Installation of {self.app_name} completed successfully!")
            return True
            
        finally:
            self.cleanup()


def main():
    """Main entry point for the installer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cross-platform installer for uv-based Python applications")
    parser.add_argument("repo_url", help="GitHub repository URL to clone and install")
    parser.add_argument("app_name", help="Name of the application")
    parser.add_argument("--python-version", default="3.8", help="Minimum required Python version")
    
    args = parser.parse_args()
    
    installer = CrossPlatformInstaller(
        repo_url=args.repo_url,
        app_name=args.app_name,
        python_version=args.python_version
    )
    
    success = installer.install()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 