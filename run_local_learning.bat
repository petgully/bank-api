@echo off
echo 🏠 Local Rule Learning Script
echo ================================

REM Set database credentials (you can also set these as environment variables)
set DB_HOST=petgully-dbserver.cmzwm2y64qh8.us-east-1.rds.amazonaws.com
set DB_USER=admin
set DB_PASS=care6886
set DB_NAME=petgully_db

echo.
echo 📦 Installing requirements...
pip install -r requirements_local.txt

echo.
echo 🔌 Testing database connection...
python -c "from local_learn_rules import LocalRuleLearner; learner = LocalRuleLearner(); conn = learner.get_db_connection(); print('✅ Database connection successful!'); conn.close()"

echo.
echo 🚀 Running rule learning (dry run)...
python local_learn_rules.py --dry-run

echo.
echo 💡 To learn and add rules, run:
echo    python local_learn_rules.py
echo.
echo 💡 To commit and push changes:
echo    git add rules.py
echo    git commit -m "Add auto-learned rules"
echo    git push
echo.
pause
