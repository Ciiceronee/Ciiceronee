# Ciicerone: Enterprise AI-Powered Threat Simulation Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Beta](https://img.shields.io/badge/status-beta-yellow.svg)](https://github.com/Ciicerone/Ciicerone)
[![Security: Bandit](https://img.shields.io/badge/security-bandit-green.svg)](https://github.com/PyCQA/bandit)

**Ciicerone** is an enterprise-grade cybersecurity threat simulation platform that leverages Large Language Models (LLMs) to generate realistic, context-aware threat scenarios for security training, red team exercises, and compliance testing.

## Overview

- **Multi-LLM Support**: ✅ Integrates with OpenAI GPT-4, Anthropic Claude, OpenRouter, and **Ollama (Local/Offline)**
- **Local LLM Support**: 🆕 Run completely offline with Ollama - no API keys or internet required!
- **YAML-Based Configuration**: ✅ Define threat scenarios using intuitive YAML schemas  
- **Core Simulation Engine (Beta)**: ✅ LLM orchestration, safety filter enforcement, and a hardened REST API with authentication — currently in production-hardening
- **CLI Interface**: ✅ Command-line tool for scenario management and execution
- **REST API**: ✅ FastAPI-based REST endpoints with authentication for enterprise integration
- **Safety Framework**: ✅ Built-in content filtering and compliance enforcement
- **Analytics & Reporting**: 🚧 Comprehensive logging & metrics (planned)
- **VM Automation, Threat Hunting, Audit CLI**: 🧪 Experimental — roadmap only, not part of v1

### Key Features

- **Multi-LLM Support**: OpenAI GPT-4, Anthropic Claude, OpenRouter, Ollama, and local models
- **YAML-Based Templates**: Define threat scenarios using intuitive, version-controlled templates
- **CLI & REST API**: Flexible interfaces for automation and integration
- **Enterprise Deployment**: Docker, Kubernetes, and cloud-native deployment options
- **Comprehensive Logging**: Audit trails and analytics for compliance
- **Safety Framework**: Built-in content filtering and ethical guidelines
- **Dataset Integration**: PhishTank, Enron Email Corpus, MITRE ATT&CK framework

---

## Architecture

### System Components

```
Ciicerone Platform
├── Core Simulation Engine
│   ├── Template Manager (YAML-based scenario definitions)
│   ├── Simulation Orchestrator (Execution and workflow management)
│   └── Output Manager (Content generation and storage)
│
├── LLM Integration Layer
│   ├── Multi-Provider Support (OpenAI, Anthropic, OpenRouter, Ollama)
│   ├── Connection Pooling (+40% performance improvement)
│   ├── Rate Limiting & Retry Logic
│   └── Fallback & Error Handling
│
├── Dataset Integration
│   ├── PhishTank (Phishing intelligence)
│   ├── Enron Email Corpus (Email communication patterns)
│   ├── MITRE ATT&CK (Threat intelligence framework)
│   └── Extensible processor architecture
│
├── Integration Layer
│   ├── Microsoft 365 (Email deployment)
│   ├── Proofpoint (Security platform integration)
│   ├── KnowBe4 (Training platform)
│   ├── Slack (Collaboration platform)
│   └── Extensible base class for custom integrations
│
├── API & CLI Interfaces
│   ├── FastAPI REST API (Enterprise integration)
│   ├── Command-Line Interface (Direct usage)
│   └── Python SDK (Programmatic access)
│
└── Safety & Compliance
    ├── Content Filtering
    ├── Audit Logging
    ├── GDPR Compliance
    └── Ethical Use Guidelines
```

### Technology Stack

- **Language**: Python 3.11+
- **API Framework**: FastAPI
- **LLM Integration**: aiohttp, httpx (with connection pooling)
- **Data Validation**: Pydantic
- **Configuration**: YAML
- **Async I/O**: asyncio, aiohttp
- **Testing**: pytest, pytest-asyncio
- **Code Quality**: black, isort, flake8, mypy
- **Deployment**: Docker, Kubernetes

---

## Quick Start

### Prerequisites

- **Python 3.11 or higher**
- **Git** (for cloning the repository)
- **LLM API Key** (OpenRouter, OpenAI, or Anthropic)
- **Virtual Environment** (recommended)

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/ciicerone/ciicerone.git
cd Ciicerone
```

#### 2. Create Virtual Environment

**Windows (PowerShell):**
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

#### 3. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (optional)
pip install -r requirements-dev.txt
```

#### 4. Configure API Keys

```bash
# Set your API key as environment variable
export OPENROUTER_API_KEY="your-api-key-here"

# Edit config.yaml with your settings
nano config.yaml
```

**Example Configuration:**
```yaml
llm:
  provider: openrouter
  openrouter:
    api_key: "your-api-key-here"
    model: "qwen/qwen-2.5-72b-instruct"
    
simulation:
  output_dir: "./generated_content"
  auto_save: true
  
logging:
  level: INFO
  file: "./logs/ciicerone.log"
```

#### 5. Verify Installation

```bash
# Check CLI availability
ciicerone --help

# Validate installation
ciicerone templates validate-all

# Test with dry run (no API calls)
ciicerone simulate -s templates/executive_phishing.yaml --dry-run
```

---

## Usage Guide

### Command-Line Interface

#### Template Management

```bash
# List all available templates
ciicerone templates list

# Show template details with validation
ciicerone templates show executive_phishing --validate

# Validate all templates
ciicerone templates validate-all

# Check template ecosystem health
ciicerone templates health
```

#### Running Simulations

```bash
# Run a simulation
ciicerone simulate -s templates/executive_phishing.yaml

# Dry run (no API calls)
ciicerone simulate -s templates/executive_phishing.yaml --dry-run

# Specify output directory
ciicerone simulate -s templates/finance_bec.yaml -o ./output/campaign_001

# Run with specific LLM provider
ciicerone simulate -s templates/it_helpdesk.yaml --provider openai
```

#### Configuration Management

```bash
# Show current configuration
ciicerone config show

# Set configuration value
ciicerone config set llm.provider openrouter

# Validate configuration
ciicerone config validate
```

#### Dataset Management

```bash
# List available datasets
ciicerone datasets list

# Download and process dataset
ciicerone datasets download phishtank

# Show dataset statistics
ciicerone datasets stats enron

# Update all datasets
ciicerone datasets update-all
```

### REST API

#### Start API Server

```bash
# Start FastAPI server
ciicerone api start

# Specify host and port
ciicerone api start --host 0.0.0.0 --port 8000

# Start with auto-reload (development)
ciicerone api start --reload
```

#### API Endpoints

**Generate Threat Content:**
```bash
curl -X POST "http://localhost:8000/llm/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a phishing email targeting HR department",
    "scenario_type": "phishing",
    "max_tokens": 500,
    "temperature": 0.7
  }'
```

**Create Scenario:**
```bash
curl -X POST "http://localhost:8000/scenarios" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q4 Security Awareness Campaign",
    "threat_type": "phishing",
    "target_role": "employee",
    "severity": "medium"
  }'
```

**List Templates:**
```bash
curl "http://localhost:8000/templates"
```

**API Documentation:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Python SDK

```python
from ciicerone import CiiceroneClient

# Initialize client
client = CiiceroneClient(api_key="your-api-key", provider="openrouter")

# Load and run simulation
simulation = client.load_template("templates/executive_phishing.yaml")
result = simulation.run()

# Access generated content
print(result.content)
print(result.metadata)

# Save to file
result.save("output/campaign_001.json")
```

---

## Configuration

### Configuration File Structure

**`config.yaml`** (YAML format):

```yaml
# LLM Provider Configuration
llm:
  provider: openrouter  # Options: openrouter, openai, anthropic, ollama
  
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
    model: "qwen/qwen-2.5-72b-instruct"
    base_url: "https://openrouter.ai/api/v1"
    timeout: 120
    
  openai:
    api_key: ${OPENAI_API_KEY}
    model: "gpt-4"
    
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: "claude-3-opus-20240229"
    
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.1:70b"

# Simulation Configuration
simulation:
  output_dir: "./generated_content"
  auto_save: true
  index_enabled: true
  max_concurrent: 5

# Dataset Configuration
datasets:
  storage_path: "./data"
  auto_update: false
  phishtank:
    enabled: true
    update_interval_days: 7
  enron:
    enabled: true
  mitre_attack:
    enabled: true

# Deployment Integration
deployment:
  enabled: false
  microsoft365:
    enabled: false
    tenant_id: ${M365_TENANT_ID}
    client_id: ${M365_CLIENT_ID}
    client_secret: ${M365_CLIENT_SECRET}

# Logging Configuration
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file: "./logs/ciicerone.log"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  rotation: "10 MB"
  retention: 30  # days

# Safety Configuration
safety:
  content_filtering: true
  audit_logging: true
  rate_limiting:
    enabled: true
    requests_per_minute: 60
```

### Environment Variables

```bash
# LLM Provider Keys
export OPENROUTER_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"

# Deployment Integration
export M365_TENANT_ID="your-tenant-id"
export M365_CLIENT_ID="your-client-id"
export M365_CLIENT_SECRET="your-client-secret"

# Application Settings
export CIICERONE_ENV="production"
export CIICERONE_LOG_LEVEL="INFO"
```

---

## Template System

### Template Structure

Templates define threat scenarios using YAML format:

```yaml
# Template metadata
template_id: executive_phishing_v1
name: "Executive Phishing Campaign"
version: "1.0.0"
author: "Security Team"
description: "Sophisticated phishing targeting C-level executives"

# Threat classification
threat_type: phishing
severity: high
complexity: advanced
target_role: executive

# Scenario configuration
scenario:
  subject_line: "Urgent: Q4 Financial Review Required"
  sender_persona: "CFO Office"
  urgency_level: high
  social_engineering_tactics:
    - authority
    - urgency
    - fear
  
  context:
    company_size: "enterprise"
    industry: "technology"
    quarter: "Q4"
    
  content_requirements:
    tone: "professional"
    length: "medium"
    technical_details: true
    personalization: high

# LLM generation parameters
generation:
  max_tokens: 800
  temperature: 0.7
  top_p: 0.9
  
# Variables for dynamic content
variables:
  ceo_name: "Michael Stevens"
  company_name: "TechCorp International"
  deadline: "End of week"
  fiscal_year: "FY2025"

# Safety controls
safety:
  content_filtering: true
  pii_masking: true
  disclaimer_required: true
```

### Creating Custom Templates

1. **Copy Example Template:**
```bash
cp templates/sample_phishing_template.yaml templates/my_custom_template.yaml
```

2. **Edit Template:**
```yaml
template_id: my_custom_scenario
name: "My Custom Threat Scenario"
threat_type: social_engineering
# ... customize fields
```

3. **Validate Template:**
```bash
ciicerone templates show my_custom_template --validate
```

4. **Run Simulation:**
```bash
ciicerone simulate -s templates/my_custom_template.yaml
```

---

## Deployment

### Docker Deployment

#### Build Image

```bash
# Build production image
docker build -t ciicerone:latest .

# Build with specific tag
docker build -t ciicerone:v1.0.0 .
```

#### Run Container

```bash
# Run with environment variables
docker run -d \
  --name ciicerone \
  -p 8000:8000 \
  -e OPENROUTER_API_KEY="your-key" \
  -v $(pwd)/generated_content:/app/generated_content \
  -v $(pwd)/logs:/app/logs \
  ciicerone:latest

# Run with config file
docker run -d \
  --name ciicerone \
  -p 8000:8000 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/generated_content:/app/generated_content \
  ciicerone:latest
```

### Docker Compose

**`docker-compose.yml`:**

```yaml
version: '3.8'

services:
  ciicerone-api:
    image: ciicerone:latest
    container_name: ciicerone-api
    ports:
      - "8000:8000"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - CIICERONE_ENV=production
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./generated_content:/app/generated_content
      - ./logs:/app/logs
      - ./data:/app/data
    restart: unless-stopped
    
  ciicerone-worker:
    image: ciicerone:latest
    container_name: ciicerone-worker
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./generated_content:/app/generated_content
      - ./data:/app/data
    command: ["python", "-m", "ciicerone.worker"]
    restart: unless-stopped
```

**Deploy:**

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Scale API instances
docker-compose up -d --scale ciicerone-api=3

# Stop services
docker-compose down
```

### Kubernetes Deployment

#### Basic Deployment

**`k8s/deployment.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ciicerone
  labels:
    app: ciicerone
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ciicerone
  template:
    metadata:
      labels:
        app: ciicerone
    spec:
      containers:
      - name: ciicerone
        image: ciicerone:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENROUTER_API_KEY
          valueFrom:
            secretKeyRef:
              name: ciicerone-secrets
              key: openrouter-api-key
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: storage
          mountPath: /app/generated_content
      volumes:
      - name: config
        configMap:
          name: ciicerone-config
      - name: storage
        persistentVolumeClaim:
          claimName: ciicerone-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: ciicerone
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: ciicerone
```

**Deploy:**

```bash
# Create namespace
kubectl create namespace ciicerone

# Create secrets
kubectl create secret generic ciicerone-secrets \
  --from-literal=openrouter-api-key="your-key" \
  -n ciicerone

# Create config map
kubectl create configmap ciicerone-config \
  --from-file=config.yaml \
  -n ciicerone

# Apply deployment
kubectl apply -f k8s/ -n ciicerone

# Check status
kubectl get pods -n ciicerone
kubectl get svc -n ciicerone

# View logs
kubectl logs -f deployment/ciicerone -n ciicerone
```

---

## Security & Compliance

### Security Best Practices

1. **API Key Management:**
   - Store keys in environment variables or secrets management systems
   - Never commit keys to version control
   - Rotate keys regularly
   - Use separate keys for development and production

2. **Network Security:**
   - Deploy behind a firewall or VPN
   - Use HTTPS/TLS for API endpoints
   - Implement IP whitelisting for sensitive deployments
   - Enable rate limiting

3. **Access Control:**
   - Implement role-based access control (RBAC)
   - Use strong authentication mechanisms
   - Log all access attempts
   - Regular access reviews

4. **Data Protection:**
   - Enable audit logging
   - Implement data retention policies
   - Encrypt sensitive data at rest and in transit
   - Regular security audits

### Compliance Features

- **GDPR Compliance**: Data protection and privacy controls
- **Audit Logging**: Comprehensive activity tracking
- **Content Filtering**: Prevents harmful content generation
- **Ethical Guidelines**: Clear usage policies and restrictions

### Responsible Use Policy

**Authorized Use Cases:**
- Security training and awareness programs
- Red team exercises and penetration testing (with authorization)
- Security control validation and testing
- Compliance and audit documentation
- Educational and research purposes

**Prohibited Use Cases:**
- Actual malicious activities or attacks
- Unauthorized system access or testing
- Harassment, threats, or harmful content
- Bypassing security controls or systems
- Any illegal activities

---

## Performance & Scalability

### Performance Metrics

- **Connection Pooling**: +40% performance improvement over per-request sessions
- **Memory Efficiency**: -30% memory usage with shared session pools
- **Download Speed**: +25% with optimized async I/O
- **API Response Time**: < 200ms (excluding LLM generation)
- **Concurrent Requests**: Supports 100+ concurrent simulations

### Scalability

- **Horizontal Scaling**: Deploy multiple API instances behind load balancer
- **Async Architecture**: Non-blocking I/O for high throughput
- **Resource Optimization**: Efficient memory and connection management
- **Caching**: Template and dataset caching for repeated operations

### Monitoring

```bash
# Enable metrics endpoint
ciicerone api start --metrics

# Prometheus metrics available at /metrics
curl http://localhost:8000/metrics

# Health check endpoint
curl http://localhost:8000/health
```

---

## Documentation

### Available Documentation

- **[API Documentation](docs/api/)** - REST API reference and OpenAPI spec
- **[User Guide](docs/guides/USER_GUIDE.md)** - Complete usage guide
- **[Developer Guide](docs/guides/DEVELOPER_GUIDE.md)** - Contributing and development
- **[Configuration Reference](docs/reference/)** - Configuration schemas
- **[Security Guide](docs/guides/SECURITY_GUIDE.md)** - Security best practices
- **[Template Manual](TEMPLATE_MANUAL.md)** - Template creation guide
- **[Dataset Integration](DATASET_INTEGRATION.md)** - Dataset processor guide

### Quick Links

- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs) (when running)
- **GitHub Repository**: [https://github.com/ciicerone/ciicerone](https://github.com/ciicerone/ciicerone)
- **Issue Tracker**: [https://github.com/ciicerone/ciicerone/issues](https://github.com/ciicerone/ciicerone/issues)

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repository
git clone https://github.com/ciicerone/ciicerone.git
cd Ciicerone

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run code quality checks
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/
```

### Contribution Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `pytest`
5. Run code quality checks
6. Commit changes: `git commit -m 'Add amazing feature'`
7. Push to branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

---

## Troubleshooting

### Common Issues

#### Installation Issues

**Problem**: `ciicerone: command not found`

**Solution**: Activate virtual environment
```bash
# Windows
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

**Problem**: `ModuleNotFoundError`

**Solution**: Install requirements in virtual environment
```bash
pip install -r requirements.txt
```

#### Configuration Issues

**Problem**: `Configuration file not found`

**Solution**: Create config.yaml from example
```bash
cp config.yaml.example config.yaml
```

**Problem**: `API authentication failed`

**Solution**: Verify API key is set
```bash
# Check environment variable
echo $OPENROUTER_API_KEY

# Or set in config.yaml
ciicerone config set llm.openrouter.api_key "your-key"
```

#### Runtime Issues

**Problem**: Template validation errors

**Solution**: Validate and fix templates
```bash
ciicerone templates show my_template --validate
ciicerone templates fix my_template
```

**Problem**: Simulation fails with timeout

**Solution**: Increase timeout in config
```yaml
llm:
  openrouter:
    timeout: 180  # Increase to 180 seconds
```

### Getting Help

- **Check Logs**: `logs/ciicerone.log`
- **Validate Configuration**: `ciicerone config validate`
- **Test Connection**: `ciicerone llm test`
- **GitHub Issues**: [Report a bug](https://github.com/ciicerone/ciicerone/issues)
- **Email Support**: ciicerone@ciicerone.com

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses

Ciicerone uses the following open-source libraries:
- FastAPI (MIT License)
- Pydantic (MIT License)
- aiohttp (Apache 2.0)
- PyYAML (MIT License)

Full license information available in `LICENSE` file.

---

## Acknowledgments

- **MITRE ATT&CK Framework** for threat intelligence taxonomy
- **OpenAI, Anthropic, Meta** for LLM capabilities
- **PhishTank** for phishing intelligence data
- **Carnegie Mellon University** for Enron Email Corpus
- **Open Source Community** for tools and libraries

---

## Support & Contact

- **Documentation**: [https://github.com/ciicerone/ciicerone](https://github.com/ciicerone/ciicerone)
- **Issues**: [GitHub Issues](https://github.com/ciicerone/ciicerone/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ciicerone/ciicerone/discussions)
- **Email**: ciicerone@ciicerone.com
- **Twitter**: [@Thundastormgod](https://twitter.com/Thundastormgod)

---

## Project Status

- **Current Version**: 0.1.0
- **Status**: Beta — core (LLM orchestration, safety framework, authenticated API) is production-hardening; VM automation, threat hunting, and the audit CLI are experimental and not part of v1
- **Last Updated**: September 2026
- **Active Maintenance**: Yes
- **Open to Contributions**: Yes

### Roadmap

**Version 1.1.0** (Q1 2026):
- Advanced analytics and reporting dashboard
- Enhanced dataset integration (additional threat intelligence sources)
- Machine learning-based content optimization
- Multi-language support

**Version 1.2.0** (Q2 2026):
- Collaborative scenario builder
- Advanced deployment integrations
- Real-time threat intelligence feeds
- Enterprise SSO integration

---

**Important Disclaimer**

Ciicerone is a simulation tool designed exclusively for:
- **Authorized security testing and training**
- **Educational purposes**
- **Research and development**

Users are solely responsible for ensuring compliance with all applicable laws, regulations, and organizational policies in their jurisdiction. Unauthorized use, malicious activities, or misuse of this tool is strictly prohibited and may result in legal consequences.

**USE AT YOUR OWN RISK. THE AUTHORS AND CONTRIBUTORS ARE NOT LIABLE FOR ANY MISUSE OR DAMAGES.**

---

**Built for the cybersecurity community**

