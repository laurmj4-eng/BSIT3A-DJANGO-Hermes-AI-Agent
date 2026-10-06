"""Views for the AI news feed."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .feeds import FEEDS, fetch_all_feeds
from .models import Article

PER_PAGE = 20
# Don't hammer the feeds — a refresh is allowed at most this often.
REFRESH_COOLDOWN_SECONDS = 300


@login_required(login_url='login')
def news_page(request):
    """Render the AI news feed with search, source filter and pagination."""
    query = request.GET.get('q', '').strip()
    source = request.GET.get('source', '').strip()

    articles = Article.objects.all()

    if query:
        articles = articles.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(source__icontains=query)
        )

    if source:
        articles = articles.filter(feed_key=source)

    paginator = Paginator(articles, PER_PAGE)
    page = paginator.get_page(request.GET.get('page', 1))

    # Filter dropdown: every configured feed, plus any source already stored
    # that is no longer in FEEDS. A list of (key, name) tuples so the template
    # can unpack with {% for key, name %}.
    names = {f['key']: f['name'] for f in FEEDS}
    for key, name in Article.objects.values_list('feed_key', 'source').distinct():
        names.setdefault(key, name)
    source_choices = sorted(names.items())

    latest_fetch = Article.objects.order_by('-fetched_at').values_list(
        'fetched_at', flat=True
    ).first()

    return render(request, 'news/feed.html', {
        'articles': page,
        'query': query,
        'source': source,
        'source_choices': source_choices,
        'total': paginator.count,
        'last_updated': latest_fetch,
        'feed_count': len(FEEDS),
    })


@login_required(login_url='login')
@require_POST
def news_refresh(request):
    """Pull every configured feed and upsert the articles into the DB."""
    from django.utils import timezone

    articles, errors = fetch_all_feeds()

    created = updated = 0
    for item in articles:
        defaults = {
            'title': item['title'][:500],
            'summary': item['summary'],
            'source': item['source'][:120],
            'feed_key': item['feed_key'][:60],
            'published_at': item['published_at'],
        }
        # get_or_create on the unique url keeps refreshes idempotent.
        _, was_created = Article.objects.get_or_create(
            url=item['url'][:1000], defaults=defaults
        )
        if was_created:
            created += 1
        else:
            updated += 1

    if not articles and errors:
        payload = {
            'error': 'No articles could be fetched. All feeds failed.',
            'errors': errors,
        }
        return JsonResponse(payload, status=502)

    if errors:
        messages.warning(
            request,
            f'Refreshed with {len(errors)} feed(s) unavailable; the rest loaded.'
        )
    else:
        messages.success(
            request,
            f'Refreshed {len(FEEDS)} feeds: {created} new, {updated} already known.'
        )

    return JsonResponse({
        'status': 'ok',
        'created': created,
        'updated': updated,
        'errors': errors,
        'total': Article.objects.count(),
        'refreshed_at': timezone.now().isoformat(),
    })


@login_required(login_url='login')
@require_POST
def news_toggle_save(request, pk):
    """Bookmark / un-bookmark an article for the current user."""
    from django.shortcuts import get_object_or_404

    article = get_object_or_404(Article, pk=pk)
    article.is_saved = not article.is_saved
    article.saved_by = request.user if article.is_saved else None
    article.save(update_fields=['is_saved', 'saved_by'])

    return JsonResponse({'status': 'ok', 'is_saved': article.is_saved})