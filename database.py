import sqlite3
import os

def setup_database():
    """
    Sets up the SQLite database and creates the necessary tables.
    """
    # Get the absolute path to the database file, which is one level up from 'backend'
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'edumentor.db')

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Create the 'users' table to store user information and gamification points
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                points INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                last_active_date TEXT DEFAULT (date('now'))
            );
        ''')
        
        # Create the 'topics' table to store predefined academic topics with metadata
        c.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                subject TEXT NOT NULL,
                difficulty TEXT NOT NULL, -- e.g., 'Beginner', 'Intermediate', 'Advanced'
                estimated_hours REAL DEFAULT 1.0
            );
        ''')

        # Create the 'study_plans' table to store generated study schedules
        c.execute('''
            CREATE TABLE IF NOT EXISTS study_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subject TEXT NOT NULL,
                plan_details TEXT NOT NULL, -- Stores JSON string of the study plan
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

        # Create the 'progress' table for gamification and tracking study performance
        c.execute('''
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                score INTEGER NOT NULL, -- Example: score on a quiz, or completion percentage
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

        # Create a 'badges' table for gamification
        c.execute('''
            CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                criteria TEXT NOT NULL -- e.g., 'Reach 100 points', 'Complete 5 study plans'
            );
        ''')

        # Create 'user_badges' to link users to earned badges
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_badges (
                user_id INTEGER,
                badge_id INTEGER,
                earned_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, badge_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (badge_id) REFERENCES badges(id)
            );
        ''')

        # Create 'feedback' table for user feedback on explanations
        c.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT NOT NULL,
                explanation_feedback INTEGER, -- e.g., 1-5 rating
                resource_feedback INTEGER, -- e.g., 1-5 rating
                comments TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

        conn.commit()
        print("Database setup complete.")

        # --- Populate initial data (example topics and badges) ---
        # Add some example topics if the table is empty
        c.execute("SELECT COUNT(*) FROM topics")
        if c.fetchone()[0] == 0:
            print("Populating initial topics...")
            topics_data = [
                ("Photosynthesis", "Biology", "Beginner", 1.5),
                ("Cellular Respiration", "Biology", "Intermediate", 2.0),
                ("Newton's Laws of Motion", "Physics", "Beginner", 1.0),
                ("Quantum Mechanics Intro", "Physics", "Advanced", 3.0),
                ("Chemical Bonding", "Chemistry", "Intermediate", 1.5),
                ("Organic Chemistry Basics", "Chemistry", "Advanced", 2.5),
                ("Calculus I: Derivatives", "Mathematics", "Intermediate", 2.0),
                ("Linear Algebra: Vectors", "Mathematics", "Advanced", 2.5),
                ("World War II Causes", "History", "Beginner", 1.0),
                ("Cold War Dynamics", "History", "Intermediate", 2.0),
                ("Shakespearean Sonnets", "Literature", "Beginner", 1.0),
                ("Modernist Literature", "Literature", "Advanced", 2.0),
                ("Python Data Structures", "Computer Science", "Beginner", 1.5),
                ("Algorithm Analysis", "Computer Science", "Intermediate", 2.0),
                ("Microeconomics: Supply & Demand", "Economics", "Beginner", 1.0),
                ("Macroeconomics: GDP", "Economics", "Intermediate", 1.5)
            ]
            c.executemany("INSERT INTO topics (name, subject, difficulty, estimated_hours) VALUES (?, ?, ?, ?)", topics_data)
            conn.commit()
            print("Initial topics populated.")

        # Add some example badges if the table is empty
        c.execute("SELECT COUNT(*) FROM badges")
        if c.fetchone()[0] == 0:
            print("Populating initial badges...")
            badges_data = [
                ("First Step", "Completed your first chat session.", "Earn 5 points"),
                ("Chatty Learner", "Engaged in 10 chat sessions.", "Complete 10 chat sessions"),
                ("Planner Pro", "Generated 3 study plans.", "Generate 3 study plans"),
                ("Consistent Learner", "Maintained a 3-day study streak.", "Achieve a 3-day study streak"),
                ("Subject Master: Biology", "Achieved high scores in Biology topics.", "Average score of 90+ in 5 Biology topics"),
                ("Feedback Champion", "Provided feedback on 5 explanations.", "Submit 5 feedback entries"),
                ("Level Up!", "Reached Level 2.", "Reach Level 2")
            ]
            c.executemany("INSERT INTO badges (name, description, criteria) VALUES (?, ?, ?)", badges_data)
            conn.commit()
            print("Initial badges populated.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    setup_database()
