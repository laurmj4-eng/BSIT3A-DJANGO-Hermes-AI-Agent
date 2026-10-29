"""Public dashboard views for the Hermes AI News Agent.

The site no longer has a sign-in wall: the dashboard is the landing page.
No admin panel is mounted; /admin/ is not routed.
"""

from datetime import timedelta

from django.db.models import Count, F, Max, Q
from django.shortcuts import render
from django.utils import timezone

from apps.news.feeds import FEEDS
from apps.news.model_watch import current_models
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
                'key': 'claude', 'label': 'Claude 5.5',
                'query': 'claude', 'color': '#D97757',
                'desc': 'Anthropic Claude Opus 5.5 / Sonnet 5.5',
                'logo': 'icons/models/model-claude.svg',
                'keywords': [
                    'claude', 'anthropic', 'claude 5', 'opus 5', 'sonnet 5',
                    'claude 4', 'opus 4', 'sonnet 4',
                ],
            },
        ],
    },
    {
        'key': 'google', 'name': 'Google',
        'color': '#4285F4', 'logo': 'icons/models/platform-google.svg',
        'models': [
            {
                'key': 'gemini', 'label': 'Gemini 4',
                'query': 'gemini', 'color': '#4285F4',
                'desc': 'Google Gemini 4 multimodal models',
                'logo': 'icons/models/model-gemini.svg',
                'keywords': ['gemini', 'deepmind', 'bard', 'gemini 4', 'gemini 3', 'gemini 3 pro'],
            },
        ],
    },
    {
        'key': 'openai', 'name': 'OpenAI',
        'color': '#10A37F', 'logo': 'icons/models/platform-openai.svg',
        'mono': True,
        'models': [
            {
                'key': 'gpt', 'label': 'GPT-6 Astra',
                'query': 'openai', 'color': '#10A37F',
                'desc': 'OpenAI GPT-6 Astra flagship',
                'logo': 'icons/models/model-openai.svg',
                'mono': True,
                'keywords': ['gpt', 'openai', 'chatgpt', 'gpt-6', 'gpt 6', 'gpt-5', 'gpt 5'],
            },
        ],
    },
    {
        'key': 'meta', 'name': 'Meta',
        'color': '#0668E1', 'logo': 'icons/models/platform-meta.svg',
        'models': [
            {
                'key': 'llama', 'label': 'Llama 4',
                'query': 'llama', 'color': '#0668E1',
                'desc': 'Meta Llama 4 open-weight models',
                'logo': 'icons/models/model-meta.svg',
                'keywords': ['llama', 'meta ai', 'at meta', 'muse', "meta's", 'meta\u2019s', 'mistral-muse', 'llama 4'],
            },
        ],
    },
    {
        'key': 'mistral', 'name': 'Mistral AI',
        'color': '#FF7000', 'logo': 'icons/models/platform-mistral.svg',
        'models': [
            {
                'key': 'mistral', 'label': 'Mistral Large 4',
                'query': 'mistral', 'color': '#FF7000',
                'desc': 'Mistral Large 4 (Le Chonk)',
                'logo': 'icons/models/model-mistral.svg',
                'keywords': [
                    'mistral', 'mixtral', 'large 4', 'mistral large 4',
                    'magistral', 'large 3',
                ],
            },
        ],
    },
    {
        'key': 'deepseek', 'name': 'DeepSeek',
        'color': '#4D6BFE', 'logo': 'icons/models/platform-deepseek.svg',
        'models': [
            {
                'key': 'deepseek', 'label': 'DeepSeek V4',
                'query': 'deepseek', 'color': '#4D6BFE',
                'desc': 'DeepSeek V4 Pro / Flash',
                'logo': 'icons/models/model-deepseek.svg',
                'keywords': [
                    'deepseek', 'qwen', 'grok', 'deepseek v4', 'v4 pro',
                    'v4 flash', 'v3.2', 'deepseek r1',
                ],
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


def _pick_highlights(articles, keyword_query, limit=3, scan=40):
    """Newest stories for one model, de-duplicated by normalised title.

    Google News mirrors the same story under different redirect URLs, so the
    newest rows can repeat one headline. Scan a wider window and keep the first
    occurrence of each title, which also hides duplicates already in the DB.

    Stories that carry a harvested thumbnail are preferred inside that window so
    the shelf shows real photography wherever the source allowed it; imageless
    rows still fill the remaining slots, newest first.
    """
    picked = []
    seen = set()
    rows = list(
        articles.filter(keyword_query)
        .exclude(title='')
        .order_by('-published_at', '-fetched_at')
        .values('pk', 'title', 'source', 'published_at', 'image_url')[:scan]
    )

    def has_usable_image(row):
        url = (row['image_url'] or '').lower().split('?', 1)[0]
        return bool(url) and not url.endswith('.gif')

    def take(candidates):
        for row in candidates:
            key = ' '.join(row['title'].split()).casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            picked.append({
                'pk': row['pk'],
                'title': row['title'],
                'source': row['source'],
                'published_at': row['published_at'],
                'image_url': row['image_url'] or '',
                'image_ok': has_usable_image(row),
            })
            if len(picked) == limit:
                return True
        return False

    if take([row for row in rows if has_usable_image(row)]):
        return picked
    take([row for row in rows if not has_usable_image(row)])
    return picked


def _model_stats(articles):
    """Count articles per model and attach its originating platform.

    Labels come from the curated ``MODEL_PLATFORMS`` roster, then get
    overridden by the newest model release the refresh pipeline detected for
    that platform (``PlatformModel``), so the dashboard keeps itself current.

    Each entry also carries ``highlights``: the top three matching stories,
    reduced to plain dicts (``pk``, ``title``, ``source``, ``published_at``) so
    they stay safe for Django's ``json_script`` filter.
    """
    auto_models = current_models()
    stats = []
    for platform in MODEL_PLATFORMS:
        for model in platform['models']:
            keyword_query = Q()
            for keyword in model['keywords']:
                keyword_query |= (
                    Q(title__icontains=keyword) | Q(summary__icontains=keyword)
                )
            detected = auto_models.get(model['key']) or {}
            detected_label = detected.get('label') or ''
            desc = model['desc']
            if detected_label:
                desc = 'Auto-detected release: {0}'.format(
                    detected.get('source_title') or detected_label
                )
            stats.append({
                'key': model['key'],
                'label': detected_label or model['label'],
                'query': model['query'],
                'color': model['color'],
                'desc': desc,
                'logo': model['logo'],
                'mono': model.get('mono', False),
                'platform_key': platform['key'],
                'platform_name': platform['name'],
                'platform_color': platform['color'],
                'platform_logo': platform['logo'],
                'platform_mono': platform.get('mono', False),
                'auto_detected': bool(detected_label),
                'detected_version': detected.get('version', ''),
                'detected_source_url': detected.get('source_url', ''),
                'total': articles.filter(keyword_query).count(),
                'highlights': _pick_highlights(articles, keyword_query),
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
