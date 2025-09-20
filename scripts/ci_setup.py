#!/usr/bin/env python3
"""
CI/CD Integration for Spec-Kit Validation

This script sets up continuous integration for Spec-Kit validation.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List
import argparse

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class SpecKitCI:
    """CI/CD integration for Spec-Kit validation."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.scripts_dir = self.project_root / "scripts"
        
    def setup_pre_commit_hooks(self) -> bool:
        """Setup pre-commit hooks for Spec-Kit validation."""
        print("🔧 Setting up pre-commit hooks...")
        
        # Check if pre-commit is installed
        try:
            subprocess.run(["pre-commit", "--version"], 
                          capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ pre-commit not found. Installing...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "pre-commit"], 
                              check=True)
                print("✅ pre-commit installed successfully")
            except subprocess.CalledProcessError:
                print("❌ Failed to install pre-commit")
                return False
                
        # Create .pre-commit-config.yaml
        pre_commit_config = {
            "repos": [
                {
                    "repo": "local",
                    "hooks": [
                        {
                            "id": "spec-validate",
                            "name": "Spec-Kit Validation",
                            "entry": "python scripts/spec_validate.py",
                            "language": "system",
                            "types": ["python"],
                            "pass_filenames": False
                        },
                        {
                            "id": "task-mapping",
                            "name": "Task Mapping Verification",
                            "entry": "python scripts/task_mapper.py",
                            "language": "system",
                            "types": ["markdown"],
                            "files": "specs/tasks\\.md$",
                            "pass_filenames": False
                        }
                    ]
                }
            ]
        }
        
        config_file = self.project_root / ".pre-commit-config.yaml"
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump(pre_commit_config, f, default_flow_style=False)
            
        print(f"✅ Created pre-commit config: {config_file}")
        
        # Install the hooks
        try:
            subprocess.run(["pre-commit", "install"], 
                          cwd=self.project_root, check=True)
            print("✅ Pre-commit hooks installed")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install pre-commit hooks")
            return False
    
    def setup_github_workflow(self) -> bool:
        """Setup GitHub Actions workflow for Spec-Kit validation."""
        print("🔧 Setting up GitHub Actions workflow...")
        
        workflows_dir = self.project_root / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        workflow_content = """
name: Spec-Kit Validation

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  spec-validation:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
      
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        
    - name: Run Spec-Kit validation
      run: |
        python scripts/spec_validate.py --report
        
    - name: Upload validation report
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: spec-validation-report
        path: spec_validation_report.json
        
    - name: Comment on PR (if validation fails)
      if: failure() && github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          let report = {};
          try {
            report = JSON.parse(fs.readFileSync('spec_validation_report.json', 'utf8'));
          } catch (e) {
            report = { errors: ['Failed to read validation report'] };
          }
          
          const errorMsg = report.errors ? report.errors.join('\\n') : 'Unknown error';
          
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: `## ❌ Spec-Kit Validation Failed\\n\\n**Errors:**\\n${errorMsg}\\n\\nPlease review the specification and ensure your implementation complies.`
          });
"""
        
        workflow_file = workflows_dir / "spec-check.yml"
        with open(workflow_file, 'w') as f:
            f.write(workflow_content.strip())
            
        print(f"✅ Created GitHub workflow: {workflow_file}")
        return True
    
    def setup_makefile(self) -> bool:
        """Setup Makefile with Spec-Kit validation targets."""
        print("🔧 Setting up Makefile...")
        
        makefile_content = """
# ECE Spec-Kit Validation Makefile

.PHONY: help spec-validate spec-report task-map ci-setup

# Default target
help:
	@echo "ECE Spec-Kit Validation Targets:"
	@echo "  spec-validate  - Run Spec-Kit validation"
	@echo "  spec-report    - Generate detailed validation report"
	@echo "  task-map       - Generate task mapping"
	@echo "  ci-setup       - Setup CI/CD integration"

# Run Spec-Kit validation
spec-validate:
	python scripts/spec_validate.py

# Generate detailed validation report
spec-report:
	python scripts/spec_validate.py --report

# Generate task mapping
task-map:
	python scripts/task_mapper.py

# Setup CI/CD integration
ci-setup:
	@echo "Setting up CI/CD integration..."
	python scripts/ci_setup.py --setup-all
	@echo "CI/CD integration setup complete!"

# Install pre-commit hooks
install-hooks:
	pre-commit install

# Run all validations
validate-all: spec-validate task-map
	@echo "✅ All validations passed!"
"""
        
        makefile_path = self.project_root / "Makefile"
        with open(makefile_path, 'w') as f:
            f.write(makefile_content.strip())
            
        print(f"✅ Created Makefile: {makefile_path}")
        return True
    
    def run_ci_setup(self) -> bool:
        """Run complete CI setup."""
        print("🚀 Running complete CI/CD setup...")
        print("=" * 50)
        
        success = True
        
        # Setup Makefile
        if not self.setup_makefile():
            success = False
            
        # Setup pre-commit hooks
        if not self.setup_pre_commit_hooks():
            success = False
            
        # Setup GitHub workflow
        if not self.setup_github_workflow():
            success = False
            
        if success:
            print("\n🎉 CI/CD setup completed successfully!")
            print("\nNext steps:")
            print("1. Run 'make install-hooks' to install pre-commit hooks")
            print("2. Run 'make spec-validate' to validate your implementation")
            print("3. Run 'make task-map' to generate task mappings")
        else:
            print("\n❌ CI/CD setup had some issues")
            
        return success

def main():
    parser = argparse.ArgumentParser(description="CI/CD Setup for Spec-Kit")
    parser.add_argument("--setup-all", action="store_true", help="Setup all CI/CD components")
    parser.add_argument("--setup-makefile", action="store_true", help="Setup Makefile")
    parser.add_argument("--setup-hooks", action="store_true", help="Setup pre-commit hooks")
    parser.add_argument("--setup-workflow", action="store_true", help="Setup GitHub workflow")
    
    args = parser.parse_args()
    
    ci = SpecKitCI()
    
    if args.setup_all:
        success = ci.run_ci_setup()
        sys.exit(0 if success else 1)
        
    if args.setup_makefile:
        success = ci.setup_makefile()
        sys.exit(0 if success else 1)
        
    if args.setup_hooks:
        success = ci.setup_pre_commit_hooks()
        sys.exit(0 if success else 1)
        
    if args.setup_workflow:
        success = ci.setup_github_workflow()
        sys.exit(0 if success else 1)
        
    # Default: show help
    parser.print_help()

if __name__ == "__main__":
    main()