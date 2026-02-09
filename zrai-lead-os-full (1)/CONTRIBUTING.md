# Contributing to ZRAI Lead OS

Thank you for your interest in contributing to ZRAI Lead OS!

## Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/your-username/zrai-lead-os.git
cd zrai-lead-os
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If exists
```

4. **Set up environment**

```bash
cp .env.example .env
# Edit .env with your API keys
```

5. **Run setup verification**

```bash
python setup.py
```

## Code Standards

### Style Guide

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use docstrings for all public functions/classes

### Formatting

```bash
# Format code
make format

# Or manually
black src/ tests/
isort src/ tests/
```

### Linting

```bash
# Run linters
make lint

# Or manually
flake8 src/ tests/
mypy src/
```

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_scoring.py

# Specific test
pytest tests/test_scoring.py::test_weighted_scoring
```

### Writing Tests

We use property-based testing with Hypothesis:

```python
from hypothesis import given, strategies as st

@given(
    score=st.integers(min_value=0, max_value=100),
    tier=st.sampled_from(['A', 'B', 'C'])
)
def test_score_tier_consistency(score, tier):
    """Property: Score and tier should be consistent."""
    if score >= 80:
        assert tier == 'A'
    elif score >= 60:
        assert tier == 'B'
    else:
        assert tier == 'C'
```

## Architecture Rules

### MUST Follow

1. **Read `.rules` first** - All rules are LAW
2. **Spec compliance** - Implement exactly what's in requirements.md and design.md
3. **Config-driven** - No hardcoded values
4. **Modular agents** - Each agent is independent
5. **Safety first** - Idempotency, circuit breakers, rate limits

### MUST NOT

1. **Change architecture** without spec update
2. **Skip safety layers** (governance, audit, eval)
3. **Hardcode values** that should be config
4. **Break modularity** by reaching across agents
5. **Use MCP at runtime** (dev-time only)

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Follow the code standards
- Add tests for new functionality
- Update documentation
- Mark deviations with `// DEVIATION:` comments

### 3. Test Your Changes

```bash
# Run tests
pytest

# Run setup verification
python setup.py

# Test CLI commands
python -m src.cli dry_run --limit 5
```

### 4. Commit

```bash
git add .
git commit -m "feat: add new feature

- Detailed description
- Requirements: 1.2, 3.4
- Tests: Property 42"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Pull Request Guidelines

### PR Title

Use conventional commits format:
- `feat: Add conversation agent hard stops`
- `fix: Circuit breaker timeout calculation`
- `docs: Update README with new CLI commands`

### PR Description

Include:
1. **What** - What does this PR do?
2. **Why** - Why is this change needed?
3. **Requirements** - Which requirements does it address?
4. **Tests** - What tests were added/updated?
5. **Breaking Changes** - Any breaking changes?

Example:

```markdown
## What
Implements the Governance Agent with RBAC, rate limiting, and audit logging.

## Why
Required by Requirements 11, 12, 13 for production safety.

## Requirements
- 11.1, 11.2, 11.3: RBAC system
- 12.1, 12.2: Rate limiting
- 13.1, 13.2: Audit logging

## Tests
- Added unit tests for RBAC permission checking
- Added tests for rate limit enforcement
- Property tests pending (separate PR)

## Breaking Changes
None
```

### Review Process

1. Automated checks must pass (linting, tests)
2. Code review by maintainer
3. Address feedback
4. Approval and merge

## Adding New Features

### New Agent

1. Create `src/agents/your_agent.py`
2. Inherit from `BaseAgent`
3. Implement `process(state: LeadGraphState)` method
4. Add node function
5. Wire into `src/graph/orchestrator.py`
6. Add config to `config/agents.yaml`
7. Add tests
8. Update documentation

### New Configuration

1. Add to appropriate YAML file in `config/`
2. Update `src/config/models.py` with Pydantic model
3. Update `src/config/loader.py` to load it
4. Add validation
5. Document in README

### New CLI Command

1. Add command to `src/cli.py`
2. Use Click decorators
3. Add help text
4. Test manually
5. Update README

## Documentation

### Code Documentation

- All public functions/classes need docstrings
- Include Requirements references
- Explain complex logic
- Add examples for non-obvious usage

```python
def calculate_score(lead: Lead) -> int:
    """
    Calculate weighted score for a lead.
    
    Requirements: 7.1, 7.2
    
    Args:
        lead: Lead object with all required data
    
    Returns:
        Final score (0-100)
    
    Example:
        >>> lead = Lead(...)
        >>> score = calculate_score(lead)
        >>> assert 0 <= score <= 100
    """
    pass
```

### README Updates

Update README.md when:
- Adding new features
- Changing configuration
- Adding CLI commands
- Changing setup process

## Questions?

- Check `.rules` and spec files first
- Review existing code for patterns
- Ask in PR comments
- Open an issue for discussion

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
