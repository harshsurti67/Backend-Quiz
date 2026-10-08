from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from quiz.models import Quiz, Question, QuestionOption, QuizAttempt


class PersonToPersonQuizTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Prem user
        self.prem_user = User.objects.create_user(
            username="prem", email="prem@example.com", password="password123", first_name="Prem"
        )
        # Create Harsh user
        self.harsh_user = User.objects.create_user(
            username="harsh", email="harsh@example.com", password="password123", first_name="Harsh"
        )

    def test_full_person_to_person_quiz_flow(self):
        # 1. Login as Prem
        login_res = self.client.post("/api/auth/login/", {
            "username": "prem",
            "password": "password123"
        }, format="json")
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        prem_token = login_res.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {prem_token}")

        # 2. Prem creates a 10-question quiz about himself
        questions_payload = []
        for i in range(1, 11):
            questions_payload.append({
                "order": i,
                "text": f"Prem Question {i}?",
                "options": [
                    {"text": f"Q{i} Option A", "is_correct": True, "order": 0},
                    {"text": f"Q{i} Option B", "is_correct": False, "order": 1},
                    {"text": f"Q{i} Option C", "is_correct": False, "order": 2},
                    {"text": f"Q{i} Option D", "is_correct": False, "order": 3},
                ]
            })

        create_res = self.client.post("/api/quizzes/create/", {
            "creator_name": "Prem",
            "title": "How Well Do You Know Prem? 👀",
            "description": "Test your friendship with Prem!",
            "avatar_id": "cool_boy",
            "questions": questions_payload,
            "publish": True
        }, format="json")

        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        prem_quiz_id = create_res.data["public_id"]
        self.assertEqual(create_res.data["status"], "published")
        self.assertEqual(len(create_res.data["questions"]), 10)

        # 3. Harsh (unauthenticated participant) opens Prem's private quiz link
        self.client.credentials() # Logout
        public_res = self.client.get(f"/api/quizzes/{prem_quiz_id}/")
        self.assertEqual(public_res.status_code, status.HTTP_200_OK)
        self.assertEqual(public_res.data["creator_name"], "Prem")
        self.assertEqual(public_res.data["avatar_id"], "cool_boy")

        # 4. Harsh enters name and starts quiz
        start_res = self.client.post(f"/api/quizzes/{prem_quiz_id}/attempts/", {
            "participant_name": "Harsh"
        }, format="json")
        self.assertEqual(start_res.status_code, status.HTTP_201_CREATED)
        attempt_id = start_res.data["attempt_id"]
        attempt_questions = start_res.data["attempt"]["questions"]
        self.assertEqual(len(attempt_questions), 10)

        # Verify NO is_correct in options
        for q in attempt_questions:
            self.assertEqual(len(q["options"]), 4)
            for opt in q["options"]:
                self.assertNotIn("is_correct", opt)

        # 5. Harsh answers all 10 questions (answer first 8 correctly, last 2 incorrectly)
        for idx, q in enumerate(attempt_questions):
            q_id = q["id"]
            if idx < 8:
                opt = QuestionOption.objects.get(question_id=q_id, is_correct=True)
            else:
                opt = QuestionOption.objects.filter(question_id=q_id, is_correct=False).first()

            ans_res = self.client.post(f"/api/attempts/{attempt_id}/answers/", {
                "question_id": q_id,
                "option_id": opt.id
            }, format="json")
            self.assertEqual(ans_res.status_code, status.HTTP_200_OK)

        # 6. Harsh submits quiz
        submit_res = self.client.post(f"/api/attempts/{attempt_id}/submit/", format="json")
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)
        self.assertEqual(submit_res.data["score"], 8)
        self.assertEqual(submit_res.data["total"], 10)
        self.assertEqual(submit_res.data["percentage"], 80.0)
        self.assertEqual(submit_res.data["participant_name"], "Harsh")
        self.assertEqual(submit_res.data["creator_name"], "Prem")

        # 7. Check that attempt is stored under Prem's quiz
        prem_quiz = Quiz.objects.get(public_id=prem_quiz_id)
        self.assertEqual(prem_quiz.attempts.count(), 1)
        self.assertEqual(prem_quiz.attempts.first().participant_name, "Harsh")
        self.assertEqual(prem_quiz.attempts.first().score, 8)

        # 8. Harsh creates his OWN separate quiz
        harsh_questions_payload = []
        for i in range(1, 11):
            harsh_questions_payload.append({
                "order": i,
                "text": f"Harsh Question {i}?",
                "options": [
                    {"text": f"H_Q{i} Option A", "is_correct": True, "order": 0},
                    {"text": f"H_Q{i} Option B", "is_correct": False, "order": 1},
                    {"text": f"H_Q{i} Option C", "is_correct": False, "order": 2},
                    {"text": f"H_Q{i} Option D", "is_correct": False, "order": 3},
                ]
            })

        harsh_create_res = self.client.post("/api/quizzes/create/", {
            "creator_name": "Harsh",
            "title": "How Well Do You Know Harsh? 👀",
            "avatar_id": "cute_boy",
            "questions": harsh_questions_payload,
            "publish": True
        }, format="json")
        self.assertEqual(harsh_create_res.status_code, status.HTTP_201_CREATED)
        harsh_quiz_id = harsh_create_res.data["public_id"]

        # 9. Prem takes Harsh's quiz
        prem_start_res = self.client.post(f"/api/quizzes/{harsh_quiz_id}/attempts/", {
            "participant_name": "Prem"
        }, format="json")
        prem_attempt_id = prem_start_res.data["attempt_id"]

        for q in prem_start_res.data["attempt"]["questions"]:
            q_id = q["id"]
            correct_opt = QuestionOption.objects.get(question_id=q_id, is_correct=True)
            self.client.post(f"/api/attempts/{prem_attempt_id}/answers/", {
                "question_id": q_id,
                "option_id": correct_opt.id
            }, format="json")

        prem_submit_res = self.client.post(f"/api/attempts/{prem_attempt_id}/submit/", format="json")
        self.assertEqual(prem_submit_res.data["score"], 10)
        self.assertEqual(prem_submit_res.data["participant_name"], "Prem")
        self.assertEqual(prem_submit_res.data["creator_name"], "Harsh")

        # 10. Verify absolute ownership isolation
        harsh_quiz = Quiz.objects.get(public_id=harsh_quiz_id)
        self.assertEqual(harsh_quiz.creator_name, "Harsh")
        self.assertEqual(harsh_quiz.attempts.count(), 1)
        self.assertEqual(harsh_quiz.attempts.first().participant_name, "Prem")
        self.assertEqual(harsh_quiz.attempts.first().score, 10)

        # Prem's quiz still has only Harsh's attempt
        self.assertEqual(prem_quiz.attempts.count(), 1)
        self.assertEqual(prem_quiz.attempts.first().participant_name, "Harsh")
