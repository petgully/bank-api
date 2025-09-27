#!/usr/bin/env python3
"""
Setup script for local rule learning
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages for local development"""
    print("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_local.txt"])
        print("✅ Requirements installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    print("🔌 Testing database connection...")
    try:
        from local_learn_rules import LocalRuleLearner
        learner = LocalRuleLearner()
        conn = learner.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        print("✅ Database connection successful!")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Make sure your database credentials are correct")
        return False

def main():
    print("🏠 Setting up local rule learning environment...")
    print("=" * 50)
    
    # Install requirements
    if not install_requirements():
        return False
    
    # Test database connection
    if not test_database_connection():
        return False
    
    print("\n🎉 Setup complete!")
    print("\n📝 Next steps:")
    print("   1. Run: python local_learn_rules.py --dry-run")
    print("   2. If you like the results: python local_learn_rules.py")
    print("   3. Commit and push: git add rules.py && git commit -m 'Add rules' && git push")
    print("   4. Pull on server: git pull")
    
    return True

if __name__ == "__main__":
    main()
