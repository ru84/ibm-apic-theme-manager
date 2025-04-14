#!/usr/bin/env python3
"""
IBM API Connect Developer Portal Theme Management Script

This script manages theme deployment for IBM API Connect Developer Portal across different environments (e.g. production, staging).
It provides functionality to check status, upload themes, and revert to default themes.

Usage examples:
  # Check status
  ./theme_manager.py status
  
  # Upload a theme
  ./theme_manager.py upload
  
  # Revert to the default theme
  ./theme_manager.py revert --env production
  
  # Specify a different theme
  ./theme_manager.py upload --theme my_custom_theme
  
  # Clear cache
  ./theme_manager.py cache-clear
  
  # Login to OpenShift
  ./theme_manager.py login

Configuration:
  This script uses a JSON configuration file (theme_manager_config.json) with the following structure:
  
  {
    "defaults": {
      "environment": "production"
    },
    "themes": {
      "active_theme": "my_new_theme",
      "default_theme": "connect_theme"
    },
    "environments": {
      "production": {
        "oc_project": "apiconnect",
        "pod_name": "apiconnect-ptl-s1444oim-www-0",
        "site_name": "developer.myapic.com",
        "platform_path": "/var/aegir/platforms/devportal-10.x-10.0.8.2-20250311-1629",
        "server_url": "https://api.ocp.myapic.com:6443"
      }
    }
  }
"""

import argparse
import os
import subprocess
import sys
import shutil
import zipfile
import tempfile
import logging
import datetime
import json


class ColorFormatter(logging.Formatter):
    """Custom formatter with colored output based on log level."""
    
    COLORS = {
        'TIMESTAMP': '\033[36m',    # Cyan for timestamps
        'INFO': '\033[32m',         # Green for info
        'WARNING': '\033[33m',      # Yellow for warnings
        'ERROR': '\033[31m',        # Red for errors
        'DEBUG': '\033[35m',        # Magenta for debug
        'COMMAND': '\033[34m',      # Blue for commands
        'RESET': '\033[0m'          # Reset color
    }
    
    def format(self, record):
        levelname = record.levelname
        # Special handling for command messages
        if getattr(record, 'is_command', False):
            color = self.COLORS['COMMAND']
            levelname = 'CMD>'
        else:
            color = self.COLORS.get(levelname, self.COLORS['RESET'])
        
        # Format timestamp with cyan color
        timestamp = self.COLORS['TIMESTAMP'] + self.formatTime(record, self.datefmt) + self.COLORS['RESET']
        
        # Format level with appropriate color
        colored_levelname = f"{color}{levelname:<5}{self.COLORS['RESET']}"
        
        # Apply format with colored components
        record.levelname = colored_levelname
        record.asctime = timestamp
        
        # Color the message text based on the log level
        message = record.getMessage()
        if not getattr(record, 'no_msg_color', False):
            record.msg = f"{color}{message}{self.COLORS['RESET']}"
        
        return super().format(record)


class ThemeManager:
    """Manages IBM API Connect Developer Portal themes."""

    # Environment configurations will be loaded from the config file
    ENV_CONFIGS = {}

    def __init__(self, env, theme_name, default_theme, config_file="theme_manager_config.json"):
        """
        Initialize the ThemeManager.

        Args:
            env (str): Environment to operate on (from config file)
            theme_name (str): Name of the custom theme
            default_theme (str): Name of the default theme to revert to
            config_file (str): Path to the configuration file
        """
        # Configure colored logging
        self.logger = logging.getLogger("ThemeManager")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers if any
        if self.logger.handlers:
            self.logger.handlers.clear()
            
        # Create console handler with color formatter
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColorFormatter(
            fmt='%(asctime)s %(levelname)s %(message)s',
            datefmt='%H:%M:%S'
        ))
        self.logger.addHandler(console_handler)

        # Set logger to propagate=False to prevent duplicate logging
        self.logger.propagate = False
        
        # Load configuration file
        try:
            if not os.path.exists(config_file):
                self.logger.error(f"Configuration file not found: {config_file}")
                sys.exit(1)
                
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            # Load environment configurations
            self.ENV_CONFIGS = config.get('environments', {})
            if not self.ENV_CONFIGS:
                self.logger.error(f"No environment configurations found in {config_file}")
                sys.exit(1)
                
            # Get theme settings
            theme_settings = config.get('themes', {})
            default_theme_from_config = theme_settings.get('default_theme', 'connect_theme')
            
            # Use command-line values if provided, otherwise use config values
            self.default_theme = default_theme or default_theme_from_config
            self.theme_name = theme_name
            
            # Validate environment
            if env not in self.ENV_CONFIGS:
                self.logger.error(f"Invalid environment '{env}'. Use: {', '.join(self.ENV_CONFIGS.keys())}")
                sys.exit(1)
                
            # Set environment and config
            self.env = env
            self.config = self.ENV_CONFIGS[env]
            
            self.logger.info(f"Initialized ThemeManager for environment: {env}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON configuration: {str(e)}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            sys.exit(1)

    # ============== Command execution helpers ==============

    def _run_command(self, command, shell=False, check=True, capture_output=True, log_command=True):
        """
        Run a shell command and handle errors.

        Args:
            command: Command to run (list or string)
            shell: Whether to run command in shell
            check: Whether to check return code
            capture_output: Whether to capture command output
            log_command: Whether to log the command being executed

        Returns:
            CompletedProcess object
        """
        try:
            # Only log the command if requested
            if log_command:
                cmd_str = command if shell else ' '.join(command)
                # Use the special command logger with blue color
                log_record = logging.LogRecord(
                    name=self.logger.name,
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg=f"{cmd_str}",
                    args=(),
                    exc_info=None
                )
                log_record.is_command = True
                self.logger.handle(log_record)

            result = subprocess.run(
                command,
                shell=shell,
                check=check,
                text=True,
                capture_output=capture_output
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed with exit code {e.returncode}")
            self.logger.error(f"Error output: {e.stderr}")
            if check:
                sys.exit(1)
            raise

    def _run_oc_exec(self, pod_command, silent=False):
        """
        Run a command in the OpenShift pod.

        Args:
            pod_command: Command to run in the pod
            silent: Whether to suppress logging the command

        Returns:
            Command output as string
        """
        full_command = [
            "oc", "exec", "-it", self.config["pod_name"],
            "-c", "admin", "--", "bash", "-c", pod_command
        ]
        
        # Only log the command if not silent
        if not silent:
            # Only log the full 'oc exec' command for copy-paste convenience
            oc_exec_str = " ".join(full_command)
            
            # Just print the full command without any prefix
            log_record = logging.LogRecord(
                name=self.logger.name,
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"{oc_exec_str}",
                args=(),
                exc_info=None
            )
            log_record.is_command = True
            self.logger.handle(log_record)

        # Skip logging when executing the command
        result = self._run_command(full_command, log_command=False)
        return result.stdout.strip()

    # ============== Authentication and status ==============

    def check_login(self):
        """Check if user is logged into OpenShift."""
        try:
            self._run_command(["oc", "whoami"])
            return True
        except subprocess.CalledProcessError:
            self.logger.error("Not logged into OpenShift. Please login first.")
            return False

    def switch_project(self):
        """Switch to the correct OpenShift project."""
        project = self.config["oc_project"]
        self.logger.info(f"Switching to project: {project}")
        self._run_command(["oc", "project", project], capture_output=False)

    def get_current_theme(self):
        """Get the currently active theme."""
        self.logger.debug("Checking current theme...")
        result = self._run_oc_exec(f"drush @{self.config['site_name']} config:get system.theme default")
        return result

    def status(self):
        """Check and display current theme status."""
        if not self.check_login():
            sys.exit(1)

        self.switch_project()
        self.logger.info(f"Checking theme status for {self.env} environment...")

        try:
            result = self._run_oc_exec(f"drush @{self.config['site_name']} config:get system.theme")
            self.logger.info(f"Current theme configuration for {self.env}:")
            for line in result.split('\n'):
                self.logger.info(line)
            return True
        except subprocess.CalledProcessError:
            self.logger.error("Failed to get theme status")
            return False

    # ============== Theme management operations ==============

    def compile_scss(self):
        """Compile SCSS to CSS before uploading."""
        self.logger.info("Compiling SCSS to CSS...")
        try:
            # Check if we can find sass command
            try:
                sass_version = self._run_command(["sass", "--version"], capture_output=True)
                self.logger.info(f"Using sass version: {sass_version.stdout.strip()}")
            except Exception:
                self.logger.error("Sass command not found. Checking for alternatives...")
                try:
                    # Try with npx sass
                    sass_version = self._run_command(["npx", "sass", "--version"], capture_output=True)
                    self.logger.info(f"Using npx sass version: {sass_version.stdout.strip()}")
                    sass_cmd = ["npx", "sass"]
                except Exception:
                    self.logger.error("No sass command found. Please install sass via npm: npm install -g sass")
                    return False
            else:
                sass_cmd = ["sass"]

            # Compile main SCSS file to CSS
            scss_file = "scss/style.scss"
            css_file = "css/style.css"

            # Create css directory if it doesn't exist
            if not os.path.exists("css"):
                os.makedirs("css")

            # Run sass compilation
            compile_cmd = sass_cmd + [scss_file, css_file, "--style=compressed"]
            result = self._run_command(compile_cmd, capture_output=True)

            self.logger.info(f"SCSS compilation successful: {scss_file} -> {css_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error compiling SCSS: {str(e)}")
            return False

    def create_theme_archive(self):
        """Create a ZIP archive of the theme files."""
        self.logger.info("Creating theme archive...")

        # Remove existing archive if it exists
        if os.path.exists(f"{self.theme_name}.zip"):
            os.remove(f"{self.theme_name}.zip")
            
        # Create the zip file with proper structure
        with zipfile.ZipFile(f"{self.theme_name}.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk('.'):
                # Skip unwanted directories
                dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__MACOSX']]
                if '.git' in root or 'node_modules' in root or '__MACOSX' in root:
                    continue
                    
                for file in files:
                    # Skip unwanted files
                    if file in ['.DS_Store', '.gitignore', f"{self.theme_name}.zip", "Makefile"] or file.endswith('.zip'):
                        continue
                        
                    # Add file to zip with proper relative path
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, '.')
                    zipf.write(file_path, arcname)

        self.logger.info(f"Theme archive created: {self.theme_name}.zip")
        return os.path.abspath(f"{self.theme_name}.zip")

    def deactivate_current_theme_if_needed(self):
        """Deactivate and uninstall the theme if needed."""
        self.logger.info(f"Deactivating theme {self.theme_name} (if active)...")

        # Switch to default theme
        cmd = f"drush @{self.config['site_name']} config-set system.theme default {self.default_theme} -y || true"
        self._run_oc_exec(cmd)

        # Uninstall theme - try both commands for compatibility
        cmd = f"drush @{self.config['site_name']} theme-uninstall {self.theme_name} -y || true"
        self._run_oc_exec(cmd)
            
        # Force removal of theme directory
        theme_path = f"{self.config['platform_path']}/sites/{self.config['site_name']}/themes/{self.theme_name}"
        cmd = f"rm -rf {theme_path}"
        self._run_oc_exec(cmd)

        # Clear caches
        cmd = f"drush @{self.config['site_name']} cr || true"
        self._run_oc_exec(cmd)

    def upload(self):
        """Upload and activate the theme."""
        if not self.check_login():
            sys.exit(1)

        self.switch_project()
        self.logger.info(f"Starting theme upload to {self.env} environment...")

        # Compile SCSS to CSS first
        if not self.compile_scss():
            self.logger.error("Failed to compile SCSS. Aborting upload.")
            return False

        # Create theme archive
        zip_path = self.create_theme_archive()

        try:
            # Deactivate current theme if it's our theme
            self.deactivate_current_theme_if_needed()

            # Copy theme ZIP to container
            self.logger.info("Copying theme ZIP to container...")
            
            # Use _run_command directly to log the command automatically
            self._run_command([
                "oc", "cp", zip_path,
                f"{self.config['pod_name']}:/tmp/", "-c", "admin"
            ])

            # Prepare theme directory path
            theme_path = f"{self.config['platform_path']}/sites/{self.config['site_name']}/themes/{self.theme_name}"

            # Extract and install the theme
            self.logger.info("Extracting theme files...")
            
            # Create fresh theme directory
            cmd = f"rm -rf {theme_path} && mkdir -p {theme_path}"
            self._run_oc_exec(cmd)
            
            # Extract zip to theme directory
            cmd = f"unzip -q /tmp/{self.theme_name}.zip -d {theme_path}/"
            self._run_oc_exec(cmd)
            
            # Check and fix potential nested directories
            cmd = f"if [ -d '{theme_path}/{self.theme_name}' ]; then mv {theme_path}/{self.theme_name}/* {theme_path}/; rm -rf {theme_path}/{self.theme_name}; fi"
            self._run_oc_exec(cmd)
            
            # Enable the theme (using compatible command)
            self.logger.info("Enabling theme...")
            cmd = f"drush @{self.config['site_name']} theme-enable {self.theme_name} -y || drush @{self.config['site_name']} theme:enable {self.theme_name} -y"
            self._run_oc_exec(cmd)

            # Set as default theme
            self.logger.info("Setting as default theme...")
            cmd = f"drush @{self.config['site_name']} config-set system.theme default {self.theme_name} -y || drush @{self.config['site_name']} config:set system.theme default {self.theme_name} -y"
            self._run_oc_exec(cmd)

            # Clear caches
            self.logger.info("Clearing caches...")
            cmd = f"drush @{self.config['site_name']} cr || drush @{self.config['site_name']} cache-clear all"
            self._run_oc_exec(cmd)
            
            # Fix any database references to incorrect paths
            cmd = f"drush @{self.config['site_name']} sql-query \"DELETE FROM key_value WHERE name LIKE '%theme_registry%'\" || true"
            self._run_oc_exec(cmd)
            
            # Check theme installation status
            self.logger.info("Verifying theme installation...")
            cmd = f"ls -la {theme_path}/templates/"
            self._run_oc_exec(cmd)

            # Clean up in the container
            cmd = f"rm -rf /tmp/{self.theme_name}.zip"
            self._run_oc_exec(cmd)

            self.logger.info(f"Theme uploaded and activated successfully to {self.env} environment!")
            return True

        except Exception as e:
            self.logger.error(f"Error during theme upload: {str(e)}")
            return False
        finally:
            # Clean up local zip file
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def zip(self):
        """Create a ZIP archive of the theme without uploading it."""
        self.logger.info(f"Creating theme ZIP archive...")

        # Compile SCSS to CSS first
        if not self.compile_scss():
            self.logger.error("Failed to compile SCSS. Aborting ZIP creation.")
            return False

        # Create theme archive
        zip_path = self.create_theme_archive()

        self.logger.info(f"Theme ZIP archive created successfully at: {zip_path}")
        return True

    def revert(self):
        """Revert to the default theme."""
        if not self.check_login():
            sys.exit(1)

        self.switch_project()
        self.logger.info(f"Reverting to default theme in {self.env} environment...")

        try:
            # Set default theme
            cmd = f"drush @{self.config['site_name']} config:set system.theme default {self.default_theme} -y"
            self._run_oc_exec(cmd)

            # Uninstall theme
            cmd = f"drush @{self.config['site_name']} theme:uninstall {self.theme_name} -y || true"
            self._run_oc_exec(cmd)

            # Clear cache
            cmd = f"drush @{self.config['site_name']} cr"
            self._run_oc_exec(cmd)

            self.logger.info(f"Successfully reverted to default theme in {self.env} environment!")
            return True
        except Exception as e:
            self.logger.error(f"Error during theme reversion: {str(e)}")
            return False

    def clear_cache(self):
        """Clear Drupal cache."""
        if not self.check_login():
            sys.exit(1)

        self.switch_project()
        self.logger.info(f"Clearing Drupal cache in {self.env} environment...")

        try:
            cmd = f"drush @{self.config['site_name']} cr"
            self._run_oc_exec(cmd)
            self.logger.info("Cache cleared successfully!")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing cache: {str(e)}")
            return False

    # ============== Authentication ==============

    def login(self, server=None, token=None):
        """
        Login to OpenShift using the environment-specific server URL.

        Args:
            server (str, optional): Custom server URL to use for login
            token (str, optional): Authentication token to use for login
        """
        server_url = server or self.config.get("server_url")
        if not server_url:
            self.logger.error(f"No server URL configured for environment: {self.env}")
            sys.exit(1)

        self.logger.info(f"Logging in to OpenShift for {self.env} environment...")

        try:
            # Build the login command
            login_cmd = ["oc", "login", server_url]

            # Add token if provided
            if token:
                login_cmd.extend(["--token", token])
                self.logger.info(f"Using provided token for authentication")
            else:
                self.logger.info(f"No token provided, will use interactive login")

            # Execute login command (don't capture output to allow interactive prompt)
            self._run_command(login_cmd, capture_output=False, check=True)

            # Check if login was successful
            whoami_result = self._run_command(["oc", "whoami"], capture_output=True)
            username = whoami_result.stdout.strip()

            self.logger.info(f"Successfully logged in as: {username}")

            # Switch to the project
            self.switch_project()

            return True
        except Exception as e:
            self.logger.error(f"Error during OpenShift login: {str(e)}")
            return False



def main():
    """Main function to parse arguments and execute commands."""
    parser = argparse.ArgumentParser(
        description="IBM API Connect Developer Portal Theme Management"
    )

    # Configuration file
    parser.add_argument(
        "--config", "-c",
        default="theme_manager_config.json",
        help="Path to the configuration file (default: theme_manager_config.json)"
    )
    
    # Environment selection (will be validated against config)
    parser.add_argument(
        "--env", "-e",
        default="default",
        help="Environment to operate on (must be defined in config file)"
    )
    
    # Theme name arguments
    parser.add_argument(
        "--theme", "-t",
        help="Name of the theme to manage (required if not specified in config)"
    )
    
    parser.add_argument(
        "--default-theme", "-d",
        help="Name of the default theme to revert to (overrides config setting)"
    )

    # Command subparsers
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Login command
    subparsers.add_parser("login", help="Login to OpenShift")

    # Status command
    subparsers.add_parser("status", help="Check current theme status")

    # Upload command
    subparsers.add_parser("upload", help="Upload and activate theme")

    # Zip command
    subparsers.add_parser("zip", help="Create a ZIP archive of the theme without uploading")

    # Revert command
    subparsers.add_parser("revert", help="Revert to default theme")

    # Cache clear command
    subparsers.add_parser("cache-clear", help="Clear Drupal cache")

    args = parser.parse_args()

    # Load configuration to get default values
    try:
        # Check if config file exists
        if not os.path.exists(args.config):
            print(f"Configuration file not found: {args.config}")
            print(f"Please create a configuration file at: {args.config}")
            print("See script documentation for the expected format.")
            sys.exit(1)
            
        with open(args.config, 'r') as f:
            config = json.load(f)
            
        # Get default values from config
        default_settings = config.get('defaults', {})
        theme_settings = config.get('themes', {})
        
        # Use command-line args or fall back to config defaults
        env = args.env or default_settings.get('environment')
        theme_name = args.theme or theme_settings.get('active_theme')
        default_theme = args.default_theme or theme_settings.get('default_theme')
        
        # Validate required values
        if not env:
            print("Error: No environment specified. Use --env or define a default in the config file.")
            sys.exit(1)
            
        if not theme_name:
            print("Error: No theme name specified. Use --theme or define an active_theme in the config file.")
            sys.exit(1)
            
        # Create theme manager instance with values from CLI or config
        manager = ThemeManager(
            env=env,
            theme_name=theme_name,
            default_theme=default_theme,
            config_file=args.config
        )
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON configuration: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {str(e)}")
        sys.exit(1)

    # Execute command
    if args.command == "login":
        manager.login()
    elif args.command == "status":
        manager.status()
    elif args.command == "upload":
        manager.upload()
    elif args.command == "zip":
        manager.zip()
    elif args.command == "revert":
        manager.revert()
    elif args.command == "cache-clear":
        manager.clear_cache()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
