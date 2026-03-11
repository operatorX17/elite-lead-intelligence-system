# Changelog

All notable changes to ZRAI Lead OS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial implementation of ZRAI Lead OS
- LangGraph orchestration with 9 specialist agents
- Supabase database with complete schema
- Configuration system with YAML files
- CLI with run_daily, replay_run, resume_failed, dry_run commands
- Governance layer with RBAC, rate limiting, audit logging
- Eval harness with offline replay and A/B testing
- Circuit breakers and kill switches for safety
- Budget guardrails for cost control
- Do Not Contact (DNC) management
- Negative signal detection and cool-downs
- Lead lifecycle state machine
- Comprehensive documentation (README, CONTRIBUTING)

### Agents Implemented
- Discovery Agent (Apify integration)
- Enrichment Agent (contact extraction)
- Intent Agent (revenue leak scoring)
- Audit Agent (Steel.dev proof generation)
- Scoring Agent (weighted scoring)
- Outreach Agent (message generation)
- Conversation Agent (AI qualification)
- Governance Agent (safety and compliance)
- Eval Agent (testing and metrics)

### Configuration Files
- `config/niches.yaml` - Niche definitions (HVAC, plumbing, roofing, dental, legal)
- `config/policies.yaml` - Rate limits, disqualification rules, lifecycle
- `config/agents.yaml` - Agent configs, LLM routing, retry settings
- `config/budgets.yaml` - Daily budget limits and alerts

### Database Tables
- leads, lead_state, enrichment_data, intent_data
- proof_artifacts, scoring_results, outreach_queue
- conversations, negative_signals, do_not_contact
- audit_log, usage_metrics, playbooks, circuit_breakers
- escalations, golden_dataset, ab_tests, ab_metrics, daily_metrics

### Safety Features
- Idempotency keys for all external writes
- Circuit breakers with auto-recovery
- Global and per-module kill switches
- Multi-level rate limiting
- Opt-out detection and enforcement
- Budget limits with alerts
- Audit logging (append-only)
- Secret redaction in logs

### Testing
- Property-based test framework setup
- Test connection scripts for APIs
- Setup verification script

### Documentation
- Comprehensive README with quick start
- Architecture overview
- Configuration guide
- CLI command reference
- Troubleshooting guide
- Contributing guidelines
- Development setup instructions

## [0.1.0] - 2026-01-04

### Initial Release
- Core implementation complete
- All agents functional
- Database schema deployed
- Configuration system operational
- CLI commands working
- Safety features active
- Documentation complete

### Known Limitations
- Property-based tests not yet implemented
- Playbook RAG integration pending
- Email/SMS sending not yet implemented
- Monitoring dashboard not included

### Next Steps
- Implement 50 property-based tests
- Add Pinecone RAG for playbooks
- Integrate email/SMS providers
- Build monitoring dashboard
- Production deployment guide
- Performance optimization

---

## Version History

### Version Numbering

- **Major** (X.0.0): Breaking changes, major features
- **Minor** (0.X.0): New features, backwards compatible
- **Patch** (0.0.X): Bug fixes, minor improvements

### Release Process

1. Update CHANGELOG.md
2. Update version in setup.py
3. Tag release: `git tag v0.1.0`
4. Push tags: `git push --tags`
5. Create GitHub release
6. Deploy to production

---

## Unreleased Changes

Track ongoing work here before next release:

### In Progress
- [ ] Property-based tests (50 properties)
- [ ] Playbook RAG with Pinecone
- [ ] Email provider integration
- [ ] SMS provider integration
- [ ] Monitoring dashboard

### Planned
- [ ] Performance optimization
- [ ] Horizontal scaling support
- [ ] Advanced A/B testing features
- [ ] Custom playbook editor
- [ ] Lead scoring ML model
- [ ] Conversation analytics
- [ ] Multi-language support

### Bug Fixes
- None reported yet

---

## Migration Guide

### From 0.0.x to 0.1.0

No migrations needed - initial release.

### Future Migrations

Migration guides will be added here for breaking changes.
