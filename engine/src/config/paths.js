const path = require('path');

// Detect if running inside pkg (compiled) or standard node
const isPkg = typeof process.pkg !== 'undefined';

let basePath;
if (isPkg) {
    // In production (pkg), process.execPath is the location of the .exe
    const exeDir = path.dirname(process.execPath);
    // If running from the 'dist' folder during testing, go up one level
    if (path.basename(exeDir).toLowerCase() === 'dist') {
        basePath = path.join(exeDir, '..', '..');
    } else {
        basePath = exeDir;
    }
} else {
    // In development, __dirname is engine/src/config, so we go up 3 levels to reach project root
    basePath = path.join(__dirname, '..', '..', '..');
}

// Allow env override for MODELS_DIR, default to parent project/models (../../models from project root)
const MODELS_DIR = process.env.MODELS_DIR || path.join(basePath, '..', 'models');

module.exports = {
    IS_PKG: isPkg,
    BASE_PATH: basePath,
    INTERFACE_DIR: path.join(basePath, 'interface'),
    CONTEXT_DIR: path.join(basePath, 'context'),
    BACKUPS_DIR: path.join(basePath, 'backups'),
    LOGS_DIR: path.join(basePath, 'logs'),
    MODELS_DIR: MODELS_DIR,
    // In production, keep the DB in the root or context folder. In dev, it's in engine/
    DB_PATH: isPkg ? path.join(basePath, 'context.db') : path.join(basePath, 'engine', 'context.db')
};
