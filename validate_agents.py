#!/usr/bin/env python3
"""
Agent Configuration Validation Script for Codex-Plus TaskExecutionEngine
Validates all agent configurations in .claude/agents/ for operational readiness.
"""

import yaml
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple

class AgentValidator:
    def __init__(self, agents_dir: str = ".claude/agents"):
        self.agents_dir = Path(agents_dir)
        self.results = {
            "total_agents": 0,
            "valid_agents": 0,
            "invalid_agents": 0,
            "warnings": [],
            "errors": [],
            "agent_details": [],
            "summary": {}
        }

    def validate_yaml_agent(self, file_path: Path) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Validate YAML-format agent configuration."""
        errors = []
        warnings = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if not isinstance(config, dict):
                errors.append("Configuration is not a dictionary")
                return False, {}, errors

            # Required fields for YAML agents
            required_fields = ["name", "description"]
            for field in required_fields:
                if field not in config:
                    errors.append(f"Missing required field: {field}")

            # Optional but recommended fields
            recommended_fields = ["capabilities", "model", "tools", "temperature", "max_tokens"]
            for field in recommended_fields:
                if field not in config:
                    warnings.append(f"Missing recommended field: {field}")

            # Validate field types
            if "capabilities" in config and not isinstance(config["capabilities"], list):
                errors.append("capabilities must be a list")

            if "tools" in config and not isinstance(config["tools"], list):
                errors.append("tools must be a list")

            if "temperature" in config:
                try:
                    temp = float(config["temperature"])
                    if not 0 <= temp <= 2:
                        warnings.append("temperature should be between 0 and 2")
                except (ValueError, TypeError):
                    errors.append("temperature must be a number")

            if "max_tokens" in config:
                try:
                    tokens = int(config["max_tokens"])
                    if tokens <= 0:
                        errors.append("max_tokens must be positive")
                except (ValueError, TypeError):
                    errors.append("max_tokens must be a positive integer")

            return len(errors) == 0, config, errors + warnings

        except yaml.YAMLError as e:
            errors.append(f"YAML parsing error: {e}")
            return False, {}, errors
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
            return False, {}, errors

    def validate_markdown_agent(self, file_path: Path) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Validate Markdown-format agent configuration."""
        errors = []
        warnings = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for YAML frontmatter
            if not content.startswith('---'):
                errors.append("Missing YAML frontmatter")
                return False, {}, errors

            # Extract frontmatter
            try:
                parts = content.split('---', 2)
                if len(parts) < 3:
                    errors.append("Invalid frontmatter format")
                    return False, {}, errors

                frontmatter = yaml.safe_load(parts[1])
                body = parts[2].strip()

            except yaml.YAMLError as e:
                errors.append(f"Frontmatter YAML error: {e}")
                return False, {}, errors

            # Validate frontmatter
            if not isinstance(frontmatter, dict):
                errors.append("Frontmatter is not a dictionary")
                return False, {}, errors

            # Required fields for Markdown agents
            required_fields = ["name", "description"]
            for field in required_fields:
                if field not in frontmatter:
                    errors.append(f"Missing required frontmatter field: {field}")

            # Check for substantial body content
            if not body or len(body.strip()) < 100:
                warnings.append("Agent prompt/body content seems minimal")

            # Look for system prompt sections
            if "## Core Responsibilities" not in content and "responsibilities" not in content.lower():
                warnings.append("No clear responsibilities section found")

            return len(errors) == 0, {**frontmatter, "body_length": len(body)}, errors + warnings

        except Exception as e:
            errors.append(f"Unexpected error: {e}")
            return False, {}, errors

    def validate_agent_file(self, file_path: Path) -> Dict[str, Any]:
        """Validate a single agent configuration file."""
        file_info = {
            "file": str(file_path.name),
            "type": file_path.suffix.lower(),
            "valid": False,
            "config": {},
            "issues": []
        }

        if file_path.suffix.lower() in ['.yaml', '.yml']:
            is_valid, config, issues = self.validate_yaml_agent(file_path)
        elif file_path.suffix.lower() == '.md':
            is_valid, config, issues = self.validate_markdown_agent(file_path)
        else:
            issues = [f"Unsupported file type: {file_path.suffix}"]
            is_valid = False
            config = {}

        file_info.update({
            "valid": is_valid,
            "config": config,
            "issues": issues
        })

        return file_info

    def run_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation on all agent configurations."""
        if not self.agents_dir.exists():
            return {
                "error": f"Agents directory not found: {self.agents_dir}",
                "total_agents": 0,
                "valid_agents": 0
            }

        # Find all agent configuration files
        agent_files = []
        for pattern in ['*.yaml', '*.yml', '*.md']:
            agent_files.extend(self.agents_dir.glob(pattern))

        # Filter out documentation files
        agent_files = [f for f in agent_files if f.name.upper() not in ['README.MD', 'CLAUDE.MD']]

        self.results["total_agents"] = len(agent_files)

        # Validate each agent
        for file_path in sorted(agent_files):
            agent_info = self.validate_agent_file(file_path)
            self.results["agent_details"].append(agent_info)

            if agent_info["valid"]:
                self.results["valid_agents"] += 1
            else:
                self.results["invalid_agents"] += 1
                self.results["errors"].extend([
                    f"{agent_info['file']}: {issue}" for issue in agent_info["issues"]
                    if "error" in issue.lower() or "missing required" in issue.lower()
                ])

            # Collect warnings
            warnings = [issue for issue in agent_info.get("issues", [])
                       if "warning" in issue.lower() or "recommended" in issue.lower() or "minimal" in issue.lower()]
            if warnings:
                self.results["warnings"].extend([
                    f"{agent_info['file']}: {warning}" for warning in warnings
                ])

        # Generate summary statistics
        self.results["summary"] = self._generate_summary()

        return self.results

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        agent_types = {}
        capabilities = {}
        models = {}

        for agent in self.results["agent_details"]:
            if agent["valid"]:
                # Count by type
                agent_type = agent["type"]
                agent_types[agent_type] = agent_types.get(agent_type, 0) + 1

                # Count capabilities
                config = agent.get("config", {})
                if "capabilities" in config:
                    for cap in config["capabilities"]:
                        capabilities[cap] = capabilities.get(cap, 0) + 1

                # Count models
                if "model" in config:
                    model = config["model"]
                    models[model] = models.get(model, 0) + 1

        return {
            "agent_types": agent_types,
            "capabilities": capabilities,
            "models": models,
            "validation_rate": (self.results["valid_agents"] / max(1, self.results["total_agents"])) * 100
        }

    def print_report(self):
        """Print comprehensive validation report."""
        print("🤖 Codex-Plus Agent Configuration Validation Report")
        print("=" * 60)
        print()

        # Overall status
        total = self.results["total_agents"]
        valid = self.results["valid_agents"]
        invalid = self.results["invalid_agents"]

        status_emoji = "✅" if invalid == 0 else "⚠️" if invalid < total // 2 else "❌"
        print(f"{status_emoji} Overall Status: {valid}/{total} agents valid ({self.results['summary']['validation_rate']:.1f}%)")
        print()

        # Agent breakdown
        if total > 0:
            print("📊 Agent Configuration Summary:")
            print(f"   Valid agents: {valid}")
            print(f"   Invalid agents: {invalid}")
            print(f"   Total agents: {total}")
            print()

            # Agent types
            types = self.results["summary"]["agent_types"]
            if types:
                print("📁 Agent Types:")
                for agent_type, count in types.items():
                    print(f"   {agent_type}: {count} agents")
                print()

            # Most common capabilities
            capabilities = self.results["summary"]["capabilities"]
            if capabilities:
                print("🔧 Top Capabilities:")
                sorted_caps = sorted(capabilities.items(), key=lambda x: x[1], reverse=True)[:5]
                for cap, count in sorted_caps:
                    print(f"   {cap}: {count} agents")
                print()

            # Models used
            models = self.results["summary"]["models"]
            if models:
                print("🧠 Models:")
                for model, count in models.items():
                    print(f"   {model}: {count} agents")
                print()

        # Individual agent details
        if self.results["agent_details"]:
            print("📋 Agent Details:")
            for agent in self.results["agent_details"]:
                status = "✅" if agent["valid"] else "❌"
                name = agent.get("config", {}).get("name", agent["file"])
                file_type = agent["type"]
                print(f"   {status} {name} ({agent['file']}) [{file_type}]")

                if agent["issues"]:
                    for issue in agent["issues"][:3]:  # Show first 3 issues
                        prefix = "      ⚠️" if any(word in issue.lower() for word in ["warning", "recommended"]) else "      ❌"
                        print(f"{prefix} {issue}")

                    if len(agent["issues"]) > 3:
                        print(f"      ... and {len(agent['issues']) - 3} more issues")
            print()

        # Errors summary
        if self.results["errors"]:
            print("❌ Critical Issues (must be fixed):")
            for error in self.results["errors"][:10]:
                print(f"   • {error}")
            if len(self.results["errors"]) > 10:
                print(f"   ... and {len(self.results['errors']) - 10} more errors")
            print()

        # Warnings summary
        if self.results["warnings"]:
            print("⚠️  Recommendations (should be addressed):")
            for warning in self.results["warnings"][:5]:
                print(f"   • {warning}")
            if len(self.results["warnings"]) > 5:
                print(f"   ... and {len(self.results['warnings']) - 5} more warnings")
            print()

        # Final assessment
        print("🎯 Assessment:")
        if invalid == 0:
            print("   🎉 All agent configurations are valid and ready for production use!")
        elif invalid < total // 2:
            print(f"   ✨ Most agents are valid. Address {invalid} invalid configurations.")
        else:
            print(f"   🚨 Multiple configuration issues found. Review and fix {invalid} agents.")

        if total >= 16:
            print(f"   📈 Target achieved: {total} agents (≥16 target)")
        else:
            print(f"   📋 Below target: {total} agents (<16 target)")

        print()
        print("=" * 60)

    def export_results(self, output_file: str = "agent_validation_results.json"):
        """Export validation results to JSON file."""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)
        print(f"📄 Detailed results exported to: {output_file}")


def main():
    """Main execution function."""
    validator = AgentValidator()

    print("🔍 Starting agent configuration validation...")
    print()

    # Run validation
    results = validator.run_validation()

    # Print report
    validator.print_report()

    # Export results
    validator.export_results()

    # Exit with appropriate code
    sys.exit(0 if results["invalid_agents"] == 0 else 1)


if __name__ == "__main__":
    main()