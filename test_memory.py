import asyncio
import os
import sqlite3
from leados_sales import run_sales_agent

async def sim():
    db_file = "sales_conversations.db"
    
    # 1. First message "Hi"
    reply1 = await run_sales_agent("testphone", "Hi")
    print("1. Reply:", reply1)
    
    # 2. Check DB
    with sqlite3.connect(db_file) as conn:
        print("1. History count:", conn.execute("SELECT COUNT(*) FROM sales_history WHERE phone='testphone'").fetchone()[0])
        print("1. State:", dict(conn.execute("SELECT * FROM sales_state WHERE phone='testphone'").fetchone()))

    # 3. Second message "Yes"
    reply2 = await run_sales_agent("testphone", "Yes")
    print("2. Reply:", reply2)
    
    with sqlite3.connect(db_file) as conn:
        print("2. History count:", conn.execute("SELECT COUNT(*) FROM sales_history WHERE phone='testphone'").fetchone()[0])
        print("2. State:", dict(conn.execute("SELECT * FROM sales_state WHERE phone='testphone'").fetchone()))

if __name__ == "__main__":
    asyncio.run(sim())
