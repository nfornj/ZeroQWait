import httpx
import asyncio
import time

async def test_live():
    # Allow insecure HTTPS since it's a self-signed dev cert
    url = "https://192.168.2.88.nip.io/api/agent/master/chat"
    queries = [
        "Hi, I'm Neekrish, how are you?",
        "Find me a barber nearby",
        "Wait, what was my name again?",
        "Actually, what are your pricing plans for shop owners?",
        "Can you help me join a queue for the first shop you found?"
    ]
    
    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        # Check if server is up
        try:
            await client.get("https://api.192.168.2.88.nip.io/docs")
        except httpx.ConnectError:
            print("Server is offline.")
            return

        session_id = f"test_live_{int(time.time())}"
        
        for q in queries:
            print(f"\\n--- User: {q} ---")
            start = time.time()
            data = {
                "message": q,
                "session_id": session_id,
                "latitude": 43.6532,
                "longitude": -79.3832
            }
            try:
                res = await client.post(url, json=data)
                if res.status_code == 200:
                    resp = res.json()
                    print(f"ZeroQ ({time.time() - start:.2f}s): {resp.get('response', 'No response field')}")
                    if resp.get('actions'):
                        print(f"  Actions triggered: {[a.get('tool') for a in resp['actions']]}")
                else:
                    print(f"Error {res.status_code}: {res.text}")
            except Exception as e:
                print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_live())
