import { config } from "dotenv";
import { drizzle } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import postgres from "postgres";

config({
  path: ".env.local",
});

const runMigrate = async () => {
  if (!process.env.POSTGRES_URL) {
    console.log("⏭️  POSTGRES_URL not defined, skipping migrations");
    process.exit(0);
  }

  const connection = postgres(process.env.POSTGRES_URL, { max: 1 });
  const db = drizzle(connection);

  console.log("⏳ Running migrations...");

  const start = Date.now();
  try {
    await migrate(db, { migrationsFolder: "./lib/db/migrations" });
    const end = Date.now();
    console.log("✅ Migrations completed in", end - start, "ms");
  } catch (err: any) {
    // Ignore "already exists" errors - schema is already set up
    if (err.message?.includes("already exists")) {
      console.log("⏭️  Schema already exists, skipping migrations");
    } else {
      throw err;
    }
  }
  
  await connection.end();
  process.exit(0);
};

runMigrate().catch((err) => {
  console.error("❌ Migration failed");
  console.error(err);
  process.exit(1);
});
