# 🏆 Wins Finder MCP Agent

An intelligent MCP (Model Context Protocol) agent that analyzes your work activity across GitHub, Linear, Notion, and Slack to generate context-aware weekly accomplishment reports for performance reviews, 1:1s, and self-reflection.

## 🎯 Who Is This For?

- **Software engineers** preparing for performance reviews
- **Engineering managers** tracking team contributions
- **Individual contributors** wanting better visibility into their impact
- **Remote workers** needing to articulate cross-platform achievements
- **Anyone** who struggles to remember and articulate weekly accomplishments

## ✨ What Makes This Special?

- **Cross-Service Intelligence**: Correlates activities across platforms (GitHub PR + Linear issue + Notion docs = feature delivery)
- **Context-Aware Reports**: Adapts tone and focus based on audience (manager vs peer vs self-reflection)
- **LLM-Powered Analysis**: Uses AI to find meaningful patterns and connections
- **Evidence-Backed Claims**: All accomplishments include links to supporting activities
- **Smart Caching**: Avoids API rate limits with intelligent data caching

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Pull and run the container
docker run -it --rm \
  -e GITHUB_TOKEN=your_github_token \
  -e OPENROUTER_API_KEY=your_openrouter_key \
  ghcr.io/yourusername/wins-finder-mcp:latest

# Or with docker compose
curl -O https://raw.githubusercontent.com/yourusername/wins-finder-mcp/main/docker-compose.yml
docker compose up
```

### Option 2: Python/uv (Development)

```bash
# Clone and install
git clone https://github.com/yourusername/wins-finder-mcp.git
cd wins-finder-mcp

# Create virtual environment and install
uv venv --python 3.13
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r pyproject.toml

# Run the server
python -m wins_finder
```

### Option 3: uvx (Recommended for Easy Use)

```bash
# Run directly without installation (when published to PyPI)
uvx wins-finder-mcp

# Or run from source
uvx --from . wins-finder

# Specify Python version
uvx --python 3.13 wins-finder-mcp
```

### Option 4: pip (System-wide)

```bash
# Install from PyPI (when published)
pip install wins-finder-mcp

# Run the server
wins-finder
```

## ⚙️ Configuration

### 1. GitHub Personal Access Token

#### Option A: Fine-Grained Personal Access Token (Recommended)

Create a token at https://github.com/settings/personal-access-tokens/new

**Repository Permissions:**
- ✅ `Actions`: Read (for workflow data)
- ✅ `Contents`: Read (for repository contents and commits)  
- ✅ `Issues`: Read (for issue comments and interactions)
- ✅ `Metadata`: Read (for basic repository info)
- ✅ `Pull requests`: Read (for PRs, reviews, comments)

**Account Permissions:**
- ✅ `Profile`: Read (for user profile information)

**Organization Permissions (if analyzing org repos):**
- ✅ `Members`: Read (for organization membership info)

#### Option B: Classic Personal Access Token

Create a token at https://github.com/settings/tokens with these scopes:
- `repo` - Full repository access
- `read:user` - Read user profile
- `read:org` - Read organization membership

> **Note**: Fine-grained tokens are more secure as they can be limited to specific repositories and have more granular permissions.

### 2. OpenRouter API Key (Optional)

For intelligent correlation analysis:
1. Sign up at https://openrouter.ai
2. Create an API key
3. Recommended models: Claude-3.5-Sonnet or GPT-4

### 3. Test Configuration

Once your MCP client connects to the server, use the `test_authentication` tool to verify all environment variables are properly configured.

### 4. Environment Variables

```bash
# Required
GITHUB_TOKEN=ghp_your_github_token_here

# Optional but recommended for intelligent analysis
OPENROUTER_API_KEY=sk-or-your_openrouter_key_here

# Optional service configurations
LINEAR_API_KEY=your_linear_token
NOTION_API_KEY=your_notion_integration_token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url

# GitHub API Rate Limiting Configuration (Optional)
GITHUB_PR_LIMIT=50              # Maximum pull requests to fetch (default: 50)
GITHUB_REPO_LIMIT=10            # Maximum repositories to analyze (default: 10)
GITHUB_COMMIT_LIMIT=20          # Maximum commits per repository (default: 20)
GITHUB_REVIEW_LIMIT=30          # Maximum reviews to fetch (default: 30)  
GITHUB_COMMENT_LIMIT=20         # Maximum issue comments to fetch (default: 20)
```

**GitHub Rate Limiting Notes:**
- These limits help avoid hitting GitHub API rate limits while still providing comprehensive analysis
- Adjust higher for more thorough analysis, lower for faster performance
- GitHub's default rate limit is 5000 requests/hour for authenticated users
- These settings balance thoroughness with API efficiency

## 🔧 Connecting to AI Clients

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "wins-finder": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "GITHUB_TOKEN=your_token_here",
        "-e", "OPENROUTER_API_KEY=your_key_here",
        "ghcr.io/yourusername/wins-finder-mcp:latest"
      ]
    }
  }
}
```

### ChatGPT Desktop

Follow ChatGPT's MCP server configuration with the Docker command above.

## 🛠️ Available Tools

- **`analyze_weekly_wins`** - Generate comprehensive wins report
- **`test_authentication`** - Verify environment variables are configured
- **`collect_activity_data`** - Fetch and cache activity data
- **`correlate_activities`** - Find cross-service connections
- **`generate_report`** - Format reports for different audiences
- **`post_to_slack`** - Share accomplishments with team
- **`clear_cache`** - Manage cached data

## 📊 Example Usage

```
User: "Generate my wins for this week's manager 1:1"

Wins Finder:
1. ✅ Fetches GitHub PRs, commits, and reviews
2. 🔍 Analyzes patterns and cross-service correlations  
3. 🎯 Generates manager-focused report with business impact
4. 📝 Returns evidence-backed accomplishments with confidence scores
```

## 🏗️ Development

### Prerequisites
- Python 3.13+
- uv package manager
- Docker (for containerized deployment)

### Local Development

```bash
# Clone repository
git clone https://github.com/yourusername/wins-finder-mcp.git
cd wins-finder-mcp

# Set up development environment
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r pyproject.toml

# Run tests
pytest

# Format code  
ruff format src/ tests/

# Run MCP server (database auto-created on first use)
python -m wins_finder
```

### Docker Development

```bash
# Build development image
docker build -t wins-finder-mcp:dev .

# Run with development volume mount
docker run -it --rm \
  -v $(pwd):/app \
  -e GITHUB_TOKEN=your_token \
  wins-finder-mcp:dev
```

## 🔒 Security & Privacy

- **Credentials**: API keys never stored, only read from environment variables
- **No Logging**: API keys are never logged or written to disk
- **Data**: Activity data cached locally, not transmitted to third parties  
- **Isolation**: Docker deployment provides container-level security
- **Minimal Permissions**: Requests only necessary API scopes

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)  
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/wins-finder-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/wins-finder-mcp/discussions)
- **Documentation**: [Full Documentation](https://yourusername.github.io/wins-finder-mcp/)

## 🎉 Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp) framework
- Powered by [Model Context Protocol](https://modelcontextprotocol.io/)
- Inspired by the need for better developer visibility and recognition