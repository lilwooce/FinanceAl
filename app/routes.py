from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from authlib.integrations.flask_client import OAuth
from .models import User, ChatHistory, Transaction, Budget, RecurringExpense, Goal, Post, Comment
from openai import OpenAI
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from flask import abort
import re
from sqlalchemy.orm import joinedload
import logging
from .config import Config

# Access the values from the Config class
SessionLocal = Config.SessionLocal
AUTH0_DOMAIN = Config.AUTH0_DOMAIN
AUTH0_CLIENT_ID = Config.AUTH0_CLIENT_ID
AUTH0_CLIENT_SECRET = Config.AUTH0_CLIENT_SECRET
AUTH0_CALLBACK_URL = Config.AUTH0_CALLBACK_URL
AUTH0_LOGOUT_REDIRECT = Config.AUTH0_LOGOUT_REDIRECT
OPENAI_API_KEY = Config.OPENAI_API_KEY


app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config["SESSION_PERMANENT"] = False  # Ensures session resets when browser is closed
app.config["SESSION_TYPE"] = "filesystem"

logging.basicConfig(level=logging.DEBUG, format="%(message)s", handlers=[
])

client = OpenAI(api_key=Config.OPENAI_API_KEY, default_headers={"OpenAI-Beta": "assistants=v2"})

# 🔹 Configure Auth0 OAuth
oauth = OAuth(app)
auth0 = oauth.register(
    "auth0",
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    api_base_url=f"https://{AUTH0_DOMAIN}",
    access_token_url=f"https://{AUTH0_DOMAIN}/oauth/token",
    authorize_url=f"https://{AUTH0_DOMAIN}/authorize",
    client_kwargs={"scope": "openid profile email"},
    server_metadata_url=f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration",
)

from flask import Blueprint

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template("index.html")

# 🔹 Auth0 Login Route
@main.route("/login")
def login():
    return auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL)

# 🔹 Auth0 Callback (Handles User Authentication)
@main.route("/callback")
def callback():
    auth0.authorize_access_token()
    user_info = auth0.get("userinfo").json()
    session["user"] = user_info

    # 🔹 Check if user exists in the database
    db_session = SessionLocal()
    existing_user = db_session.query(User).filter_by(auth0_id=user_info["sub"]).first()

    if not existing_user:
        # 🔹 Initialize new user with default values
        new_user = User(
            auth0_id=user_info["sub"],
            name=user_info.get("name", "Unknown User"),
            email=user_info.get("email", ""),
            picture=user_info.get("picture", ""),
            monthly_income=0.0  # Default income (user sets later)
        )
        db_session.add(new_user)
        db_session.commit()

    db_session.close()

    return redirect(url_for("main.profile"))

def generate_budget_recommendations(user_id):
    db = SessionLocal()
    transactions = db.query(Transaction).filter_by(user_id=user_id).all()
    db.close()

    if not transactions:
        return {
            "Food": 300,
            "Rent": 1000,
            "Utilities": 150,
            "Savings": 200,
            "Entertainment": 100
        }, "No AI-generated advice available."  # Fallback default budget & advice

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expenses = sum(t.amount for t in transactions if t.type == "expense")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a smart financial assistant that helps users create budgets based on their past transactions."},
                {"role": "user", "content": f"My total income from transactions is ${total_income}, and my total expenses are ${total_expenses}. How should I budget my money?"}
            ],
        )

        budget_text = response.choices[0].message.content.strip()
        
        # Extract values using regex to handle structured response format
        budget_data = {}
        advice = ""

        budget_pattern = re.compile(r"\*\*(.*?)\*\*:\s*\$?([\d,]+)")
        advice_pattern = re.compile(r"\*\*Key Advice:\*\* (.*)")

        for match in budget_pattern.findall(budget_text):
            category = match[0].strip()
            amount = float(match[1].replace(",", ""))
            budget_data[category] = amount

        advice_match = advice_pattern.search(budget_text)
        if advice_match:
            advice = advice_match.group(1).strip()

        return budget_data, advice

    except Exception as e:
        print(f"Error generating budget: {e}")
        return {
            "Food": 300,
            "Rent": 1000,
            "Utilities": 150,
            "Savings": 200,
            "Entertainment": 100
        }, "No AI-generated advice available."  # Fallback default budget & advice


# 🔹 Profile Page
@main.route("/profile")
def profile():
    user_info = session.get("user")
    if not user_info:
        return redirect(url_for("main.login"))
    return render_template("profile.html", user=user_info)

@main.route("/goals")
def goals():
    return render_template("goals.html")

@main.route('/chat')
def chat():
    return render_template('chat.html')

# 🔹 Function to Generate a Summary of Chat History Including User's Name
def summarize_chat_history(user_id):
    db = SessionLocal()
    chat_messages = db.query(ChatHistory).filter_by(user_id=user_id).order_by(ChatHistory.timestamp.desc()).limit(10).all()
    user_name = db.query(User).filter_by(id=user_id).first().name
    db.close()

    if not chat_messages:
        return None  # No history, no summary needed

    conversation_text = "\n".join([f"{msg.sender}: {msg.message}" for msg in reversed(chat_messages)])

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "## Task\r\nYou are an AI assistant with the name Al and you are an Alpaca that summarizes a user\'s past conversations to provide context for the next interaction. \r\n\r\n## Input Data\r\n- A structured list of previous messages, including both user and AI responses.\r\n- The messages will be retrieved from a database and formatted as a list of structured entries.\r\n\r\n## Instructions\r\n1. **Identify key discussion points:** Extract the main topics, user preferences, and critical decisions.\r\n2. **Summarize user concerns and requests:** Clearly state what the user has been asking about.\r\n3. **Summarize AI responses:** Provide a concise breakdown of the advice, explanations, or solutions given.\r\n4. **Highlight unresolved questions:** If the conversation includes open-ended or unresolved inquiries, list them.\r\n5. **Remove redundant or irrelevant details:** The summary should be **clear, concise, and actionable**.\r\n6. **Output in a structured format:**\r\n\r\n## Format\r\n\\`\\`\\`\r\n### Previous Conversation Summary:\r\n- **Main topics discussed:** [List key topics]\r\n- **User preferences or concerns:** [Summarize user preferences, concerns, or requests]\r\n- **AI responses given:** [Summarize AI\'s guidance]\r\n- **Unresolved questions:** [List any unanswered questions]\r\n\\`\\`\\`\r\n\r\n### Example Output:\r\n\\`\\`\\`\r\n### Previous Conversation Summary:\r\n- **Main topics discussed:** Financial planning, stock investments, tax strategies.\r\n- **User preferences or concerns:** Interested in reducing tax liability while maximizing long-term investments.\r\n- **AI responses given:** Provided tax-saving strategies, investment diversification tips, and budgeting methods.\r\n- **Unresolved questions:** User asked about advanced stock trading algorithms, awaiting further details.\r\n\\`\\`\\`\r\n\r\nThis summary will be **used in the next prompt** to ensure continuity in the conversation.\r\n ENSURE THAT YOU DON'T USE MARKUP IN THE OUTPUT"},
                {"role": "user", "content": f"User's name: {user_name}\nChat history:\n{conversation_text}"}
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating chat summary: {e}")
        return None
    
def summarize_goals(user_id):
    """
    Summarizes the user's goals, including progress and completion status.
    """
    db = SessionLocal()
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    db.close()

    if not goals:
        return "No active financial goals set."

    goal_summary = []
    for goal in goals:
        completion_status = "✅ Completed" if goal.completed else "⏳ In Progress"
        progress_percentage = (goal.progress / goal.target) * 100 if goal.target > 0 else 0
        goal_summary.append(f"- **{goal.name}**: ${goal.progress:.2f} / ${goal.target:.2f} ({progress_percentage:.1f}%) - {completion_status}")

    return "### Financial Goals Summary:\n" + "\n".join(goal_summary)


# 🔹 Function to Generate a Personalized Greeting
def generate_greeting(user_id, name, page=""):
    chat_summary = summarize_chat_history(user_id)
    transaction_summary = summarize_past_transactions(user_id)  # ✅ Include past transactions
    goal_summary = summarize_goals(user_id)  # ✅ Include goal summary
    
    try:
        prompt = "## You have the name Al and you are an Alpaca! Instructions  \r\n1. Using the user\'s **name**, **past chat history**, and **transactional history**, craft a **personalized greeting** that acknowledges their progress and aligns with their financial goals.  \r\n2. Incorporate relevant **financial goals**, **key activities**, and **recent changes** based on the provided details.  \r\n3. Ensure the greeting is **warm, humanlike, and motivational**, tailored to encourage continued financial growth.  \r\n4. Avoid generic or repetitive phrasing—each greeting should feel unique and specific to the user.  \r\n5. Keep the message **concise** but **engaging**, with a focus on the user’s achievements and next steps.  \r\n\r\n## Output Format  \r\nGenerate the greeting message based on the provided details.  \r\n\r\n---\r\n\r\n## **Example Output**  \r\n\r\n\\`\\`\\`\r\nWelcome back, [User\'s Name]! 👋 You’ve made fantastic progress with optimizing your budget, and your focus on reducing miscellaneous expenses is clearly paying off. Staying on track with your financial goals will only lead to more success. Let’s keep pushing forward and continue building your financial future together. 🚀\r\n\\`\\`\\`\r\n\r\n---\r\n\r\nOnly include the text. Include no special characters (other than emojis). Keep your responses incredibly short and concise. No yapping. Max 15 words"
        prompt += f"\nUser's name: {name}\n"
        if ("index" not in page) and page !="":
            prompt += f"User is on the {page} page so think about that while greeting.\n"
        if chat_summary:
            prompt += f" Here is a summary of their last conversation: {chat_summary}. Use this to personalize your greeting."
        if transaction_summary:
            prompt += f"## User's Financial Overview\n{transaction_summary}\n\n"
        if goal_summary:
            prompt += f"## User's Goal Progress\n{goal_summary}\n\n"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=50
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating personalized greeting: {e}")
        return "Hello! I'm here to assist you with financial questions. How can I help today?"
    
@main.route("/generate_greeting", methods=["POST"])
def fetch_greeting():
    user_info = session.get("user")
    data = request.get_json()  # ✅ Get JSON data from request
    page_name = data.get("page", "index") 

    if not user_info:
        return jsonify({"greeting": f"Hello, I'm Al, how can I assist you today?"})  # ✅ Include page name in fallback

    # ✅ Fetch user from the database
    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    db.close()

    if not user:
        return jsonify({"greeting": f"Hello, I'm Al, how can I assist you today?"})  # ✅ Default greeting with page name

    # ✅ Generate AI Greeting using User Data
    personalized_greeting = generate_greeting(user.id, user.name, page_name)
    
    return jsonify({"greeting": f"{personalized_greeting}"})  # ✅ Include page name in greeting

def summarize_past_transactions(user_id):
    db = SessionLocal()
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.date.desc())
        .limit(20)
        .all()
    )
    db.close()

    if not transactions:
        return "No recent transactions available."

    # 🔹 Summarize transactions with full details
    summary = "### Summary of the Last 20 Transactions:\n"

    for txn in transactions:
        summary += f"- **{txn.type.capitalize()}** | **Category**: {txn.category} | **Amount**: ${txn.amount:.2f} | **Date**: {txn.date.strftime('%Y-%m-%d %H:%M:%S')}"
        if txn.description:
            summary += f" | **Description**: {txn.description}"
        summary += "\n"

    return summary


@main.route("/send_message", methods=["POST"])
def send_message():
    user_message = request.json.get("message", "").strip()
    user_info = session.get("user")

    if not user_message:
        return jsonify({"response": "Please enter a message!"})

    if not user_info:
        return jsonify({"response": "Please log in to chat."})
        

    # 🔹 Get user from database
    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    user_id = user.id if user else None
    db.close()

    if not user:
        return jsonify({"response": "User not found in database."})
    
    chat_summary = summarize_chat_history(user_id)
    transaction_summary = summarize_past_transactions(user_id)  # ✅ Include past transactions
    goal_summary = summarize_goals(user_id)  # ✅ Include goal summary

    # ✅ Get financial summary for the past 30 days
    total_income, total_expenses = get_financial_summary(user_id)
    
    # ✅ Check if expenses exceed 75% of income
    spending_warning = ""
    if total_income > 0 and total_expenses > (0.75 * total_income):
        spending_warning = (f"\n\n## Alert: The user has spent {total_expenses:.2f} in the past month, "
                            f"which is more than 75% of their income ({total_income:.2f}). "
                            f"Suggest ways to reduce spending and save more.")

    try:
        prompt = "##You have the name Al and you are an Alpaca! Task\r\nYou are a highly intelligent and financially savvy AI assistant with expertise in **investments, savings, budgeting, tax strategies, risk management, and financial growth**. Your goal is to provide **precise, data-driven, and strategic advice** tailored to the user’s financial goals.\r\n\r\n## Context\r\n- You must adapt your responses based on the user’s financial profile, risk tolerance, and preferences.\r\n- Use **real-world financial principles** and up-to-date strategies to guide the user.\r\n- You must **explain concepts in simple terms** while providing **professional-level advice**.\r\n\r\n## Instructions\r\n1. **Gather user profile details:** Before giving advice, ask for key details such as income range, risk tolerance, financial goals (short-term and long-term), and investment knowledge.\r\n2. **Provide expert financial insights:** Offer clear, **data-backed strategies** for wealth building.\r\n3. **Adapt to different financial needs:**\r\n   - If the user is a beginner, simplify explanations and suggest safer investment options.\r\n   - If the user is experienced, provide **advanced insights** into investment strategies.\r\n4. **Balance risk and reward:** Guide the user towards **smart, calculated risks** for higher returns.\r\n5. **Include tax-efficient strategies:** Suggest ways to **minimize taxes** legally while maximizing financial growth.\r\n6. **Help with debt management and budgeting:** Offer strategies to reduce debt and optimize savings.\r\n\r\n## Output Format\r\n\\`\\`\\`\r\n### Personalized Financial Strategy:\r\n- **Current financial standing:** [If available, summarize user’s financial profile]\r\n- **Goals identified:** [Summarize user’s financial objectives]\r\n- **Recommended actions:** [Provide a clear step-by-step plan]\r\n- **Potential risks and considerations:** [Outline any risk factors]\r\n\\`\\`\\`\r\n\r\n## Example Interaction:\r\nUser: \"I have $10,000 to invest. What should I do?\"\r\nAI Response:\r\n\\`\\`\\`\r\n### Personalized Financial Strategy:\r\n- **Current financial standing:** Beginner investor with $10,000 to allocate.\r\n- **Goals identified:** Seeking growth with moderate risk tolerance.\r\n- **Recommended actions:**\r\n  1. **Allocate 50%** to diversified index funds (S&P 500, NASDAQ ETFs).\r\n  2. **Invest 20%** in high-dividend stocks for passive income.\r\n  3. **Keep 20%** in high-yield savings for liquidity.\r\n  4. **Use 10%** for learning (books, courses, financial mentorship).\r\n- **Potential risks and considerations:** Market volatility may impact stock investments; maintain a long-term view.\r\n\\`\\`\\`\r\n\r\n---\r\n\r\n ENSURE THAT YOU DON'T USE MARKUP IN THE OUTPUT. KEEP THE OUTPUT PURE TEXT (NO HASHTAS NO STARS JUST TEXT)"
        prompt += spending_warning
        if request.json.get("beginner"):
            prompt += "\n\n## Explain everything in simple terms as if teaching a beginner."
        if chat_summary:
            prompt += f" Here is a summary of their last conversation: {chat_summary}. Use this to personalize your response."
        if transaction_summary:
            prompt += f"## User's Financial Overview\n{transaction_summary}\n\n"
        if goal_summary:
            prompt += f"## User's Goal Progress\n{goal_summary}\n\n"

        # 🔹 Call OpenAI API for Chat Response
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ],
        )

        # 🔹 Extract response from OpenAI API
        bot_reply = response.choices[0].message.content.strip()

        # ✅ Generate Quick Replies Based on User Input
        quick_replies = []
        user_message_lower = user_message.lower()

        if "save money" in user_message_lower:
            quick_replies = ["Create a budget", "Cut expenses", "Invest savings"]
        elif "invest" in user_message_lower:
            quick_replies = ["Stocks", "Crypto", "Real estate"]
        elif "budget" in user_message_lower:
            quick_replies = ["Track expenses", "Set savings goals", "Reduce debt"]
        elif "loan" in user_message_lower:
            quick_replies = ["Compare interest rates", "Check credit score", "Apply for a loan"]

        # 🔹 Store conversation in the database
        store_message(user.id, "user", user_message)
        store_message(user.id, "bot", bot_reply)

    except Exception as e:
        print(e)
        bot_reply = "I'm having trouble responding right now. Please try again later!"

    return jsonify({"response": bot_reply, "quick_replies": quick_replies})

@main.route("/get_chat_history", methods=["GET"])
def get_chat_history():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"chat_history": [{"sender": "bot", "text": "Please log in to view your chat history."}]})

    # 🔹 Get user from database
    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()

    if not user:
        db.close()
        return jsonify({"chat_history": [{"sender": "bot", "text": "User not found in database."}]})

# 🔹 Store Chat Message in Database
def store_message(user_id, sender, message):
    db = SessionLocal()
    chat_entry = ChatHistory(user_id=user_id, sender=sender, message=message)
    db.add(chat_entry)
    db.commit()
    db.close()

# Initialize chat history if it doesn't exist
def init_chat_session():
    session["chat_history"] = [{"sender": "bot", "text": generate_greeting()}]
    session.modified = True

# 🔹 Logout Route
@main.route("/logout")
def logout():
    session.clear()
    return redirect(
        f"https://{AUTH0_DOMAIN}/v2/logout?"
        f"client_id={AUTH0_CLIENT_ID}&"
        f"returnTo={AUTH0_LOGOUT_REDIRECT}"
    )

def categorize_transaction(description):
    """
    Uses AI to categorize a transaction based on its description.
    Defaults to 'Misc' if the AI cannot determine a valid category.
    """
    categories = ["Food", "Rent", "Utilities", "Savings", "Entertainment", "Misc", "Transportation", "Income"]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "## Task  \r\nYou are a finance assistant with the name Al and you are an Alpaca!that classifies financial transactions into one of the following categories:  \r\n\r\n[\"Food\", \"Rent\", \"Utilities\", \"Savings\", \"Entertainment\", \"Misc\", \"Transportation\", \"Income\"]  \r\n\r\n## Instructions  \r\n1. **Analyze the transaction description** and assign it to the most appropriate category.  \r\n2. **Use logical classification rules** based on common spending patterns.  \r\n3. **If the category is unclear**, classify it as **\"Misc\"**.  \r\n4. **Output ONLY the category name**—no explanations, no additional text.  \r\n\r\n## Output Format  \r\nReturn ONLY one of the following words:  \r\n**Food, Rent, Utilities, Savings, Entertainment, Misc**  \r\n\r\n---\r\n\r\n## **Example Inputs & Outputs**  \r\n\r\n**User Input:**  \r\n\\`\\`\\`\r\n\"Starbucks coffee - $5.50\"\r\n\\`\\`\\`  \r\n**AI Response:**  \r\n\\`\\`\\`\r\nFood\r\n\\`\\`\\`  \r\n\r\n**User Input:**  \r\n\\`\\`\\`\r\n\"Netflix subscription - $15.99\"\r\n\\`\\`\\`  \r\n**AI Response:**  \r\n\\`\\`\\`\r\nEntertainment\r\n\\`\\`\\`  \r\n\r\n**User Input:**  \r\n\\`\\`\\`\r\n\"Bank transfer - $200\"\r\n\\`\\`\\`  \r\n**AI Response:**  \r\n\\`\\`\\`\r\nMisc\r\n\\`\\`\\`  \r\n\r\n---\r\n\r\nENSURE THAT YOU DON'T USE MARKUP IN THE OUTPUT"},
                {"role": "user", "content": f"Classify this transaction: '{description}'"}
            ],
        )
        
        ai_category = response.choices[0].message.content.strip()
        if ai_category in categories:
            return ai_category
        return "Misc"  # Default if AI response is not in expected categories

    except Exception as e:
        print(f"AI Categorization Error: {e}")
        return "Misc"  # Fallback category in case of an error

@main.route("/add_transaction", methods=["POST"])
def add_transaction():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"status": "error", "message": "Please log in to add transactions."})

    data = request.json
    description = data.get("description", "").strip()
    amount = float(data.get("amount", 0))
    transaction_type = data.get("type", "expense")

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    
    if not user:
        db.close()
        return jsonify({"status": "error", "message": "User not found."})

    # ✅ AI Categorization Function
    category = categorize_transaction(description)

    # ✅ Create Transaction Entry
    new_transaction = Transaction(
        user_id=user.id,
        type=transaction_type,
        category=category,
        amount=amount,
        description=description
    )
    db.add(new_transaction)

    # ✅ Match Transaction to a Goal
    if transaction_type == "expense":
        matched_goal = find_matching_goal(user.id, description)
        if matched_goal:
            logging.debug(f"Updating goal progress for {matched_goal.name} with amount {amount}")
            matched_goal.progress += amount

            # ✅ Check if goal is completed
            if matched_goal.progress >= matched_goal.target:
                matched_goal.progress = matched_goal.target  # Ensure progress does not exceed target
                matched_goal.completed = True
                logging.debug(f"Goal '{matched_goal.name}' completed!")

            db.add(matched_goal)  # ✅ Ensure goal updates are committed

    db.commit()
    db.close()

    return jsonify({"status": "success", "message": f"Transaction added under '{category}'."})


@main.route("/get_transactions", methods=["GET"])
def get_transactions():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"transactions": []})

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    if not user:
        db.close()
        return jsonify({"transactions": []})

    transactions = db.query(Transaction).filter_by(user_id=user.id).all()
    db.close()

    return jsonify([{
        "id": t.id,
        "type": t.type,
        "category": t.category,
        "amount": t.amount,
        "description": t.description,  # ✅ Send original input back to frontend
        "date": t.date.strftime("%Y-%m-%d %H:%M:%S")
    } for t in transactions])

@main.route("/set_budget", methods=["POST"])
def set_budget():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"status": "error", "message": "Please log in to set a budget."})

    data = request.json
    db = SessionLocal()

    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    if not user:
        db.close()
        return jsonify({"status": "error", "message": "User not found."})

    existing_budget = db.query(Budget).filter_by(user_id=user.id, category=data["category"]).first()
    if existing_budget:
        existing_budget.limit_amount = float(data["limit_amount"])  # Update existing budget
    else:
        new_budget = Budget(
            user_id=user.id,
            category=data["category"],
            limit_amount=float(data["limit_amount"])
        )
        db.add(new_budget)

    db.commit()
    db.close()

    return jsonify({"status": "success", "message": "Budget set successfully."})

@main.route("/get_budgets", methods=["GET"])
def get_budgets():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"budgets": []})

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    if not user:
        db.close()
        return jsonify({"budgets": []})

    budgets = db.query(Budget).filter_by(user_id=user.id).all()
    db.close()

    return jsonify([{
        "category": b.category,
        "limit_amount": b.limit_amount
    } for b in budgets])

@main.route("/set_income", methods=["POST"])
def set_income():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"status": "error", "message": "Please log in to set your income."})

    data = request.json
    db = SessionLocal()

    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    if not user:
        db.close()
        return jsonify({"status": "error", "message": "User not found."})

    user.monthly_income = float(data["income"])  # 🔹 Update income in the database
    db.commit()

    # 🔹 Generate AI-based budget recommendations
    suggested_budgets, financial_advice = generate_budget_recommendations(user.monthly_income)

    # 🔹 Store financial advice in session
    session["financial_advice"] = financial_advice

    # 🔹 Update or Create New Budget Entries
    for category, amount in suggested_budgets.items():
        existing_budget = db.query(Budget).filter_by(user_id=user.id, category=category).first()
        if existing_budget:
            existing_budget.limit_amount = amount
        else:
            new_budget = Budget(user_id=user.id, category=category, limit_amount=amount)
            db.add(new_budget)

    db.commit()
    db.close()

    return jsonify({
        "status": "success",
        "message": "Income updated successfully and budget adjusted.",
        "budget": suggested_budgets,
        "financial_advice": financial_advice
    })


@main.route("/get_financial_advice", methods=["GET"])
def get_financial_advice():
    advice = session.get("financial_advice", "No financial advice available.")
    return jsonify({"advice": advice})

@main.route("/get_financial_summary", methods=["GET"])
def get_financial_summary():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"income": 400000, "expenses": 159919})  # Default values

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()

    if not user:
        db.close()
        return jsonify({"income": 400000, "expenses": 159919})  # Default values

    # Get transactions from the past 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.date >= thirty_days_ago
    ).all()

    # Calculate income and expenses dynamically
    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expenses = sum(t.amount for t in transactions if t.type == "expense")

    db.close()

    return jsonify({"income": total_income, "expenses": total_expenses})

@main.route("/delete_transaction", methods=["POST"])
def delete_transaction():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"status": "error", "message": "Please log in to delete transactions."})

    data = request.json
    transaction_id = data.get("id")

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()

    if not user:
        db.close()
        return jsonify({"status": "error", "message": "User not found."})

    transaction = db.query(Transaction).filter_by(id=transaction_id, user_id=user.id).first()
    
    if not transaction:
        db.close()
        return jsonify({"status": "error", "message": "Transaction not found."})

    db.delete(transaction)
    db.commit()
    db.close()

    return jsonify({"status": "success", "message": "Transaction deleted successfully."})

@main.route("/edit_transaction", methods=["POST"])
def edit_transaction():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"status": "error", "message": "Please log in to edit transactions."})

    data = request.json
    transaction_id = data.get("id")
    new_category = data.get("category", "").strip()
    new_amount = float(data.get("amount", 0))

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    transaction = db.query(Transaction).filter_by(id=transaction_id, user_id=user.id).first()
    
    if not transaction:
        db.close()
        return jsonify({"status": "error", "message": "Transaction not found."})

    transaction.category = new_category
    transaction.amount = new_amount

    db.commit()
    db.close()

    return jsonify({"status": "success", "message": "Transaction updated successfully."})

@main.route("/get_income", methods=["GET"])
def get_income():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"income": 0})

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    db.close()

    if not user:
        return jsonify({"income": 0})

    return jsonify({"income": user.monthly_income})

@main.route("/add_recurring_expense", methods=["POST"])
def add_recurring_expense():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"status": "error", "message": "Please log in to add a recurring expense."})

    data = request.json
    db = SessionLocal()

    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    if not user:
        db.close()
        return jsonify({"status": "error", "message": "User not found."})

    # Determine next due date based on frequency
    frequency_map = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(weeks=4),
        "yearly": timedelta(weeks=52),
    }
    next_due_date = datetime.utcnow() + frequency_map[data["frequency"]]

    new_recurring_expense = RecurringExpense(
        user_id=user.id,
        category=data["category"],
        amount=float(data["amount"]),
        frequency=data["frequency"],
        next_due_date=next_due_date
    )

    db.add(new_recurring_expense)
    db.commit()
    db.close()

    return jsonify({"status": "success", "message": "Recurring expense added successfully."})

@main.route("/get_recurring_expenses", methods=["GET"])
def get_recurring_expenses():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"recurring_expenses": []})

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()
    if not user:
        db.close()
        return jsonify({"recurring_expenses": []})

    recurring_expenses = db.query(RecurringExpense).filter_by(user_id=user.id).all()
    db.close()

    return jsonify([{
        "id": re.id,
        "category": re.category,
        "amount": re.amount,
        "frequency": re.frequency,
        "next_due_date": re.next_due_date.strftime("%Y-%m-%d")
    } for re in recurring_expenses])

def process_recurring_expenses():
    db = SessionLocal()
    now = datetime.now()

    # Find all due recurring expenses
    due_expenses = db.query(RecurringExpense).filter(RecurringExpense.next_due_date <= now).all()

    for expense in due_expenses:
        # Create a new expense transaction
        new_transaction = Transaction(
            user_id=expense.user_id,
            type="expense",
            category=expense.category,
            amount=expense.amount,
            date=now
        )
        db.add(new_transaction)

        # Update next due date
        frequency_map = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(weeks=4),
            "yearly": timedelta(weeks=52),
        }
        expense.next_due_date += frequency_map[expense.frequency]

    db.commit()
    db.close()

@main.route("/get_spend_analysis", methods=["GET"])
def get_spend_analysis():
    user_info = session.get("user")

    if not user_info:
        return jsonify({"status": "error", "message": "User not logged in"})

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()

    if not user:
        db.close()
        return jsonify({"status": "error", "message": "User not found"})

    # Calculate total spending per category
    spending_data = defaultdict(float)
    transactions = db.query(Transaction).filter_by(user_id=user.id, type="expense").all()
    
    total_spending = 0
    for transaction in transactions:
        spending_data[transaction.category] += transaction.amount
        total_spending += transaction.amount

    db.close()

    return jsonify({"total_spending": total_spending, "categories": spending_data})

from datetime import datetime, timedelta

def get_financial_summary(user_id):
    db = SessionLocal()
    
    # Get transactions from the past 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.date >= thirty_days_ago
    ).all()
    
    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expenses = sum(t.amount for t in transactions if t.type == "expense")
    
    db.close()
    
    return total_income, total_expenses

@main.route("/add_goal", methods=["POST"])
def add_goal():
    user_info = session.get("user")
    if not user_info:
        return jsonify({"message": "User not logged in!"}), 401

    data = request.json
    goal_name = data.get("name", "").strip()
    target_amount = float(data.get("target", 0))
    progress_amount = float(data.get("progress", 0))

    if not goal_name or target_amount <= 0:
        return jsonify({"message": "Invalid goal details!"}), 400

    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info["sub"]).first()

    if not user:
        db.close()
        return jsonify({"message": "User not found!"}), 400

    new_goal = Goal(
        user_id=user.id,  
        name=goal_name,
        target=target_amount,
        progress=progress_amount
    )

    db.add(new_goal)
    db.commit()
    db.close()

    return jsonify({"message": "Goal added successfully!"})


@main.route("/get_goals", methods=["GET"])
def get_goals():
    user_info = session.get("user")
    logging.debug("Fetching goals for user")  # ✅ Debugging log
    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info['sub']).first()
    goals = db.query(Goal).filter_by(user_id=user.id).all()
    db.close()
    logging.debug(goals)
    return jsonify([
        {
            "id": g.id,
            "name": g.name,
            "target": g.target,
            "progress": g.progress,
            "completed": g.completed  # ✅ Send correct completed status
        }
        for g in goals
    ])
    

@main.route("/edit_goal", methods=["POST"])
def edit_goal():
    user_info = session.get("user")
    if not user_info:
        return jsonify({"message": "User not logged in!"}), 401

    data = request.json
    db = SessionLocal()

    goal = db.query(Goal).filter_by(id=data["id"]).first()
    if goal:
        goal.progress = float(data["progress"])
        db.commit()

    db.close()
    return jsonify({"message": "Goal updated successfully!"})


@main.route("/delete_goal", methods=["POST"])
def delete_goal():
    user_info = session.get("user")
    if not user_info:
        return jsonify({"message": "User not logged in!"}), 401

    data = request.json
    db = SessionLocal()
    goal = db.query(Goal).filter_by(id=data["id"]).delete()
    db.commit()
    db.close()
    
    return jsonify({"message": "Goal deleted successfully!"})

def find_matching_goal(user_id, transaction_description):
    """
    Uses AI to find a goal that closely matches the transaction description.
    If a match is found and is not completed, returns the goal object.
    """
    db = SessionLocal()
    goals = db.query(Goal).filter(Goal.user_id == user_id, Goal.completed == False).all()  # ✅ Ignore completed goals

    if not goals:
        db.close()
        return None

    goal_names = [goal.name for goal in goals]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You have the name Al and you are an Alpaca! You are an AI assistant that finds a matching goal based on a transaction description."},
                {"role": "user", "content": f"Transaction description: {transaction_description}\n\nUser's goals: {goal_names}\n\nFind the closest matching goal."}
            ],
        )
        
        matched_goal_name = response.choices[0].message.content.strip()
        
        for goal in goals:
            logging.debug(f"Checking goal: {goal.name} against AI match: {matched_goal_name}")  # ✅ Debugging log
            if goal.name.lower() in matched_goal_name.lower():
                logging.debug(f"Matched goal found: {goal.name}")  # ✅ Debugging log
                db.close()
                return goal

    except Exception as e:
        logging.error(f"AI Goal Matching Error: {e}")  # ✅ Use logging for better debugging
    
    db.close()
    return None  # No match found

# 🔹 Forum Page (View Posts)
@main.route('/forum')
def forum():
    db = SessionLocal()  # Get the database session
    # Eager load the 'user' relationship with posts using joinedload
    posts = db.query(Post).options(joinedload(Post.user)).order_by(Post.date.desc()).all()
    db.close()  # Close the session
    return render_template('forum.html', posts=posts)


# 🔹 Function to Protect Routes That Need Authentication
def require_login():
    if "user" not in session:
        return redirect(url_for("main.login"))
    return session["user"]

# 🔹 Route to Create a New Post
@main.route('/forum/new', methods=['GET', 'POST'])
def new_post():
    user_info = require_login()  # Ensure user is logged in
    db = SessionLocal()
    user = db.query(User).filter_by(auth0_id=user_info['sub']).first()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        db = SessionLocal()  # Get the database session
        post = Post(user_id=user.id, title=title, content=content)  # Use Auth0's user ID
        db.add(post)  # Add the new post to the database
        db.commit()  # Commit the changes
        db.close()
        return redirect(url_for('main.forum'))  # Redirect back to the forum
    return render_template('new_post.html')  # Render the new post creation form

@main.route('/forum/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    user_info = require_login()  # Ensure user is logged in
    db = SessionLocal()  # Get the database session
    user = db.query(User).filter_by(auth0_id=user_info['sub']).first()
    userid = user.id

    # Fetch the specific post and eagerly load the 'user' relationship for both the post and its comments
    post = db.query(Post).options(joinedload(Post.user)).get(post_id)
    
    if not post:
        db.close()  # Ensure the session is closed if no post is found
        abort(404)  # If the post is not found, return a 404 error

    # Eagerly load the 'user' relationship for all comments
    comments = db.query(Comment).options(joinedload(Comment.user)).filter_by(post_id=post.id).order_by(Comment.date.asc()).all()

    if request.method == 'POST':
        content = request.form['content']
        comment = Comment(user_id=userid, post_id=post.id, content=content)  # Use Auth0's user ID
        db.add(comment)  # Add the new comment
        db.commit()  # Commit the changes

        # Reload the post and comments to include the new comment
        post = db.query(Post).options(joinedload(Post.user)).get(post_id)
        comments = db.query(Comment).options(joinedload(Comment.user)).filter_by(post_id=post.id).order_by(Comment.date.asc()).all()

    db.close()  # Close the session after all operations

    return render_template('view_post.html', post=post, comments=comments)

# 🔹 Route to Delete a Post (Only Author)
@main.route('/forum/post/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    user_info = require_login()  # Ensure user is logged in
    db = SessionLocal()  # Get the database session
    user = db.query(User).filter_by(auth0_id=user_info['sub']).first()

    post = db.query(Post).get(post_id)  # Fetch the post or None if not found
    if not post:
        db.close()
        abort(404)  # If the post is not found, return a 404 error

    if post.user_id != user.id:  # Check if the current user is the author of the post
        db.close()
        abort(403)  # Forbidden

    db.delete(post)  # Delete the post from the database
    db.commit()  # Commit the changes
    db.close()
    return redirect(url_for('main.forum'))  # Redirect back to the forum


# 🔹 Route to Edit a Comment
@main.route('/forum/comment/edit/<int:comment_id>', methods=['GET', 'POST'])
def edit_comment(comment_id):
    user_info = require_login()  # Ensure user is logged in
    db = SessionLocal()  # Get the database session
    user = db.query(User).filter_by(auth0_id=user_info['sub']).first()

    comment = db.query(Comment).options(joinedload(Comment.user)).get(comment_id)  # Fetch the comment with the user eager-loaded
    if not comment:
        db.close()
        abort(404)  # If the comment is not found, return a 404 error

    if comment.user_id != user.id:  # Ensure the logged-in user is the author
        db.close()
        abort(403)  # Forbidden

    if request.method == 'POST':
        comment.content = request.form['content']
        db.commit()  # Commit the changes

        # Reload the post and comments after the commit to keep the session open
        post = db.query(Post).options(joinedload(Post.user)).get(comment.post_id)
        comments = db.query(Comment).options(joinedload(Comment.user)).filter_by(post_id=post.id).order_by(Comment.date.asc()).all()

        db.close()  # Close the session after all operations
        return render_template('view_post.html', post=post, comments=comments)  # Redirect to the post page with the updated comment

    db.close()  # Close the session after all operations
    return render_template('edit_comment.html', comment=comment)  # Return the edit comment form



@main.route('/forum/post/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    user_info = require_login()  # Ensure user is logged in
    db = SessionLocal()  # Get the database session
    user = db.query(User).filter_by(auth0_id=user_info['sub']).first()

    # Fetch the specific post and eagerly load the 'user' relationship
    post = db.query(Post).options(joinedload(Post.user)).get(post_id)
    
    if not post:
        db.close()  # Ensure the session is closed if no post is found
        abort(404)  # If the post is not found, return a 404 error

    if post.user_id != user.id:  # Ensure the logged-in user is the author
        db.close()  # Close the session after all operations
        abort(403)  # Forbidden

    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        db.commit()  # Commit the changes

        # Reload the post to get the updated information
        post = db.query(Post).options(joinedload(Post.user)).get(post.id)
        comments = db.query(Comment).options(joinedload(Comment.user)).filter_by(post_id=post.id).order_by(Comment.date.asc()).all()

        db.close()  # Close the session after all operations

        return render_template('view_post.html', post=post, comments=comments)  # Redirect to the updated post page

    db.close()  # Close the session after all operations
    return render_template('edit_post.html', post=post)  # Return the edit post form

# 🔹 Route to Delete a Comment (Only Author)
@main.route('/forum/comment/delete/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    user_info = require_login()  # Ensure user is logged in
    db = SessionLocal()  # Get the database session
    user = db.query(User).filter_by(auth0_id=user_info['sub']).first()

    comment = db.query(Comment).get(comment_id)  # Fetch the comment or None if not found
    if not comment:
        db.close()
        abort(404)  # If the comment is not found, return a 404 error

    if comment.user_id != user.id:  # Check if the current user is the author of the comment
        db.close()
        abort(403)  # Forbidden

    db.delete(comment)  # Delete the comment from the database
    db.commit()  # Commit the changes
    db.close()
    return redirect(url_for('main.view_post', post_id=comment.post_id))  # Redirect back to the post page

