import random
from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import (
    Quiz, QuizTab, Category, Question, QuestionOption,
    QuizAttempt, QuizAttemptQuestion, QuizAnswer
)


def get_score_message(score, total, creator_name):
    """Generate fun message based on the participant's score."""
    name = creator_name or "them"
    if score == 10:
        return f"🔥 You basically know {name} better than {name} knows himself!"
    elif score >= 8:
        return f"😍 You know {name} really well!"
    elif score >= 6:
        return f"😎 Not bad! You know {name} pretty well."
    elif score >= 4:
        return f"🤔 You need to spend more time with {name}!"
    else:
        return f"💀 Does {name} even know you?"


@transaction.atomic
def start_quiz_attempt(quiz_public_id, participant_name, tab_id=None):
    """
    Starts a new quiz attempt for a private person-to-person quiz.
    - Validates quiz is published.
    - Retrieves the EXACT 10 creator questions (maintaining creator order 1..10).
    - Shuffles the 4 options per question and stores it permanently for this attempt.
    """
    try:
        quiz = Quiz.objects.get(public_id=quiz_public_id)
    except Quiz.DoesNotExist:
        raise ValidationError({"error": "This quiz isn't available right now."})

    if quiz.status == 'draft':
        raise ValidationError({"error": "This quiz is currently in draft mode and has not been published yet."})
    elif quiz.status == 'disabled':
        raise ValidationError({"error": "This quiz link has been deactivated."})

    if not participant_name or not participant_name.strip():
        raise ValidationError({"participant_name": "Please enter your name to start the quiz."})

    tab = None
    if tab_id:
        try:
            tab = QuizTab.objects.get(id=tab_id, quiz=quiz, is_active=True)
        except QuizTab.DoesNotExist:
            tab = None

    # Get the 10 questions for this personal quiz in creator order
    questions_list = list(quiz.questions.filter(active=True).order_by('order').prefetch_related('options'))

    # If personal quiz doesn't have custom questions yet, fallback to eligible global pool questions
    if len(questions_list) < 10:
        global_qs = Question.objects.filter(quiz__isnull=True, active=True).prefetch_related('options')
        if global_qs.count() >= 10:
            questions_list = random.sample(list(global_qs), 10)
        else:
            raise ValidationError({"error": "This quiz currently does not have enough questions configured."})

    # Exactly 10 questions
    selected_questions = questions_list[:10]

    # Create the attempt record
    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        tab=tab,
        participant_name=participant_name.strip(),
        status='in_progress',
        total_questions=10,
        score=0,
        percentage=0.0
    )

    # Store the 10 selected questions and randomize option order per question
    attempt_questions = []
    for order_idx, question in enumerate(selected_questions, start=1):
        option_ids = list(question.options.values_list('id', flat=True))
        random.shuffle(option_ids) # Randomize option order A/B/C/D for participant

        attempt_questions.append(
            QuizAttemptQuestion(
                attempt=attempt,
                question=question,
                order=order_idx,
                option_order=option_ids
            )
        )

    QuizAttemptQuestion.objects.bulk_create(attempt_questions)
    return attempt


@transaction.atomic
def record_quiz_answer(attempt, question_id, option_id):
    """
    Validates and stores a participant's answer to a question within an active attempt.
    """
    if attempt.status == 'completed':
        raise ValidationError({"error": "This quiz attempt is already completed."})

    # Validate that question belongs to this attempt
    try:
        attempt_q = QuizAttemptQuestion.objects.get(attempt=attempt, question_id=question_id)
    except QuizAttemptQuestion.DoesNotExist:
        raise ValidationError({"error": "Question does not belong to this quiz attempt."})

    # Validate option belongs to question
    try:
        option = QuestionOption.objects.get(id=option_id, question_id=question_id)
    except QuestionOption.DoesNotExist:
        raise ValidationError({"error": "Option does not belong to this question."})

    # Record or update answer
    answer, created = QuizAnswer.objects.update_or_create(
        attempt=attempt,
        question_id=question_id,
        defaults={
            'selected_option': option,
            'is_correct': option.is_correct
        }
    )
    return answer


@transaction.atomic
def submit_quiz_attempt(attempt):
    """
    Finalizes the quiz attempt:
    - Calculates score
    - Calculates percentage
    - Generates result message
    - Marks attempt as COMPLETED
    """
    if attempt.status == 'completed':
        return attempt

    # Check answers for all attempt questions
    attempt_questions = QuizAttemptQuestion.objects.filter(attempt=attempt)
    answers = QuizAnswer.objects.filter(attempt=attempt).select_related('selected_option', 'question')
    answers_map = {ans.question_id: ans for ans in answers}

    correct_count = 0
    for aq in attempt_questions:
        ans = answers_map.get(aq.question_id)
        if ans and ans.selected_option.is_correct:
            correct_count += 1

    total = attempt.total_questions or 10
    percentage = round((correct_count / total) * 100, 1)
    message = get_score_message(correct_count, total, attempt.quiz.creator_name)

    from django.utils import timezone
    attempt.score = correct_count
    attempt.percentage = percentage
    attempt.result_message = message
    attempt.status = 'completed'
    attempt.completed_at = timezone.now()
    attempt.save()

    return attempt
