#!/usr/bin/env node
/**
 * Test Orchestrator — end-to-end integration test suite for Anchor Engine
 *
 * Orchestrates the complete test lifecycle:
 *   Phase 1: Pathfinder — audit hardcoded paths in codebase
 *   Phase 2: Start engine → wait for healthy
 *   Phase 3: Ingest test corpus into inbox → verify inbox drain
 *   Phase 4: Watchdog processing → verify atoms ingested + metrics
 *   Phase 5: Search tests → query known content
 *   Phase 6: Distillation tests → verify compression metrics
 *
 * Usage:
 *   node tests/test-orchestrator.js [phase]
 *   node tests/test-orchestrator.js --all          (run all phases)
 *   node tests/test-orchestrator.js --pathfinder    (only path audit)
 *   node tests/test-orchestrator.js --start         (only start engine)
 *   node tests/test-orchestrator.js --ingest        (only ingest phase)
 *   node tests/test-orchestrator.js --watchdog      (only watchdog phase)
 *   node tests/test-orchestrator.js --search        (only search phase)
 *   node tests/test-orchestrator.js --distill       (only distillation phase)
 */

import { spawn, execFile } from "child_process";
import path from "path";
import fs from "fs";
import { homedir } from "os";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

// === Configuration ===
const ENGINE_PORT = 3160;
const ENGINE_URL = `http://localhost:${ENGINE_PORT}`;
// FIX (2026-08-21): ANCHOR_DIR must resolve to ~/.anchor (Standard 110). The previous value
// (`<engine>/.anchor`) made the orchestrator create a .anchor tree inside the repo, and it
// passed that path to the spawned engine via env.ANCHOR_ROOT. Now uses homedir; the deprecated
// `local-data` layer is removed (data dirs live directly under ~/.anchor/).
const ANCHOR_DIR = process.env.ANCHOR_ROOT || path.join(homedir(), ".anchor");
const INBOX_DIR = path.join(ANCHOR_DIR, "inbox");
const EXT_INBOX_DIR = path.join(ANCHOR_DIR, "external-inbox");
const DISTILLS_DIR = path.join(ANCHOR_DIR, "distills");
const MIRROR_DIR = path.join(ANCHOR_DIR, "mirrored_brain");
const LOGS_DIR = path.join(ANCHOR_DIR, "logs", "orchestrator");

// Timing
const HEALTH_CHECK_INTERVAL = 1000; // ms
const HEALTH_CHECK_TIMEOUT = 60000; // ms
const INGEST_POLL_INTERVAL = 2000; // ms
const INGEST_TIMEOUT = 300000; // 5 minutes

// === Logging ===

function logPhase(phase, message) {
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] [PHASE: ${phase}] ${message}`;
  console.log(logLine);
  writeLog(phase, message);
}

function logSuccess(phase, message) {
  logPhase(phase, `✅ ${message}`);
}

function logError(phase, message) {
  logPhase(phase, `❌ ${message}`);
}

function writeLog(phase, message) {
  try {
    if (!fs.existsSync(LOGS_DIR)) {
      fs.mkdirSync(LOGS_DIR, { recursive: true });
    }
    const logFile = path.join(LOGS_DIR, `orchestrator.log`);
    fs.appendFileSync(logFile, message + "\n");
  } catch (err) {
    console.error("Failed to write log:", err.message);
  }
}

// === Phase 1: Pathfinder Test ===

/**
 * Audit hardcoded paths in the codebase
 * Searches through all .ts and .js files and checks if any path references
 * could be replaced with imports from the PATHS module.
 */
function runPathfinderTest() {
  logPhase("PATHFINDER", "Starting path audit...");
  const results = [];
  const knownDirs = [
    "inbox/",
    "inbox\\",
    "external-inbox/",
    "external-inbox\\",
    "mirrored_brain/",
    "mirrored_brain\\",
    "distills/",
    "distills\\",
    "sessions/",
    "sessions\\",
    "logs/",
    "logs\\",
    "backups/",
    "backups\\",
  ];

  function scanDirectory(dir, relativePath = "") {
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const currentRelPath = path.join(relativePath, entry.name);

      // Skip directories we don't need to scan
      if (
        ["node_modules", "dist", "coverage", ".git", "dist-test"].includes(
          entry.name,
        )
      ) {
        continue;
      }

      if (entry.isDirectory()) {
        scanDirectory(fullPath, currentRelPath);
        continue;
      }

      // Only scan .ts and .js files
      if (!entry.name.endsWith(".ts") && !entry.name.endsWith(".js")) {
        continue;
      }

      try {
        const content = fs.readFileSync(fullPath, "utf-8");
        const lines = content.split("\n");

        for (let lineNum = 0; lineNum < lines.length; lineNum++) {
          const line = lines[lineNum];
          const lineNumber = lineNum + 1;

          for (const dirPattern of knownDirs) {
            if (line.includes(dirPattern) && !line.includes("paths.ts")) {
              // Check if it's a comment or string literal
              if (line.includes('"') || line.includes("'")) {
                results.push({
                  file: currentRelPath,
                  line: lineNumber,
                  pattern: dirPattern,
                  code: line.trim(),
                  description: `Hardcoded path reference: ${dirPattern}`,
                });
              }
            }
          }

          // Check for hardcoded .anchor references
          if (line.includes(".anchor") && !line.includes("paths.ts")) {
            results.push({
              file: currentRelPath,
              line: lineNumber,
              pattern: ".anchor",
              code: line.trim(),
              description: "Hardcoded .anchor reference",
            });
          }
        }
      } catch (err) {
        console.error(`Failed to read ${fullPath}:`, err.message);
      }
    }
  }

  logPhase("PATHFINDER", "Scanning engine/src/ directory...");
  const engineSrcDir = path.join(ROOT, "engine", "src");
  if (fs.existsSync(engineSrcDir)) {
    scanDirectory(engineSrcDir, "engine/src");
  }

  logPhase(
    "PATHFINDER",
    `Path audit complete. Found ${results.length} potential issues.`,
  );

  // Display results
  if (results.length > 0) {
    logError(
      "PATHFINDER",
      `Found ${results.length} hardcoded path references:`,
    );
    for (const result of results) {
      logError(
        "PATHFINDER",
        `  • ${result.file}:${result.line} - ${result.pattern} (${result.description})\n` +
          `    Code: ${result.code}`,
      );
    }
  } else {
    logSuccess("PATHFINDER", "All paths properly referenced via PATHS module");
  }

  return results;
}

// === Phase 2: Start Engine ===

let engineProcess = null;

async function setupAPIKey() {
  logPhase("START", "Checking for API key configuration...");

  // Settings are stored in ~/.anchor/user_settings.json (user's home directory)
  // This is the single source of truth, matching the engine's config loader
  const { homedir } = await import("os");
  const settingsPath = path.join(homedir(), ".anchor", "user_settings.json");

  try {
    // Check if the settings file already exists with a valid API key
    if (fs.existsSync(settingsPath)) {
      try {
        const settings = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
        if (
          settings.server &&
          settings.server.api_key &&
          settings.server.api_key !== "anchor-engine-default-key"
        ) {
          logSuccess(
            "START",
            `API key configured at ${settingsPath} (${settings.server.api_key.substring(0, 8)}...)`,
          );
          return true;
        }
      } catch (err) {
        console.error("Failed to read settings:", err.message);
      }
    }

    // Create settings with API key at ~/.anchor/user_settings.json
    const settings = { server: { api_key: "anchor-test-key-" + Date.now() } };

    const anchorDir = path.dirname(settingsPath);
    if (!fs.existsSync(anchorDir)) {
      fs.mkdirSync(anchorDir, { recursive: true });
    }
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    logSuccess(
      "START",
      `API key created at ${settingsPath} (single source of truth)`,
    );

    return true;
  } catch (err) {
    logError("START", `Failed to setup API key: ${err.message}`);
    return false;
  }
}

async function startEngine() {
  logPhase("START", "Starting Anchor Engine...");

  const enginePath = path.join(ROOT, "engine", "dist", "index.js");
  if (!fs.existsSync(enginePath)) {
    logError(
      "START",
      `Engine not built at ${enginePath}. Run 'pnpm build' first.`,
    );
    return false;
  }

  // Ensure API key exists
  if (!(await setupAPIKey())) {
    logError("START", "API key setup failed");
    return false;
  }

  engineProcess = spawn("node", [enginePath], {
    cwd: ROOT,
    env: { ...process.env, ANCHOR_ROOT: ANCHOR_DIR },
    stdio: ["pipe", "pipe", "pipe"],
  });

  engineProcess.stdout.on("data", (data) => {
    const output = data.toString();
    console.log("[ENGINE] " + output);
    logPhase("START", "ENGINE: " + output);
  });

  engineProcess.stderr.on("data", (data) => {
    const error = data.toString();
    console.error("[ENGINE ERROR] " + error);
    logPhase("START", "ENGINE ERROR: " + error);
  });

  engineProcess.on("error", (err) => {
    logError("START", `Failed to start engine: ${err.message}`);
  });

  // Wait for engine to be ready
  try {
    await waitForHealthCheck();
    logSuccess("START", "Engine is healthy and ready");
    return true;
  } catch (err) {
    logError("START", `Engine health check failed: ${err.message}`);
    return false;
  }
}

function waitForHealthCheck() {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    const interval = setInterval(async () => {
      if (Date.now() - startTime > HEALTH_CHECK_TIMEOUT) {
        clearInterval(interval);
        reject(new Error("Health check timeout"));
        return;
      }

      try {
        const response = await fetch(`${ENGINE_URL}/health`);
        if (response.ok) {
          const health = await response.json();
          if (health.status === "healthy") {
            clearInterval(interval);
            resolve();
          }
        }
      } catch (err) {
        // Engine not ready yet, continue polling
      }
    }, HEALTH_CHECK_INTERVAL);
  });
}

// === Phase 3: Ingest Test Corpus ===

function ingestTestCorpus() {
  logPhase("INGEST", `Starting ingestion of ${TEST_CORPUS} into ${INBOX_DIR}`);
  const ingestStartTime = Date.now();

  // Copy repo files into inbox
  const filesToIngest = [];

  function copyDirectory(src, dest, relPath = "") {
    const entries = fs.readdirSync(src, { withFileTypes: true });

    for (const entry of entries) {
      const srcPath = path.join(src, entry.name);
      const destPath = path.join(dest, entry.name);
      const relEntryPath = path.join(relPath, entry.name);

      // Skip directories we don't need
      if (
        ["node_modules", "dist", "coverage", ".git", ".anchor"].includes(
          entry.name,
        )
      ) {
        continue;
      }

      if (entry.isDirectory()) {
        // Don't recurse into nested .anchor or node_modules
        if ([".anchor", "node_modules"].includes(entry.name)) {
          continue;
        }
        copyDirectory(srcPath, path.join(dest, entry.name), relEntryPath);
        continue;
      }

      // Only copy source files (code, config, docs)
      const ext = path.extname(entry.name);
      if (
        [
          ".ts",
          ".js",
          ".json",
          ".md",
          ".yaml",
          ".yml",
          ".html",
          ".txt",
          ".css",
        ].includes(ext)
      ) {
        try {
          if (!fs.existsSync(dest)) {
            fs.mkdirSync(dest, { recursive: true });
          }
          fs.copyFileSync(srcPath, destPath);
          filesToIngest.push(relEntryPath);
        } catch (err) {
          console.error(`Failed to copy ${srcPath}:`, err.message);
        }
      }
    }
  }

  copyDirectory(TEST_CORPUS, INBOX_DIR, "");

  const ingestDuration = Date.now() - ingestStartTime;
  logSuccess(
    "INGEST",
    `Copied ${filesToIngest.length} files to inbox (${ingestDuration}ms)`,
  );
  return { fileCount: filesToIngest.length, duration: ingestDuration };
}

// === Phase 4: Watchdog Processing ===

async function waitForWatchdogProcessing() {
  logPhase("WATCHDOG", "Waiting for watchdog to finish processing...");
  const processingStartTime = Date.now();

  // Poll until inbox is empty or timeout
  while (Date.now() - processingStartTime < INGEST_TIMEOUT) {
    try {
      // Check inbox files
      const inboxEntries = fs.readdirSync(INBOX_DIR);
      if (inboxEntries.length === 0) {
        logSuccess("WATCHDOG", "Inbox is empty — processing complete");
        break;
      }

      // Check mirrored brain
      if (fs.existsSync(MIRROR_DIR)) {
        const mirrorEntries = fs.readdirSync(MIRROR_DIR, { recursive: true });
        logPhase(
          "WATCHDOG",
          `Mirrored brain has ${mirrorEntries.length} entries`,
        );
      }

      await new Promise((resolve) => setTimeout(resolve, INGEST_POLL_INTERVAL));
    } catch (err) {
      console.error("Error checking inbox:", err.message);
      await new Promise((resolve) => setTimeout(resolve, INGEST_POLL_INTERVAL));
    }
  }

  const totalDuration = Date.now() - processingStartTime;
  logPhase("WATCHDOG", `Processing completed in ${totalDuration}ms`);
  return { duration: totalDuration };
}

// === Phase 5: Search Tests ===

async function runSearchTests() {
  logPhase("SEARCH", "Starting search tests...");
  const searchStartTime = Date.now();

  // Test search queries based on known content in the repo
  const testQueries = [
    "distillation pipeline",
    "watchdog service",
    "inbox processing",
    "atomizer",
  ];

  const results = {
    queries: [],
    totalDuration: 0,
    successCount: 0,
    failureCount: 0,
  };

  for (const query of testQueries) {
    const queryStart = Date.now();
    try {
      const response = await fetch(`${ENGINE_URL}/v1/memory/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer anchor-engine-default-key",
        },
        body: JSON.stringify({
          query,
          max_chars: 1000,
          strategy: "standard",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const queryDuration = Date.now() - queryStart;
        results.totalDuration += queryDuration;

        if (data.results && data.results.length > 0) {
          logSuccess(
            "SEARCH",
            `Query "${query}" returned ${data.results.length} results (${queryDuration}ms)`,
          );
          results.queries.push({
            query,
            status: "success",
            results: data.results.length,
            duration: queryDuration,
          });
          results.successCount++;
        } else {
          logPhase(
            "SEARCH",
            `Query "${query}" returned 0 results (${queryDuration}ms)`,
          );
          results.queries.push({
            query,
            status: "no_results",
            duration: queryDuration,
          });
        }
      } else {
        const queryDuration = Date.now() - queryStart;
        const errorData = await response.json();
        logError(
          "SEARCH",
          `Query "${query}" failed: ${errorData.error} (${queryDuration}ms)`,
        );
        results.queries.push({
          query,
          status: "error",
          error: errorData.error,
          duration: queryDuration,
        });
        results.failureCount++;
      }
    } catch (err) {
      const queryDuration = Date.now() - queryStart;
      logError(
        "SEARCH",
        `Query "${query}" exception: ${err.message} (${queryDuration}ms)`,
      );
      results.queries.push({
        query,
        status: "exception",
        error: err.message,
        duration: queryDuration,
      });
      results.failureCount++;
    }
  }

  const totalDuration = Date.now() - searchStartTime;
  results.totalDuration = totalDuration;
  logPhase(
    "SEARCH",
    `Search tests complete in ${totalDuration}ms — ${results.successCount} success, ${results.failureCount} failure`,
  );
  return results;
}

// === Phase 6: Distillation Tests ===

async function runDistillationTests() {
  logPhase("DISTILLATION", "Starting distillation tests...");
  const distillStartTime = Date.now();

  const testDistill = async () => {
    try {
      const response = await fetch(`${ENGINE_URL}/v1/memory/distill`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer anchor-engine-default-key",
        },
        body: JSON.stringify({
          output_format: "json",
          output_path: path.join(
            DISTILLS_DIR,
            `test-distill-${Date.now()}.json`,
          ),
        }),
      });

      if (response.ok) {
        const result = await response.json();
        const duration = Date.now() - distillStartTime;

        logSuccess("DISTILLATION", `Distillation complete in ${duration}ms`);
        logSuccess(
          "DISTILLATION",
          `Stats: ${JSON.stringify(result.stats, null, 2)}`,
        );

        // Validate metrics
        if (result.stats && result.stats.compression_ratio) {
          logPhase(
            "DISTILLATION",
            `Compression ratio: ${result.stats.compression_ratio}:1`,
          );

          // Check if compression ratio is reasonable (should be > 1:1)
          const ratio = parseFloat(result.stats.compression_ratio);
          if (ratio >= 1) {
            logSuccess("DISTILLATION", "Compression ratio is valid");
          } else {
            logError("DISTILLATION", `Compression ratio ${ratio}:1 is invalid`);
          }

          // Validate output file exists
          if (result.output && result.output.path) {
            if (fs.existsSync(result.output.path)) {
              const stats = fs.statSync(result.output.path);
              logSuccess(
                "DISTILLATION",
                `Output file exists (${stats.size} bytes)`,
              );
            } else {
              logError(
                "DISTILLATION",
                `Output file not found: ${result.output.path}`,
              );
            }
          }
        }

        return result;
      } else {
        const errorData = await response.json();
        logError("DISTILLATION", `Distillation failed: ${errorData.error}`);
        return { error: errorData.error };
      }
    } catch (err) {
      logError("DISTILLATION", `Distillation exception: ${err.message}`);
      return { error: err.message };
    }
  };

  const result = await testDistill();
  const totalDuration = Date.now() - distillStartTime;
  return { ...result, totalDuration };
}

// === Main Orchestrator ===

async function runOrchestrator(phase) {
  const phases = [
    "pathfinder",
    "start",
    "ingest",
    "watchdog",
    "search",
    "distillation",
  ];
  const phaseIndex = phases.indexOf(phase);
  const activePhases = phases.slice(0, phaseIndex + 1);

  console.log("\n" + "=".repeat(80));
  console.log(`Running Phase: ${phase.toUpperCase()}`);
  console.log("=".repeat(80) + "\n");

  const phaseStartTime = Date.now();
  const overallResults = { phases: {} };

  try {
    // Phase 1: Pathfinder
    if (activePhases.includes("pathfinder")) {
      const pathResults = runPathfinderTest();
      overallResults.phases.pathfinder = {
        results: pathResults,
        status: "complete",
      };
    }

    // Phase 2: Start Engine
    if (activePhases.includes("start")) {
      if (await startEngine()) {
        overallResults.phases.start = { status: "complete" };
      } else {
        overallResults.phases.start = { status: "failed" };
      }
    }

    // Phase 3: Ingest
    if (activePhases.includes("ingest")) {
      const ingestResults = ingestTestCorpus();
      overallResults.phases.ingest = { ...ingestResults, status: "complete" };
    }

    // Phase 4: Watchdog
    if (activePhases.includes("watchdog")) {
      const watchdogResults = await waitForWatchdogProcessing();
      overallResults.phases.watchdog = {
        ...watchdogResults,
        status: "complete",
      };
    }

    // Phase 5: Search
    if (activePhases.includes("search")) {
      const searchResults = await runSearchTests();
      overallResults.phases.search = searchResults;
    }

    // Phase 6: Distillation
    if (activePhases.includes("distillation")) {
      const distillResults = await runDistillationTests();
      overallResults.phases.distillation = distillResults;
    }

    const phaseDuration = Date.now() - phaseStartTime;
    overallResults.duration = phaseDuration;
    overallResults.status = "complete";

    logSuccess("ORCHESTRATOR", `All phases complete in ${phaseDuration}ms`);
  } catch (err) {
    logError("ORCHESTRATOR", `Orchestrator failed: ${err.message}`);
    overallResults.status = "failed";
    overallResults.error = err.message;
  } finally {
    // Cleanup
    if (engineProcess) {
      logPhase("ORCHESTRATOR", "Shutting down engine...");
      engineProcess.kill("SIGTERM");
      await new Promise((resolve) => setTimeout(resolve, 2000));
      logPhase("ORCHESTRATOR", "Engine stopped");
    }
  }

  // Write summary log
  const summaryLog = path.join(LOGS_DIR, "orchestrator-summary.json");
  fs.writeFileSync(summaryLog, JSON.stringify(overallResults, null, 2));
  logPhase("ORCHESTRATOR", `Summary written to ${summaryLog}`);

  return overallResults;
}

// === CLI Entry Point ===

const AVAILABLE_PHASES = [
  "pathfinder",
  "start",
  "ingest",
  "watchdog",
  "search",
  "distillation",
];

const args = process.argv.slice(2);
const targetPhase = args[0] || "all";

if (targetPhase === "all") {
  console.log("Running full test orchestrator...");
  runOrchestrator("distillation").then((overallResults) => {
    console.log("\n=== Full Test Suite Results ===");
    console.log(JSON.stringify(overallResults, null, 2));
    process.exit(overallResults.status === "complete" ? 0 : 1);
  });
} else if (AVAILABLE_PHASES.includes(targetPhase)) {
  runOrchestrator(targetPhase).then((overallResults) => {
    console.log("\n=== Phase Results ===");
    console.log(JSON.stringify(overallResults, null, 2));
    process.exit(overallResults.status === "complete" ? 0 : 1);
  });
} else {
  console.error(
    `Unknown phase: ${targetPhase}. Available: ${AVAILABLE_PHASES.join(", ")}`,
  );
  process.exit(1);
}
