/**
 * Live Search Test Script
 * 
 * Tests search functionality against a running Anchor Engine instance.
 * Logs results to console and generates an MD report.
 * 
 * Usage: node test-search-live.js [engine_url]
 * Default: http://localhost:3160
 * 
 * Standard 132: Adaptive Concurrency Testing
 */

import http from 'http';
import os from 'os';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ENGINE_URL = process.argv[2] || 'http://localhost:3160';
const REPORT_FILE = path.join(__dirname, 'search-test-report.md');

// Test queries of varying complexity
const TEST_QUERIES = [
  // Simple queries
  { name: "Single Word", query: "test", expected_behavior: "Basic single term search" },
  { name: "Two Words", query: "rob coda", expected_behavior: "Multi-term search" },
  { name: "Simple Phrase", query: "music education", expected_behavior: "Phrase search" },
  
  // Medium complexity
  { name: "Three Terms", query: "graph nodes consciousness", expected_behavior: "Multiple concept search" },
  { name: "Technical Query", query: "async file processing", expected_behavior: "Technical term search" },
  { name: "Long Phrase", query: "College Music education", expected_behavior: "Longer phrase search" },
  
  // Complex queries (these stress the system)
  { name: "Complex Technical", query: "context inflation radial expansion", expected_behavior: "Complex multi-word" },
  { name: "Many Terms", query: "search memory database query optimization performance", expected_behavior: "Many terms - stress test" },
  { name: "Max Recall Style", query: "Rob and coda music education graph nodes", expected_behavior: "Max recall simulation" }
];

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function getMemoryInfo() {
  const total = Math.floor(os.totalmem() / 1024 / 1024);
  const free = Math.floor(os.freemem() / 1024 / 1024);
  const used = total - free;
  return { total, free, used, percent: Math.round((used / total) * 100) };
}

async function makeRequest(endpoint, data = null) {
  const url = new URL(endpoint, ENGINE_URL);
  const options = {
    hostname: url.hostname,
    port: url.port || 3160,
    path: url.pathname,
    method: data ? 'POST' : 'GET',
    headers: data ? { 'Content-Type': 'application/json' } : {}
  };

  return new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      let responseData = '';
      res.on('data', (chunk) => responseData += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(responseData));
        } catch (e) {
          resolve({ raw: responseData, error: e.message });
        }
      });
    });

    req.on('error', (err) => reject(err));
    
    if (data) {
      req.write(JSON.stringify(data));
    }
    req.end();
  });
}

async function testSearch(query, maxChars = 5000) {
  const startTime = Date.now();
  const startMemory = getMemoryInfo();
  
  try {
    const result = await makeRequest('/v1/memory/search', {
      query,
      max_chars: maxChars,
      token_budget: 1250,
      provenance: 'all',
      strategy: 'standard'
    });
    
    const endTime = Date.now();
    const endMemory = getMemoryInfo();
    
    return {
      success: true,
      query,
      duration_ms: endTime - startTime,
      memory_before: startMemory,
      memory_after: endMemory,
      memory_delta: endMemory.used - startMemory.used,
      results_count: result.results?.length || 0,
      result
    };
  } catch (error) {
    const endTime = Date.now();
    return {
      success: false,
      query,
      duration_ms: endTime - startTime,
      memory_before: startMemory,
      error: error.message
    };
  }
}

function generateReport(results) {
  const timestamp = new Date().toISOString();
  const systemInfo = {
    platform: os.platform(),
    arch: os.arch(),
    cpus: os.cpus().length,
    totalMemory: Math.floor(os.totalmem() / 1024 / 1024),
    nodeVersion: process.version
  };
  
  let report = `# Anchor Engine Live Search Test Report\n\n`;
  report += `**Generated:** ${timestamp}\n`;
  report += `**Engine URL:** ${ENGINE_URL}\n\n`;
  
  report += `## System Information\n\n`;
  report += `- Platform: ${systemInfo.platform} (${systemInfo.arch})\n`;
  report += `- CPUs: ${systemInfo.cpus}\n`;
  report += `- Total Memory: ${systemInfo.totalMemory} MB\n`;
  report += `- Node Version: ${systemInfo.nodeVersion}\n\n`;
  
  report += `## Executive Summary\n\n`;
  const successful = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;
  const avgDuration = Math.round(results.filter(r => r.success).reduce((sum, r) => sum + r.duration_ms, 0) / successful || 0);
  const avgResults = Math.round(results.filter(r => r.success).reduce((sum, r) => sum + r.results_count, 0) / successful || 0);
  
  report += `- **Total Tests:** ${results.length}\n`;
  report += `- **Successful:** ${successful}\n`;
  report += `- **Failed:** ${failed}\n`;
  report += `- **Average Duration:** ${avgDuration} ms\n`;
  report += `- **Average Results:** ${avgResults} per query\n\n`;
  
  report += `## Detailed Results\n\n`;
  
  results.forEach((result, index) => {
    report += `### Test ${index + 1}: ${result.query}\n\n`;
    report += `- **Status:** ${result.success ? '✅ SUCCESS' : '❌ FAILED'}\n`;
    report += `- **Expected:** ${result.expected_behavior}\n`;
    
    if (result.success) {
      report += `- **Duration:** ${result.duration_ms} ms\n`;
      report += `- **Results Found:** ${result.results_count}\n`;
      report += `- **Memory Before:** ${result.memory_before.free} MB free\n`;
      report += `- **Memory After:** ${result.memory_after.free} MB free\n`;
      report += `- **Memory Delta:** ${result.memory_delta} MB\n`;
      
      if (result.result.results && result.result.results.length > 0) {
        report += `\n**Top 3 Results:**\n\n`;
        result.result.results.slice(0, 3).forEach((atom, i) => {
          report += `${i + 1}. **${atom.content?.substring(0, 100) || 'N/A'}...**\n`;
          report += `   - Source: ${atom.source?.filepath || atom.source || 'N/A'}\n`;
          report += `   - Score: ${atom.score || 'N/A'}\n`;
        });
      }
    } else {
      report += `- **Error:** ${result.error}\n`;
    }
    
    report += `\n---\n\n`;
  });
  
  report += `## Memory Analysis\n\n`;
  const memoryDeltas = results.filter(r => r.success).map(r => r.memory_delta);
  if (memoryDeltas.length > 0) {
    const avgDelta = Math.round(memoryDeltas.reduce((sum, d) => sum + d, 0) / memoryDeltas.length);
    const maxDelta = Math.max(...memoryDeltas);
    const minDelta = Math.min(...memoryDeltas);
    
    report += `- **Average Memory Change:** ${avgDelta} MB\n`;
    report += `- **Max Memory Change:** ${maxDelta} MB\n`;
    report += `- **Min Memory Change:** ${minDelta} MB\n`;
    report += `- **Interpretation:** ${avgDelta > 100 ? '⚠️ High memory usage - consider low_memory mode' : '✅ Memory usage acceptable'}\n\n`;
  }
  
  report += `## Recommendations\n\n`;
  if (failed > 0) {
    report += `- ⚠️ ${failed} test(s) failed. Check engine logs for errors.\n`;
  }
  if (avgDuration > 5000) {
    report += `- ⚠️ Average response time is slow (${avgDuration}ms). Consider enabling low_memory mode for sequential processing.\n`;
  }
  if (avgResults < 5) {
    report += `- ℹ️ Low result count. Consider expanding corpus or adjusting search strategy.\n`;
  }
  if (successful === results.length && avgDuration < 2000) {
    report += `- ✅ All tests passed with good performance!\n`;
  }
  
  return report;
}

async function main() {
  log(`\n🔍 Anchor Engine Live Search Test`, 'cyan');
  log(`=====================================\n`, 'cyan');
  log(`Engine URL: ${ENGINE_URL}`, 'blue');
  log(`Report File: ${REPORT_FILE}\n`, 'blue');
  
  // Check if engine is running
  log(`Checking engine status...`, 'yellow');
  try {
    const health = await makeRequest('/v1/health');
    if (health.status === 'ok') {
      log(`✅ Engine is running and healthy!\n`, 'green');
    } else {
      log(`⚠️  Engine responded but health check failed\n`, 'yellow');
    }
  } catch (error) {
    log(`❌ Cannot connect to engine at ${ENGINE_URL}`, 'red');
    log(`Error: ${error.message}\n`, 'red');
    log(`Make sure the engine is running: pnpm start`, 'yellow');
    process.exit(1);
  }
  
  // Run tests
  const results = [];
  for (const testCase of TEST_QUERIES) {
    log(`Testing: ${testCase.name} - "${testCase.query}"`, 'blue');
    const result = await testSearch(testCase.query);
    result.expected_behavior = testCase.expected_behavior;
    results.push(result);
    
    if (result.success) {
      log(`  ✅ ${result.results_count} results in ${result.duration_ms}ms (${result.memory_delta > 0 ? '+' : ''}${result.memory_delta}MB)`, 'green');
    } else {
      log(`  ❌ Failed: ${result.error}`, 'red');
    }
  }
  
  // Generate report
  log(`\n📊 Generating report...`, 'yellow');
  const report = generateReport(results);
  fs.writeFileSync(REPORT_FILE, report, 'utf-8');
  log(`✅ Report saved to: ${REPORT_FILE}`, 'green');
  
  // Print summary
  log(`\n📈 Test Summary:`, 'cyan');
  log(`  Total: ${results.length} | Success: ${results.filter(r => r.success).length} | Failed: ${results.filter(r => !r.success).length}`, 'blue');
  
  const avgDuration = Math.round(results.filter(r => r.success).reduce((sum, r) => sum + r.duration_ms, 0) / results.length || 0);
  log(`  Average Duration: ${avgDuration}ms`, 'blue');
  
  process.exit(results.filter(r => !r.success).length > 0 ? 1 : 0);
}

main();
