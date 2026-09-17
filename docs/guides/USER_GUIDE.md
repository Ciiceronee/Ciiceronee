# Ciicerone User Guide

**Version:** 0.1.0  
**Last Updated:** September 2026

Complete guide for installing, configuring, and using Ciicerone for threat simulation and security training.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [CLI Reference](#cli-reference)
5. [Template Usage](#template-usage)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Installation

### Prerequisites

- **Python 3.11+** (Required)
- **Git** (for cloning repository)
- **API Key** for LLM provider (OpenRouter, OpenAI, or Anthropic)

### Step 1: Clone Repository

```bash
git clone https://github.com/Ciicerone-AI/Ciicerone.git
cd Ciicerone
```

### Step 2: Create Virtual Environment

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure API Keys

```bash
# Set OpenRouter API key (recommended)
export OPENROUTER_API_KEY="your-api-key-here"

# Or OpenAI
export OPENAI_API_KEY="your-api-key-here"

# Or Anthropic
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Step 5: Verify Installation

```bash
python3 -m Ciicerone --version
python3 -m Ciicerone templates list
```

---

## Quick Start

### Run Your First Simulation

```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.\.venv\Scripts\Activate.ps1  # Windows

# Run a phishing simulation
python3 -m Ciicerone simulate -s templates/executive_phishing.yaml

# View generated content
ls generated_content/
```

### Test Without API Calls

```bash
# Dry run validates configuration without LLM calls
python3 -m Ciicerone simulate -s templates/executive_phishing.yaml --dry-run

# Preview scenario details
python3 -m Ciicerone simulate -s templates/finance_bec.yaml --preview
```

---

## Configuration

### Configuration File: `config.yaml`

Ciicerone uses `config.yaml` for system configuration:

```yaml
llm:
  default_provider: "openrouter"
  
  openrouter:
    base_url: "https://openrouter.ai/api/v1"
    model: "openai/gpt-5.1-chat"
    max_tokens: 1000
    temperature: 0.7
    timeout: 60
    retry_attempts: 3
  
  openai:
    model: "gpt-4"
    max_tokens: 1000
    
  anthropic:
    model: "claude-3-haiku-20240307"
    max_tokens: 1000

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/Ciicerone.log"

content:
  output_directory: "generated_content"
  save_format: "markdown"
  include_metadata: true
```

### Environment Variables

Override config with environment variables:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export CIICERONE_LOG_LEVEL="DEBUG"
export CIICERONE_OUTPUT_DIR="./my_output"
```

---

## CLI Reference

### Global Options

Available for all commands:

```bash
python3 -m Ciicerone [OPTIONS] COMMAND [ARGS]

Options:
  --version           Show version and exit
  --verbose, -v       Enable verbose output
  --config PATH       Configuration file path
  --help              Show help message
```

### Simulation Commands

#### Run Simulation

```bash
python3 -m Ciicerone simulate [OPTIONS]

Options:
  -s, --scenario PATH     Scenario template file (required)
  -t, --target TEXT       Custom target profile
  -o, --output FORMAT     Output format (json|yaml|report)
  --dry-run               Validate without executing
  --preview               Show scenario preview

Examples:
  # Basic execution
  python3 -m Ciicerone simulate -s templates/executive_phishing.yaml
  
  # Dry run
  python3 -m Ciicerone simulate -s templates/finance_bec.yaml --dry-run
  
  # JSON output
  python3 -m Ciicerone simulate -s templates/it_helpdesk.yaml -o json
```

### Template Commands

#### List Templates

```bash
python3 -m Ciicerone templates list

# List with validation
python3 -m Ciicerone templates list --validate

# Tree format
python3 -m Ciicerone templates list --format tree
```

#### Show Template Details

```bash
python3 -m Ciicerone templates show TEMPLATE_NAME

# Example
python3 -m Ciicerone templates show executive_phishing
```

#### Validate Templates

```bash
# Validate single template
python3 -m Ciicerone templates show executive_phishing --validate

# Validate all templates
python3 -m Ciicerone templates validate-all
```

#### Create Template

```bash
# Copy existing template
python3 -m Ciicerone templates copy executive_phishing.yaml my_phishing.yaml

# Edit the new template
nano templates/my_phishing.yaml
```

### LLM Commands

#### Test LLM Providers

```bash
python3 -m Ciicerone llm test-providers

# Test specific provider
python3 -m Ciicerone llm test-providers --provider openrouter
```

#### Generate Content

```bash
python3 -m Ciicerone llm generate templates/executive_phishing.yaml

# Specify content type
python3 -m Ciicerone llm generate \
    --content-type email_phishing \
    templates/executive_phishing.yaml
```

### Intelligence Commands

#### Query Threat Intelligence

```bash
python3 -m Ciicerone intel query "phishing techniques"

# Get MITRE ATT&CK mapping
python3 -m Ciicerone intel mitre T1566.001
```

### Deployment Commands

#### Start API Server

```bash
python3 -m Ciicerone deploy start-api

# Custom port
python3 -m Ciicerone deploy start-api --port 8080

# With workers
python3 -m Ciicerone deploy start-api --workers 4
```

---

## Template Usage

### Template Structure

Templates are YAML files defining threat scenarios:

```yaml
metadata:
  name: "My Phishing Campaign"
  description: "Custom phishing simulation"
  version: "1.0.0"
  author: "Security Team"
  tags: ["phishing", "email"]

threat_type: "phishing"
delivery_vector: "email"
difficulty_level: 7
estimated_duration: 30

target_profile:
  role: "Employee"
  department: "finance"
  seniority: "mid"
  technical_level: "moderate"
  security_awareness_level: 5

behavioral_pattern:
  psychological_triggers:
    - "urgency"
    - "authority"
  social_engineering_tactics:
    - "impersonation"
    - "pretexting"
  technical_methods:
    - "email_spoofing"
    - "credential_harvesting"
```

### Customizing Templates

1. **Copy template:**
   ```bash
   cp templates/executive_phishing.yaml templates/my_scenario.yaml
   ```

2. **Edit metadata:**
   - Update `name`, `description`, `author`
   - Add relevant `tags`

3. **Configure target:**
   - Set `role`, `department`, `seniority`
   - Adjust `security_awareness_level` (1-10)

4. **Adjust difficulty:**
   - `difficulty_level`: 1-10 (affects complexity)
   - `estimated_duration`: Minutes

5. **Validate:**
   ```bash
   python3 -m Ciicerone templates show my_scenario --validate
   ```

### Available Templates

- **executive_phishing.yaml** - C-level spear-phishing
- **finance_bec.yaml** - Business Email Compromise
- **it_helpdesk_impersonation.yaml** - IT support social engineering
- **executive_smishing.yaml** - SMS phishing targeting executives
- **supply_chain_compromise.yaml** - Vendor impersonation
- **healthcare_variable_scenario.yaml** - HIPAA-themed attacks
- **rich_adaptive_scenario.yaml** - Multi-stage adaptive campaign

---

## Best Practices

### Security Training

1. **Start Simple:** Begin with difficulty level 3-5
2. **Progressive Training:** Increase difficulty over time
3. **Department-Specific:** Customize for target departments
4. **Measure Results:** Track click rates and report rates

### Simulation Execution

1. **Always Use Dry Run:** Validate before executing
2. **Review Content:** Check generated content for appropriateness
3. **Document Campaigns:** Use clear naming and metadata
4. **Compliance Mode:** Enable for regulated industries

### Template Development

1. **Version Control:** Use semantic versioning (1.0.0)
2. **MITRE Mapping:** Include ATT&CK technique references
3. **Clear Documentation:** Add comprehensive descriptions
4. **Test Thoroughly:** Validate before production use

---

## Troubleshooting

### "Command Not Found"

**Problem:** `Ciicerone: command not found`

**Solution:** Activate virtual environment
```bash
source .venv/bin/activate  # macOS/Linux
.\.venv\Scripts\Activate.ps1  # Windows
```

### "Configuration File Not Found"

**Problem:** Cannot find scenario template

**Solution:** Use full path from project root
```bash
# Correct
python3 -m Ciicerone simulate -s templates/executive_phishing.yaml

# Wrong
python3 -m Ciicerone simulate -s executive_phishing.yaml
```

### "API Authentication Error"

**Problem:** 401 Unauthorized or 403 Forbidden

**Solution:** Set API key environment variable
```bash
export OPENROUTER_API_KEY="your-key-here"

# Verify
python3 -m Ciicerone llm test-providers
```

### Template Validation Errors

**Problem:** Template fails validation

**Solution:** Check validation output
```bash
# See detailed errors
python3 -m Ciicerone templates show my_template --validate

# Common issues:
# - Missing required fields
# - Invalid enum values
# - Incorrect data types
```

### Content Generation Failures

**Problem:** LLM generation fails or times out

**Solution:**
1. Check API key is valid
2. Verify internet connectivity
3. Try different provider
4. Reduce max_tokens in config.yaml

```bash
# Test provider
python3 -m Ciicerone llm test-providers

# Use dry-run to test template
python3 -m Ciicerone simulate -s template.yaml --dry-run
```

### "ModuleNotFoundError"

**Problem:** Python cannot find modules

**Solution:** Reinstall dependencies in virtual environment
```bash
# Activate environment
source .venv/bin/activate

# Reinstall
pip install -r requirements.txt

# Verify
pip list | grep Ciicerone
```

---

## Additional Resources

- **API Documentation:** See API_DOCUMENTATION.md
- **Configuration Reference:** See CONFIGURATION_REFERENCE.md
- **Security Guide:** See SECURITY_GUIDE.md
- **Developer Guide:** See DEVELOPER_GUIDE.md

---

## Support

- **GitHub Issues:** https://github.com/Ciicerone-AI/Ciicerone/issues
- **Email:** Ciicerone@hotmail.com
- **Documentation:** Project README.md
