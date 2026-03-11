// Test database connection
import { config } from 'dotenv';
config({ path: '.env.local' });

import postgres from 'postgres';

const url = process.env.POSTGRES_URL;
console.log('Testing connection to:', url?.replace(/:[^:@]+@/, ':****@'));

if (!url) {
  console.error('POSTGRES_URL not set');
  process.exit(1);
}

try {
  const sql = postgres(url, { 
    max: 1,
    connect_timeout: 10,
    idle_timeout: 5
  });
  
  console.log('Attempting query...');
  const result = await sql`SELECT 1 as test`;
  console.log('✅ Connection successful!', result);
  
  // Check if User table exists
  const tables = await sql`
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
  `;
  console.log('Tables in database:', tables.map(t => t.table_name));
  
  await sql.end();
} catch (err) {
  console.error('❌ Connection failed:', err.message);
  process.exit(1);
}
