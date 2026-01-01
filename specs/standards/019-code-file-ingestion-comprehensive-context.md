# Standard 019: Code File Ingestion for Comprehensive Context

## What Happened?
The Watchdog service was only monitoring text files (.txt, .md, .markdown) but ignoring code files which represent a significant portion of developer context. This created an "Ingestion Blind Spot" where the system was blind to codebase context.

## The Cost
- Limited context ingestion for developers
- Missing important code-related information
- 30 minutes spent updating watchdog.py to include code extensions

## The Rule
1. **Expand File Extensions**: Include common programming language extensions in file monitoring:
   ```python
   enabled_extensions = {".txt", ".md", ".markdown", ".py", ".js", ".html", ".css", 
                         ".json", ".yaml", ".yml", ".sh", ".bat", ".ts", ".tsx", 
                         ".jsx", ".xml", ".sql", ".rs", ".go", ".cpp", ".c", ".h", ".hpp"}
   ```

2. **Comprehensive Coverage**: Monitor all relevant text-based file types that contain context

3. **Maintain Performance**: Ensure file size limits still apply to prevent performance issues with large code files

This standard ensures that developer context is fully captured by including code files in passive ingestion.