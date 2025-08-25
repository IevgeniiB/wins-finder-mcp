# 🏆 Wins Finder MCP Agent

An intelligent MCP (Model Context Protocol) agent that analyzes your work activity across **GitHub**, **Linear**, **Notion**, and **Slack** to generate context-aware weekly accomplishment reports. Perfect for performance reviews, 1:1s, manager updates, and personal growth tracking.

> ✨ **What makes this special?** Cross-service intelligence that correlates your GitHub PRs with Linear tickets, Notion docs, and team communications to paint the complete picture of your impact.

## 🎯 Who Is This For?

- **Software Engineers** preparing for performance reviews and promotion packets
- **Engineering Managers** tracking team contributions and identifying collaboration patterns  
- **Individual Contributors** wanting better visibility into cross-platform achievements
- **Remote Workers** needing to articulate distributed work impact
- **Anyone** who struggles to remember and communicate weekly accomplishments

## ✨ Core Capabilities

### 🔗 **Cross-Service Intelligence**
- **GitHub** ↔ **Linear**: Links pull requests to tickets for complete feature delivery stories
- **Linear** ↔ **Notion**: Connects project planning with documentation efforts
- **Code Reviews** ↔ **Team Communication**: Identifies mentoring and collaboration patterns
- **Multi-repository Analysis**: Aggregates contributions across your entire GitHub presence

### 🧠 **AI-Powered Analysis** 
- **Pattern Recognition**: Identifies meaningful work patterns using Claude 3.5 Sonnet
- **Impact Assessment**: Automatically categorizes work by business impact and complexity
- **Audience Adaptation**: Tailors reports for managers, peers, or self-reflection
- **Evidence-Backed Claims**: Every accomplishment includes links to supporting activities

### ⚡ **Smart Performance**
- **Intelligent Caching**: 6-hour cache freshness avoids API rate limits
- **Fallback Strategies**: Heuristic analysis when LLM APIs are unavailable  
- **Rate Limit Management**: Configurable limits to balance thoroughness with API efficiency
- **Incremental Updates**: Only fetches new data since last analysis

### 🎯 **Multiple Report Formats**
- **Manager 1:1s**: Business impact focus with metrics and evidence
- **Performance Reviews**: Comprehensive analysis with growth trajectory
- **Peer Updates**: Technical depth with collaboration highlights
- **Self-Reflection**: Personal growth insights and skill development tracking

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager (`pip install uv`)

### Option 1: uvx (Recommended - when published)

```bash
# Install and run directly from PyPI (coming soon)
uvx wins-finder-mcp

# Or run with specific Python version
uvx --python 3.13 wins-finder-mcp
```

### Option 2: Development/Local Installation

```bash
# Clone and set up the project
git clone https://github.com/IevgeniiB/wins-finder-mcp.git
cd wins-finder-mcp

# Create virtual environment and install dependencies
uv venv --python 3.13
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Run the MCP server
python -m wins_finder
```

### Option 3: Development Mode

```bash
# Install with development dependencies
uv pip install -e .[dev]

# Verify installation with tests
pytest

# Run with coverage reporting
pytest --cov-report=html
```

## ⚙️ Configuration

### 1. Essential Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required for basic functionality
GITHUB_TOKEN=ghp_your_github_token_here

# Optional but recommended for intelligent correlation analysis  
OPENROUTER_API_KEY=sk-or-your_openrouter_key_here

# Optional service integrations
LINEAR_API_KEY=lin_api_your_linear_token_here
NOTION_API_KEY=secret_your_notion_integration_token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
```

### 2. GitHub Token Setup

**Fine-Grained Personal Access Token (Recommended)**:
1. Go to https://github.com/settings/personal-access-tokens/new
2. Repository permissions needed:
   - ✅ **Contents**: Read (commits and repository data)
   - ✅ **Pull requests**: Read (PRs, reviews, comments)
   - ✅ **Issues**: Read (issue comments and interactions)
   - ✅ **Actions**: Read (workflow insights)
   - ✅ **Metadata**: Read (basic repository info)
3. Account permissions:
   - ✅ **Profile**: Read (user profile information)

**Classic Token Alternative**: Use `repo` and `read:user` scopes

### 3. OpenRouter Setup (Optional but Recommended)

For intelligent analysis and cross-service correlation:
1. Sign up at https://openrouter.ai  
2. Create an API key
3. Recommended models: **Claude-3.5-Sonnet** or **GPT-4o**
4. **Fallback**: System works without LLM using heuristic analysis

### 4. Test Your Configuration

```bash
# After setting environment variables, test all connections
python -c \"
import os
from wins_finder.mcp.server import test_authentication
print(test_authentication())
\"
```

## 🔌 Connecting to AI Clients

### Claude Desktop

Add to your `claude_desktop_config.json`:

**Option 1: From PyPI (when published)**
```json
{
  \"mcpServers\": {
    \"wins-finder\": {
      \"command\": \"uvx\",
      \"args\": [\"wins-finder-mcp\"],
      \"env\": {
        \"GITHUB_TOKEN\": \"your_github_token_here\",
        \"OPENROUTER_API_KEY\": \"your_openrouter_key_here\",
        \"LINEAR_API_KEY\": \"your_linear_key_here\"
      }
    }
  }
}
```

**Option 2: Local Development**
```json
{
  \"mcpServers\": {
    \"wins-finder\": {
      \"command\": \"uvx\",
      \"args\": [
        \"--from\", 
        \"/path/to/your/wins-finder-mcp\",
        \"wins-finder\"
      ],
      \"env\": {
        \"GITHUB_TOKEN\": \"your_github_token_here\",
        \"OPENROUTER_API_KEY\": \"your_openrouter_key_here\",
        \"LINEAR_API_KEY\": \"your_linear_key_here\"
      }
    }
  }
}
```

### ChatGPT Desktop

Similar configuration using the `uvx` approach above.

## 🛠️ Available Tools

| Tool | Purpose | Example Usage |
|------|---------|---------------|
| `analyze_weekly_wins` | Generate comprehensive accomplishment reports | \"Analyze my wins for manager 1:1\" |
| `test_authentication` | Verify all API connections | \"Check my GitHub and Linear tokens\" |
| `collect_activity_data` | Fetch and cache fresh activity data | \"Get my last 2 weeks of GitHub data\" |
| `correlate_activities` | Find cross-service connections | \"Show me GitHub PRs linked to Linear tickets\" |
| `generate_report` | Format reports for different audiences | \"Generate peer-focused technical report\" |
| `post_to_slack` | Share accomplishments with team | \"Post this week's wins to #engineering\" |
| `clear_cache` | Manage cached data lifecycle | \"Clear cache older than 3 days\" |

## 📊 Example Workflows

### Manager 1:1 Preparation
```
User: \"Generate my wins for this week's manager 1:1\"

Wins Finder Agent:
1. 🔍 Fetches GitHub PRs, commits, reviews, and issue comments
2. 📋 Retrieves Linear tickets, updates, and project contributions  
3. 📝 Analyzes Notion page updates and documentation work
4. 🤖 Runs LLM correlation analysis to find meaningful connections
5. 📊 Generates manager-focused report emphasizing business impact
6. 🔗 Returns evidence-backed accomplishments with confidence scores
```

### Performance Review Analysis
```
User: \"Analyze my technical contributions over the last month for performance review\"

Result:
## Technical Leadership & Impact
- **Feature Delivery**: 3 major features shipped (GitHub PR #123 → Linear IEV-15)
- **Code Quality**: 25+ code reviews with architectural guidance  
- **Cross-Team Collaboration**: 8 contributions to shared libraries
- **Documentation**: 12 Notion pages updated, 3 new technical guides
- **Mentoring**: 15+ constructive review comments, pair programming sessions

*Evidence links and confidence scores included*
```

## 🏗️ Development & Testing

### Running Tests
```bash
# Full test suite with coverage
pytest

# Unit tests only (fast)
pytest -m unit

# Integration tests with external API mocking
pytest -m integration

# Skip slow tests for quick feedback
pytest -m \"not slow\"
```

### Code Quality
```bash
# Format code
ruff format src/ tests/

# Lint and fix issues
ruff check --fix src/ tests/

# Type checking (planned improvement)
mypy src/
```

### Database Management
```bash
# Database auto-creates on first run
python -m wins_finder

# Clear all cached data
python -c \"from wins_finder.database.models import WinsDatabase; WinsDatabase().clear_cache(0)\"
```

## 🛠️ Current Implementation Status & Limitations

### ✅ **Fully Implemented**
- **GitHub Integration**: Complete API coverage including PRs, commits, reviews, and issue comments
- **Linear Integration**: Full GraphQL API implementation with smart query fallback strategies
- **Analysis Engine**: Both LLM-powered and heuristic analysis with automatic fallback
- **Caching System**: SQLite-based with 6-hour freshness and intelligent invalidation
- **Report Generation**: Multiple audience formats with evidence-backed claims

### ⚠️ **Partial Implementation**
- **Notion Integration**: API client structure in place, full implementation pending
- **Slack Integration**: Webhook foundation ready, posting functionality in development

### 🔧 **Known Limitations**
- **API Rate Limits**: GitHub (5000/hour) and Linear GraphQL optimized, but concurrent requests not implemented
- **Correlation Accuracy**: Currently temporal-based, semantic correlation via embeddings planned
- **Concurrent Processing**: Sequential API calls impact performance for comprehensive reports
- **Error Recovery**: Basic retry logic implemented, advanced backoff strategies planned

### 🎯 **Performance Characteristics**
- **Cache Hit Scenarios**: Sub-second response times for recently analyzed periods
- **Fresh Data Requests**: 5-15 seconds for comprehensive multi-service analysis
- **Fallback Reliability**: 100% uptime with heuristic analysis when LLM APIs unavailable

## 🎯 Roadmap & Planned Features

### ✅ **Currently Available**
- **GitHub Integration**: Complete API integration with authentication, PR analysis, commit tracking, and code review insights
- **Linear Integration**: Full GraphQL API integration with smart query optimization and activity correlation
- **Intelligent Analysis**: LLM-powered wins analysis with heuristic fallback for reliability
- **Smart Caching**: 6-hour cache freshness system to avoid API rate limits
- **Multiple Report Formats**: Manager, peer, performance review, and self-reflection report styles

### 🚧 **In Active Development**
- **Enhanced Testing**: Expanding test coverage for integration scenarios and edge cases
- **Code Quality Automation**: Pre-commit hooks and formatting consistency improvements
- **Performance Optimization**: Enhanced caching strategies and query optimization
- **PyPI Package Distribution**: Build and ship package to PyPI for easy `uvx wins-finder-mcp` installation

### 🔄 **Next Priority Features**  
- **Notion API Integration**: 
  - Document analysis and knowledge work tracking
  - **Performance Review Storage**: Archive and analyze historical performance reviews for growth tracking
  - **Career Progression Timeline**: Connect past reviews with current accomplishments for promotion narratives
- **Slack Deep Integration**: Channel analysis, DM insights, reaction patterns, and automated win posting
- **Advanced Correlation Logic**: Semantic matching and confidence scoring for cross-service connections
- **Claude Desktop Testing Workflows**: Automated MCP testing suite with mock data scenarios

### 🎯 **Enterprise & Team Features**
- **Jira Integration**: Sprint analysis, story point tracking, epic contribution patterns
- **Confluence Integration**: Documentation impact analysis and knowledge contribution tracking
- **GitLab Support**: Complete GitLab API integration as GitHub alternative
- **Microsoft Teams Integration**: Meeting participation, collaboration insights, team communication analysis
- **Team Dashboard**: Anonymous aggregation insights for engineering managers with privacy controls

### 💰 **Cost & Performance Optimization**
- **Fast/Slow Model Strategy**: 
  - **Fast Models** (GPT-3.5, Claude-Haiku): Text formatting, simple categorization, routine analysis
  - **Slow Models** (GPT-4, Claude-Sonnet): Complex correlation discovery, strategic insights, nuanced analysis
- **Intelligent Model Routing**: Automatic task complexity assessment for optimal model selection
- **Bulk Processing**: Batch similar requests to maximize cost efficiency
- **Smart Caching**: Pre-computed insights to reduce LLM API calls by 60-80%

### 🧪 **Developer Experience & Testing**
- **MCP Testing Suite**: Comprehensive testing framework for Claude Desktop integration scenarios
- **Mock Data Generators**: Realistic test datasets for development and debugging
- **Integration Test Automation**: Automated testing against real API endpoints with rate limit management
- **Performance Benchmarking**: Automated performance regression testing and optimization insights

### 🔬 **Advanced Analytics & AI**
- **Semantic Correlation Engine**: Embedding-based activity matching for nuanced cross-service connections
- **Predictive Career Insights**: AI-driven growth trajectory and skill development recommendations  
- **Historical Performance Analysis**: 
  - **Performance Review Integration**: Store and analyze past reviews in Notion for growth tracking
  - **Career Timeline Visualization**: Multi-year progression analysis with achievement milestones
- **Contribution Pattern Analysis**: Identify optimal work patterns and collaboration effectiveness
- **Burnout Prevention**: Workload analysis and sustainable productivity insights
- **Skill Gap Analysis**: Automated identification of growth opportunities based on industry trends

### 🌐 **Extended Integrations**
- **Calendar Integration**: Meeting analysis, time allocation insights, focus time optimization
- **Code Quality Tools**: SonarQube, CodeClimate integration for technical debt impact
- **Documentation Platforms**: GitBook, Bookstack, Slab integration for knowledge work tracking
- **Communication Platforms**: Discord, Mattermost support for distributed team analysis
- **Project Management**: Asana, Monday.com, Trello integration for broader project visibility

### 🔒 **Enterprise Security & Compliance**
- **SSO Integration**: SAML, OAuth2, Active Directory support
- **Audit Logging**: Comprehensive activity tracking for compliance requirements
- **Data Retention Policies**: Configurable data lifecycle management
- **Encrypted Storage**: End-to-end encryption for sensitive activity data
- **GDPR/CCPA Compliance**: Privacy-first data handling with user control over personal data

## 🔒 Security & Privacy

- **API Key Safety**: Never stored in database, only read from environment
- **Local Processing**: All analysis happens locally, no data sent to third parties
- **Minimal Permissions**: Requests only necessary GitHub API scopes
- **Cache Encryption**: Sensitive data encrypted at rest (planned enhancement)
- **Audit Logging**: API usage and data access logging (planned enhancement)

## 🤝 Contributing

We welcome contributions! Current priority areas:

1. **Additional Service Integrations**: Jira, GitLab, Confluence connectors
2. **Enhanced Correlation Logic**: Semantic matching and confidence scoring  
3. **Performance Optimization**: Async API calls and intelligent caching
4. **Testing Coverage**: Integration tests and API mocking improvements

```bash
# Development setup
git clone https://github.com/IevgeniiB/wins-finder-mcp.git
cd wins-finder-mcp
uv venv --python 3.13 && source .venv/bin/activate
uv pip install -e .[dev]

# Run tests before submitting
pytest
ruff format src/ tests/ && ruff check src/ tests/
```

## 📄 Architecture Overview

- **FastMCP Framework**: Synchronous MCP server with tool decorators
- **SQLite + Alembic**: Local database with migration support
- **PyGitHub**: Mature GitHub API integration with rate limit handling
- **Linear GraphQL**: Direct API integration with smart query optimization
- **OpenRouter**: Multi-model LLM access via OpenAI-compatible client
- **Modular Design**: Plugin architecture for easy service integration

## 🆘 Support & Resources

- **Issues & Bugs**: [GitHub Issues](https://github.com/IevgeniiB/wins-finder-mcp/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/IevgeniiB/wins-finder-mcp/discussions)  
- **Development Chat**: [Linear Workspace](https://linear.app/ievgeniib/team/IEV/active) (current active development)
- **Architecture Details**: See [TRADEOFFS.md](./TRADEOFFS.md) for design decisions

## 🎉 Acknowledgments

- **FastMCP Framework**: Built on [FastMCP](https://github.com/jlowin/fastmcp) for rapid MCP development
- **Model Context Protocol**: Powered by [MCP](https://modelcontextprotocol.io/) for AI tool integration
- **Open Source Libraries**: PyGitHub, SQLAlchemy, OpenAI, and other excellent Python libraries
- **Community**: Inspired by the need for better developer recognition and career growth tools

---

**License**: MIT | **Python**: 3.13+ | **Status**: Active Development