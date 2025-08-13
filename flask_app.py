import sqlite3
import json
import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from pydantic import BaseModel, ValidationError, Field
import datetime
import random
import requests
import time

# --- Pydantic Models for Request Body Validation ---
class ChatRequest(BaseModel):
    user_id: int
    message: str

class ScheduleRequest(BaseModel):
    user_id: int
    subject: str
    topics: list[str] # List of topic names
    total_hours: int = Field(..., ge=1) # Total hours must be at least 1
    days_per_week: int = Field(..., ge=1, le=7) # Days per week must be between 1 and 7

class AddProgressRequest(BaseModel):
    user_id: int
    subject: str
    topic: str
    score: int = Field(..., ge=0, le=100) # Score between 0 and 100
    date: str = Field(datetime.date.today().isoformat()) # Date in ISO format

class FeedbackRequest(BaseModel):
    user_id: int
    query: str
    explanation_feedback: int = Field(..., ge=1, le=5) # Rating 1-5
    resource_feedback: int = Field(..., ge=1, le=5) # Rating 1-5
    comments: str | None = None

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'))

# Construct the absolute path to the SQLite database file.
DATABASE = os.path.join(os.path.dirname(__file__), '..', 'edumentor.db')
API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Database Connection Helper ---
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# --- Gamification Logic ---
LEVEL_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 300,
    4: 600,
    5: 1000
}

def get_level(points):
    """Calculates the user's level based on their points."""
    for lvl in sorted(LEVEL_THRESHOLDS.keys(), reverse=True):
        if points >= LEVEL_THRESHOLDS[lvl]:
            return lvl
    return 1

def check_for_badges(user_id):
    """
    Checks if a user has earned any new badges based on their current stats.
    Awards badges and returns a list of newly earned badge names.
    """
    newly_earned_badges = []
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            user_stats = c.execute("SELECT points, level, last_active_date FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user_stats:
                return newly_earned_badges

            user_points = user_stats['points']
            user_level = user_stats['level']
            
            all_badges = c.execute("SELECT id, name, criteria FROM badges").fetchall()
            earned_badge_ids = {row['badge_id'] for row in c.execute("SELECT badge_id FROM user_badges WHERE user_id = ?", (user_id,)).fetchall()}

            for badge in all_badges:
                badge_id = badge['id']
                badge_name = badge['name']
                criteria = badge['criteria']

                if badge_id in earned_badge_ids:
                    continue

                earned = False
                if criteria == "Earn 5 points" and user_points >= 5:
                    earned = True
                elif criteria == "Complete 10 chat sessions":
                    chat_sessions = c.execute("SELECT COUNT(*) FROM feedback WHERE user_id = ?", (user_id,)).fetchone()[0]
                    if chat_sessions >= 10:
                        earned = True
                elif criteria == "Generate 3 study plans":
                    study_plans = c.execute("SELECT COUNT(*) FROM study_plans WHERE user_id = ?", (user_id,)).fetchone()[0]
                    if study_plans >= 3:
                        earned = True
                elif criteria == "Achieve a 3-day study streak":
                    streak_count = 0
                    today = datetime.date.today()
                    for i in range(3):
                        check_date = (today - datetime.timedelta(days=i)).isoformat()
                        has_progress = c.execute("SELECT COUNT(*) FROM progress WHERE user_id = ? AND date = ?", (user_id, check_date)).fetchone()[0] > 0
                        if has_progress:
                            streak_count += 1
                        else:
                            break
                    if streak_count >= 3:
                        earned = True
                elif criteria.startswith("Average score of 90+ in 5"):
                    subject_name = criteria.split('in 5 ')[1].replace(' topics', '')
                    subject_scores = c.execute("SELECT score FROM progress WHERE user_id = ? AND subject = ?", (user_id, subject_name)).fetchall()
                    if len(subject_scores) >= 5:
                        avg_score = sum(s['score'] for s in subject_scores) / len(subject_scores)
                        if avg_score >= 90:
                            earned = True
                elif criteria == "Submit 5 feedback entries":
                    feedback_count = c.execute("SELECT COUNT(*) FROM feedback WHERE user_id = ?", (user_id,)).fetchone()[0]
                    if feedback_count >= 5:
                        earned = True
                elif criteria == "Reach Level 2" and user_level >= 2:
                    earned = True
                
                if earned:
                    c.execute("INSERT INTO user_badges (user_id, badge_id) VALUES (?, ?)", (user_id, badge_id))
                    newly_earned_badges.append(badge_name)
            
            conn.commit()

    except sqlite3.Error as e:
        print(f"Database error in check_for_badges: {e}")
        # Optionally, log the error and handle it gracefully
    
    return newly_earned_badges

# --- LLM Integration and Resource Curation ---
def get_llm_response_and_resources(prompt):
    """
    Calls the Gemini API to get an explanation and curates resources.
    """
    if not API_KEY:
        print("API key is not set. Cannot call LLM.")
        return {
            "explanation": "I'm sorry, my AI capabilities are currently unavailable. Please check the server configuration.",
            "resources": []
        }

    explanation_prompt = f"Explain the academic concept '{prompt}' in a simple, clear, and engaging manner for a student. Include 2-3 practical examples if applicable. Keep the explanation concise, around 150-200 words."
    
    chat_history = [{ "role": "user", "parts": [{ "text": explanation_prompt }] }]
    payload = { "contents": chat_history }
    
    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"
    
    generated_text = "I'm sorry, I couldn't generate a response. Please try again."
    max_retries = 3
    for i in range(max_retries):
        try:
            response = requests.post(apiUrl, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result and result.get("candidates") and result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts"):
                generated_text = result["candidates"][0]["content"]["parts"][0]["text"]
                break
            else:
                print("LLM response structure was unexpected or content was missing.")
        except requests.exceptions.RequestException as e:
            print(f"API call failed with request error: {e}. Retrying in {2 ** i} seconds...")
            if i < max_retries - 1:
                time.sleep(2 ** i)
            else:
                print(f"API call failed after {max_retries} attempts.")
        except Exception as e:
            print(f"An unexpected error occurred during API call: {e}. Retrying in {2 ** i} seconds...")
            if i < max_retries - 1:
                time.sleep(2 ** i)
            else:
                print(f"API call failed after {max_retries} attempts.")

    resources = [
        {"title": f"Khan Academy: {prompt}", "url": f"https://www.khanacademy.org/search?search_query={prompt.replace(' ', '%20')}"},
        {"title": f"Wikipedia: {prompt}", "url": f"https://en.wikipedia.org/wiki/{prompt.replace(' ', '_')}"},
        {"title": f"YouTube: {prompt} explained", "url": f"https://www.youtube.com/results?search_query={prompt.replace(' ', '+')}+explained"}
    ]
    
    full_response = {
        "explanation": generated_text,
        "resources": resources
    }
    return full_response

# --- Scheduling Algorithm ---
def create_study_schedule(user_id, subject, topics_names, total_hours, days_per_week):
    """
    Generates a personalized study schedule based on user input and topic metadata.
    Prioritizes topics based on difficulty and distributes them across days.
    """
    if not topics_names or total_hours <= 0 or days_per_week <= 0:
        return {"error": "Please provide valid topics, hours, and days to create a schedule."}

    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            placeholders = ','.join('?' for _ in topics_names)
            query = f"SELECT name, difficulty, estimated_hours FROM topics WHERE name IN ({placeholders}) AND subject = ?"
            topics_data = c.execute(query, topics_names + [subject]).fetchall()

    except sqlite3.Error as e:
        print(f"Database error in create_study_schedule: {e}")
        return {"error": "An internal database error occurred."}

    if not topics_data:
        return {"error": "No matching topics found for the selected subject. Please ensure topics are correctly spelled and belong to the subject."}

    difficulty_map = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}
    sorted_topics = sorted([dict(row) for row in topics_data], key=lambda x: (difficulty_map.get(x['difficulty'], 99), x['estimated_hours']), reverse=True)

    hours_per_day_target = total_hours / days_per_week
    
    schedule = {
        "subject": subject,
        "total_hours": total_hours,
        "days_per_week": days_per_week,
        "daily_schedule": []
    }

    current_topic_idx = 0
    for day_num in range(days_per_week):
        daily_plan = {
            "day": f"Day {day_num + 1}",
            "hours_allocated": 0.0,
            "topics": []
        }
        
        remaining_daily_hours = hours_per_day_target
        
        while remaining_daily_hours > 0.1 and current_topic_idx < len(sorted_topics):
            topic = sorted_topics[current_topic_idx]
            topic_name = topic['name']
            estimated_time = topic['estimated_hours']

            time_to_allocate = min(remaining_daily_hours, estimated_time)
            
            daily_plan["topics"].append({
                "topic": topic_name,
                "time_allocated": round(time_to_allocate, 2),
                "difficulty": topic['difficulty']
            })
            
            daily_plan["hours_allocated"] += time_to_allocate
            remaining_daily_hours -= time_to_allocate
            
            if time_to_allocate >= estimated_time:
                current_topic_idx += 1
            else:
                sorted_topics[current_topic_idx]['estimated_hours'] -= time_to_allocate
                break

        daily_plan["hours_allocated"] = round(daily_plan["hours_allocated"], 2)
        schedule["daily_schedule"].append(daily_plan)
        
    return schedule

# --- API Endpoints ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/static/js/<path:filename>')
def serve_static_js(filename):
    """Serves static JavaScript files."""
    return send_from_directory(app.static_folder + '/js', filename)

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handles chatbot conversations. Receives a message, gets an LLM response,
    curates resources, and updates user points.
    """
    try:
        data = ChatRequest(**request.json)
        response = get_llm_response_and_resources(data.message)
        
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET points = points + 5 WHERE id = ?", (data.user_id,))
            conn.commit()
        
        new_badges = check_for_badges(data.user_id)
        if new_badges:
            response['new_badges'] = new_badges
        
        return jsonify(response)
    except ValidationError as e:
        return jsonify({"error": f"Invalid request data: {e.errors()}"}), 400
    except sqlite3.Error as e:
        print(f"Database error in /api/chat: {e}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        print(f"Error in /api/chat: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/api/schedule', methods=['POST'])
def schedule():
    """
    Generates a study schedule based on user input and saves it to the database.
    """
    try:
        data = ScheduleRequest(**request.json)
        schedule_plan = create_study_schedule(
            data.user_id,
            data.subject,
            data.topics,
            data.total_hours,
            data.days_per_week
        )
        
        if "error" in schedule_plan:
            return jsonify(schedule_plan), 400

        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO study_plans (user_id, subject, plan_details) VALUES (?, ?, ?)",
                      (data.user_id, data.subject, json.dumps(schedule_plan)))
            conn.commit()
        
        new_badges = check_for_badges(data.user_id)
        
        response_data = {"schedule": schedule_plan, "message": "Study plan created successfully!"}
        if new_badges:
            response_data['new_badges'] = new_badges
        
        return jsonify(response_data)
    except ValidationError as e:
        return jsonify({"error": f"Invalid request data: {e.errors()}"}), 400
    except sqlite3.Error as e:
        print(f"Database error in /api/schedule: {e}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        print(f"Error in /api/schedule: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/api/user/add', methods=['POST'])
def add_user():
    """
    Endpoint to add a new user to the database or retrieve an existing user's ID.
    Updates last_active_date and checks for daily streak.
    """
    try:
        username = request.json.get('username')
        if not username:
            return jsonify({"error": "Username is required"}), 400
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            c.execute("SELECT id, username, points, level FROM users WHERE username = ?", (username,))
            existing_user = c.fetchone()
            
            today_date = datetime.date.today().isoformat()
            
            if existing_user:
                user_id = existing_user["id"]
                c.execute("UPDATE users SET last_active_date = ? WHERE id = ?", (today_date, user_id))
                conn.commit()
                new_badges = check_for_badges(user_id)

                return jsonify({
                    "user_id": user_id,
                    "username": existing_user["username"],
                    "points": existing_user["points"],
                    "level": existing_user["level"],
                    "message": "User already exists, session started.",
                    "new_badges": new_badges
                })
            else:
                c.execute("INSERT INTO users (username, last_active_date) VALUES (?, ?)", (username, today_date))
                user_id = c.lastrowid
                conn.commit()
                return jsonify({"user_id": user_id, "username": username, "points": 0, "level": 1, "message": "New user created successfully!"})
            
    except sqlite3.Error as e:
        print(f"Database error in /api/user/add: {e}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        print(f"Error in /api/user/add: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/api/user/<int:user_id>/progress', methods=['GET'])
def get_user_progress(user_id):
    """
    Retrieves user progress and gamification data (points, level, recent scores, earned badges).
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            user = c.execute("SELECT username, points, level FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                return jsonify({"error": "User not found"}), 404

            progress_data = c.execute("SELECT subject, topic, score, date FROM progress WHERE user_id = ? ORDER BY date DESC LIMIT 20", (user_id,)).fetchall()
            earned_badges = c.execute("""
                SELECT b.name, b.description, ub.earned_at 
                FROM user_badges ub JOIN badges b ON ub.badge_id = b.id 
                WHERE ub.user_id = ? ORDER BY ub.earned_at DESC
            """, (user_id,)).fetchall()
            
            return jsonify({
                "username": user["username"],
                "points": user["points"],
                "level": user["level"],
                "progress": [dict(row) for row in progress_data],
                "earned_badges": [dict(row) for row in earned_badges]
            })

    except sqlite3.Error as e:
        print(f"Database error in /api/user/<int:user_id>/progress: {e}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        print(f"Error in /api/user/<int:user_id>/progress: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/api/user/<int:user_id>/add_progress', methods=['POST'])
def add_progress(user_id):
    """
    Endpoint to manually add progress for a user (e.g., after completing a study session).
    Awards points and checks for badges.
    """
    try:
        data = AddProgressRequest(user_id=user_id, **request.json)
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            c.execute("INSERT INTO progress (user_id, subject, topic, date, score) VALUES (?, ?, ?, ?, ?)",
                      (data.user_id, data.subject, data.topic, data.date, data.score))
            
            points_awarded = data.score // 5
            c.execute("UPDATE users SET points = points + ? WHERE id = ?", (points_awarded, data.user_id))
            
            current_points = c.execute("SELECT points FROM users WHERE id = ?", (data.user_id,)).fetchone()['points']
            new_level = get_level(current_points)
            c.execute("UPDATE users SET level = ? WHERE id = ?", (new_level, data.user_id))
            
            conn.commit()

        new_badges = check_for_badges(data.user_id)

        return jsonify({"message": "Progress added successfully!", "points_awarded": points_awarded, "new_level": new_level, "new_badges": new_badges})
    except ValidationError as e:
        return jsonify({"error": f"Invalid request data: {e.errors()}"}), 400
    except sqlite3.Error as e:
        print(f"Database error in /api/user/<int:user_id>/add_progress: {e}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        print(f"Error in /api/user/<int:user_id>/add_progress: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/api/topics', methods=['GET'])
def get_topics():
    """Retrieves all available topics from the database."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            topics = c.execute("SELECT name, subject, difficulty, estimated_hours FROM topics ORDER BY subject, name").fetchall()
            return jsonify([dict(row) for row in topics])
    except sqlite3.Error as e:
        print(f"Database error in /api/topics: {e}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        print(f"Error in /api/topics: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Allows users to submit feedback on chatbot explanations/resources."""
    try:
        data = FeedbackRequest(**request.json)
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO feedback (user_id, query, explanation_feedback, resource_feedback, comments) VALUES (?, ?, ?, ?, ?)",
                      (data.user_id, data.query, data.explanation_feedback, data.resource_feedback, data.comments))
            conn.commit()
        
        new_badges = check_for_badges(data.user_id)
        
        response_data = {"message": "Feedback submitted successfully!"}
        if new_badges:
            response_data['new_badges'] = new_badges
        
        return jsonify(response_data)
    except ValidationError as e:
        return jsonify({"error": f"Invalid request data: {e.errors()}"}), 400
    except sqlite3.Error as e:
        print(f"Database error in /api/feedback: {e}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        print(f"Error in /api/feedback: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)