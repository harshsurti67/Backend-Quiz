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
    - Selects 10 random questions, preferring unseen questions for this participant.
    - Respects category distribution when categories are present.
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

    # Get all active questions for this quiz
    all_questions = list(quiz.questions.filter(active=True).prefetch_related('options'))
    question_count = len(all_questions)

    # If personal quiz doesn't have custom questions yet, fallback to eligible global pool questions
    if question_count < 5:
        global_qs = Question.objects.filter(quiz__isnull=True, active=True).prefetch_related('options')
        if global_qs.count() >= 5:
            all_questions = random.sample(list(global_qs), 5)
        else:
            raise ValidationError({"error": "This quiz currently does not have enough questions configured."})

    # Get questions this participant has already seen in previous attempts
    participant_name_clean = participant_name.strip().lower()
    previous_attempt_questions = QuizAttemptQuestion.objects.filter(
        attempt__quiz=quiz,
        attempt__participant_name__iexact=participant_name_clean
    ).values_list('question_id', flat=True).distinct()

    seen_question_ids = set(previous_attempt_questions)

    # Group questions by category
    from collections import defaultdict
    questions_by_category = defaultdict(list)
    for q in all_questions:
        cat_id = q.category_id if q.category else None
        questions_by_category[cat_id].append(q)

    # Split into seen and unseen per category
    unseen_by_category = defaultdict(list)
    seen_by_category = defaultdict(list)
    
    for cat_id, questions in questions_by_category.items():
        for q in questions:
            if q.id in seen_question_ids:
                seen_by_category[cat_id].append(q)
            else:
                unseen_by_category[cat_id].append(q)

    # Calculate category distribution (proportional to available questions)
    total_available = len(all_questions)
    target_question_count = question_count if question_count >= 5 else 5
    category_targets = {}

    if len(questions_by_category) > 1:
        # Multiple categories - distribute proportionally
        for cat_id, questions in questions_by_category.items():
            proportion = len(questions) / total_available
            target = max(1, round(proportion * target_question_count))  # At least 1 per category
            category_targets[cat_id] = target

        # Adjust to sum to exactly target_question_count
        current_total = sum(category_targets.values())
        while current_total > target_question_count:
            # Reduce from largest category
            largest_cat = max(category_targets, key=category_targets.get)
            if category_targets[largest_cat] > 1:
                category_targets[largest_cat] -= 1
                current_total -= 1
            else:
                break
        while current_total < target_question_count:
            # Add to category with most available
            largest_cat = max(questions_by_category, key=lambda k: len(questions_by_category[k]))
            category_targets[largest_cat] += 1
            current_total += 1
    else:
        # Single category or no categories - just select target_question_count randomly
        category_targets[list(questions_by_category.keys())[0]] = target_question_count

    # Select questions per category preferring unseen
    selected_questions = []
    for cat_id, target_count in category_targets.items():
        unseen = unseen_by_category[cat_id]
        seen = seen_by_category[cat_id]
        
        if len(unseen) >= target_count:
            # Enough unseen in this category
            selected = random.sample(unseen, target_count)
        else:
            # Use all unseen, fill from seen
            selected = unseen.copy()
            needed = target_count - len(selected)
            if needed > 0 and seen:
                additional = random.sample(seen, min(needed, len(seen)))
                selected.extend(additional)
        
        selected_questions.extend(selected)

    # If we didn't get exactly target_question_count (edge case), adjust
    if len(selected_questions) < target_question_count:
        # Fill from remaining questions
        selected_ids = {q.id for q in selected_questions}
        remaining = [q for q in all_questions if q.id not in selected_ids]
        needed = target_question_count - len(selected_questions)
        if remaining:
            selected_questions.extend(random.sample(remaining, min(needed, len(remaining))))
    elif len(selected_questions) > target_question_count:
        # Trim randomly
        selected_questions = random.sample(selected_questions, target_question_count)

    # Shuffle the selected questions to randomize order
    random.shuffle(selected_questions)

    # Create the attempt record
    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        tab=tab,
        participant_name=participant_name.strip(),
        status='in_progress',
        total_questions=target_question_count,
        score=0,
        percentage=0.0
    )

    # Store the selected questions and randomize option order per question
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
