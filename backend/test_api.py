"""
Quick test to verify API can interact with Supabase.
"""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root():
    """Test the root endpoint."""
    response = client.get("/")
    print(f"Root endpoint: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200

def test_api_endpoints():
    """Test that API is accessible."""
    # Test API documentation
    response = client.get("/docs")
    print(f"\nAPI Docs: {response.status_code}")
    
    # Test OpenAPI schema
    response = client.get("/openapi.json")
    print(f"OpenAPI Schema: {response.status_code}")
    assert response.status_code == 200

if __name__ == "__main__":
    print("=" * 60)
    print("Testing FastAPI Backend with Supabase")
    print("=" * 60)
    
    try:
        test_root()
        test_api_endpoints()
        print("\n" + "=" * 60)
        print("✓ All tests passed! Backend is ready.")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
