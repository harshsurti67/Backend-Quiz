from django.urls import path
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    CurrentUserView,
    PublicQuizDetailView,
    QuizTabsListView,
    CategoryListView,
    QuizAttemptCreateView,
    QuizAttemptDetailView,
    QuizAttemptAnswerView,
    QuizAttemptSubmitView,
    QuizAttemptResultView,
    QuizCreateOrUpdateView,
    QuizPublishView,
    MyQuizzesListView,
    QuizStatsView,
)
from .admin_views import (
    AdminLoginView,
    AdminDashboardOverviewView,
    AdminCreatorsListView,
    AdminCreatorDetailView,
    AdminCreatorStatusToggleView,
    AdminCreatorResetPasswordView,
    AdminQuizzesListView,
    AdminQuizDetailView,
    AdminQuizStatusToggleView,
    AdminQuestionsListView,
    AdminCategoryListCreateView,
    AdminCategoryDetailView,
    AdminAttemptsListView,
    AdminAttemptDetailView,
    AdminAnalyticsView,
    AdminGlobalSearchView,
)

urlpatterns = [
    # Health Check
    path('health/', lambda request: JsonResponse({'status': 'ok'}), name='health'),

    # Auth
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/me/', CurrentUserView.as_view(), name='auth-me'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # Creator Quiz Management
    path('quizzes/create/', QuizCreateOrUpdateView.as_view(), name='quiz-create'),
    path('quizzes/<int:quiz_id>/publish/', QuizPublishView.as_view(), name='quiz-publish'),
    path('my/quizzes/', MyQuizzesListView.as_view(), name='my-quizzes'),

    # Public Quiz (Person-to-Person)
    path('quizzes/<str:public_id>/', PublicQuizDetailView.as_view(), name='quiz-detail'),
    path('quizzes/<str:public_id>/tabs/', QuizTabsListView.as_view(), name='quiz-tabs'),
    path('quizzes/<str:public_id>/attempts/', QuizAttemptCreateView.as_view(), name='quiz-start-attempt'),
    path('quizzes/<str:public_id>/stats/', QuizStatsView.as_view(), name='quiz-stats'),

    # Categories
    path('categories/', CategoryListView.as_view(), name='categories-list'),

    # Quiz Attempts (Participant Session)
    path('attempts/<uuid:attempt_id>/', QuizAttemptDetailView.as_view(), name='attempt-detail'),
    path('attempts/<uuid:attempt_id>/answers/', QuizAttemptAnswerView.as_view(), name='attempt-answer'),
    path('attempts/<uuid:attempt_id>/submit/', QuizAttemptSubmitView.as_view(), name='attempt-submit'),
    path('attempts/<uuid:attempt_id>/result/', QuizAttemptResultView.as_view(), name='attempt-result'),

    # =========================================================================
    # Admin Panel APIs (Protected by IsAdminUser)
    # =========================================================================
    path('admin/login/', AdminLoginView.as_view(), name='admin-login'),
    path('admin/dashboard/', AdminDashboardOverviewView.as_view(), name='admin-dashboard'),
    path('admin/creators/', AdminCreatorsListView.as_view(), name='admin-creators-list'),
    path('admin/creators/<int:creator_id>/', AdminCreatorDetailView.as_view(), name='admin-creator-detail'),
    path('admin/creators/<int:creator_id>/status/', AdminCreatorStatusToggleView.as_view(), name='admin-creator-status'),
    path('admin/creators/<int:creator_id>/reset-password/', AdminCreatorResetPasswordView.as_view(), name='admin-creator-reset-password'),
    path('admin/quizzes/', AdminQuizzesListView.as_view(), name='admin-quizzes-list'),
    path('admin/quizzes/<int:quiz_id>/', AdminQuizDetailView.as_view(), name='admin-quiz-detail'),
    path('admin/quizzes/<int:quiz_id>/status/', AdminQuizStatusToggleView.as_view(), name='admin-quiz-status'),
    path('admin/questions/', AdminQuestionsListView.as_view(), name='admin-questions-list'),
    path('admin/categories/', AdminCategoryListCreateView.as_view(), name='admin-categories-list'),
    path('admin/categories/<int:category_id>/', AdminCategoryDetailView.as_view(), name='admin-category-detail'),
    path('admin/attempts/', AdminAttemptsListView.as_view(), name='admin-attempts-list'),
    path('admin/attempts/<uuid:attempt_id>/', AdminAttemptDetailView.as_view(), name='admin-attempt-detail'),
    path('admin/analytics/', AdminAnalyticsView.as_view(), name='admin-analytics'),
    path('admin/search/', AdminGlobalSearchView.as_view(), name='admin-global-search'),
]

