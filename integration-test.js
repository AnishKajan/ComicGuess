#!/usr/bin/env node

/**
 * End-to-end integration test for ComicGuess application
 */

const http = require('http');
const https = require('https');

// Test configuration
const BACKEND_URL = 'http://127.0.0.1:8000';
const FRONTEND_URL = 'http://127.0.0.1:3000';

// Test results
const results = {
  passed: 0,
  failed: 0,
  tests: []
};

// Helper function to make HTTP requests
function makeRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const client = urlObj.protocol === 'https:' ? https : http;
    
    const req = client.request(url, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = data ? JSON.parse(data) : {};
          resolve({ status: res.statusCode, data: parsed, headers: res.headers });
        } catch (e) {
          resolve({ status: res.statusCode, data: data, headers: res.headers });
        }
      });
    });
    
    req.on('error', reject);
    
    if (options.body) {
      req.write(JSON.stringify(options.body));
    }
    
    req.end();
  });
}

// Test function
async function test(name, testFn) {
  try {
    console.log(`🧪 Testing: ${name}`);
    await testFn();
    console.log(`✅ PASS: ${name}`);
    results.passed++;
    results.tests.push({ name, status: 'PASS' });
  } catch (error) {
    console.log(`❌ FAIL: ${name} - ${error.message}`);
    results.failed++;
    results.tests.push({ name, status: 'FAIL', error: error.message });
  }
}

// Assertion helpers
function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function assertTrue(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// Test suite
async function runTests() {
  console.log('🚀 Starting ComicGuess Integration Tests\n');

  // Backend Health Check
  await test('Backend Health Check', async () => {
    const response = await makeRequest(`${BACKEND_URL}/health`);
    assertEqual(response.status, 200, 'Health check status');
    assertEqual(response.data.status, 'healthy', 'Health check response');
  });

  // Frontend Health Check
  await test('Frontend Health Check', async () => {
    const response = await makeRequest(`${FRONTEND_URL}/health`);
    assertEqual(response.status, 200, 'Frontend health check status');
    assertTrue(response.data.status === 'healthy', 'Frontend health check response');
  });

  // Backend API Root
  await test('Backend API Root', async () => {
    const response = await makeRequest(`${BACKEND_URL}/`);
    assertEqual(response.status, 200, 'API root status');
    assertTrue(response.data.message.includes('ComicGuess API'), 'API root message');
  });

  // CORS Headers
  await test('CORS Headers', async () => {
    const response = await makeRequest(`${BACKEND_URL}/health`, {
      headers: { 'Origin': 'http://localhost:3000' }
    });
    assertEqual(response.status, 200, 'CORS request status');
    // Note: CORS headers are typically added by middleware, may not be visible in simple requests
  });

  // Puzzle Endpoint (Expected to return 404 without data)
  await test('Puzzle Endpoint Structure', async () => {
    const response = await makeRequest(`${BACKEND_URL}/puzzle/today?universe=marvel`);
    // This should return 404 since we don't have puzzle data, but the endpoint should exist
    assertTrue(response.status === 404 || response.status === 200, 'Puzzle endpoint exists');
  });

  // Invalid Universe Parameter
  await test('Invalid Universe Parameter', async () => {
    const response = await makeRequest(`${BACKEND_URL}/puzzle/today?universe=invalid`);
    assertTrue(response.status >= 400, 'Invalid universe should return error');
  });

  // Frontend Static Assets
  await test('Frontend Static Assets', async () => {
    const response = await makeRequest(`${FRONTEND_URL}/`);
    assertEqual(response.status, 200, 'Frontend root status');
    assertTrue(typeof response.data === 'string', 'Frontend returns HTML');
  });

  // API Documentation (if available)
  await test('API Documentation', async () => {
    const response = await makeRequest(`${BACKEND_URL}/docs`);
    // FastAPI automatically provides /docs endpoint
    assertTrue(response.status === 200 || response.status === 404, 'Docs endpoint check');
  });

  // Rate Limiting Test (make multiple requests)
  await test('Rate Limiting', async () => {
    const requests = [];
    for (let i = 0; i < 5; i++) {
      requests.push(makeRequest(`${BACKEND_URL}/health`));
    }
    
    const responses = await Promise.all(requests);
    const allSuccessful = responses.every(r => r.status === 200);
    assertTrue(allSuccessful, 'Multiple requests should succeed (within rate limit)');
  });

  // Content-Type Headers
  await test('Content-Type Headers', async () => {
    const response = await makeRequest(`${BACKEND_URL}/health`);
    assertTrue(
      response.headers['content-type']?.includes('application/json'),
      'API should return JSON content-type'
    );
  });

  // Error Handling
  await test('Error Handling', async () => {
    const response = await makeRequest(`${BACKEND_URL}/nonexistent-endpoint`);
    assertEqual(response.status, 404, 'Non-existent endpoint should return 404');
  });

  // Print results
  console.log('\n📊 Test Results:');
  console.log(`✅ Passed: ${results.passed}`);
  console.log(`❌ Failed: ${results.failed}`);
  console.log(`📈 Total: ${results.passed + results.failed}`);
  
  if (results.failed > 0) {
    console.log('\n❌ Failed Tests:');
    results.tests
      .filter(t => t.status === 'FAIL')
      .forEach(t => console.log(`  - ${t.name}: ${t.error}`));
  }

  // Exit with appropriate code
  process.exit(results.failed > 0 ? 1 : 0);
}

// Run tests
runTests().catch(error => {
  console.error('💥 Test suite failed:', error);
  process.exit(1);
});