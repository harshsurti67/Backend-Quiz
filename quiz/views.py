from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from django.db import transaction
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Quiz, QuizTab, Category, Question, QuestionOption, QuizAttempt, QuizAnswer
from .serializers import (
    RegisterSerializer, UserProfileSerializer,
    CategorySerializer, QuizTabSerializer,
    PublicQuizSerializer, QuizAttemptStateSerializer,
    StartAttemptSerializer, AnswerSubmissionSerializer,
    QuizResultSerializer, QuizDraftCreateUpdateSerializer,
    CreatorQuizDetailSerializer
)
from .services import start_quiz_attempt, record_quiz_answer, submit_quiz_attempt


# =========================================================================
# Authentication Views
# =========================================================================
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            serializer = RegisterSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserProfileSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Registration error: {str(e)}", exc_info=True)
            return Response({'error': 'An error occurred during registration. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            username = request.data.get('username') or request.data.get('email')
            password = request.data.get('password')

            if not username or not password:
                return Response({'error': 'Username/email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

            # Allow login by email or username
            user = authenticate(username=username, password=password)
            if not user and '@' in username:
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None

            if not user:
                return Response({'error': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)

            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserProfileSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Login error: {str(e)}", exc_info=True)
            return Response({'error': 'An error occurred during login. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)


# =========================================================================
# Public Quiz & Attempt Views (Person-to-Person)
# =========================================================================
class PublicQuizDetailView(APIView):
    """GET /api/quizzes/{public_id}/ - Retrieve public quiz details if published."""
    def get(self, request, public_id):
        quiz = get_object_or_404(Quiz, public_id=public_id)
        if quiz.status == 'draft':
            return Response({
                "error": "This quiz is currently in draft mode and has not been published yet."
            }, status=status.HTTP_400_BAD_REQUEST)
        elif quiz.status == 'disabled':
            return Response({
                "error": "This quiz link is currently disabled."
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = PublicQuizSerializer(quiz)
        return Response(serializer.data)


class QuizTabsListView(APIView):
    """GET /api/quizzes/{public_id}/tabs/ - Retrieve available tabs for a quiz."""
    def get(self, request, public_id):
        quiz = get_object_or_404(Quiz, public_id=public_id, status='published')
        tabs = quiz.tabs.filter(is_active=True).order_by('order')
        serializer = QuizTabSerializer(tabs, many=True)
        return Response(serializer.data)


class CategoryListView(APIView):
    """GET /api/categories/ - Global categories list."""
    def get(self, request):
        categories = Category.objects.filter(active=True).order_by('name')
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class QuizAttemptCreateView(APIView):
    """
    POST /api/quizzes/{public_id}/attempts/
    Starts a new quiz attempt on creator's quiz. Delivers creator's EXACT 10 questions.
    """
    def post(self, request, public_id):
        serializer = StartAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant_name = serializer.validated_data['participant_name']
        tab_id = serializer.validated_data.get('tab_id')

        try:
            attempt = start_quiz_attempt(
                quiz_public_id=public_id,
                participant_name=participant_name,
                tab_id=tab_id
            )
        except Exception as e:
            if hasattr(e, 'detail'):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        state_serializer = QuizAttemptStateSerializer(attempt)
        return Response({
            "attempt_id": str(attempt.public_id),
            "attempt": state_serializer.data
        }, status=status.HTTP_201_CREATED)


class QuizAttemptDetailView(APIView):
    """GET /api/attempts/{attempt_id}/ - Preserves active attempt state on reload."""
    def get(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, public_id=attempt_id)
        serializer = QuizAttemptStateSerializer(attempt)
        return Response(serializer.data)


class QuizAttemptAnswerView(APIView):
    """POST /api/attempts/{attempt_id}/answers/ - Records participant answer."""
    def post(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, public_id=attempt_id)
        serializer = AnswerSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question_id = serializer.validated_data['question_id']
        option_id = serializer.validated_data['option_id']

        try:
            record_quiz_answer(attempt, question_id, option_id)
        except Exception as e:
            if hasattr(e, 'detail'):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"success": True, "message": "Answer recorded successfully."})


class QuizAttemptSubmitView(APIView):
    """POST /api/attempts/{attempt_id}/submit/ - Calculates score and completes attempt."""
    def post(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, public_id=attempt_id)
        try:
            completed_attempt = submit_quiz_attempt(attempt)
        except Exception as e:
            if hasattr(e, 'detail'):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "score": completed_attempt.score,
            "total": completed_attempt.total_questions,
            "percentage": completed_attempt.percentage,
            "message": completed_attempt.result_message,
            "participant_name": completed_attempt.participant_name,
            "creator_name": completed_attempt.quiz.creator_name,
            "avatar_id": completed_attempt.quiz.avatar_id,
            "quiz_public_id": completed_attempt.quiz.public_id,
            "public_id": str(completed_attempt.public_id)
        }, status=status.HTTP_200_OK)


class QuizAttemptResultView(APIView):
    """GET /api/attempts/{attempt_id}/result/ - View finalized score."""
    def get(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, public_id=attempt_id, status='completed')
        serializer = QuizResultSerializer(attempt)
        return Response(serializer.data)


# =========================================================================
# Creator Quiz Management APIs
# =========================================================================
class QuizCreateOrUpdateView(APIView):
    """
    POST /api/quizzes/create/
    Creates a new private personal quiz (draft or published) with 10 questions.
    """
    def post(self, request):
        serializer = QuizDraftCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        creator_name = data['creator_name'].strip()
        title = data.get('title')
        if not title:
            title = f"How Well Do You Know {creator_name}? 👀"
        description = data.get('description', f"Take this quiz to test how well you really know {creator_name}!")
        avatar_id = data.get('avatar_id', 'cool_boy')
        publish = data.get('publish', False)

        user = request.user if request.user.is_authenticated else None

        with transaction.atomic():
            quiz = Quiz.objects.create(
                creator=user,
                creator_name=creator_name,
                title=title,
                description=description,
                avatar_id=avatar_id,
                status='draft'
            )

            # Create default tabs
            tabs_data = data.get('tabs', [])
            if not tabs_data:
                QuizTab.objects.create(quiz=quiz, title="Main Quiz", order=1)
            else:
                for idx, t in enumerate(tabs_data[:10], start=1):
                    cat_id = t.get('category_id')
                    cat = Category.objects.filter(id=cat_id).first() if cat_id else None
                    QuizTab.objects.create(quiz=quiz, title=t.get('title', f"Tab {idx}"), category=cat, order=idx)

            # Create 10 creator questions
            questions_data = data.get('questions', [])
            for q_data in questions_data:
                q_text = q_data['text'].strip()
                q_order = q_data['order']
                cat = Category.objects.filter(id=q_data.get('category_id')).first() if q_data.get('category_id') else None

                question = Question.objects.create(
                    quiz=quiz,
                    creator=user,
                    category=cat,
                    text=q_text,
                    order=q_order,
                    active=True
                )

                for opt_idx, opt_data in enumerate(q_data['options']):
                    QuestionOption.objects.create(
                        question=question,
                        text=opt_data['text'].strip(),
                        is_correct=opt_data.get('is_correct', False),
                        order=opt_idx
                    )

            if publish:
                is_valid, msg = quiz.is_valid_for_publishing()
                if not is_valid:
                    transaction.set_rollback(True)
                    return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
                quiz.status = 'published'
                quiz.save()

        detail_serializer = CreatorQuizDetailSerializer(quiz)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class QuizPublishView(APIView):
    """POST /api/quizzes/{id}/publish/ - Validates 10 questions and marks quiz published."""
    def post(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if request.user.is_authenticated and quiz.creator and quiz.creator != request.user:
            return Response({"error": "You do not have permission to publish this quiz."}, status=status.HTTP_403_FORBIDDEN)

        is_valid, msg = quiz.is_valid_for_publishing()
        if not is_valid:
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        quiz.status = 'published'
        quiz.save()

        return Response({
            "success": True,
            "message": "Quiz published successfully!",
            "public_id": quiz.public_id,
            "status": quiz.status
        })


class MyQuizzesListView(APIView):
    """GET /api/my/quizzes/ - List quizzes owned by authenticated creator."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        quizzes = Quiz.objects.filter(creator=request.user).order_by('-created_at')
        serializer = CreatorQuizDetailSerializer(quizzes, many=True)
        return Response(serializer.data)


class QuizStatsView(APIView):
    """GET /api/quizzes/{public_id}/stats/ - Creator statistics and attempts leaderboard."""
    def get(self, request, public_id):
        quiz = get_object_or_404(Quiz, public_id=public_id)
        attempts = quiz.attempts.filter(status='completed')

        total_attempts = attempts.count()
        if total_attempts > 0:
            from django.db.models import Avg, Max, Min
            avg_score = round(attempts.aggregate(Avg('score'))['score__avg'] or 0, 1)
            highest_score = attempts.aggregate(Max('score'))['score__max'] or 0
            lowest_score = attempts.aggregate(Min('score'))['score__min'] or 0
        else:
            avg_score = 0
            highest_score = 0
            lowest_score = 0

        # Leaderboard: top scores
        top_attempts = attempts.order_by('-score', 'completed_at')[:10]
        recent_attempts = attempts.order_by('-completed_at')[:20]

        return Response({
            "quiz": CreatorQuizDetailSerializer(quiz).data,
            "total_attempts": total_attempts,
            "average_score": avg_score,
            "highest_score": highest_score,
            "lowest_score": lowest_score,
            "leaderboard": [
                {
                    "participant_name": a.participant_name,
                    "score": a.score,
                    "percentage": a.percentage,
                    "completed_at": a.completed_at
                }
                for a in top_attempts
            ],
            "recent_attempts": [
                {
                    "participant_name": a.participant_name,
                    "score": a.score,
                    "percentage": a.percentage,
                    "completed_at": a.completed_at
                }
                for a in recent_attempts
            ]
        })
