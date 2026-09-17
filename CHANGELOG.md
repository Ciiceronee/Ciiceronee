# Changelog

All notable changes to Ciicerone will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### API Security & Storage Hardening
- **API authentication**: Token-based auth middleware protecting REST endpoints
- **Safety filter enforcement**: Content filtering now enforced on API generation paths
- **CORS configuration**: Explicit CORS policy for the FastAPI application
- **Postgres storage**: Postgres-backed storage layer for scenarios and simulations

#### Compliance Documentation (Issue #115)
- **GDPR Compliance Framework**: Comprehensive documentation suite for GDPR (EU) 2016/679 compliance
  - Data mapping and processing activities register (Article 30)
  - Consent management framework with technical implementation (Article 7)
  - Data subject rights implementation guide (Articles 12-23)
  - Data Protection Impact Assessment (DPIA) template (Article 35)
  - Privacy notice for platform users (Articles 13-14)
  - Data Processing Agreement (DPA) template (Article 28)
  - Breach notification templates and procedures (Articles 33-34)
  - Records of Processing Activities (ROPA) (Article 30)
- **Acceptable Use Policy**: Foundation policy document for platform usage guidelines
- Industry standard alignment: ISO 27701, ICO Guidance, EDPB Guidelines

### Changed
- Default Anthropic model updated

### Fixed
- LLM provider wiring bugs

---

## [0.1.0] - 2025-12-29

_Note: this release has not been tagged yet._

### 🎉 Initial Release

This is the first official release of Ciicerone, an enterprise-grade AI-powered threat simulation platform.

### Added

#### Core Features
- **Multi-LLM Support**: Integration with OpenAI GPT-4, Anthropic Claude, OpenRouter, and Ollama (local/offline)
- **YAML-Based Templates**: Define threat scenarios using intuitive, version-controlled templates
- **Production-Ready Core**: Scalable simulation engine with proper data models
- **CLI Interface**: Command-line tool for scenario management and execution
- **REST API**: FastAPI-based REST endpoints for enterprise integration

#### Template System
- Executive phishing scenarios
- Business Email Compromise (BEC) templates
- Supply chain compromise simulations
- IT helpdesk impersonation scenarios
- Healthcare and finance-specific templates
- Variable scenario support with dynamic content generation

#### LLM Integration
- Multi-provider support with automatic fallback
- Connection pooling for improved performance
- Rate limiting and retry logic
- Response streaming support
- Token usage tracking and cost estimation

#### RAG System (Experimental)
- Neo4j-based knowledge graph
- MITRE ATT&CK integration
- PhishTank intelligence feeds
- Semantic search capabilities
- Context-aware content generation

#### Safety Framework
- Content filtering and validation
- Ethical use guidelines
- Educational use markers
- Compliance checks

#### Dataset Integration
- PhishTank phishing intelligence
- Enron Email Corpus patterns
- MITRE ATT&CK framework
- CERT Insider Threat Dataset
- LANL Authentication Dataset

#### CLI Commands
- `Ciicerone simulate` - Run threat simulations
- `Ciicerone templates` - Manage templates
- `Ciicerone llm` - Configure LLM providers
- `Ciicerone datasets` - Manage datasets
- `Ciicerone deploy` - Deployment integration
- `Ciicerone logs` - View simulation logs
- `Ciicerone intel` - Threat intelligence
- `Ciicerone rag` - RAG system management
- `Ciicerone feedback` - Feedback loop system

#### API Endpoints
- `/api/v1/simulate` - Run simulations
- `/api/v1/templates` - Template management
- `/api/v1/health` - Health checks
- `/api/v1/metrics` - Prometheus metrics

#### DevOps & Deployment
- Docker and Docker Compose support
- GitHub Actions CI/CD workflows
- Kubernetes Helm charts (planned)
- Multi-environment configuration

### Security
- API key protection with environment variables
- Input validation and sanitization
- Audit logging infrastructure
- Security vulnerability reporting process

### Documentation
- Comprehensive README
- Quick Start Guide
- User Guide
- Developer Guide
- Security Guide
- Template Creation Guide
- API Reference

---

## Versioning

Ciicerone follows Semantic Versioning:

- **MAJOR** version: Incompatible API changes
- **MINOR** version: New functionality (backwards compatible)
- **PATCH** version: Bug fixes (backwards compatible)

## Migration Notes

### Upgrading from Development Builds

If you were using pre-release development builds:

1. Update your environment configuration
2. Review new template schema requirements
3. Check LLM provider configuration changes
4. Update any custom integrations

## Links

- [GitHub Repository](https://github.com/Ciicerone/Ciicerone)
- [Documentation](https://github.com/Ciicerone/Ciicerone/docs)
- [Issue Tracker](https://github.com/Ciicerone/Ciicerone/issues)
- [Security Policy](https://github.com/Ciicerone/Ciicerone/security)

---

[Unreleased]: https://github.com/Ciicerone/Ciicerone/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ciicerone/Ciicerone/releases/tag/v0.1.0
