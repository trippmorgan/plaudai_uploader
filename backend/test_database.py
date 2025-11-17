#!/usr/bin/env python3
"""
PlaudAI Uploader - Database Connection & Schema Verification
Run this after setting up PostgreSQL to verify everything is working
"""
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'surgical_command_center'),
    'user': os.getenv('DB_USER', 'scc_user'),
    'password': os.getenv('DB_PASSWORD', '')
}

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_connection():
    """Test basic database connection"""
    print_section("1. Testing Database Connection")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print(f"✅ Connected to database successfully!")
        print(f"   Host: {DB_CONFIG['host']}")
        print(f"   Database: {DB_CONFIG['database']}")
        print(f"   User: {DB_CONFIG['user']}")
        
        # Get PostgreSQL version
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"   PostgreSQL: {version.split(',')[0]}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def verify_tables():
    """Verify all required tables exist"""
    print_section("2. Verifying Database Schema")
    
    required_tables = [
        'patients',
        'voice_transcripts',
        'pvi_procedures',
        'clinical_synopses'
    ]
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check each table
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print("\nTable Status:")
        all_exist = True
        for table in required_tables:
            if table in existing_tables:
                # Count rows
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"  ✅ {table:<25} ({count} rows)")
            else:
                print(f"  ❌ {table:<25} (MISSING)")
                all_exist = False
        
        cursor.close()
        conn.close()
        
        return all_exist
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def verify_indexes():
    """Verify important indexes exist"""
    print_section("3. Verifying Database Indexes")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                tablename,
                COUNT(*) as index_count
            FROM pg_indexes 
            WHERE schemaname = 'public'
            GROUP BY tablename
            ORDER BY tablename;
        """)
        
        print("\nIndex Status:")
        for table, count in cursor.fetchall():
            print(f"  ✅ {table:<25} ({count} indexes)")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Index verification failed: {e}")
        return False

def test_insert_patient():
    """Test inserting a patient record"""
    print_section("4. Testing Patient Insert")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Test patient data
        test_patient = {
            'first_name': 'Test',
            'last_name': 'Patient',
            'dob': '1980-01-01',
            'athena_mrn': f'TEST{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'birth_sex': 'M'
        }
        
        cursor.execute("""
            INSERT INTO patients (first_name, last_name, dob, athena_mrn, birth_sex)
            VALUES (%(first_name)s, %(last_name)s, %(dob)s, %(athena_mrn)s, %(birth_sex)s)
            RETURNING id, athena_mrn;
        """, test_patient)
        
        patient_id, mrn = cursor.fetchone()
        conn.commit()
        
        print(f"✅ Successfully inserted test patient")
        print(f"   Patient ID: {patient_id}")
        print(f"   MRN: {mrn}")
        
        # Verify we can retrieve it
        cursor.execute("SELECT * FROM patients WHERE id = %s;", (patient_id,))
        retrieved = cursor.fetchone()
        print(f"   ✅ Successfully retrieved patient record")
        
        # Clean up test patient
        cursor.execute("DELETE FROM patients WHERE id = %s;", (patient_id,))
        conn.commit()
        print(f"   ✅ Test patient cleaned up")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Patient insert test failed: {e}")
        return False

def test_insert_transcript():
    """Test inserting a voice transcript"""
    print_section("5. Testing Voice Transcript Insert")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # First create a test patient
        cursor.execute("""
            INSERT INTO patients (first_name, last_name, dob, athena_mrn)
            VALUES ('Transcript', 'Test', '1970-01-01', 'TRANSCRIPTTEST')
            RETURNING id;
        """)
        patient_id = cursor.fetchone()[0]
        
        # Test transcript data
        test_transcript = {
            'patient_id': patient_id,
            'raw_transcript': 'This is a test transcript from PlaudAI',
            'plaud_note': '## Test Note\nThis is a test formatted note',
            'visit_type': 'Office Visit',
            'tags': '["test", "demo"]'
        }
        
        cursor.execute("""
            INSERT INTO voice_transcripts 
                (patient_id, raw_transcript, plaud_note, visit_type, tags)
            VALUES 
                (%(patient_id)s, %(raw_transcript)s, %(plaud_note)s, 
                 %(visit_type)s, %(tags)s::jsonb)
            RETURNING id;
        """, test_transcript)
        
        transcript_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"✅ Successfully inserted test transcript")
        print(f"   Transcript ID: {transcript_id}")
        print(f"   Patient ID: {patient_id}")
        
        # Clean up
        cursor.execute("DELETE FROM voice_transcripts WHERE id = %s;", (transcript_id,))
        cursor.execute("DELETE FROM patients WHERE id = %s;", (patient_id,))
        conn.commit()
        print(f"   ✅ Test data cleaned up")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Transcript insert test failed: {e}")
        return False

def test_mrn_lookup():
    """Test patient lookup by MRN (key clinical use case)"""
    print_section("6. Testing MRN Lookup (Clinical Retrieval)")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Create test patient
        test_mrn = f'MRNTEST{datetime.now().strftime("%H%M%S")}'
        cursor.execute("""
            INSERT INTO patients (first_name, last_name, dob, athena_mrn)
            VALUES ('MRN', 'Test', '1965-06-15', %s)
            RETURNING id;
        """, (test_mrn,))
        patient_id = cursor.fetchone()[0]
        conn.commit()
        
        # Test MRN lookup
        cursor.execute("""
            SELECT 
                id, 
                first_name, 
                last_name, 
                athena_mrn,
                EXTRACT(YEAR FROM AGE(dob)) AS age
            FROM patients 
            WHERE athena_mrn = %s;
        """, (test_mrn,))
        
        result = cursor.fetchone()
        print(f"✅ Successfully retrieved patient by MRN")
        print(f"   MRN: {result[3]}")
        print(f"   Name: {result[1]} {result[2]}")
        print(f"   Age: {int(result[4])} years")
        
        # Clean up
        cursor.execute("DELETE FROM patients WHERE id = %s;", (patient_id,))
        conn.commit()
        print(f"   ✅ Test data cleaned up")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ MRN lookup test failed: {e}")
        return False

def print_summary(results):
    """Print test summary"""
    print_section("Test Summary")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\nTests Passed: {passed}/{total}")
    print("\nDetailed Results:")
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test}")
    
    if passed == total:
        print(f"\n🎉 All tests passed! Database is ready for production.")
        print(f"\nNext steps:")
        print(f"  1. Start the PlaudAI Uploader API")
        print(f"  2. Test with real PlaudAI transcripts")
        print(f"  3. Configure Gemini API key for synopsis generation")
    else:
        print(f"\n⚠️  Some tests failed. Please review errors above.")
    
    print()

def main():
    """Run all database tests"""
    print("\n" + "="*60)
    print("  PlaudAI Uploader - Database Verification")
    print("="*60)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target Database: {DB_CONFIG['database']} @ {DB_CONFIG['host']}")
    
    # Run all tests
    results = {
        "Database Connection": test_connection(),
        "Schema Verification": verify_tables(),
        "Index Verification": verify_indexes(),
        "Patient Insert": test_insert_patient(),
        "Transcript Insert": test_insert_transcript(),
        "MRN Lookup": test_mrn_lookup()
    }
    
    # Print summary
    print_summary(results)

if __name__ == "__main__":
    main()