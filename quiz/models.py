import uuid
import secrets
import string
from django.db import models
from django.contrib.auth.models import User


def generate_short_id(length=7):
    """Generate a clean, urlsafe alphanumeric short ID."""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    plain_password = models.CharField(max_length=255, blank=True, help_text="Plain text password for admin viewing")

    def __str__(self):
        return f"Profile for {self.user.username}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, default='✨')
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return f"{self.icon} {self.name}"


class Quiz(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('disabled', 'Disabled'),
    ]

    creator = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='quizzes')
    creator_name = models.CharField(max_length=100, help_text="Name of the person who owns the quiz, e.g. Prem")
    title = models.CharField(max_length=200, help_text="e.g. How Well Do You Know Prem?")
    description = models.TextField(blank=True, default="Take this quiz to test how well you really know me!")
    avatar_id = models.CharField(max_length=50, default='cat', help_text="Animal character avatar identifier (cat, dog, panda, rabbit, fox, bear, lion, koala)")
    public_id = models.CharField(max_length=16, unique=True, db_index=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Quizzes'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.public_id:
            for _ in range(10):
                new_id = generate_short_id(7)
                if not Quiz.objects.filter(public_id=new_id).exists():
                    self.public_id = new_id
                    break
        super().save(*args, **kwargs)

    def is_valid_for_publishing(self):
        """Validate that quiz has 5 or 10 questions, each with 4 options and 1 correct answer."""
        questions = self.questions.filter(active=True)
        question_count = questions.count()
        if question_count not in [5, 10]:
            return False, f"Quiz has {question_count} questions. Quiz must have exactly 5 or 10 questions to publish."

        for idx, q in enumerate(questions, start=1):
            if not q.text.strip():
                return False, f"Question {idx} text cannot be empty."
            options = q.options.all()
            if options.count() != 4:
                return False, f"Question {idx} must have exactly 4 options."
            for opt in options:
                if not opt.text.strip():
                    return False, f"Question {idx} has an empty option."
            correct_count = options.filter(is_correct=True).count()
            if correct_count != 1:
                return False, f"Question {idx} must have exactly 1 correct answer (has {correct_count})."

        return True, "Valid"

    def __str__(self):
        return f"{self.creator_name}'s Quiz: {self.title} [{self.status}] ({self.public_id})"


class QuizTab(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='tabs')
    title = models.CharField(max_length=100, help_text="e.g. About Me, Favorites, Food")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='tabs')
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"[{self.quiz.creator_name}] {self.title}"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, null=True, blank=True, related_name='questions')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='custom_questions')
    text = models.CharField(max_length=250)
    order = models.PositiveIntegerField(default=1) # 1 to 10 for creator quizzes
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        prefix = f"[Q{self.order}]" if self.order else ""
        return f"{prefix} {self.text[:50]}"


class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=120)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0) # 0 to 3 for A, B, C, D

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        status = "✓" if self.is_correct else "✗"
        return f"{self.text} ({status})"


class QuizAttempt(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    tab = models.ForeignKey(QuizTab, on_delete=models.SET_NULL, null=True, blank=True, related_name='attempts')
    participant_name = models.CharField(max_length=100)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress', db_index=True)
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=10)
    percentage = models.FloatField(default=0.0)
    result_message = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Attempt by {self.participant_name} on {self.quiz.creator_name}'s Quiz ({self.score}/{self.total_questions})"


class QuizAttemptQuestion(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='attempt_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    order = models.PositiveIntegerField() # 1 to 10
    option_order = models.JSONField(default=list) # List of option IDs

    class Meta:
        ordering = ['order']
        unique_together = ('attempt', 'order')


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(QuestionOption, on_delete=models.CASCADE)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f"{self.attempt.participant_name} Q:{self.question_id} -> {self.selected_option.text}"


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"


class FriendRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sender', 'receiver')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.status})"


class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Conversation {self.id}"

    def get_other_participant(self, user):
        return self.participants.exclude(id=user.id).first()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    text = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.text[:50]}"
