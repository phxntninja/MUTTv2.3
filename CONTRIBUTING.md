# Contributing to MUTT v2.3

Thank you for your interest in contributing to MUTT! This document provides guidelines and instructions for contributing.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contribution Workflow](#contribution-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Enhancements](#suggesting-enhancements)

---

## Code of Conduct

This project adheres to a code of professional conduct. By participating, you are expected to:

- Be respectful and inclusive
- Accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

---

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/mutt.git
   cd mutt
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/mutt.git
   ```

---

## Development Setup

### Prerequisites

- Python 3.9+
- Docker 20.10+ and Docker Compose 1.29+
- Git

### Local Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r tests/requirements-test.txt

# Start services with Docker
docker-compose up -d redis postgres vault

# Run tests
pytest tests/ -v
```

---

## Contribution Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write clear, concise code
   - Follow coding standards (see below)
   - Add tests for new functionality

3. **Test your changes**:
   ```bash
   # Run all tests
   pytest tests/ -v

   # Run with coverage
   pytest tests/ --cov=services --cov-report=term-missing

   # Ensure coverage >= 80%
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request** on GitHub

---

## Coding Standards

### Python Style Guide

- Follow **PEP 8** style guide
- Use **4 spaces** for indentation (no tabs)
- Maximum line length: **100 characters**
- Use **type hints** for function signatures
- Write **docstrings** for all public functions/classes

Example:
```python
def process_message(message: dict, config: Config) -> tuple[bool, str]:
    """
    Process an incoming message.

    Args:
        message: The message dictionary to process
        config: Configuration object

    Returns:
        Tuple of (success, error_message)

    Raises:
        ValueError: If message format is invalid
    """
    pass
```

### Code Organization

- Keep functions small and focused (< 50 lines)
- Avoid deep nesting (max 3 levels)
- Use meaningful variable names
- Extract magic numbers into named constants
- Add comments for complex logic

### Error Handling

- Use specific exception types
- Always log errors with context
- Include correlation IDs in error messages
- Provide helpful error messages to users

---

## Testing Requirements

### Unit Tests

- **All new code must have unit tests**
- Aim for **>80% code coverage**
- Test edge cases and error conditions
- Use mocks for external dependencies

Example:
```python
def test_api_key_authentication_rejects_invalid_key(mock_config, mock_secrets):
    """Test that invalid API key is rejected with 401"""
    # Arrange
    invalid_key = "wrong-key"
    expected_key = mock_secrets["INGEST_API_KEY"]

    # Act
    result = secrets.compare_digest(invalid_key, expected_key)

    # Assert
    assert result is False
```

### Test Organization

- Place tests in `tests/` directory
- Name test files `test_<module>_unit.py`
- Group related tests in classes
- Use descriptive test names

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_ingestor_unit.py -v

# Run specific test
pytest tests/test_ingestor_unit.py::TestAPIKeyAuthentication::test_valid_api_key_accepted -v

# Run with coverage
pytest tests/ --cov=services --cov-report=html
```

---

## Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```
feat(alerter): add support for regex matching in rules

Implemented regex pattern matching for alert rules to support
more flexible message filtering.

Closes #123
```

```
fix(ingestor): prevent timing attack in API key validation

Changed API key comparison from == to secrets.compare_digest()
to prevent timing-based attacks.

Fixes #456
```

### Best Practices

- Use present tense ("add feature" not "added feature")
- Keep subject line under 50 characters
- Capitalize subject line
- No period at end of subject
- Separate subject from body with blank line
- Wrap body at 72 characters
- Use body to explain what and why, not how

---

## Pull Request Process

### Before Submitting

1. ✅ All tests pass
2. ✅ Code coverage >= 80%
3. ✅ Code follows style guidelines
4. ✅ Documentation updated (if needed)
5. ✅ Commit messages follow guidelines
6. ✅ No merge conflicts with main branch

### PR Title Format

Same format as commit messages:
```
feat(service): brief description of changes
```

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally

## Related Issues
Closes #(issue number)
```

### Review Process

1. At least one approval required
2. All CI checks must pass
3. No unresolved conversations
4. Maintainer will merge (no self-merging)

---

## Reporting Bugs

### Before Reporting

- Check existing issues
- Verify bug with latest version
- Collect relevant information

### Bug Report Template

```markdown
**Describe the bug**
A clear description of the bug.

**To Reproduce**
Steps to reproduce:
1. Start service with '...'
2. Send request '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Environment:**
- MUTT Version: [e.g. v2.3]
- OS: [e.g. RHEL 8.5]
- Python Version: [e.g. 3.9.7]
- Deployment: [Docker/RHEL/Other]

**Logs**
```
Paste relevant logs here
```

**Additional context**
Any other relevant information.
```

---

## Suggesting Enhancements

### Enhancement Proposal Template

```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Other solutions you've thought about.

**Additional context**
Any other relevant information, diagrams, etc.
```

---

## Development Tips

### Running Individual Services

```bash
# Ingestor (requires Redis and Vault)
python services/ingestor_service.py

# Alerter (requires Redis, PostgreSQL, and Vault)
python services/alerter_service.py

# Moog Forwarder (requires Redis and Vault)
python services/moog_forwarder_service.py

# Web UI (requires Redis, PostgreSQL, and Vault)
python services/web_ui_service.py
```

### Debugging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debugger
python -m pdb services/ingestor_service.py
```

### Code Quality Tools

```bash
# Linting
flake8 services/ tests/

# Type checking
mypy services/

# Security scanning
bandit -r services/
```

---

## Questions?

- **Documentation**: See [README.md](README.md)
- **Discussions**: Use GitHub Discussions
- **Issues**: Use GitHub Issues

---

Thank you for contributing to MUTT! 🎉
