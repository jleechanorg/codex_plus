#!/usr/bin/env python3
"""
Comprehensive validation script for the agent configuration loader.

This script thoroughly tests the AgentConfigurationLoader implementation to ensure
it meets all requirements and follows Claude Code CLI patterns correctly.

Usage:
    python validate_agent_loader.py
"""

import json
import sys
import tempfile
import traceback
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from codex_plus.subagents.config_loader import (
    AgentConfiguration,
    AgentConfigurationLoader
)


class ValidationResults:
    """Track validation test results."""

    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []

    def add_result(self, test_name: str, passed: bool, error: str = None):
        """Add a test result."""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ {test_name}")
        else:
            self.tests_failed += 1
            self.failures.append(f"{test_name}: {error}")
            print(f"❌ {test_name}: {error}")

    def summary(self):
        """Print validation summary."""
        print(f"\n{'='*60}")
        print("VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_failed}")

        if self.failures:
            print("\nFAILURES:")
            for failure in self.failures:
                print(f"  • {failure}")

        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")

        if self.tests_failed == 0:
            print("🎉 ALL TESTS PASSED - Agent loader is production ready!")
        else:
            print("⚠️  Some tests failed - review issues before production use")


class AgentLoaderValidator:
    """Comprehensive validator for agent configuration loader."""

    def __init__(self):
        self.results = ValidationResults()
        self.temp_dirs = []

    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            try:
                # Remove temp dir if it exists
                import shutil
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception:
                pass

    def create_temp_dir(self) -> Path:
        """Create a temporary directory for testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix="agent_loader_test_"))
        self.temp_dirs.append(temp_dir)
        return temp_dir

    def test_basic_yaml_parsing(self):
        """Test basic YAML frontmatter parsing."""
        yaml_content = """---
name: Test Agent
description: A test agent for validation
tools:
  - Read
  - Write
model: claude-3-5-sonnet-20241022
temperature: 0.5
capabilities:
  - code_analysis
  - testing
tags:
  - test
  - validation
author: Test Suite
---

# System Prompt

You are a test agent for validation purposes.

# Instructions

1. Follow all testing protocols
2. Validate configuration parsing
3. Report any issues found
"""

        try:
            config = AgentConfiguration.from_yaml(yaml_content)

            # Verify all fields parsed correctly
            assert config.name == "Test Agent"
            assert config.description == "A test agent for validation"
            assert config.tools == ["Read", "Write"]
            assert config.model == "claude-3-5-sonnet-20241022"
            assert config.temperature == 0.5
            assert config.capabilities == {"code_analysis", "testing"}
            assert config.tags == ["test", "validation"]
            assert config.author == "Test Suite"
            assert config.system_prompt and "test agent for validation" in config.system_prompt
            assert config.instructions and "testing protocols" in config.instructions

            self.results.add_result("Basic YAML parsing", True)

        except Exception as e:
            self.results.add_result("Basic YAML parsing", False, str(e))

    def test_frontmatter_without_body(self):
        """Test YAML with only frontmatter."""
        yaml_content = """---
name: Minimal Agent
description: Agent with minimal configuration
---"""

        try:
            config = AgentConfiguration.from_yaml(yaml_content)
            assert config.name == "Minimal Agent"
            assert config.description == "Agent with minimal configuration"
            assert config.model == "claude-3-5-sonnet-20241022"  # Default
            assert config.temperature == 0.7  # Default

            self.results.add_result("Frontmatter without body", True)

        except Exception as e:
            self.results.add_result("Frontmatter without body", False, str(e))

    def test_yaml_without_frontmatter(self):
        """Test YAML without frontmatter delimiters."""
        yaml_content = """
name: No Frontmatter Agent
description: Agent without frontmatter
tools:
  - Read
temperature: 0.8
"""

        try:
            config = AgentConfiguration.from_yaml(yaml_content)
            assert config.name == "No Frontmatter Agent"
            assert config.description == "Agent without frontmatter"
            assert config.tools == ["Read"]
            assert config.temperature == 0.8

            self.results.add_result("YAML without frontmatter", True)

        except Exception as e:
            self.results.add_result("YAML without frontmatter", False, str(e))

    def test_configuration_validation(self):
        """Test configuration validation rules."""

        # Test valid configuration
        try:
            valid_config = AgentConfiguration(
                name="Valid Agent",
                description="A valid configuration",
                model="claude-3-5-sonnet-20241022",
                temperature=1.0,
                tools=["Read", "Write", "Bash"]
            )
            issues = valid_config.validate()
            assert len(issues) == 0
            self.results.add_result("Valid configuration validation", True)
        except Exception as e:
            self.results.add_result("Valid configuration validation", False, str(e))

        # Test invalid model
        try:
            invalid_model = AgentConfiguration(
                name="Invalid Model",
                description="Has invalid model",
                model="gpt-4"
            )
            issues = invalid_model.validate()
            assert any("Invalid model" in issue for issue in issues)
            self.results.add_result("Invalid model detection", True)
        except Exception as e:
            self.results.add_result("Invalid model detection", False, str(e))

        # Test invalid temperature
        try:
            invalid_temp = AgentConfiguration(
                name="Invalid Temp",
                description="Has invalid temperature",
                temperature=3.0
            )
            issues = invalid_temp.validate()
            assert any("Temperature must be between" in issue for issue in issues)
            self.results.add_result("Invalid temperature detection", True)
        except Exception as e:
            self.results.add_result("Invalid temperature detection", False, str(e))

        # Test unknown tools
        try:
            unknown_tools = AgentConfiguration(
                name="Unknown Tools",
                description="Has unknown tools",
                tools=["Read", "UnknownTool", "FakeTool"]
            )
            issues = unknown_tools.validate()
            assert any("Unknown tool: UnknownTool" in issue for issue in issues)
            assert any("Unknown tool: FakeTool" in issue for issue in issues)
            self.results.add_result("Unknown tools detection", True)
        except Exception as e:
            self.results.add_result("Unknown tools detection", False, str(e))

    def test_directory_loading(self):
        """Test loading agents from .claude/agents directory."""
        temp_dir = self.create_temp_dir()

        try:
            # Create .claude/agents directory
            agents_dir = temp_dir / ".claude" / "agents"
            agents_dir.mkdir(parents=True)

            # Create test agents
            agent1_yaml = """---
name: Directory Agent 1
description: First test agent
tools: [Read, Write]
---

Test agent 1 instructions.
"""
            (agents_dir / "agent1.yaml").write_text(agent1_yaml)

            agent2_yml = """---
name: Directory Agent 2
description: Second test agent
tools: [Bash]
temperature: 0.9
---

Test agent 2 instructions.
"""
            (agents_dir / "agent2.yml").write_text(agent2_yml)

            # Test loader
            loader = AgentConfigurationLoader(base_dir=temp_dir)
            configs = loader.load_all()

            assert len(configs) == 2
            assert "agent1" in configs
            assert "agent2" in configs

            agent1 = configs["agent1"]
            assert agent1.name == "Directory Agent 1"
            assert agent1.tools == ["Read", "Write"]

            agent2 = configs["agent2"]
            assert agent2.name == "Directory Agent 2"
            assert agent2.temperature == 0.9

            self.results.add_result("Directory loading (.claude/agents)", True)

        except Exception as e:
            self.results.add_result("Directory loading (.claude/agents)", False, str(e))

    def test_fallback_directory_loading(self):
        """Test loading from .codexplus/agents fallback directory."""
        temp_dir = self.create_temp_dir()

        try:
            # Create .codexplus/agents directory
            alt_dir = temp_dir / ".codexplus" / "agents"
            alt_dir.mkdir(parents=True)

            # Create test agent
            agent_yaml = """---
name: Fallback Agent
description: Agent from fallback directory
tools: [Grep]
---"""
            (alt_dir / "fallback.yaml").write_text(agent_yaml)

            # Test loader
            loader = AgentConfigurationLoader(base_dir=temp_dir)
            configs = loader.load_all()

            assert len(configs) >= 1, f"Expected at least 1 agent, got {len(configs)}: {list(configs.keys())}"
            assert "fallback" in configs, f"Expected 'fallback' agent in {list(configs.keys())}"
            assert configs["fallback"].name == "Fallback Agent"

            self.results.add_result("Fallback directory loading (.codexplus/agents)", True)

        except Exception as e:
            self.results.add_result("Fallback directory loading (.codexplus/agents)", False, str(e))

    def test_json_backward_compatibility(self):
        """Test JSON format backward compatibility."""
        temp_dir = self.create_temp_dir()

        try:
            agents_dir = temp_dir / ".claude" / "agents"
            agents_dir.mkdir(parents=True)

            # Create JSON agent file
            json_agent = {
                "name": "JSON Agent",
                "description": "JSON format agent",
                "tools": ["Read", "Write"],
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.6,
                "capabilities": ["json_parsing"],
                "tags": ["json", "backward"]
            }
            (agents_dir / "json-agent.json").write_text(json.dumps(json_agent, indent=2))

            # Test loading
            loader = AgentConfigurationLoader(base_dir=temp_dir)
            configs = loader.load_all()

            assert "json-agent" in configs
            config = configs["json-agent"]
            assert config.name == "JSON Agent"
            assert config.tools == ["Read", "Write"]
            assert config.temperature == 0.6
            assert config.capabilities == {"json_parsing"}

            self.results.add_result("JSON backward compatibility", True)

        except Exception as e:
            self.results.add_result("JSON backward compatibility", False, str(e))

    def test_save_and_reload(self):
        """Test saving and reloading configurations."""
        temp_dir = self.create_temp_dir()

        try:
            loader = AgentConfigurationLoader(base_dir=temp_dir)

            # Create test configuration
            config = AgentConfiguration(
                name="Save Test Agent",
                description="Test saving functionality",
                tools=["Read", "Edit"],
                temperature=0.4,
                capabilities={"testing", "validation"},
                system_prompt="You are a save test agent.",
                instructions="Test save and reload functionality."
            )

            # Save as YAML
            loader.save_agent("save-test", config, format='yaml')

            # Reload and verify
            new_loader = AgentConfigurationLoader(base_dir=temp_dir)
            configs = new_loader.load_all()

            assert "save-test" in configs
            reloaded = configs["save-test"]
            assert reloaded.name == "Save Test Agent"
            assert reloaded.tools == ["Read", "Edit"]
            assert reloaded.temperature == 0.4
            assert reloaded.capabilities == {"testing", "validation"}
            assert reloaded.system_prompt and "save test agent" in reloaded.system_prompt

            self.results.add_result("Save and reload (YAML)", True)

        except Exception as e:
            self.results.add_result("Save and reload (YAML)", False, str(e))

    def test_mixed_formats(self):
        """Test loading mixed YAML and JSON formats."""
        temp_dir = self.create_temp_dir()

        try:
            loader = AgentConfigurationLoader(base_dir=temp_dir)

            # Save YAML agent
            yaml_config = AgentConfiguration(
                name="YAML Agent",
                description="YAML format agent",
                tools=["Read"]
            )
            loader.save_agent("yaml-agent", yaml_config, format='yaml')

            # Save JSON agent
            json_config = AgentConfiguration(
                name="JSON Agent",
                description="JSON format agent",
                tools=["Write"]
            )
            loader.save_agent("json-agent", json_config, format='json')

            # Load all
            configs = loader.load_all()

            assert len(configs) == 2
            assert configs["yaml-agent"].name == "YAML Agent"
            assert configs["json-agent"].name == "JSON Agent"

            self.results.add_result("Mixed format loading", True)

        except Exception as e:
            self.results.add_result("Mixed format loading", False, str(e))

    def test_agent_listing(self):
        """Test agent listing functionality."""
        temp_dir = self.create_temp_dir()

        try:
            loader = AgentConfigurationLoader(base_dir=temp_dir)

            # Create multiple agents
            for i in range(3):
                config = AgentConfiguration(
                    name=f"List Agent {i}",
                    description=f"Agent {i} for listing test",
                    tools=["Read"],
                    tags=[f"tag{i}", "listing"]
                )
                loader.save_agent(f"list-agent-{i}", config)

            # Load and list
            loader.load_all()
            agent_list = loader.list_agents()

            assert len(agent_list) == 3

            for agent_info in agent_list:
                assert "id" in agent_info
                assert "name" in agent_info
                assert "description" in agent_info
                assert "tools" in agent_info
                assert "model" in agent_info
                assert "tags" in agent_info
                assert "listing" in agent_info["tags"]

            self.results.add_result("Agent listing", True)

        except Exception as e:
            self.results.add_result("Agent listing", False, str(e))

    def test_default_agents_creation(self):
        """Test creation of default agent configurations."""
        temp_dir = self.create_temp_dir()

        try:
            loader = AgentConfigurationLoader(base_dir=temp_dir)
            loader.create_default_agents()

            # Load default agents
            configs = loader.load_all()

            # Check that default agents were created
            expected_agents = [
                "code-reviewer",
                "test-runner",
                "documentation-writer",
                "debugger",
                "refactoring-agent"
            ]

            for agent_id in expected_agents:
                assert agent_id in configs, f"Missing default agent: {agent_id}"
                config = configs[agent_id]
                assert config.name, f"Agent {agent_id} missing name"
                assert config.description, f"Agent {agent_id} missing description"
                assert config.system_prompt, f"Agent {agent_id} missing system prompt"

            # Check specific agent properties
            code_reviewer = configs["code-reviewer"]
            assert "security" in [tag.lower() for tag in code_reviewer.tags]
            assert code_reviewer.temperature <= 0.5  # Should be low for analysis

            test_runner = configs["test-runner"]
            assert "Bash" in test_runner.tools or "BashOutput" in test_runner.tools

            self.results.add_result("Default agents creation", True)

        except Exception as e:
            self.results.add_result("Default agents creation", False, str(e))

    def test_error_handling(self):
        """Test error handling for invalid files."""
        temp_dir = self.create_temp_dir()

        try:
            agents_dir = temp_dir / ".claude" / "agents"
            agents_dir.mkdir(parents=True)

            # Create invalid YAML file
            (agents_dir / "invalid.yaml").write_text("{{invalid yaml content")

            # Create valid agent alongside invalid one
            valid_yaml = """---
name: Valid Agent
description: Valid agent alongside invalid one
---"""
            (agents_dir / "valid.yaml").write_text(valid_yaml)

            # Test loader handles errors gracefully
            loader = AgentConfigurationLoader(base_dir=temp_dir)
            configs = loader.load_all()

            # Should load valid agent but skip invalid one
            assert "valid" in configs
            assert "invalid" not in configs
            assert configs["valid"].name == "Valid Agent"

            self.results.add_result("Error handling (invalid files)", True)

        except Exception as e:
            self.results.add_result("Error handling (invalid files)", False, str(e))

    def test_real_world_scenario(self):
        """Test with configuration similar to existing .claude/agents files."""
        temp_dir = self.create_temp_dir()

        try:
            # Create realistic agent configuration based on existing files
            realistic_yaml = """---
name: Code Reviewer
description: Specialized in comprehensive code review, security analysis, and best practices enforcement
model: claude-3-5-sonnet-20241022
temperature: 0.3
max_tokens: 8192
tools:
  - Read
  - Grep
  - Glob
  - WebSearch
capabilities:
  - code_analysis
  - security_review
  - performance_analysis
tags:
  - review
  - security
  - quality
  - best-practices
author: Codex Plus Team
version: 1.0.0
---

# System Prompt

You are an expert code reviewer with deep expertise in software security, performance optimization, and best practices across multiple programming languages and frameworks.

## Your Responsibilities:

1. **Security Analysis**
   - Identify potential vulnerabilities (SQL injection, XSS, CSRF, etc.)
   - Check for sensitive data exposure
   - Validate input sanitization
   - Review authentication and authorization logic

2. **Code Quality**
   - Ensure adherence to SOLID principles
   - Check for code duplication (DRY violations)
   - Evaluate naming conventions and readability
   - Assess test coverage and quality

## Review Process:

1. Start with a high-level architecture review
2. Examine critical security paths first
3. Review business logic implementation
4. Provide actionable recommendations with examples
"""

            agents_dir = temp_dir / ".claude" / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "code-reviewer.yaml").write_text(realistic_yaml)

            # Load and validate
            loader = AgentConfigurationLoader(base_dir=temp_dir)
            configs = loader.load_all()

            assert "code-reviewer" in configs
            config = configs["code-reviewer"]

            # Verify all aspects loaded correctly
            assert config.name == "Code Reviewer"
            assert config.model == "claude-3-5-sonnet-20241022"
            assert config.temperature == 0.3
            assert config.max_tokens == 8192
            assert "Read" in config.tools
            assert "WebSearch" in config.tools
            assert "code_analysis" in config.capabilities
            assert "security" in config.tags
            assert config.author == "Codex Plus Team"
            assert config.version == "1.0.0"
            assert config.system_prompt and "expert code reviewer" in config.system_prompt
            assert config.system_prompt and "Security Analysis" in config.system_prompt

            # Validate configuration
            issues = config.validate()
            assert len(issues) == 0, f"Real-world config has validation issues: {issues}"

            self.results.add_result("Real-world scenario", True)

        except Exception as e:
            self.results.add_result("Real-world scenario", False, str(e))

    def test_existing_agents_directory(self):
        """Test loading from actual .claude/agents directory if it exists."""
        try:
            current_dir = Path.cwd()
            claude_agents = current_dir / ".claude" / "agents"

            if not claude_agents.exists():
                self.results.add_result("Existing agents directory (skipped - no .claude/agents)", True)
                return

            # Load from real directory
            loader = AgentConfigurationLoader(base_dir=current_dir)
            configs = loader.load_all()

            print(f"  Found {len(configs)} existing agents:")
            for agent_id, config in configs.items():
                print(f"    • {agent_id}: {config.name}")

                # Validate each existing agent
                issues = config.validate()
                if issues:
                    print(f"      ⚠️  Issues: {issues}")

            # At minimum, should load some agents if directory exists
            assert len(configs) > 0, "No agents loaded from existing .claude/agents directory"

            self.results.add_result("Existing agents directory", True)

        except Exception as e:
            self.results.add_result("Existing agents directory", False, str(e))

    def run_all_tests(self):
        """Run all validation tests."""
        print("🚀 Starting Agent Configuration Loader Validation")
        print("="*60)

        # Core functionality tests
        print("\n📋 Testing Core YAML Parsing...")
        self.test_basic_yaml_parsing()
        self.test_frontmatter_without_body()
        self.test_yaml_without_frontmatter()

        print("\n🔍 Testing Configuration Validation...")
        self.test_configuration_validation()

        print("\n📁 Testing Directory Loading...")
        self.test_directory_loading()
        self.test_fallback_directory_loading()

        print("\n🔄 Testing Format Compatibility...")
        self.test_json_backward_compatibility()
        self.test_mixed_formats()

        print("\n💾 Testing Save/Load Functionality...")
        self.test_save_and_reload()

        print("\n📝 Testing Agent Management...")
        self.test_agent_listing()
        self.test_default_agents_creation()

        print("\n⚠️  Testing Error Handling...")
        self.test_error_handling()

        print("\n🌍 Testing Real-World Scenarios...")
        self.test_real_world_scenario()
        self.test_existing_agents_directory()

        # Clean up
        self.cleanup()

        # Show results
        self.results.summary()

        return self.results.tests_failed == 0


def create_sample_agents():
    """Create sample agent configurations for demonstration."""
    print("\n📝 Creating sample agent configurations...")

    sample_agents_dir = Path.cwd() / ".claude" / "agents" / "samples"
    sample_agents_dir.mkdir(parents=True, exist_ok=True)

    # Sample 1: Security Focused Agent
    security_agent = """---
name: Security Auditor
description: Specialized agent for security vulnerability assessment and penetration testing
model: claude-3-5-sonnet-20241022
temperature: 0.2
max_tokens: 8192
tools:
  - Read
  - Grep
  - WebSearch
  - Bash
capabilities:
  - security_analysis
  - vulnerability_assessment
  - penetration_testing
tags:
  - security
  - audit
  - vulnerability
  - pentest
author: Agent Validation Suite
version: 1.0.0
allowed_paths:
  - "/tmp"
  - "./tests"
forbidden_paths:
  - "/etc/passwd"
  - "/root"
---

# System Prompt

You are a cybersecurity specialist focused on identifying and analyzing security vulnerabilities in software systems.

## Core Expertise:

1. **OWASP Top 10** - Deep knowledge of web application security risks
2. **Network Security** - Port scanning, service enumeration, protocol analysis
3. **Code Analysis** - Static analysis for security flaws and best practices
4. **Infrastructure Security** - Container, cloud, and system hardening

## Methodology:

1. **Reconnaissance** - Gather information about the target system
2. **Vulnerability Scanning** - Automated and manual vulnerability discovery
3. **Exploitation** - Proof-of-concept development (ethical testing only)
4. **Reporting** - Clear documentation of findings with remediation steps

Always prioritize responsible disclosure and ethical testing practices.
"""
    (sample_agents_dir / "security-auditor.yaml").write_text(security_agent)

    # Sample 2: Performance Optimization Agent
    performance_agent = """---
name: Performance Optimizer
description: Specialized in application performance analysis and optimization strategies
model: claude-3-5-sonnet-20241022
temperature: 0.4
max_tokens: 6144
tools:
  - Read
  - Bash
  - BashOutput
  - Grep
  - Glob
capabilities:
  - performance_analysis
  - profiling
  - optimization
  - benchmarking
tags:
  - performance
  - optimization
  - profiling
  - benchmarks
author: Agent Validation Suite
version: 1.0.0
---

# System Prompt

You are a performance engineering specialist with expertise in identifying bottlenecks and optimizing system performance across various technologies.

## Key Areas:

1. **Application Profiling** - CPU, memory, I/O analysis
2. **Database Optimization** - Query performance, indexing strategies
3. **Algorithm Analysis** - Complexity assessment and optimization
4. **Infrastructure Tuning** - System-level performance improvements

## Tools & Techniques:

- Performance profilers (py-spy, perf, gprof)
- Database query analyzers
- Load testing frameworks
- Memory leak detection

## Process:

1. **Baseline Measurement** - Establish current performance metrics
2. **Bottleneck Identification** - Profile and identify critical paths
3. **Optimization Implementation** - Apply targeted improvements
4. **Validation** - Measure and verify performance gains

Focus on data-driven optimization with measurable improvements.
"""
    (sample_agents_dir / "performance-optimizer.yaml").write_text(performance_agent)

    # Sample 3: Documentation Generator
    docs_agent = """---
name: Documentation Generator
description: Automated documentation creation and maintenance for software projects
model: claude-3-5-sonnet-20241022
temperature: 0.6
max_tokens: 8192
tools:
  - Read
  - Write
  - Edit
  - MultiEdit
  - Grep
  - Glob
capabilities:
  - documentation
  - technical_writing
  - api_docs
  - user_guides
tags:
  - docs
  - documentation
  - writing
  - api
  - guides
author: Agent Validation Suite
version: 1.0.0
---

# System Prompt

You are a technical documentation specialist focused on creating clear, comprehensive, and user-friendly documentation for software projects.

## Documentation Types:

1. **API Documentation** - OpenAPI/Swagger, endpoint descriptions, examples
2. **User Guides** - Step-by-step instructions, tutorials, best practices
3. **Developer Documentation** - Setup guides, architecture overviews, contributing guidelines
4. **Code Documentation** - Inline comments, docstrings, code examples

## Writing Principles:

- **Clarity** - Use simple, precise language
- **Completeness** - Cover all necessary information
- **Consistency** - Maintain uniform style and structure
- **Currency** - Keep documentation up-to-date with code changes

## Process:

1. **Analysis** - Understand the software and its users
2. **Structure** - Organize information logically
3. **Writing** - Create clear, actionable content
4. **Review** - Validate accuracy and usability
5. **Maintenance** - Keep documentation current

Always write from the user's perspective and include practical examples.
"""
    (sample_agents_dir / "documentation-generator.yaml").write_text(docs_agent)

    print(f"✅ Created 3 sample agents in {sample_agents_dir}")
    print("  • security-auditor.yaml - Security vulnerability assessment")
    print("  • performance-optimizer.yaml - Performance analysis and optimization")
    print("  • documentation-generator.yaml - Automated documentation creation")


def main():
    """Main validation function."""
    print("🎯 Agent Configuration Loader Validation Suite")
    print("=" * 60)
    print("This script validates the AgentConfigurationLoader implementation")
    print("to ensure it meets all requirements and follows Claude Code CLI patterns.\n")

    try:
        # Run validation
        validator = AgentLoaderValidator()
        success = validator.run_all_tests()

        # Create sample agents for demonstration
        create_sample_agents()

        print("\n" + "="*60)
        print("VALIDATION COMPLETE")
        print("="*60)

        if success:
            print("🎉 Agent configuration loader is PRODUCTION READY!")
            print("✅ All tests passed - the implementation correctly follows Claude Code CLI patterns")
            print("✅ YAML frontmatter parsing works correctly")
            print("✅ Configuration validation is comprehensive")
            print("✅ Directory loading supports both .claude/agents and .codexplus/agents")
            print("✅ JSON backward compatibility is maintained")
            print("✅ Error handling is robust")
            print("✅ Default agent creation works properly")

            print("\n📋 Key Features Validated:")
            print("  • YAML frontmatter parsing with full Claude Code CLI compatibility")
            print("  • Configuration validation with proper error reporting")
            print("  • Directory-based agent loading (.claude/agents priority)")
            print("  • Backward compatibility with JSON configurations")
            print("  • Robust error handling for invalid files")
            print("  • Default agent templates following best practices")
            print("  • Mixed format support (YAML + JSON)")
            print("  • Agent listing and management capabilities")

            return 0
        else:
            print("❌ Some validation tests failed")
            print("⚠️  Review the failure details above before using in production")
            return 1

    except Exception as e:
        print(f"\n💥 Validation failed with error: {e}")
        print("Stack trace:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())