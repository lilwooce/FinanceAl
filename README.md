FinanceAl - UGAHacks X Project

Overview

FinanceAl is an AI-powered personal finance assistant designed to help users track expenses, manage transactions, and gain financial insights through a chat-based interface. The project was built during UGAHacks X and features an intuitive UI, OpenAI API integration, and a robust backend powered by Flask and SQLAlchemy.

Features

AI Chat Assistant: Uses OpenAI's API to provide financial insights and suggestions.

Transaction Management: Allows users to log and categorize transactions.

Expense Tracking: Helps users visualize spending habits.

User Authentication: Secures data with authentication mechanisms.

Responsive UI: A clean, modern interface with smooth transitions and animations.

Technologies Used

Frontend: HTML, CSS, JavaScript, Bootstrap

Backend: Flask, Python

Database: SQLAlchemy (PostgreSQL)

AI Integration: OpenAI API

Hosting: InMotion Hosting (Planned Deployment)

Installation

Clone the repository:

git clone https://github.com/lilwooce/financeal.git

Navigate to the project directory:

cd financeal

Create and activate a virtual environment:

python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Set up environment variables:

export FLASK_APP=app.py
export FLASK_ENV=development

Initialize the database:

flask db upgrade

Run the application:

flask run

Usage

Register/Login to start managing transactions.

Use the AI chat feature to ask for financial insights.

Add, edit, and delete transactions as needed.

View expense summaries and reports.

AI Usage

Tools Used: ChatGPT, GitHub CopilotPurpose: Assisted with debugging, UI suggestions, and API handling.Contribution to Learning: Helped refine error handling strategies and optimize front-end components.

Contributing

Fork the repository.

Create a new branch (git checkout -b feature-branch).

Make your changes and commit (git commit -m "Added new feature").

Push to your fork (git push origin feature-branch).

Open a Pull Request.

License

This project is open-source and available under the MIT License.

Contact

Developer: Jean-Guy Leconte

Email: jeanguy.leconte.iv@gmail.com

GitHub: lilwooce

Acknowledgments

UGAHacks X for hosting the hackathon.

OpenAI for providing powerful AI capabilities.

The amazing open-source community for inspiring development!