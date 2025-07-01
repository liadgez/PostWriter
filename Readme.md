# PostWriter - Facebook Ads CLI Tool

A local CLI tool for analyzing Facebook posts and generating marketing content based on successful patterns from your existing posts.

## Table of Contents

- [Features Overview](#features-overview)
- [Installation & Setup](#installation--setup)
- [Usage Guide](#usage-guide)
- [Technical Architecture](#technical-architecture)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Security & Privacy](#security--privacy)

## Features Overview

PostWriter analyzes your existing Facebook posts to identify successful marketing patterns and generates new content based on proven templates. Key capabilities include:

- **Post Analysis**: Extract and analyze existing posts from your Facebook profile
- **Template Mining**: Identify successful post structures and patterns
- **Content Generation**: Create new marketing posts based on high-performing templates
- **A/B Testing**: Generate multiple variations for testing
- **Performance Tracking**: Rank templates by engagement metrics

## Installation & Setup

### Requirements
- Python 3.8+
- Node.js (for Playwright)
- Facebook account access

### Installation Steps
```bash
# Install the tool
pip install postwriter

# Setup Playwright for web scraping
playwright install

# Configure your settings
fbads config --setup
```

### Initial Configuration
Create a `config.yaml` file with your preferences:
```yaml
cookies_path: ~/.fbads/cookies.json
language: he
max_vars: 3
fine_tune: false
```

## Usage Guide

### Basic Commands

```bash
# Sync posts from your Facebook profile
fbads sync

# View identified topics from your posts
fbads topics

# List available templates
fbads tpl list

# Generate new content ideas
fbads idea "AI Marketing"

# Create new ads with variations
fbads adgen --idea "Your marketing idea" --vars 2

# Preview content before publishing
fbads preview
```

### Workflow Example
1. Sync your existing posts: `fbads sync`
2. Analyze successful patterns: `fbads topics`
3. Generate new content: `fbads adgen --idea "New product launch"`
4. Review and refine: `fbads preview`

## Technical Architecture

### Core Components

#### 1. Post Analysis Engine
- **Playwright Integration**: Scrapes HTML → JSON conversion of all posts
- **Marketing Post Detection**: Identifies posts with CTAs, links, and promotional content

#### 2. Content Processing Pipeline
- **Text Cleaning**: Removes tags, non-essential emojis, UTM parameters
- **Structure Preservation**: Maintains paragraphs, line breaks, and hashtags

#### 3. Metadata Extraction
- **Performance Metrics**: Date, reach, interactions, attached media
- **CTA Analysis**: Type and effectiveness of calls-to-action

#### 4. Hook Identification System
- **Pattern Recognition**: Regex + Embeddings for pain points, benefits, solutions
- **Hook Classification**: FOMO, Proof, Gain, and other hook types

#### 5. Tone & Voice Analysis
- **Style Metrics**: Formality, slang usage, emoji ratios, rhetorical questions
- **Voice Fingerprinting**: Average sentence length, emoji ratios, linguistic patterns

#### 6. Template Mining Engine
- **Structure Clustering**: Groups posts by HEADLINE / BODY / CTA patterns
- **Template Generation**: Creates reusable templates with placeholders: `{HOOK}`, `{BENEFIT}`, `{CTA}`

#### 7. Performance Ranking
- **Engagement Scoring**: Formula: (likes + comments) / followers
- **Template Success Tracking**: Maintains `template_success_score` for recommendations

#### 8. Template Storage
- **SQLite Database**: `templates(id, topic, structure, success_score, tone_vec)`
- **CLI Access**: Commands like `tpl list`, `tpl show <id>`

#### 9. Topic Analysis
- **BERTopic Integration**: Identifies 5-10 leading topics from all posts
- **Topic-Template-Engagement Mapping**: Links topics to successful templates

#### 10. Idea Generation
- **Content Seeding**: Takes existing topic or external keyword as input
- **Creative Suggestions**: Generates new headlines/angles (doesn't write full content)

#### 11. Template Matching Engine
- **Similarity Scoring**: Cosine similarity between idea embeddings and tone vectors
- **Recommendation System**: Returns top-k suggested templates

#### 12. Ad Text Generator
- **Template Population**: Fills placeholders based on input ideas
- **CTA Integration**: Adds CTAs similar to most successful templates

#### 13. A/B Variation Creator
- **Hook Variations**: Changes hooks and CTAs while maintaining tone and topic
- **Batch Generation**: Command: `adgen create --idea "..." --vars 3`

#### 14. Quality Assurance
- **Platform Compliance**: Facebook limits (≤63k chars, compelling first 125 characters)
- **Content Validation**: Checks first-line clarity, emoji excess, compliance words

#### 15. Preview Mode
- **Dry-Run Capability**: `adgen preview` shows:
  1. Idea → selected template
  2. Full generated text
  3. Brief explanations for choices

#### 16. Fine-Tuning (Optional)
- **Local Model Training**: LoRA over 7b model with local GPU memory
- **Personalized Training**: Uses only your texts for quick training (few minutes)

#### 17. Unified CLI Interface
All functionality accessible through simple commands:
```bash
fbads sync          # Pull existing posts
fbads topics        # Leading topics
fbads tpl list      # Templates
fbads idea "AI Marketing"    # New ideas
fbads adgen --idea "..." --vars 2
```

## Configuration

### config.yaml Options
```yaml
# Authentication
cookies_path: ~/.fbads/cookies.json

# Language settings
language: he  # Hebrew/English

# Generation settings
max_vars: 3
fine_tune: false

# Debugging
debug_mode: false
save_html: true
```

### Environment Variables
- `FBADS_HOME`: Custom data directory (default: ~/.fbads/)
- `FBADS_DEBUG`: Enable debug logging
- `FBADS_CONFIG`: Custom config file path

## Troubleshooting

### Common Issues

**Authentication Problems**
- Ensure cookies are valid and up-to-date
- Check Facebook login status
- Verify cookies_path in config

**Scraping Failures**
- Facebook may have changed their HTML structure
- Check debug logs in `~/.fbads/logs/`
- Try updating Playwright: `playwright install`

**Template Generation Issues**
- Ensure sufficient post data (minimum 10-20 posts recommended)
- Check if posts contain marketing content
- Verify language settings match your content

### Debug Options
```bash
# Enable verbose logging
fbads --debug sync

# Save raw HTML for inspection
fbads sync --save-html

# Check logs
tail -f ~/.fbads/logs/fbads.log
```

### Log Locations
- **Debug Logs**: `~/.fbads/logs/`
- **Raw HTML**: `~/.fbads/html_dump/` (when debug enabled)
- **Performance Metrics**: Execution times and template counts in INFO logs

## Security & Privacy

### Data Handling
- **Local Storage Only**: All data stored in `~/.fbads/` directory
- **No External APIs**: No data sent to external services (except Playwright → Facebook)
- **User Control**: Complete ownership of scraped data and generated templates

### Privacy Features
- **Data Purging**: `fbads purge` command removes all data (DB, HTML, fine-tuned models)
- **Secure Storage**: Cookies and sensitive data encrypted locally
- **No Tracking**: Tool doesn't collect usage analytics or user behavior

### Security Best Practices
- Regularly update cookies and authentication tokens
- Use the purge command when switching accounts
- Keep the tool updated for latest security patches
- Review generated content before publishing

---

For more information or support, check the documentation or submit issues to the project repository.