// setup-user-config.mjs - Cross-platform user configuration setup script
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  readdirSync,
  unlinkSync,
} from "fs";
import { randomBytes } from "crypto";
import { fileURLToPath } from "url";
import { dirname, join, sep } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = __dirname;

console.log("🔧 Anchor Engine User Config Setup");
console.log("=".repeat(50));

// 1. Detect user home directory (Cross-platform)
let USER_HOME = process.env.USERPROFILE || process.env.HOME || "/tmp"; // Windows, Linux/macOS fallback

// Platform-specific detection
if (process.platform === "win32") {
  USER_HOME = process.env.USERPROFILE || join(process.cwd(), "..");
} else if (process.platform === "darwin" || process.platform === "linux") {
  USER_HOME = process.env.HOME;
}

console.log(`📍 Detected User Home: ${USER_HOME}`);
const ANCHOR_ROOT = join(USER_HOME, ".anchor");

// 2. Create .anchor directory if needed (check for existing)
if (!existsSync(ANCHOR_ROOT)) {
  console.log(`✨ Creating root directory: ${ANCHOR_ROOT}`);
  mkdirSync(ANCHOR_ROOT, { recursive: true });
} else {
  // Check if it's already a valid .anchor or something else
  const existingItems = readdirSync(ANCHOR_ROOT);
  if (existingItems.length === 0) {
    console.log(`📁 Empty .anchor found at ${ANCHOR_ROOT}, cleaning...`);
    mkdirSync(ANCHOR_ROOT, { recursive: true });
  } else if (!existingItems.some((f) => f.startsWith("user_settings"))) {
    console.log(
      `⚠️  Existing .anchor without user_settings.json found. Overwriting...`,
    );
    // Clear existing content to avoid conflicts
    readdirSync(ANCHOR_ROOT).forEach((file) => {
      const filePath = join(ANCHOR_ROOT, file);
      if (existsSync(filePath)) {
        try {
          unlinkSync(filePath);
        } catch {}
      }
    });
  }
}

// 3. Read template and expand variables
let configText = readFileSync(
  join(PROJECT_ROOT, "user_settings.json.template"),
  "utf-8",
);

console.log(`📄 Reading template: user_settings.json.template`);

// Replace <ANCHOR_ROOT> placeholder (literal syntax in JSON)
configText = configText.replace(/<ANCHOR_ROOT>/g, ANCHOR_ROOT);

// Extract anchor_root variable value for ${...} replacements
const ANCHOR_VAR = `"anchor_root": "${ANCHOR_ROOT}"`;

console.log(`🔄 Expanding variables...`);
configText = configText.replace(/\$\{([^}]+)\}/g, (_, key) => {
  if (key === "anchor_root") return ANCHOR_ROOT;
  return ""; // Handle other vars if needed
});

// 4. Ensure version is updated from template
const VERSION_FROM_TEMPLATE = configText.match(/"VERSION":\s*"([^"]+)"/)?.[1];
if (VERSION_FROM_TEMPLATE) {
  // Replace the version in the server and ui sections with the correct one
  configText = configText.replace(
    /"version":\s*"[^"]+"/g,
    `"version": "${VERSION_FROM_TEMPLATE}"`,
  );
}

// Generate API key (64-char hex string) or use existing one from settings
let apiKey = "";
const USER_SETTINGS_PATH = join(ANCHOR_ROOT, "user_settings.json");
if (existsSync(USER_SETTINGS_PATH)) {
  try {
    const existingConfig = JSON.parse(
      readFileSync(USER_SETTINGS_PATH, "utf-8"),
    );
    if (existingConfig.server?.api_key) {
      apiKey = existingConfig.server.api_key;
    }
  } catch {}
}

if (!apiKey || apiKey.length < 64) {
  // Generate a new 64-char hex key (32 bytes)
  apiKey = randomBytes(32).toString("hex");
}

// Replace existing api_key with our generated hex key
// Matches: "anchor-engine-default-key" OR empty string ""
configText = configText.replace(
  /"api_key":\s*"(anchor-engine-default-key|")/g,
  `"api_key": "${apiKey}"`,
);

console.log(
  `🔑 Using API key: ${apiKey.substring(0, 16)}... (${apiKey.length} chars hex)`,
);

// Convert all backslash paths to forward slashes for valid JSON on Windows
configText = configText.replace(/\\/g, "/");

// Write user_settings.json to .anchor directory
writeFileSync(USER_SETTINGS_PATH, configText.trim(), { encoding: "utf-8" });
console.log(`✅ Created ${USER_SETTINGS_PATH}`);

// 6. Create required subdirectories structure
const SUBDIRS = [
  "notebook",
  "inbox",
  "external-inbox",
  "distills",
  "mirrored_brain",
  "sessions",
  "logs",
  "context_data",
  "test-dbs",
];

console.log(
  `📁 Creating directory structure: ${SUBDIRS.length} directories...`,
);

SUBDIRS.forEach((dir) => {
  const fullPath = join(ANCHOR_ROOT, dir);
  if (!existsSync(fullPath)) {
    mkdirSync(fullPath, { recursive: true });
    console.log(`  ✓ ${dir}/`);
  } else {
    // Check if directory is empty or needs cleaning
    if (readdirSync(fullPath).length === 0) {
      console.log(`  → ${dir}/ (existing but empty)`);
    } else {
      console.log(`  ✗ ${dir}/ (exists with content, skipping)`);
    }
  }
});

// 7. Print summary
console.log("=".repeat(50));
console.log("✅ Configuration setup complete!");
console.log(`   Anchor Root: ${ANCHOR_ROOT}`);
console.log(`   User Settings: ${USER_SETTINGS_PATH}`);
if (apiKey.length >= 32) {
  console.log(`🔑 Valid hex API key: ${apiKey.substring(0, 16)}...`);
} else {
  console.warn(`⚠️  Short API key (${apiKey.length}/32). No auth required.`);
}
console.log(
  "   Next Step: Run 'pnpm start' or 'pnpm dev' to initialize the engine.",
);

// 9. Verify configuration by reading back what was written
// Verify the api_key was properly set
const verifiedConfig = readFileSync(USER_SETTINGS_PATH, "utf-8");
let jsonValid = false;
try {
  JSON.parse(verifiedConfig);
  jsonValid = true;
} catch {}
console.log(`   ✓ JSON valid: ${jsonValid ? "✅" : "❌"}`);
if (jsonValid) {
  const parsed = JSON.parse(verifiedConfig);
  const keyLen = (parsed.server?.api_key || "").length;
  console.log(
    `   ✓ API key length: ${keyLen} chars ${keyLen >= 32 ? "✅" : "(too short, no auth required)"}`,
  );
}
