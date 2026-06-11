import asyncio, websockets, json

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJ0ZXN0QHRlc3QuY29tIiwiZXhwIjoxNzgwOTg3MTIzfQ.aK-hPSDZEBzP6ZfGAOEe-gFWZGsFfUkj_NJbeRDk4_U"   # from /login

async def test():
    uri = f"ws://localhost:8000/ws/task?token={TOKEN}"
    async with websockets.connect(uri) as ws:
        # Send a task
        await ws.send(json.dumps({
            "task": "Write a short summary of solar panel technology",
            "thread_id": "tier2_test_006"
        }))
        print("✅ Task sent. Watching agent stream...\n")

        while True:
            msg = json.loads(await ws.recv())
            event = msg.get("event")

            if event == "status":
                print(f"  → {msg['message']}")

            elif event == "human_review":
                print(f"\n⏸️  PIPELINE PAUSED FOR HUMAN REVIEW")
                print(f"  Draft preview: {msg['current_draft'][:200]}...")
                print(f"  Review score so far: {msg.get('review_score', 'N/A')}/10")

                # Simulate human approving — see step 3 below
                print("\n  (Waiting for /approve call — run step 3 now)")
                # Keep listening for resume confirmation
                continue

            elif event == "complete":
                print(f"\n✅ PIPELINE COMPLETE")
                print(f"  Output preview: {msg['result'][:300]}...")
                break

            elif event == "cost":
                print(f"\n💰 Cost: {msg['tokens']} tokens | ${msg['cost_usd']:.6f} USD")
                break

            elif event == "error":
                print(f"\n❌ Error: {msg['message']}")
                break

asyncio.run(test())
