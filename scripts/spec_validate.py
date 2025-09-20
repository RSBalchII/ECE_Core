#!/usr/bin/env python3
"""
Spec-Kit Validation Framework for ECE Project

This script validates that the ECE implementation conforms to the 
specifications defined in the specs/ directory.
"""

import os
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any
import argparse
import hashlib

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class SpecKitValidator:
    """Validates ECE implementation against specifications."""
    
    def __init__(self, specs_dir: str = "specs", src_dir: str = "ece"):
        self.specs_dir = Path(specs_dir)
        self.src_dir = Path(src_dir)
        self.validation_errors = []
        self.validation_warnings = []
        
    def validate_spec_files(self) -> bool:
        """Validate that all required spec files exist."""
        required_specs = [
            "spec.md",
            "tasks.md"
        ]
        
        print("🔍 Validating spec files...")
        all_valid = True
        
        for spec_file in required_specs:
            spec_path = self.specs_dir / spec_file
            if not spec_path.exists():
                self.validation_errors.append(f"Missing required spec file: {spec_file}")
                all_valid = False
            else:
                print(f"✅ Found spec file: {spec_file}")
                
        return all_valid
    
    def validate_task_mapping(self) -> bool:
        """Validate that tasks are properly mapped to implementation."""
        print("\n🔍 Validating task mapping...")
        
        tasks_file = self.specs_dir / "tasks.md"
        if not tasks_file.exists():
            self.validation_errors.append("tasks.md not found for task mapping validation")
            return False
            
        # Read tasks file
        with open(tasks_file, 'r') as f:
            tasks_content = f.read()
            
        # Extract task IDs (TASK-XXX format)
        import re
        task_pattern = r'\*\*Task (\d+(?:\.\d+)*):.*?\*\*'
        task_ids = re.findall(task_pattern, tasks_content)
        
        if not task_ids:
            # Try alternative pattern
            task_pattern = r'TASK-(\d+)'
            task_ids = re.findall(task_pattern, tasks_content)
            
        print(f"📋 Found {len(task_ids)} tasks in specification")
        
        # Check if implementation files exist for key components
        key_components = [
            "agents/tier3/archivist/archivist_agent.py",
            "agents/tier3/distiller/",
            "agents/tier3/injector/",
            "agents/tier3/qlearning/"
        ]
        
        components_found = 0
        for component in key_components:
            component_path = self.src_dir / component
            if component_path.exists():
                print(f"✅ Found implementation: {component}")
                components_found += 1
            else:
                self.validation_warnings.append(f"Missing implementation: {component}")
                
        print(f"📊 Found {components_found}/{len(key_components)} key components")
        
        return len(task_ids) > 0 and components_found > 0
    
    def validate_architecture_compliance(self) -> bool:
        """Validate that implementation follows specified architecture."""
        print("\n🔍 Validating architecture compliance...")
        
        # Check for required directories
        required_dirs = [
            "agents/tier1",
            "agents/tier2", 
            "agents/tier3",
            "components"
        ]
        
        dirs_found = 0
        for dir_name in required_dirs:
            dir_path = self.src_dir / dir_name
            if dir_path.exists():
                print(f"✅ Found required directory: {dir_name}")
                dirs_found += 1
            else:
                self.validation_errors.append(f"Missing required directory: {dir_name}")
                
        return dirs_found == len(required_dirs)
    
    def validate_agent_implementation(self) -> bool:
        """Validate that key agents are properly implemented."""
        print("\n🔍 Validating agent implementations...")
        
        # Check Archivist agent (already examined)
        archivist_path = self.src_dir / "agents/tier3/archivist/archivist_agent.py"
        if archivist_path.exists():
            print("✅ Archivist agent implementation found")
            
            # Check for key features
            with open(archivist_path, 'r') as f:
                content = f.read()
                
            required_features = [
                "continuous_temporal_scanning",
                "get_context",
                "receive_distiller_data",
                "_process_cache_entry"
            ]
            
            features_found = 0
            for feature in required_features:
                if feature in content:
                    print(f"✅ Found feature: {feature}")
                    features_found += 1
                else:
                    self.validation_warnings.append(f"Missing feature in Archivist: {feature}")
                    
            print(f"📊 Found {features_found}/{len(required_features)} required features in Archivist")
        else:
            self.validation_errors.append("Archivist agent implementation not found")
            return False
            
        return True
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate a comprehensive validation report."""
        print("\n📋 Generating validation report...")
        
        report = {
            "project": "External Context Engine (ECE)",
            "validation_timestamp": "2025-09-20T00:00:00Z",
            "spec_files_valid": self.validate_spec_files(),
            "task_mapping_valid": self.validate_task_mapping(),
            "architecture_compliant": self.validate_architecture_compliance(),
            "agent_implementation_valid": self.validate_agent_implementation(),
            "errors": self.validation_errors,
            "warnings": self.validation_warnings,
            "summary": {
                "total_errors": len(self.validation_errors),
                "total_warnings": len(self.validation_warnings)
            }
        }
        
        return report
    
    def run_full_validation(self) -> bool:
        """Run all validation checks."""
        print("🚀 Running Spec-Kit validation...")
        print("=" * 50)
        
        report = self.generate_validation_report()
        
        print("\n" + "=" * 50)
        print("VALIDATION RESULTS")
        print("=" * 50)
        
        # Print summary
        print(f"Spec Files Valid: {'✅' if report['spec_files_valid'] else '❌'}")
        print(f"Task Mapping Valid: {'✅' if report['task_mapping_valid'] else '❌'}")
        print(f"Architecture Compliant: {'✅' if report['architecture_compliant'] else '❌'}")
        print(f"Agent Implementation Valid: {'✅' if report['agent_implementation_valid'] else '❌'}")
        
        # Print errors
        if report['errors']:
            print(f"\n❌ ERRORS ({len(report['errors'])}):")
            for error in report['errors']:
                print(f"  • {error}")
                
        # Print warnings
        if report['warnings']:
            print(f"\n⚠️ WARNINGS ({len(report['warnings'])}):")
            for warning in report['warnings']:
                print(f"  • {warning}")
                
        # Overall result
        is_valid = (
            report['spec_files_valid'] and 
            report['task_mapping_valid'] and 
            report['architecture_compliant'] and 
            report['agent_implementation_valid'] and
            len(report['errors']) == 0
        )
        
        print(f"\n{'🎉 VALIDATION PASSED' if is_valid else '💥 VALIDATION FAILED'}")
        print(f"Errors: {len(report['errors'])}, Warnings: {len(report['warnings'])}")
        
        return is_valid

def main():
    parser = argparse.ArgumentParser(description="Spec-Kit Validator for ECE")
    parser.add_argument("--specs-dir", default="specs", help="Specifications directory")
    parser.add_argument("--src-dir", default="ece", help="Source code directory")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    
    args = parser.parse_args()
    
    validator = SpecKitValidator(
        specs_dir=args.specs_dir,
        src_dir=args.src_dir
    )
    
    success = validator.run_full_validation()
    
    if args.report:
        report = validator.generate_validation_report()
        report_file = "spec_validation_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Detailed report saved to {report_file}")
        
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()