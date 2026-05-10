// Test Supabase connection via REST API
import { config } from 'dotenv';
config({ path: '.env.local' });

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

console.log('Supabase URL:', supabaseUrl);
console.log('Service Key:', supabaseKey?.substring(0, 20) + '...');

if (!supabaseUrl || !supabaseKey) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

try {
  // Try to query the User table
  const { data, error } = await supabase
    .from('User')
    .select('id')
    .limit(1);
  
  if (error) {
    console.error('❌ Query error:', error.message);
    if (error.message.includes('does not exist')) {
      console.log('The User table does not exist. Did you run the migration SQL?');
    }
  } else {
    console.log('✅ Supabase connection successful!');
    console.log('User table exists, found', data?.length || 0, 'users');
  }
} catch (err) {
  console.error('❌ Connection failed:', err.message);
}
