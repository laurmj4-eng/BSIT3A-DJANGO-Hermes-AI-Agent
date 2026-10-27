import re


TOPIC_DEFS = [
    {
        'slug': 'openai-gpt',
        'name': 'OpenAI / GPT',
        'color': '#10a37f',
        'description': 'OpenAI chat and reasoning models',
        'keywords': ['openai', 'gpt', 'chatgpt', 'o1', 'o3', 'sora', 'gpt-6', 'gpt 6', 'gpt-6 astra', 'gpt-5', 'gpt-5.1', 'gpt-5.2'],
    },
    {
        'slug': 'claude',
        'name': 'Claude',
        'color': '#d97757',
        'description': 'Anthropic reasoning models',
        'keywords': ['claude', 'anthropic', 'claude 5.5', 'claude opus 5.5', 'opus 5.5', 'sonnet 5.5', 'claude opus 4.5', 'claude sonnet 4.5', 'opus 4.5', 'sonnet 4.5'],
    },
    {
        'slug': 'gemini',
        'name': 'Gemini',
        'color': '#4285f4',
        'description': 'Google multimodal models',
        'keywords': ['gemini', 'deepmind', 'bard', 'gemini 4', 'gemini 3 pro'],
    },
    {
        'slug': 'llama-meta',
        'name': 'Llama / Meta',
        'color': '#0668e1',
        'description': 'Meta open-weight models',
        'keywords': ['llama', 'meta ai', 'muse', 'llama 4'],
    },
    {
        'slug': 'mistral',
        'name': 'Mistral',
        'color': '#ff7000',
        'description': 'Mistral open models',
        'keywords': ['mistral', 'mixtral', 'mistral large 4', 'large 4', 'mistral large 3'],
    },
    {
        'slug': 'deepseek',
        'name': 'DeepSeek',
        'color': '#67e8f9',
        'description': 'DeepSeek and emerging labs',
        'keywords': ['deepseek', 'qwen', 'grok', 'deepseek v4', 'v4 pro', 'v4 flash', 'qwen3.8', 'deepseek v3.2', 'qwen3', 'grok 4'],
    },
    {
        'slug': 'robotics',
        'name': 'Robotics',
        'color': '#22c55e',
        'description': 'Embodied AI and robots',
        'keywords': ['robot', 'robotics', 'humanoid', 'autonomous vehicle', 'self-driving'],
    },
    {
        'slug': 'research',
        'name': 'Research',
        'color': '#8b5cf6',
        'description': 'Papers benchmarks and labs',
        'keywords': ['arxiv', 'paper', 'benchmark', 'research', 'study'],
    },
    {
        'slug': 'policy',
        'name': 'Policy & Safety',
        'color': '#f59e0b',
        'description': 'Regulation and AI safety',
        'keywords': ['regulation', 'policy', 'lawsuit', 'safety', 'ethics', 'copyright'],
    },
    {
        'slug': 'hardware',
        'name': 'Hardware',
        'color': '#06b6d4',
        'description': 'Chips and infrastructure',
        'keywords': ['gpu', 'chip', 'nvidia', 'semiconductor', 'data center', 'tpu'],
    },
    {
        'slug': 'tools',
        'name': 'Tools & Apps',
        'color': '#0ea5e9',
        'description': 'AI tools, agents and apps',
        'keywords': ['tool', 'app', 'agent', 'copilot', 'plugin', 'extension', 'workflow'],
    },
    {
        'slug': 'open-models',
        'name': 'Free & Open Models',
        'color': '#84cc16',
        'description': 'Open weights, local models and free tiers',
        'keywords': [
            'open source',
            'open-source',
            'open weights',
            'open-weight',
            'free model',
            'free tier',
            'local llm',
            'ollama',
            'llama.cpp',
            'gguf',
            'quantization',
            'kimi k3',
            'kimi k2',
        ],
    },
    {
        'slug': 'coding-agents',
        'name': 'Coding Agents',
        'color': '#ec4899',
        'description': 'AI coding tools and terminals',
        'keywords': [
            'opencode',
            'freebuff',
            'codebuff',
            'aider',
            'cline',
            'cursor',
            'copilot',
            'codex',
            'claude code',
            'coding agent',
            'swe-bench',
            'devin',
        ],
    },
]

TOPIC_SLUGS = [d['slug'] for d in TOPIC_DEFS]


def _word_boundary_pattern(keyword):
    escaped = re.escape(keyword)
    # allow whitespace between words for multi-word phrases
    escaped = escaped.replace(r'\ ', r'\s+')
    return r'(?<!\w)' + escaped + r'(?!\w)'


def classify_text(title, summary=''):
    text_title = title or ''
    text_summary = summary or ''
    matched = []
    seen = set()
    for topic in TOPIC_DEFS:
        slug = topic['slug']
        keywords = topic.get('keywords') or []
        for kw in keywords:
            if not kw:
                continue
            pattern = _word_boundary_pattern(kw)
            # title matches all keywords
            if re.search(pattern, text_title, re.IGNORECASE):
                if slug not in seen:
                    matched.append(slug)
                    seen.add(slug)
                break
            # summary matches only keywords longer than 3 chars
            if len(kw) > 3 and re.search(pattern, text_summary, re.IGNORECASE):
                if slug not in seen:
                    matched.append(slug)
                    seen.add(slug)
                break
    return matched


def ensure_topics():
    from .models import Topic

    result = {}
    for topic in TOPIC_DEFS:
        obj, _ = Topic.objects.get_or_create(
            slug=topic['slug'],
            defaults={
                'name': topic['name'],
                'color': topic['color'],
                'description': topic['description'],
                'keywords': ','.join(topic.get('keywords') or []),
            },
        )
        changed = False
        if obj.name != topic['name']:
            obj.name = topic['name']
            changed = True
        if obj.color != topic['color']:
            obj.color = topic['color']
            changed = True
        if obj.description != topic['description']:
            obj.description = topic['description']
            changed = True
        kw_str = ','.join(topic.get('keywords') or [])
        if obj.keywords != kw_str:
            obj.keywords = kw_str
            changed = True
        if changed:
            obj.save()
        result[obj.slug] = obj
    return result


def apply_topics(article):
    slugs = classify_text(getattr(article, 'title', '') or '', getattr(article, 'summary', '') or '')
    if not slugs:
        return []
    ensure_topics()
    from .models import Topic

    topics = list(Topic.objects.filter(slug__in=slugs))
    # preserve order from slugs
    topic_map = {t.slug: t for t in topics}
    ordered = [topic_map[s] for s in slugs if s in topic_map]
    if ordered:
        article.topics.set(ordered)
    return ordered
