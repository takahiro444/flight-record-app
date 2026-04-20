"""
Direct database connection test using the same code as the agent.
This helps diagnose if the issue is with DB connection or something else.
"""

import os
import sys

# Expects these environment variables to be set by the caller:
#   DB_SECRET_ARN    - Secrets Manager ARN holding DB credentials
#   MODEL_ID         - optional (default: anthropic.claude-3-5-haiku-20241022-v1:0)
#   BEDROCK_REGION   - optional (default: us-west-2)
if not os.environ.get('DB_SECRET_ARN'):
    print("ERROR: DB_SECRET_ARN environment variable is required", file=sys.stderr)
    sys.exit(2)

os.environ.setdefault('MODEL_ID', 'anthropic.claude-3-5-haiku-20241022-v1:0')
os.environ.setdefault('BEDROCK_REGION', 'us-west-2')

from db import get_connection

def test_connection():
    """Test basic DB connection"""
    print("=" * 60)
    print("Database Connection Test")
    print("=" * 60)
    
    try:
        print("\n1. Attempting to connect to database...")
        conn = get_connection()
        print("✅ Connection established successfully!")
        
        print("\n2. Testing query execution...")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM flight_record WHERE user_sub = %s", ("test-user",))
        count = cursor.fetchone()[0]
        print(f"✅ Query executed successfully! Found {count} records for test-user")
        
        print("\n3. Checking table schema...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'flight_record' 
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print("✅ Table columns:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]}")
        
        cursor.close()
        conn.close()
        print("\n✅ Connection closed successfully")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"   {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(test_connection())
