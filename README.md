# TikTok Auto Poster

Harness-engineered multi-skill agent system for TikTok content creation and posting. Built on Claude Code CLI (no Anthropic API key needed).

## What this is

A production-grade harness around Claude Code that:
- **Creates content** (hook → caption → hashtag) with 10 specialized skills
- **Validates quality** with 4 sensors (computational + inferential)
- **Manages state** via persistent memory file
- **Self-improves** via gardener meta-skill that detects patterns
- **Falls back gracefully** when TikTok API unavailable

## Harness engineering design

Follows patterns from OpenAI (Feb 2026), Martin Fowler (April 2026), Microsoft Azure SRE team:

```
Agent = Model + Harness

                 ┌──────────────┐
                 │  User prompt │
                 └──────┬───────┘
                        ▼
          ┌─────────────────────────┐
          │  Orchestrator (CLAUDE.md)│
          └────────────┬────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌────────┐    ┌──────────┐   ┌──────────┐
   │ GUIDES │    │ SENSORS  │   │  MEMORY  │
   │(skills)│    │(sensor_*)│   │(.agents/)│
   └────────┘    └──────────┘   └──────────┘
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                 ┌───────────┐
                 │   TOOLS   │
                 │(tool_*.py)│
                 └───────────┘
                       │
                       ▼
              ┌────────────────┐
              │  TikTok API or │
              │ Advisory pkg   │
              └────────────────┘
```

## Directory map

```
tiktok_auto_poster/
├── CLAUDE.md                      # Orchestrator rules
├── AGENTS.md                      # Agent-agnostic (Cursor/Codex/Gemini)
├── README.md                      # This file
├── validate-skills.sh             # Lint SKILL.md files
├── audit-harness.sh               # Score harness 0-100
│
├── .claude/
│   ├── skills/                    # 10 skills (guides)
│   │   ├── tiktok-context/
│   │   ├── tiktok-video-prep/
│   │   ├── tiktok-hook-writer/
│   │   ├── tiktok-caption-writer/
│   │   ├── tiktok-hashtag-strategy/
│   │   ├── tiktok-scheduler/
│   │   ├── tiktok-uploader/
│   │   ├── tiktok-advisory-mode/
│   │   ├── tiktok-analyzer/
│   │   └── tiktok-harness-gardener/  # meta-skill
│   ├── commands/                  # Slash commands
│   │   ├── post.md
│   │   ├── schedule.md
│   │   ├── advisory.md
│   │   ├── memory.md
│   │   ├── audit-harness.md
│   │   └── gardener-scan.md
│   └── settings.json              # Permissions
│
├── .agents/                       # Agent-writable state
│   ├── memory.md                  # Recent posts, errors, todos, learned rules
│   └── tiktok-context.md          # Creator profile (generated)
│
├── scripts/                       # Tools + sensors (Python)
│   ├── tool_process_video.py      # Video prep (ffmpeg)
│   ├── tool_upload.py             # TikTok API upload
│   ├── tool_schedule.py           # Queue management
│   ├── tool_hashtag.py            # Hashtag generator
│   ├── tool_memory.py             # Memory refresh/append
│   ├── tool_gardener.py           # Pattern detection
│   ├── tool_record_manual_post.py # Advisory post tracking
│   ├── sensor_caption_quality.py  # Caption linter
│   ├── sensor_pre_upload.py       # Preconditions
│   ├── sensor_post_upload.py      # Visibility verify
│   ├── sensor_content_review.py   # LLM-as-judge (inferential)
│   ├── cron_worker.py             # Background worker
│   ├── oauth_setup.py             # First-time token
│   └── run_agent.py               # Legacy Python entry
│
├── tools/                         # Internal libs (imported by scripts)
│   ├── tiktok_api.py              # Content Posting API client
│   ├── video_processor.py         # FFmpeg wrapper
│   ├── content_generator.py       # Claude CLI wrapper
│   ├── hashtag_generator.py       # Pyramid strategy
│   ├── scheduler.py               # SQLite queue
│   └── analytics.py               # Stats tracker
│
├── templates/                     # Niche starter packs
│   ├── coding-creator/
│   ├── food-creator/
│   └── beauty-creator/
│
├── config/
│   ├── config.yaml
│   └── .env.example
│
└── data/                          # Runtime state (SQLite, processed videos)
    ├── queue.db
    ├── analytics.db
    ├── processed/                 # FFmpeg outputs
    └── ready_to_post/             # Advisory mode packages
```

## Setup

### 1. Install

```bash
bash scripts/setup.sh
```

Prerequisites: Python 3.10+, ffmpeg, Claude Code CLI (logged in).

### 2. Pick a template (optional but fast)

```bash
cp templates/coding-creator/tiktok-context.md .agents/
cp templates/coding-creator/hashtag-pool.json data/custom_hashtags.json
# Edit .agents/tiktok-context.md to fill your specifics
```

### 3. Choose posting path

**Option A — TikTok API (audited apps only)**
```bash
cp config/.env.example config/.env
# Fill TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET
python scripts/oauth_setup.py
```

**Option B — Advisory mode (recommended for personal accounts)**
No credentials needed. System generates packages for you to paste into TikTok app in ~60s per post.

### 4. Verify harness quality

```bash
./validate-skills.sh    # lint all SKILL.md
./audit-harness.sh      # score 0-100
```

## Usage

### Via Claude Code CLI (primary)

```bash
cd tiktok_auto_poster
claude
# then in REPL:
> /post /path/to/video.mp4 "học python"
> /schedule /path/to/video.mp4 auto
> /advisory /path/to/video.mp4
> /memory show
> /audit-harness
> /gardener-scan 7
```

### Via Python (legacy, direct)

```bash
python scripts/run_agent.py --mode=once --video=test.mp4 --topic="học python"
python scripts/cron_worker.py --interval=300  # background worker
```

## Key concepts

### Guides vs Sensors (Martin Fowler 2026)

- **Guides** (`.claude/skills/`): anticipate agent behavior, steer BEFORE it acts. Feedforward.
- **Sensors** (`scripts/sensor_*.py`): observe AFTER agent acts, help self-correct. Feedback.

Without sensors, agent repeats mistakes. Without guides, agent wastes tokens guessing. Need both.

### Computational vs Inferential sensors

- **Computational** (fast, deterministic): `sensor_caption_quality.py`, `sensor_pre_upload.py`. Run on every post.
- **Inferential** (slow, semantic): `sensor_content_review.py` (LLM-as-judge). Run only for critical posts.

### Self-correcting error messages

Every tool emits error JSON with `remediation` field:

```json
{
  "success": false,
  "error_type": "spam_risk_too_many_posts",
  "remediation": {
    "explanation": "Account đã đăng 6+ posts trong 24h",
    "action": "halt",
    "next_step": "Invoke tiktok-scheduler enqueue với --when=<24h_from_now>",
    "do_not": "retry ngay — sẽ làm TikTok flag nặng hơn",
    "user_message": "Quota hôm nay đã hết."
  }
}
```

Agent reads `remediation` and acts accordingly — no blind retries.

### Memory as progressive context

Agent reads `.agents/memory.md` first — recent posts, errors, todos, learned rules. Cuts context window waste by ~60% vs re-querying DB every session.

### Gardener steering loop

Weekly, `tiktok-harness-gardener` scans logs + analytics → finds patterns → writes proposals to memory. Human reviews + moves accepted rules into SKILL.md. System self-improves without auto-modifying code.

## Harness quality

Current score: **82/100** (run `./audit-harness.sh` to verify).

Dimensions measured:
1. Skill format compliance (20)
2. Guide-to-sensor ratio (20)
3. Error remediation coverage (20)
4. Memory + context infrastructure (15)
5. Tool error handling quality (25)

## Why not Selenium/browser automation?

**Don't do it.** Violates TikTok ToS. Account ban risk.

Alternatives this system supports:
1. **Official TikTok API** — needs audit (~2 weeks), requires website + app store listing
2. **Advisory mode** (this system's default) — 60s manual step per post, 100% compliant
3. **Third-party schedulers** (Buffer $6/mo, Later) — they're audited with TikTok, you authorize account

For personal accounts, option 2 or 3 is correct.

## Credits

Built on research from:
- OpenAI Harness Engineering (Feb 2026)
- Martin Fowler / Thoughtworks harness patterns (April 2026)
- Microsoft Azure SRE filesystem-based context engineering
- LangChain Agent Builder memory system
- blacktwist/social-media-skills (skill architecture pattern)

## License

Your code is yours. Rules in SKILL.md files are for your agent. Be kind to TikTok's infrastructure.
#   t i k t o k _ a u t o _ p o s t e r  
 