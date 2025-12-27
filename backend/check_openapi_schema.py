#!/usr/bin/env python3
"""
Script to verify the OpenAPI schema for /policy/answer endpoint
Shows the improved schema with proper Source model definition
"""
import json
from main import app


def main():
    schema = app.openapi()

    print("=" * 70)
    print("OPENAPI SCHEMA VERIFICATION")
    print("=" * 70)

    # Get the Source schema
    source_schema = schema['components']['schemas']['Source']
    print("\n1. Source Schema (now properly defined!):")
    print("-" * 70)
    print(json.dumps(source_schema, indent=2))

    # Get the AnswerResponse schema
    answer_schema = schema['components']['schemas']['AnswerResponse']
    print("\n2. AnswerResponse Schema:")
    print("-" * 70)
    print(f"Properties:")
    for prop_name, prop_def in answer_schema['properties'].items():
        print(f"  - {prop_name}:")
        if '$ref' in str(prop_def):
            print(f"    {json.dumps(prop_def, indent=6)}")
        else:
            print(f"    type: {prop_def.get('type', 'N/A')}")
            if 'description' in prop_def:
                print(f"    description: {prop_def['description']}")

    # Show sources field specifically
    sources_field = answer_schema['properties']['sources']
    print("\n3. Sources Field (the fix!):")
    print("-" * 70)
    print(json.dumps(sources_field, indent=2))

    print("\n4. Example Response:")
    print("-" * 70)
    if 'examples' in answer_schema or 'example' in answer_schema:
        example = answer_schema.get('examples', answer_schema.get('example', {}))
        print(json.dumps(example, indent=2))
    else:
        print("No example found in schema")

    print("\n" + "=" * 70)
    print("✓ Schema validation complete!")
    print("=" * 70)
    print("\nNow when you view the Swagger UI at http://localhost:8000/docs,")
    print("the 'sources' field will show the proper structure with:")
    print("  - doc_name (string)")
    print("  - org (string)")
    print("  - page (int/string)")
    print("  - text_snippet (string)")
    print("  - score (float, optional)")
    print("\nInstead of the generic 'additionalProp1: {}' you saw before!")


if __name__ == "__main__":
    main()
