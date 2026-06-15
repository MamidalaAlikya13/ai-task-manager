from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import google.generativeai as genai
import os

app = Flask(__name__)

app.config["SECRET_KEY"] = "new-task-ai-secret-key-2026"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///new_tasks.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    total_created = db.Column(db.Integer, default=0)
    total_completed = db.Column(db.Integer, default=0)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default="Medium")
    due_date = db.Column(db.String(20))
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        existing_user = User.query.filter_by(email=request.form["email"]).first()

        if existing_user:
            flash("Email already registered. Please login.", "danger")
            return redirect(url_for("login"))

        new_user = User(
            username=request.form["username"],
            email=request.form["email"],
            password=generate_password_hash(request.form["password"]),
            total_created=0,
            total_completed=0
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()

        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()

    total = current_user.total_created or 0
    completed = current_user.total_completed or 0
    pending = len([task for task in tasks if task.status == "Pending"])
    productivity = int((completed / total) * 100) if total > 0 else 0

    return render_template(
        "dashboard.html",
        tasks=tasks,
        total=total,
        completed=completed,
        pending=pending,
        productivity=productivity
    )


@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    task = Task(
        title=request.form["title"],
        description=request.form["description"],
        priority=request.form["priority"],
        due_date=request.form["due_date"],
        user_id=current_user.id
    )

    current_user.total_created = (current_user.total_created or 0) + 1

    db.session.add(task)
    db.session.commit()

    flash("Task added successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/complete/<int:task_id>")
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)

    if task.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("dashboard"))

    if task.status != "Completed":
        task.status = "Completed"
        current_user.total_completed = (current_user.total_completed or 0) + 1
        db.session.commit()

    flash("Task completed successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)

    if task.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        old_status = task.status
        new_status = request.form["status"]

        task.title = request.form["title"]
        task.description = request.form["description"]
        task.priority = request.form["priority"]
        task.due_date = request.form["due_date"]
        task.status = new_status

        if old_status != "Completed" and new_status == "Completed":
            current_user.total_completed = (current_user.total_completed or 0) + 1

        if old_status == "Completed" and new_status == "Pending":
            current_user.total_completed = max((current_user.total_completed or 0) - 1, 0)

        db.session.commit()

        flash("Task updated successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_task.html", task=task)


@app.route("/delete/<int:task_id>")
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)

    if task.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("dashboard"))

    db.session.delete(task)
    db.session.commit()

    flash("Task deleted successfully. Productivity history is safe.", "success")
    return redirect(url_for("dashboard"))


@app.route("/clear_tasks")
@login_required
def clear_tasks():
    Task.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    flash("All tasks cleared. Productivity history is safe.", "success")
    return redirect(url_for("dashboard"))


@app.route("/full_reset")
@login_required
def full_reset():
    Task.query.filter_by(user_id=current_user.id).delete()

    current_user.total_created = 0
    current_user.total_completed = 0

    db.session.commit()

    flash("Everything has been reset successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/ai_suggest", methods=["POST"])
@login_required
def ai_suggest():
    tasks = Task.query.filter_by(user_id=current_user.id, status="Pending").all()

    if not tasks:
        return jsonify({
            "response": "Great! You have no pending tasks. Enjoy your free time 🎉"
        })

    today = datetime.today().date()
    task_info = []

    for task in tasks:
        due_date = task.due_date
        remaining_time = "No deadline"
        urgency_score = 0

        if due_date:
            try:
                due = datetime.strptime(due_date, "%Y-%m-%d").date()
                days_left = (due - today).days

                if days_left < 0:
                    remaining_time = f"Overdue by {abs(days_left)} day(s)"
                    urgency_score = 100
                elif days_left == 0:
                    remaining_time = "Due today"
                    urgency_score = 90
                elif days_left == 1:
                    remaining_time = "1 day left"
                    urgency_score = 80
                else:
                    remaining_time = f"{days_left} days left"
                    urgency_score = max(10, 70 - days_left)

            except ValueError:
                remaining_time = "Invalid date"
                urgency_score = 0

        priority_score = {
            "High": 30,
            "Medium": 20,
            "Low": 10
        }.get(task.priority, 10)

        total_score = urgency_score + priority_score

        task_info.append({
            "title": task.title,
            "priority": task.priority,
            "due_date": due_date,
            "remaining_time": remaining_time,
            "score": total_score
        })

    task_info = sorted(task_info, key=lambda x: x["score"], reverse=True)
    best_task = task_info[0]

    task_list = "\n".join(
        [
            f"Task: {task['title']} | Priority: {task['priority']} | Due Date: {task['due_date']} | Remaining Time: {task['remaining_time']} | Score: {task['score']}"
            for task in task_info
        ]
    )

    if not GEMINI_API_KEY:
        return jsonify({
            "response": f"Do this task next: {best_task['title']}\nReason: {best_task['remaining_time']} and priority is {best_task['priority']}."
        })

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
        You are an intelligent AI task planner.

        Choose EXACTLY ONE task the user should do next.

        Consider:
        1. Current date: {today}
        2. Deadline proximity
        3. Overdue tasks
        4. Tasks due today
        5. Priority level

        Important:
        - Mention the exact task title from the list.
        - Do not give generic advice.
        - If a task is overdue or due today, strongly prefer it.
        - Answer in maximum 2 lines.

        Required format:
        Do this task next: <task title>
        Reason: <short reason mentioning days left or deadline>

        Pending tasks:
        {task_list}
        """

        response = model.generate_content(prompt)

        return jsonify({"response": response.text})

    except Exception:
        return jsonify({
            "response": f"Do this task next: {best_task['title']}\nReason: {best_task['remaining_time']} and priority is {best_task['priority']}."
        })


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)