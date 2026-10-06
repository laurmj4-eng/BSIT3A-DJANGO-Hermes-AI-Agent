from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'published_at', 'is_saved')
    list_filter = ('source', 'is_saved')
    search_fields = ('title', 'summary')
    readonly_fields = ('fetched_at',)