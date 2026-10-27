from django.contrib import admin

from .models import Article, RefreshRun, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name', 'color', 'description')
    search_fields = ('slug', 'name')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(RefreshRun)
class RefreshRunAdmin(admin.ModelAdmin):
    list_display = ('started_at', 'status', 'trigger', 'created_count', 'updated_count', 'total_articles')
    list_filter = ('status', 'trigger')
    readonly_fields = ('started_at', 'finished_at', 'created_count', 'updated_count', 'total_articles', 'errors')


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'published_at', 'view_count', 'is_saved')
    list_filter = ('source', 'is_saved', 'topics')
    search_fields = ('title', 'summary')
    filter_horizontal = ('topics',)
    readonly_fields = ('fetched_at', 'view_count')