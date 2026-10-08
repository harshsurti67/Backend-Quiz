from django.core.management.base import BaseCommand
from quiz.models import Category, Question, QuestionOption, Quiz, QuizTab, QuizAttempt


class Command(BaseCommand):
    help = 'Seeds database with categories, questions, options, and sample social quizzes'

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding...")

        categories_data = [
            {"name": "Favorites", "slug": "favorites", "icon": "⭐", "desc": "All-time favorites, preferences, and go-to choices"},
            {"name": "Food", "slug": "food", "icon": "🍕", "desc": "Cuisines, comfort foods, snacks, and dining tastes"},
            {"name": "Movies", "slug": "movies", "icon": "🎬", "desc": "Cinema, shows, actors, and binge-watching favorites"},
            {"name": "Music", "slug": "music", "icon": "🎵", "desc": "Genres, concerts, favorite artists, and tracks"},
            {"name": "Personality", "slug": "personality", "icon": "🧠", "desc": "Character traits, vibes, mindset, and attitudes"},
            {"name": "Sports", "slug": "sports", "icon": "⚽", "desc": "Athletics, fitness routines, teams, and outdoor games"},
            {"name": "Friends", "slug": "friends", "icon": "👯", "desc": "Friendship memories, hangout styles, and loyalty"},
            {"name": "Games", "slug": "games", "icon": "🎮", "desc": "Video games, board games, esports, and hobbies"},
            {"name": "Travel", "slug": "travel", "icon": "✈️", "desc": "Dream destinations, road trips, beaches, and mountains"},
            {"name": "Funny", "slug": "funny", "icon": "😂", "desc": "Hilarious quirks, embarrassing moments, and laughter"},
            {"name": "Habits", "slug": "habits", "icon": "⏰", "desc": "Daily routines, quirks, sleep patterns, and rituals"},
            {"name": "Relationships", "slug": "relationships", "icon": "❤️", "desc": "Bonding, emotional depth, and secrets"},
        ]

        categories = {}
        for c in categories_data:
            cat, _ = Category.objects.update_or_create(
                slug=c["slug"],
                defaults={
                    "name": c["name"],
                    "icon": c["icon"],
                    "description": c["desc"],
                    "active": True,
                }
            )
            categories[c["slug"]] = cat

        self.stdout.write("Categories updated.")

        # Seed Prem's Flagship Quiz (Person-to-Person)
        prem_quiz, _ = Quiz.objects.update_or_create(
            public_id="WQme30Q",
            defaults={
                "creator_name": "Prem",
                "title": "How Well Do You Know Prem? 👀",
                "description": "Prem created this quiz just for his friends. Let's see how well you really know him! 👀",
                "avatar_id": "cool_boy",
                "status": "published",
            }
        )

        prem_questions_data = [
            ("What is my all-time favorite comfort food?", ["Pizza", "Spicy Dum Biryani", "Cheeseburger", "Creamy Pasta"], 1),
            ("What is my dream travel destination?", ["Tokyo, Japan", "Swiss Alps", "Iceland Lights", "Bali Islands"], 0),
            ("Which movie could I watch 10 times without getting bored?", ["Interstellar", "The Dark Knight", "Inception", "Avengers Endgame"], 0),
            ("How do I take my morning caffeine kick?", ["Black Coffee", "Sweet Iced Latte", "Hot Masala Chai", "Matcha Green Tea"], 1),
            ("What time of the day is my peak energy state?", ["Late Night Nocturnal", "Early Morning", "Sunset Golden Hour", "High Noon"], 0),
            ("What is my primary personality vibe?", ["Chill & Ambivert", "Wild Extrovert", "Deep Introvert", "Workaholic Thinker"], 0),
            ("What is my favorite music genre for a drive?", ["Hip-Hop & Rap", "Synthwave & Indie", "EDM & House", "Classic Rock"], 0),
            ("What is my most used emoji in chat?", ["💀 Skull", "😂 Laughing Crying", "👀 Shifty Eyes", "🔥 Fire"], 0),
            ("How many alarms do I set to wake up?", ["1 Alarm", "5+ Alarms", "No Alarm", "10 Alarms"], 1),
            ("What is the best way to cheer me up when down?", ["Bring me food & chill", "Long drive with music", "Sit in peaceful silence", "Go party outside"], 0),
        ]

        # Attach exactly 10 questions to Prem's quiz
        prem_quiz.questions.all().delete()
        for idx, (q_text, opts, correct_idx) in enumerate(prem_questions_data, start=1):
            q = Question.objects.create(
                quiz=prem_quiz,
                text=q_text,
                order=idx,
                active=True
            )
            for opt_idx, opt_text in enumerate(opts):
                QuestionOption.objects.create(
                    question=q,
                    text=opt_text,
                    is_correct=(opt_idx == correct_idx),
                    order=opt_idx
                )

        self.stdout.write("Flagship Prem quiz with 10 questions seeded.")

        # Seed a sample attempt for Harsh under Prem's quiz
        if not QuizAttempt.objects.filter(quiz=prem_quiz, participant_name="Harsh").exists():
            QuizAttempt.objects.create(
                quiz=prem_quiz,
                participant_name="Harsh",
                status="completed",
                score=8,
                total_questions=10,
                percentage=80.0,
                result_message="You know Prem really well!"
            )

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
