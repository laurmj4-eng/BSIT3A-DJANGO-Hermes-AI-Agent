"""Public dashboard views for the Hermes AI News Agent.

The site no longer has a sign-in wall: the dashboard is the landing page.
No admin panel is mounted; /admin/ is not routed.
"""

from datetime import timedelta

from django.db.models import Count, F, Max, Q
from django.shortcuts import render
from django.utils import timezone

from apps.news.feeds import FEEDS
from apps.news.models import Article, Topic
from apps.news.services import latest_run

# Models shown on the dashboard, grouped by the platform that created them.
# Counts are articles mentioning any keyword in the title or summary.
MODEL_PLATFORMS = [
    {
        'key': 'anthropic', 'name': 'Anthropic',
        'color': '#D97757', 'logo': 'icons/models/platform-anthropic.svg',
        'mono': True,
        'models': [
            {
                'key': 'claude', 'label': 'Claude',
                'query': 'claude', 'color': '#D97757',
                'desc': 'Anthropic reasoning models',
                'logo': 'icons/models/model-claude.svg',
                'keywords': ['claude', 'anthropic'],
            },
        ],
    },
    {
        'key': 'google', 'name': 'Google',
        'color': '#4285F4', 'logo': 'icons/models/platform-google.svg',
        'models': [
            {
                'key': 'gemini', 'label': 'Gemini',
                'query': 'gemini', 'color': '#4285F4',
                'desc': 'Google multimodal models',
                'logo': 'icons/models/model-gemini.svg',
                'keywords': ['gemini', 'deepmind', 'bard'],
            },
        ],
    },
    {
        'key': 'openai', 'name': 'OpenAI',
        'color': '#10A37F', 'logo': 'icons/models/platform-openai.svg',
        'mono': True,
        'models': [
            {
                'key': 'gpt', 'label': 'GPT / OpenAI',
                'query': 'openai', 'color': '#10A37F',
                'desc': 'OpenAI chat + reasoning',
                'logo': 'icons/models/model-openai.svg',
                'mono': True,
                'keywords': ['gpt', 'openai', 'chatgpt'],
            },
        ],
    },
    {
        'key': 'meta', 'name': 'Meta',
        'color': '#0668E1', 'logo': 'icons/models/platform-meta.svg',
        'models': [
            {
                'key': 'llama', 'label': 'Llama / Meta',
                'query': 'llama', 'color': '#0668E1',
                'desc': 'Meta open-weight models',
                'logo': 'icons/models/model-meta.svg',
                'keywords': ['llama', 'meta ai', 'at meta', 'muse', "meta's", 'meta\u2019s', 'mistral-muse'],
            },
        ],
    },
    {
        'key': 'mistral', 'name': 'Mistral AI',
        'color': '#FF7000', 'logo': 'icons/models/platform-mistral.svg',
        'models': [
            {
                'key': 'mistral', 'label': 'Mistral',
                'query': 'mistral', 'color': '#FF7000',
                'desc': 'Mistral open models',
                'logo': 'icons/models/model-mistral.svg',
                'keywords': ['mistral', 'mixtral'],
            },
        ],
    },
    {
        'key': 'deepseek', 'name': 'DeepSeek',
        'color': '#4D6BFE', 'logo': 'icons/models/platform-deepseek.svg',
        'models': [
            {
                'key': 'deepseek', 'label': 'DeepSeek',
                'query': 'deepseek', 'color': '#4D6BFE',
                'desc': 'DeepSeek + emerging labs',
                'logo': 'icons/models/model-deepseek.svg',
                'keywords': ['deepseek', 'qwen', 'grok'],
            },
        ],
    },
    {
        'key': 'groq', 'name': 'Groq',
        'color': '#F43E01', 'logo': 'icons/models/platform-groq.svg',
        'models': [
            {
                'key': 'groq', 'label': 'Groq',
                'query': 'groq', 'color': '#F43E01',
                'desc': 'LPU inference platform',
                'logo': 'icons/models/model-groq.svg',
                'keywords': ['groq', 'groqcloud', 'lpu'],
            },
        ],
    },
]


def _model_stats(articles):
    """Count articles per model and attach its originating platform."""
    stats = []
    for platform in MODEL_PLATFORMS:
        for model in platform['models']:
            keyword_query = Q()
            for keyword in model['keywords']:
                keyword_query |= (
                    Q(title__icontains=keyword) | Q(summary__icontains=keyword)
                )
            stats.append({
                'key': model['key'],
                'label': model['label'],
                'query': model['query'],
                'color': model['color'],
                'desc': model['desc'],
                'logo': model['logo'],
                'mono': model.get('mono', False),
                'platform_key': platform['key'],
                'platform_name': platform['name'],
                'platform_color': platform['color'],
                'platform_logo': platform['logo'],
                'platform_mono': platform.get('mono', False),
                'total': articles.filter(keyword_query).count(),
            })
    return stats


TRENDING_WINDOW_HOURS = 72
TRENDING_EXCLUDED_FEEDS = {'arxiv_cs_ai'}
TRENDING_OFFICIAL_FEEDS = {
    'openai_news',
    'anthropic_news',
    'google_ai_blog',
    'deepmind_blog',
    'meta_ai_news',
    'mistral_ai',
    'huggingface_blog',
    'freebuff_blog',
    'opencode_releases',
    'ollama_blog',
}
TRENDING_PRESS_FEEDS = {
    'techcrunch_ai',
    'verge_ai',
    'venturebeat_ai',
    'google_ai',
    'google_free_models',
    'mit_news_ai',
}


def _topic_counts(start, end):
    """Article counts per topic inside a half-open time window."""
    window = Article.objects.filter(
        Q(published_at__gte=start, published_at__lt=end)
        | Q(published_at__isnull=True, fetched_at__gte=start, fetched_at__lt=end)
    )
    return {
        row['topics__slug']: row['n']
        for row in window.exclude(topics__isnull=True)
        .values('topics__slug')
        .annotate(n=Count('id'))
        if row['topics__slug']
    }


def _trending_articles(now, saved_ids, read_ids, limit=5):
    """Rank stories by topic *surge* + reads, never by last click.

    A public dashboard has no per-article traffic, so trending compares the
    last 24h with the 48h before it: topics accelerating right now win.
    Official model/tool feeds get a boost, research-paper dumps are skipped.
    """
    day_start = now - timedelta(hours=24)
    baseline_start = now - timedelta(hours=72)
    end = now + timedelta(seconds=1)
    recent = _topic_counts(day_start, end)
    prior = _topic_counts(baseline_start, day_start)

    window_start = now - timedelta(hours=TRENDING_WINDOW_HOURS)
    candidates = (
        Article.objects.filter(
            Q(published_at__gte=window_start)
            | Q(published_at__isnull=True, fetched_at__gte=window_start)
        )
        .exclude(feed_key__in=TRENDING_EXCLUDED_FEEDS)
        .prefetch_related('topics')
        .order_by('-fetched_at')[:300]
    )

    scored = []
    for article in candidates:
        topics = list(article.topics.all())
        surge = max(
            (
                min((recent.get(topic.slug, 0) + 0.5) / (prior.get(topic.slug, 0) / 2 + 1), 4)
                for topic in topics
            ),
            default=0,
        )
        if article.feed_key in TRENDING_OFFICIAL_FEEDS:
            source_boost = 10
        elif article.feed_key in TRENDING_PRESS_FEEDS:
            source_boost = 4
        else:
            source_boost = 0
        age_hours = max(
            (now - (article.published_at or article.fetched_at)).total_seconds() / 3600,
            0,
        )
        score = (
            surge * 12
            + min(article.view_count, 25) * 2
            + source_boost
            - age_hours * 0.2
        )
        key = topics[0].slug if topics else f'feed:{article.feed_key}'
        scored.append((score, article, key))

    scored.sort(key=lambda row: row[0], reverse=True)

    picked = []
    seen_topics = set()
    for _score, article, key in scored:
        if key in seen_topics:
            continue
        picked.append(article)
        seen_topics.add(key)
        if len(picked) == limit:
            break

    if len(picked) < limit:
        chosen = {article.pk for article in picked}
        for _score, article, _key in scored:
            if article.pk in chosen:
                continue
            picked.append(article)
            if len(picked) == limit:
                break

    for article in picked:
        article.is_saved = article.pk in saved_ids
        article.is_read = article.pk in read_ids
    return picked


def _session_ids(request, key):
    """Session-stored list of article ids (ints) for ``key``."""
    raw = request.session.get(key) or []
    try:
        return {int(pk) for pk in raw}
    except (TypeError, ValueError):
        return set()


def home(request):
    """Public dashboard: headline AI-news stats plus the newest articles."""
    articles = Article.objects.all()
    now = timezone.now()
    today = now.date()

    saved_ids = _session_ids(request, 'saved_articles')
    read_ids = _session_ids(request, 'read_articles')

    total_articles = articles.count()
    saved_articles = len(saved_ids)
    read_total = len(read_ids)
    unread_total = articles.exclude(pk__in=read_ids).count() if read_ids else total_articles
    articles_today = articles.filter(fetched_at__date=today).count()
    articles_week = articles.filter(fetched_at__gte=now - timedelta(days=7)).count()

    # Newest stories, saved/read flags annotated in bulk (no per-article hits).
    latest_articles = list(
        articles
        .prefetch_related('topics')
        .order_by(F('published_at').desc(nulls_last=True), '-fetched_at')[:6]
    )
    for article in latest_articles:
        article.is_saved = article.pk in saved_ids
        article.is_read = article.pk in read_ids

    # Article count per source, biggest first, for the mini breakdown table.
    by_source = (
        articles.values('source')
        .annotate(total=Count('id'))
        .order_by('-total')[:6]
    )
    latest_sources = [{'source': row['source'], 'total': row['total']} for row in by_source]

    last_updated = (
        articles.order_by('-fetched_at')
        .values_list('fetched_at', flat=True)
        .first()
    )

    model_stats = _model_stats(articles)

    # Topic coverage: one aggregate query, share of the whole corpus.
    topic_rows = (
        Topic.objects
        .annotate(total=Count('articles'))
        .order_by('-total', 'name')
    )
    topic_stats = [
        {
            'slug': topic.slug,
            'name': topic.name,
            'color': topic.color,
            'description': topic.description,
            'total': topic.total,
            'share': int(round(topic.total * 100 / total_articles)) if total_articles else 0,
        }
        for topic in topic_rows
    ]

    # Trending: fresh topic surges + real reads, never "what I clicked last".
    trending_articles = _trending_articles(now, saved_ids, read_ids)

    # Source health: one aggregate over stored feed keys, merged with FEEDS.
    stored = {
        row['feed_key']: row
        for row in articles.values('feed_key').annotate(
            total=Count('id'), last_fetch=Max('fetched_at')
        )
    }
    run = latest_run()
    errors = {
        err.get('key'): err
        for err in (run.errors or [])
        if isinstance(err, dict) and err.get('key')
    } if run else {}

    source_health = []
    for feed in FEEDS:
        row = stored.get(feed['key'])
        total = row['total'] if row else 0
        if feed['key'] in errors:
            status = 'error'
        elif total > 0:
            status = 'ok'
        else:
            status = 'idle'
        source_health.append({
            'key': feed['key'],
            'name': feed['name'],
            'url': feed.get('url', ''),
            'total': total,
            'status': status,
            'error': errors.get(feed['key'], {}).get('error'),
        })
    for key, row in stored.items():
        if key in {feed['key'] for feed in FEEDS}:
            continue
        source_health.append({
            'key': key,
            'name': key,
            'url': '',
            'total': row['total'],
            'status': 'ok' if row['total'] > 0 else 'idle',
            'error': None,
        })

    feeds_ok = sum(1 for item in source_health if item['status'] == 'ok')
    feeds_error = sum(1 for item in source_health if item['status'] == 'error')

    return render(request, 'home.html', {
        'total_articles': total_articles,
        'saved_articles': saved_articles,
        'read_total': read_total,
        'unread_total': unread_total,
        'articles_today': articles_today,
        'articles_week': articles_week,
        'total_sources': articles.values('feed_key').distinct().count(),
        'configured_sources': len(FEEDS),
        'feeds': FEEDS,
        'latest_articles': latest_articles,
        'latest_sources': latest_sources,
        'last_updated': last_updated,
        'model_stats': model_stats,
        'topic_stats': topic_stats,
        'trending_articles': trending_articles,
        'latest_run': run,
        'source_health': source_health,
        'feeds_ok': feeds_ok,
        'feeds_error': feeds_error,
        'topic_count': len(topic_stats),
        'refresh_status': run.status if run else 'idle',
    })
