from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Quiz, QuizTab, Question, QuestionOption, QuizAttempt, QuizAnswer


class AdminCreatorListSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='first_name', read_only=True)
    quizzes_count = serializers.IntegerField(read_only=True, default=0)
    attempts_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'name', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'date_joined',
            'quizzes_count', 'attempts_count'
        ]


class AdminQuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'is_correct', 'order']


class AdminQuestionSerializer(serializers.ModelSerializer):
    options = AdminQuestionOptionSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    quiz_title = serializers.CharField(source='quiz.title', read_only=True, default=None)
    creator_name = serializers.CharField(source='creator.first_name', read_only=True, default=None)
    is_global_bank = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id', 'text', 'order', 'active', 'category', 'category_name',
            'quiz', 'quiz_title', 'creator', 'creator_name',
            'is_global_bank', 'created_at', 'updated_at', 'options'
        ]

    def get_is_global_bank(self, obj):
        return obj.quiz is None


class AdminQuizListSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True, default=None)
    creator_email = serializers.CharField(source='creator.email', read_only=True, default=None)
    questions_count = serializers.IntegerField(read_only=True, default=10)
    attempts_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Quiz
        fields = [
            'id', 'creator', 'creator_name', 'creator_username', 'creator_email',
            'title', 'description', 'avatar_id', 'public_id', 'status',
            'questions_count', 'attempts_count', 'created_at', 'updated_at'
        ]


class AdminQuizDetailSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True, default=None)
    creator_email = serializers.CharField(source='creator.email', read_only=True, default=None)
    questions = AdminQuestionSerializer(many=True, read_only=True)
    attempts_count = serializers.IntegerField(read_only=True, default=0)
    avg_score = serializers.FloatField(read_only=True, default=0.0)
    highest_score = serializers.IntegerField(read_only=True, default=0)
    lowest_score = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Quiz
        fields = [
            'id', 'creator', 'creator_name', 'creator_username', 'creator_email',
            'title', 'description', 'avatar_id', 'public_id', 'status',
            'attempts_count', 'avg_score', 'highest_score', 'lowest_score',
            'created_at', 'updated_at', 'questions'
        ]


class AdminCreatorDetailSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='first_name', read_only=True)
    quizzes = AdminQuizListSerializer(many=True, read_only=True)
    total_quizzes = serializers.IntegerField(read_only=True, default=0)
    total_attempts = serializers.IntegerField(read_only=True, default=0)
    avg_score = serializers.FloatField(read_only=True, default=0.0)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'name', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'date_joined',
            'total_quizzes', 'total_attempts', 'avg_score', 'quizzes'
        ]


class AdminCategorySerializer(serializers.ModelSerializer):
    questions_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'description', 'active', 'created_at', 'questions_count']


class AdminAttemptListSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    quiz_public_id = serializers.CharField(source='quiz.public_id', read_only=True)
    creator_name = serializers.CharField(source='quiz.creator_name', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'public_id', 'participant_name', 'quiz', 'quiz_title',
            'quiz_public_id', 'creator_name', 'score', 'total_questions',
            'percentage', 'status', 'started_at', 'completed_at'
        ]


class AdminAnswerDetailSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    selected_option_id = serializers.IntegerField(source='selected_option.id', read_only=True)
    selected_option_text = serializers.CharField(source='selected_option.text', read_only=True)
    options = AdminQuestionOptionSerializer(source='question.options', many=True, read_only=True)
    correct_option = serializers.SerializerMethodField()

    class Meta:
        model = QuizAnswer
        fields = [
            'id', 'question_id', 'question_text', 'selected_option_id',
            'selected_option_text', 'is_correct', 'options', 'correct_option'
        ]

    def get_correct_option(self, obj):
        correct = obj.question.options.filter(is_correct=True).first()
        if correct:
            return {'id': correct.id, 'text': correct.text}
        return None


class AdminAttemptDetailSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    quiz_public_id = serializers.CharField(source='quiz.public_id', read_only=True)
    creator_name = serializers.CharField(source='quiz.creator_name', read_only=True)
    creator_email = serializers.CharField(source='quiz.creator.email', read_only=True, default=None)
    answers = AdminAnswerDetailSerializer(many=True, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'public_id', 'participant_name', 'quiz', 'quiz_title',
            'quiz_public_id', 'creator_name', 'creator_email', 'score',
            'total_questions', 'percentage', 'result_message', 'status',
            'started_at', 'completed_at', 'answers'
        ]
