/**
 * Settings API Routes (v5.2.0+) — Database-Backed Configuration
 * 
 * All settings now live in PGlite `app_settings` table with bidirectional sync
 * to user_settings.json for persistence across restarts.
 * Priority: Function params → DB → env vars → file defaults
 */

import type { Application, Request, Response } from "express";
import { getSetting, setSetting, getAllSettings } from "../../services/settings.js";
import { DEFAULT_SETTINGS } from "../../config/index.js";

export function setupSettingsRoutes(app: Application) {
  // GET /v1/settings — Get all settings (from DB with file fallback)
  app.get("/v1/settings", async (_req: Request, res: Response) => {
    try {
      const settings = await getAllSettings();
      res.status(200).json({ status: "success", settings });
    } catch (error: any) {
      res.status(500).json({ status: "error", error: `Failed to read settings: ${error.message}` });
    }
  });

  // GET /v1/settings/:key — Get a specific setting by key (dot-notation)
  app.get("/v1/settings/:key", async (req: Request, res: Response) => {
    try {
      const key = Array.isArray(req.params.key) ? req.params.key[0] : req.params.key;
      const value = await getSetting(key);
      if (value === undefined) {
        return res.status(404).json({ status: "error", error: `Setting '${key}' not found` });
      }
      res.status(200).json({ status: "success", key, value });
    } catch (error: any) {
      res.status(500).json({ status: "error", error: `Failed to read setting: ${error.message}` });
    }
  });

  // PUT /v1/settings/:key — Update a specific setting (writes to both DB and file)
  app.put("/v1/settings/:key", async (req: Request, res: Response) => {
    try {
      const key = Array.isArray(req.params.key) ? req.params.key[0] : req.params.key;
      const value = req.body.value;
      if (value === undefined) {
        return res.status(400).json({ status: "error", error: "Missing 'value' in request body" });
      }
      await setSetting(key, value);
      res.status(200).json({ status: "success", message: `Setting '${key}' updated`, key, value });
    } catch (error: any) {
      res.status(500).json({ status: "error", error: `Failed to update setting: ${error.message}` });
    }
  });

  // PUT /v1/settings — Update multiple settings at once
  app.put("/v1/settings", async (req: Request, res: Response) => {
    try {
      const updates = req.body;
      if (!updates || typeof updates !== "object") {
        return res.status(400).json({ status: "error", error: "Invalid settings format" });
      }
      for (const [key, value] of Object.entries(updates)) {
        await setSetting(key, value);
      }
      res.status(200).json({ status: "success", message: `${Object.keys(updates).length} setting(s) updated` });
    } catch (error: any) {
      res.status(500).json({ status: "error", error: `Failed to update settings: ${error.message}` });
    }
  });

  // GET /v1/settings/defaults — Get default settings template
  app.get("/v1/settings/defaults", (_req: Request, res: Response) => {
    res.status(200).json({ status: "success", settings: DEFAULT_SETTINGS });
  });

  // GET /v1/settings/paths — Get auto-discovered file paths (Standard 051)
  app.get("/v1/settings/paths", async (_req: Request, res: Response) => {
    try {
      const { PATHS } = await import("../../config/paths.js");
      const { PROJECT_ROOT } = await import("../../config/paths.js");
      res.status(200).json({ status: "success", paths: { project_root: PROJECT_ROOT, inbox: PATHS.INBOX_DIR, mirrored_brain: PATHS.MIRRORED_BRAIN_DIR, database: PATHS.DATABASE_FILE, user_settings: PATHS.USER_SETTINGS } });
    } catch (error: any) {
      res.status(500).json({ status: "error", error: `Failed to discover paths: ${error.message}` });
    }
  });
}
