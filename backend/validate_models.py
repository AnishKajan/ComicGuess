"""
Validation script to check model syntax and basic functionality
"""

# Test imports
try:
    from pydantic import BaseModel, Field, validator
    from typing import Dict, Optional, List
    from datetime import datetime
    import uuid
    print("✓ All required imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)

# Test basic Pydantic model creation
class TestModel(BaseModel):
    name: str = Field(..., min_length=1)
    value: int = Field(default=0, ge=0)
    
    @validator('name')
    def validate_name(cls, v):
        return v.strip()

try:
    test = TestModel(name="test", value=5)
    print("✓ Basic Pydantic model works")
except Exception as e:
    print(f"✗ Pydantic model error: {e}")
    exit(1)

print("✓ Model validation environment is working correctly")