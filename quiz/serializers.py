from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    UserProfile, Category, Quiz, QuizTab, Question, QuestionOption,
    QuizAttempt, QuizAttemptQuestion, QuizAnswer
)


# =========================================================================
# Authentication Serializers
# =========================================================================
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    name = serializers.CharField(write_only=True, max_length=100)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'name']

    def create(self, validated_data):
        name = validated_data.pop('name', '')
        password = validated_data.pop('password')
        email = validated_data.get('email', '')
        username = validated_data.get('username')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=name
        )
        # Store plain password in UserProfile
        UserProfile.objects.create(user=user, plain_password=password)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='first_name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'is_staff', 'is_superuser']


# =========================================================================
# Category & Tab Serializers
# =========================================================================
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'description']


class QuizTabSerializer(serializers.ModelSerializer):
    category_slug = serializers.CharField(source='category.slug', read_only=True, default=None)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    category_icon = serializers.CharField(source='category.icon', read_only=True, default='✨')

    class Meta:
        model = QuizTab
        fields = ['id', 'title', 'order', 'is_active', 'category', 'category_slug', 'category_name', 'category_icon']


# =========================================================================
# Public Quiz Serializers (Safe for Participants)
# =========================================================================
class PublicQuizSerializer(serializers.ModelSerializer):
    tabs = QuizTabSerializer(many=True, read_only=True)
    questions_count = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            'public_id',
            'title',
            'creator_name',
            'description',
            'avatar_id',
            'status',
            'tabs',
            'questions_count',
            'created_at'
        ]

    def get_questions_count(self, obj):
        return obj.questions.filter(active=True).count()


# Public participant view - DOES NOT EXPOSE is_correct
class PublicOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'order']


class PublicQuestionSerializer(serializers.ModelSerializer):
    options = PublicOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'order', 'text', 'options']


class QuizAttemptStateSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    creator_name = serializers.CharField(source='quiz.creator_name', read_only=True)
    avatar_id = serializers.CharField(source='quiz.avatar_id', read_only=True)
    quiz_public_id = serializers.CharField(source='quiz.public_id', read_only=True)
    questions = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = [
            'public_id',
            'participant_name',
            'status',
            'score',
            'total_questions',
            'percentage',
            'result_message',
            'quiz_public_id',
            'quiz_title',
            'creator_name',
            'avatar_id',
            'answered_count',
            'questions',
            'started_at',
            'completed_at'
        ]

    def get_answered_count(self, obj):
        return obj.answers.count()

    def get_questions(self, obj):
        attempt_qs = obj.attempt_questions.select_related('question').prefetch_related('question__options')
        answers_map = {ans.question_id: ans.selected_option_id for ans in obj.answers.all()}

        results = []
        for aq in attempt_qs:
            q = aq.question
            options_dict = {opt.id: opt for opt in q.options.all()}
            ordered_options = []
            for opt_id in aq.option_order:
                if opt_id in options_dict:
                    ordered_options.append(options_dict[opt_id])

            if not ordered_options:
                ordered_options = list(q.options.all())

            results.append({
                'id': q.id,
                'order': aq.order,
                'text': q.text,
                'options': PublicOptionSerializer(ordered_options, many=True).data,
                'selected_option_id': answers_map.get(q.id, None)
            })
        return results


class StartAttemptSerializer(serializers.Serializer):
    participant_name = serializers.CharField(max_length=100, required=True)
    tab_id = serializers.IntegerField(required=False, allow_null=True)


class AnswerSubmissionSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(required=True)
    option_id = serializers.IntegerField(required=True)


class QuizResultSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    creator_name = serializers.CharField(source='quiz.creator_name', read_only=True)
    avatar_id = serializers.CharField(source='quiz.avatar_id', read_only=True)
    quiz_public_id = serializers.CharField(source='quiz.public_id', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'public_id',
            'participant_name',
            'score',
            'total_questions',
            'percentage',
            'result_message',
            'quiz_public_id',
            'quiz_title',
            'creator_name',
            'avatar_id',
            'completed_at'
        ]


# =========================================================================
# Creator Quiz Creation & Editing Serializers
# =========================================================================
class CreatorOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    text = serializers.CharField(max_length=100)
    is_correct = serializers.BooleanField(default=False)
    order = serializers.IntegerField(default=0)


class CreatorQuestionSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    order = serializers.IntegerField(required=True)
    text = serializers.CharField(max_length=200)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    options = CreatorOptionSerializer(many=True)

    def validate_options(self, options):
        if len(options) != 4:
            raise serializers.ValidationError("Every question must contain EXACTLY 4 options.")
        
        for opt in options:
            if not opt.get('text', '').strip():
                raise serializers.ValidationError("Option text cannot be empty.")
            if len(opt.get('text', '')) > 100:
                raise serializers.ValidationError("Option text cannot exceed 100 characters.")

        correct_count = sum(1 for opt in options if opt.get('is_correct', False))
        if correct_count != 1:
            raise serializers.ValidationError("Exactly one option must be selected as the correct answer.")
        return options


class QuizDraftCreateUpdateSerializer(serializers.Serializer):
    creator_name = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    avatar_id = serializers.CharField(max_length=50, default='cool_boy')
    tabs = serializers.ListField(child=serializers.DictField(), required=False)
    questions = CreatorQuestionSerializer(many=True, required=False)
    publish = serializers.BooleanField(default=False)

    def validate_questions(self, questions):
        publish = self.initial_data.get('publish', False)
        if publish and len(questions) != 10:
            raise serializers.ValidationError(f"Cannot publish quiz. A published quiz must have EXACTLY 10 questions (currently {len(questions)}).")
        return questions


class CreatorQuizDetailSerializer(serializers.ModelSerializer):
    tabs = QuizTabSerializer(many=True, read_only=True)
    questions = serializers.SerializerMethodField()
    attempts_count = serializers.SerializerMethodField()
    average_score = serializers.SerializerMethodField()
    highest_score = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            'id',
            'public_id',
            'title',
            'creator_name',
            'description',
            'avatar_id',
            'status',
            'tabs',
            'questions',
            'attempts_count',
            'average_score',
            'highest_score',
            'created_at',
            'updated_at'
        ]

    def get_questions(self, obj):
        qs = obj.questions.filter(active=True).order_by('order').prefetch_related('options')
        results = []
        for q in qs:
            results.append({
                'id': q.id,
                'order': q.order,
                'text': q.text,
                'category_id': q.category_id,
                'options': [
                    {
                        'id': opt.id,
                        'text': opt.text,
                        'is_correct': opt.is_correct,
                        'order': opt.order
                    }
                    for opt in q.options.all()
                ]
            })
        return results

    def get_attempts_count(self, obj):
        return obj.attempts.count()

    def get_average_score(self, obj):
        completed = obj.attempts.filter(status='completed')
        if not completed.exists():
            return 0
        from django.db.models import Avg
        return round(completed.aggregate(Avg('score'))['score__avg'] or 0, 1)

    def get_highest_score(self, obj):
        completed = obj.attempts.filter(status='completed')
        if not completed.exists():
            return 0
        from django.db.models import Max
        return completed.aggregate(Max('score'))['score__max'] or 0
