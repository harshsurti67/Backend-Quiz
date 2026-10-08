from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from django.db import models
from django.db.models import Count, Avg, Max, Min, Q
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Quiz, Category, Question, QuestionOption, QuizAttempt, QuizAnswer
from .serializers import UserProfileSerializer
from .admin_serializers import (
    AdminCreatorListSerializer, AdminCreatorDetailSerializer,
    AdminQuizListSerializer, AdminQuizDetailSerializer,
    AdminQuestionSerializer, AdminCategorySerializer,
    AdminAttemptListSerializer, AdminAttemptDetailSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# =========================================================================
# 1. Admin Authentication
# =========================================================================
class AdminLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            username = request.data.get('username') or request.data.get('email')
            password = request.data.get('password')

            if not username or not password:
                return Response({'error': 'Username/email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

            user = authenticate(username=username, password=password)
            if not user and '@' in username:
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None

            if not user:
                return Response({'error': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)

            # Enforce Backend Admin / Staff Permission
            if not (user.is_staff or user.is_superuser):
                return Response({
                    'error': 'Access Denied. You do not have administrator privileges.'
                }, status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserProfileSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Admin login error: {str(e)}", exc_info=True)
            return Response({'error': 'An error occurred during admin login. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =========================================================================
# 2. Admin Dashboard Overview
# =========================================================================
class AdminDashboardOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request):
        total_creators = User.objects.filter(is_superuser=False).count()
        if total_creators == 0:
            total_creators = User.objects.count()

        total_quizzes = Quiz.objects.count()
        published_quizzes = Quiz.objects.filter(status='published').count()
        draft_quizzes = Quiz.objects.filter(status='draft').count()
        disabled_quizzes = Quiz.objects.filter(status='disabled').count()

        total_attempts = QuizAttempt.objects.count()
        completed_attempts = QuizAttempt.objects.filter(status='completed').count()

        avg_score_data = QuizAttempt.objects.filter(status='completed').aggregate(Avg('score'))
        avg_score = round(avg_score_data['score__avg'] or 0.0, 1)

        recent_quizzes = Quiz.objects.select_related('creator').order_by('-created_at')[:5]
        recent_attempts = QuizAttempt.objects.select_related('quiz').order_by('-started_at')[:5]

        recent_quizzes_data = AdminQuizListSerializer(recent_quizzes, many=True).data
        recent_attempts_data = AdminAttemptListSerializer(recent_attempts, many=True).data

        return Response({
            'stats': {
                'total_creators': total_creators,
                'total_quizzes': total_quizzes,
                'published_quizzes': published_quizzes,
                'draft_quizzes': draft_quizzes,
                'disabled_quizzes': disabled_quizzes,
                'total_attempts': total_attempts,
                'completed_attempts': completed_attempts,
                'average_score': avg_score,
            },
            'recent_quizzes': recent_quizzes_data,
            'recent_attempts': recent_attempts_data,
        })


# =========================================================================
# 3. Creators Management
# =========================================================================
class AdminCreatorsListView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        queryset = User.objects.annotate(
            quizzes_count=Count('quizzes', distinct=True),
            attempts_count=Count('quizzes__attempts', distinct=True)
        ).order_by('-date_joined')

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )

        status_param = request.query_params.get('is_active')
        if status_param in ['true', 'false']:
            is_active_val = status_param == 'true'
            queryset = queryset.filter(is_active=is_active_val)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AdminCreatorListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminCreatorDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request, creator_id):
        creator = get_object_or_404(User, id=creator_id)

        user_quizzes = Quiz.objects.filter(creator=creator).annotate(
            questions_count=Count('questions', filter=Q(questions__active=True), distinct=True),
            attempts_count=Count('attempts', distinct=True)
        )

        total_quizzes = user_quizzes.count()
        total_attempts = QuizAttempt.objects.filter(quiz__creator=creator).count()
        avg_score_data = QuizAttempt.objects.filter(quiz__creator=creator, status='completed').aggregate(Avg('score'))
        avg_score = round(avg_score_data['score__avg'] or 0.0, 1)

        creator_data = AdminCreatorDetailSerializer(creator).data
        creator_data['total_quizzes'] = total_quizzes
        creator_data['total_attempts'] = total_attempts
        creator_data['avg_score'] = avg_score
        creator_data['quizzes'] = AdminQuizListSerializer(user_quizzes, many=True).data

        return Response(creator_data)


class AdminCreatorStatusToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def patch(self, request, creator_id):
        creator = get_object_or_404(User, id=creator_id)
        if creator.is_superuser:
            return Response({'error': 'Superuser accounts cannot be disabled.'}, status=status.HTTP_400_BAD_REQUEST)

        is_active = request.data.get('is_active')
        if is_active is not None:
            creator.is_active = bool(is_active)
            creator.save()

        return Response({
            'message': f"Creator '{creator.username}' account updated.",
            'is_active': creator.is_active
        })


# =========================================================================
# 4. Quizzes Management
# =========================================================================
class AdminQuizzesListView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        queryset = Quiz.objects.select_related('creator').annotate(
            questions_count=Count('questions', filter=Q(questions__active=True), distinct=True),
            attempts_count=Count('attempts', distinct=True)
        ).order_by('-created_at')

        status_param = request.query_params.get('status')
        if status_param in ['draft', 'published', 'disabled']:
            queryset = queryset.filter(status=status_param)

        creator_id = request.query_params.get('creator_id')
        if creator_id:
            queryset = queryset.filter(creator_id=creator_id)

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(creator_name__icontains=search) |
                Q(public_id__icontains=search)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AdminQuizListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminQuizDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request, quiz_id):
        quiz = get_object_or_404(Quiz.objects.select_related('creator'), id=quiz_id)

        attempts_qs = QuizAttempt.objects.filter(quiz=quiz, status='completed')
        attempts_count = QuizAttempt.objects.filter(quiz=quiz).count()

        agg = attempts_qs.aggregate(
            avg=Avg('score'),
            max=Max('score'),
            min=Min('score')
        )

        quiz_data = AdminQuizDetailSerializer(quiz).data
        quiz_data['attempts_count'] = attempts_count
        quiz_data['avg_score'] = round(agg['avg'] or 0.0, 1)
        quiz_data['highest_score'] = agg['max'] or 0
        quiz_data['lowest_score'] = agg['min'] or 0

        return Response(quiz_data)


class AdminQuizStatusToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def patch(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id)
        new_status = request.data.get('status')

        if new_status in ['draft', 'published', 'disabled']:
            quiz.status = new_status
            quiz.save()
            return Response({
                'message': f"Quiz status updated to {new_status}.",
                'status': quiz.status
            })

        return Response({'error': 'Invalid status choice.'}, status=status.HTTP_400_BAD_REQUEST)


# =========================================================================
# 5. Questions Database Management
# =========================================================================
class AdminQuestionsListView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        queryset = Question.objects.select_related('category', 'quiz', 'creator').prefetch_related('options').order_by('-id')

        category_id = request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        source_param = request.query_params.get('source')
        if source_param == 'global':
            queryset = queryset.filter(quiz__isnull=True)
        elif source_param == 'creator':
            queryset = queryset.filter(quiz__isnull=False)

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(text__icontains=search)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AdminQuestionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# =========================================================================
# 6. Categories Management
# =========================================================================
class AdminCategoryListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request):
        categories = Category.objects.annotate(questions_count=Count('questions')).order_by('name')
        serializer = AdminCategorySerializer(categories, many=True)
        return Response(serializer.data)

    def post(self, request):
        name = request.data.get('name')
        icon = request.data.get('icon', '✨')
        description = request.data.get('description', '')
        slug = request.data.get('slug') or name.lower().replace(' ', '-')

        if not name:
            return Response({'error': 'Category name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        category = Category.objects.create(
            name=name,
            slug=slug,
            icon=icon,
            description=description,
            active=True
        )

        return Response(AdminCategorySerializer(category).data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def patch(self, request, category_id):
        category = get_object_or_404(Category, id=category_id)
        
        if 'name' in request.data:
            category.name = request.data['name']
        if 'icon' in request.data:
            category.icon = request.data['icon']
        if 'description' in request.data:
            category.description = request.data['description']
        if 'active' in request.data:
            category.active = bool(request.data['active'])

        category.save()
        return Response(AdminCategorySerializer(category).data)


# =========================================================================
# 7. Attempts Management & Detail Review
# =========================================================================
class AdminAttemptsListView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        queryset = QuizAttempt.objects.select_related('quiz', 'quiz__creator').order_by('-started_at')

        status_param = request.query_params.get('status')
        if status_param in ['in_progress', 'completed']:
            queryset = queryset.filter(status=status_param)

        quiz_id = request.query_params.get('quiz_id')
        if quiz_id:
            queryset = queryset.filter(quiz_id=quiz_id)

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(participant_name__icontains=search) |
                Q(quiz__title__icontains=search) |
                Q(quiz__creator_name__icontains=search)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AdminAttemptListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminAttemptDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt.objects.select_related('quiz', 'quiz__creator').prefetch_related('answers__question__options'),
            public_id=attempt_id
        )

        serializer = AdminAttemptDetailSerializer(attempt)
        return Response(serializer.data)


# =========================================================================
# 8. Analytics Engine
# =========================================================================
class AdminAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request):
        total_creators = User.objects.filter(is_superuser=False).count() or User.objects.count()
        total_quizzes = Quiz.objects.count()
        published_quizzes = Quiz.objects.filter(status='published').count()
        draft_quizzes = Quiz.objects.filter(status='draft').count()
        disabled_quizzes = Quiz.objects.filter(status='disabled').count()

        total_attempts = QuizAttempt.objects.count()
        completed_attempts = QuizAttempt.objects.filter(status='completed').count()

        avg_score_data = QuizAttempt.objects.filter(status='completed').aggregate(Avg('score'))
        avg_score = round(avg_score_data['score__avg'] or 0.0, 1)

        # Top Creators
        top_creators_qs = User.objects.annotate(
            total_quizzes=Count('quizzes', distinct=True),
            total_attempts=Count('quizzes__attempts', distinct=True)
        ).order_by('-total_attempts', '-total_quizzes')[:5]

        top_creators = [
            {
                'id': c.id,
                'name': c.first_name or c.username,
                'email': c.email,
                'total_quizzes': c.total_quizzes,
                'total_attempts': c.total_attempts
            }
            for c in top_creators_qs
        ]

        # Category Breakdown
        categories_breakdown = [
            {
                'name': cat.name,
                'icon': cat.icon,
                'count': cat.questions.count()
            }
            for cat in Category.objects.annotate(Count('questions')).order_by('-questions__count')[:6]
        ]

        return Response({
            'overview': {
                'total_creators': total_creators,
                'total_quizzes': total_quizzes,
                'published_quizzes': published_quizzes,
                'draft_quizzes': draft_quizzes,
                'disabled_quizzes': disabled_quizzes,
                'total_attempts': total_attempts,
                'completed_attempts': completed_attempts,
                'average_score': avg_score
            },
            'quiz_status_distribution': {
                'published': published_quizzes,
                'draft': draft_quizzes,
                'disabled': disabled_quizzes
            },
            'top_creators': top_creators,
            'categories_breakdown': categories_breakdown
        })


# =========================================================================
# 9. Global Admin Search
# =========================================================================
class AdminGlobalSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'creators': [], 'quizzes': [], 'attempts': []})

        creators = User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query)
        )[:5]

        quizzes = Quiz.objects.filter(
            Q(title__icontains=query) |
            Q(creator_name__icontains=query) |
            Q(public_id__icontains=query)
        )[:5]

        attempts = QuizAttempt.objects.filter(
            Q(participant_name__icontains=query) |
            Q(quiz__title__icontains=query)
        )[:5]

        return Response({
            'creators': AdminCreatorListSerializer(creators, many=True).data,
            'quizzes': AdminQuizListSerializer(quizzes, many=True).data,
            'attempts': AdminAttemptListSerializer(attempts, many=True).data
        })
