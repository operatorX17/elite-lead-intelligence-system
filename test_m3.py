import asyncio
import traceback
from leados_sales import run_sales_agent

async def main():
    try:
        reply = await run_sales_agent(
            phone="whatsapp:+1234567890",
            user_message="hello",
            lead_data={"clinic_name": "Test Clinic"}
        )
        print("SUCCESS:", reply)
    except Exception as e:
        with open("test_error.txt", "w") as f:
            f.write(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
