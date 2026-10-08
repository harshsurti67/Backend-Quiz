from django.contrib import admin
from .models import (
    Category, Quiz, QuizTab, Question, QuestionOption,
    QuizAttempt, QuizAttemptQuestion, QuizAnswer
)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 4
    fields = ('text', 'is_correct', 'order')


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ('order', 'text', 'category', 'active')
    show_change_link = True


class QuizTabInline(admin.TabularInline):
    model = QuizTab
    extra = 0
    fields = ('order', 'title', 'category', 'is_active')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'active', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('active',)
    search_fields = ('name',)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator_name', 'creator', 'status', 'avatar_id', 'public_id', 'get_questions_count', 'get_attempts_count', 'created_at')
    list_filter = ('status', 'avatar_id', 'created_at')
    search_fields = ('title', 'creator_name', 'public_id', 'creator__username', 'creator__email')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    inlines = [QuizTabInline, QuestionInline]

    @admin.display(description="Questions")
    def get_questions_count(self, obj):
        return f"{obj.questions.count()}/10"

    @admin.display(description="Attempts")
    def get_attempts_count(self, obj):
        return obj.attempts.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'text', 'quiz', 'category', 'creator', 'active', 'created_at')
    list_filter = ('category', 'active', 'created_at')
    search_fields = ('text', 'quiz__title', 'quiz__creator_name')
    inlines = [QuestionOptionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('participant_name', 'get_quiz_creator', 'quiz', 'score', 'total_questions', 'percentage', 'status', 'started_at', 'completed_at')
    list_filter = ('status', 'started_at')
    search_fields = ('participant_name', 'quiz__title', 'quiz__creator_name', 'public_id')
    readonly_fields = ('public_id', 'started_at', 'completed_at')

    @admin.display(description="Creator")
    def get_quiz_creator(self, obj):
        return obj.quiz.creator_name


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'selected_option', 'is_correct', 'answered_at')
    list_filter = ('is_correct', 'answered_at')
