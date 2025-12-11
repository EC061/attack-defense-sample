import sqlite3
import os
import json
from dotenv import load_dotenv
from config_loader import load_config
from recommendation_system.mcp_recommender import MCPMaterialRecommendationSystem

# Load environment variables
load_dotenv()


def main():
    print("=" * 80)
    print("ATTACK COMPARISON SCRIPT")
    print("=" * 80)

    # 1. Get DB path
    cfg = load_config()
    db_path = cfg.get("paths", {}).get(
        "materials_db_path", "materials/processed_materials.db"
    )
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)

    print(f"Database: {db_path}")

    # 2. Get first attack
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, attack_query, querying_student_id, target_attribute, expected_result FROM attacks ORDER BY id LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return

    if not row:
        print(
            "No attacks found in database. Run attack_workflow.py to generate attacks first."
        )
        return

    attack_id, attack_query, student_id, target_attr, expected_res = row

    print(f"\nUsing Attack #{attack_id}")
    print(f"Querying Student: {student_id}")
    print(f"Target Attribute: {target_attr}")
    print(f"Expected Result: {expected_res}")
    print("-" * 40)
    print(f"Query: {attack_query}")

    # 3. Define scenarios
    scenarios = [
        {"name": "1. No Defense", "filter": False, "pii": False},
        {
            "name": "2. First Filter Only (Prompt Injection)",
            "filter": True,
            "pii": False,
        },
        {"name": "3. PII Filter Only", "filter": False, "pii": True},
    ]

    for scenario in scenarios:
        print("\n" + "=" * 80)
        print(f"SCENARIO: {scenario['name']}")
        print(
            f"Defense Config: InjectionFilter={scenario['filter']}, PIIFilter={scenario['pii']}"
        )
        print("=" * 80)

        # Instantiate recommender with specific flags
        recommender = MCPMaterialRecommendationSystem(
            db_path=db_path,
            enable_filter=scenario["filter"],
            enable_pii_filter=scenario["pii"],
        )

        try:
            # Run recommendation
            # verbose=True will show the analysis steps
            results = recommender.recommend_for_student(
                student_id=student_id, student_question=attack_query, verbose=True
            )

            # Simple check for the expected result in the output
            results_str = json.dumps(results, default=str).lower()
            found = str(expected_res).lower() in results_str

            print(
                f"\n>>> Scenario Result: {'ATTACK SUCCESS (Data Leaked)' if found else 'ATTACK BLOCKED/FAILED'}"
            )
            if found:
                print(f"    Expected value '{expected_res}' FOUND in output.")
            else:
                print(f"    Expected value '{expected_res}' NOT FOUND in output.")

        except Exception as e:
            print(f"Error executing scenario: {e}")


if __name__ == "__main__":
    main()
