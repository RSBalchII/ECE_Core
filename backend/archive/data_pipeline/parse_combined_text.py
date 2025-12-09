"""
Parse combined_text.txt to understand its structure.

combined_text.txt contains 311 embedded files delimited by:
  --- START OF FILE: <path> ---
  <content>
  --- END OF FILE: <path> ---

This script:
1. Extracts all embedded files
2. Identifies which ones contain conversations
3. Analyzes conversation turn patterns
4. Reports statistics for import planning
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter


class CombinedTextParser:
    def __init__(self, filepath: str = "combined_text.txt"):
        self.filepath = filepath
        self.files: List[Dict] = []
        
    def parse(self):
        """Extract all embedded files from combined_text.txt"""
        print(f"Parsing {self.filepath}...")
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by file markers
        pattern = r'--- START OF FILE: (.+?) ---\n(.*?)(?=--- END OF FILE:|$)'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            file_path = match.group(1).strip()
            file_content = match.group(2).strip()
            
            # Analyze file type and content
            file_info = {
                'path': file_path,
                'content': file_content,
                'lines': len(file_content.split('\n')),
                'type': self._classify_file(file_path, file_content),
                'has_conversations': self._has_conversation_turns(file_content)
            }
            
            self.files.append(file_info)
        
        print(f"✓ Found {len(self.files)} embedded files")
        return self.files
    
    def _classify_file(self, path: str, content: str) -> str:
        """Classify file type based on path and content"""
        path_lower = path.lower()
        content_sample = content[:500].lower()
        
        if path_lower.endswith('.yaml') or path_lower.endswith('.yml'):
            return 'yaml_config'
        elif path_lower.endswith('.poml'):
            return 'poml_config'
        elif path_lower.endswith('.md'):
            if 'pauline' in path_lower or 'pauline' in content_sample:
                return 'pauline_session'
            elif any(kw in content_sample for kw in ['memory', 'conversation', 'session']):
                return 'conversation_transcript'
            else:
                return 'markdown_doc'
        elif path_lower.endswith('.txt'):
            return 'text_file'
        else:
            return 'unknown'
    
    def _has_conversation_turns(self, content: str) -> bool:
        """Check if content contains conversation turns"""
        # Look for common conversation patterns
        patterns = [
            r'^(User|Coda|You|Assistant|Human|AI):\s',
            r'^\*\*(User|Coda|You|Assistant)\*\*:',
            r'^###\s+(User|Coda|Assistant)',
        ]
        
        lines = content.split('\n')
        turn_count = 0
        
        for line in lines[:100]:  # Check first 100 lines
            for pattern in patterns:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    turn_count += 1
                    break
        
        return turn_count >= 3  # At least 3 turns to be a conversation
    
    def analyze(self):
        """Analyze parsed files and report statistics"""
        if not self.files:
            print("No files parsed yet. Run parse() first.")
            return
        
        print("\n" + "="*60)
        print("COMBINED_TEXT.TXT ANALYSIS")
        print("="*60)
        
        # Overall stats
        total_lines = sum(f['lines'] for f in self.files)
        print(f"\nTotal embedded files: {len(self.files)}")
        print(f"Total lines: {total_lines:,}")
        
        # File type breakdown
        type_counts = Counter(f['type'] for f in self.files)
        print(f"\nFile types:")
        for ftype, count in type_counts.most_common():
            total_type_lines = sum(f['lines'] for f in self.files if f['type'] == ftype)
            print(f"  {ftype:25} {count:4} files  {total_type_lines:8,} lines")
        
        # Conversation files
        conv_files = [f for f in self.files if f['has_conversations']]
        print(f"\nFiles with conversations: {len(conv_files)}")
        
        if conv_files:
            conv_lines = sum(f['lines'] for f in conv_files)
            print(f"  Total conversation lines: {conv_lines:,}")
            print(f"\nSample conversation files:")
            for f in conv_files[:10]:
                print(f"  {f['path']:60} {f['lines']:6} lines")
        
        # Largest files
        print(f"\nLargest files:")
        sorted_files = sorted(self.files, key=lambda x: x['lines'], reverse=True)
        for f in sorted_files[:10]:
            print(f"  {f['path']:60} {f['lines']:6} lines  [{f['type']}]")
        
        print("\n" + "="*60)
        
        return {
            'total_files': len(self.files),
            'total_lines': total_lines,
            'type_counts': type_counts,
            'conversation_files': len(conv_files),
            'files': self.files
        }
    
    def extract_sample_conversations(self, output_dir: str = "samples", limit: int = 5):
        """Extract first N conversation files for testing"""
        conv_files = [f for f in self.files if f['has_conversations']]
        
        if not conv_files:
            print("No conversation files found.")
            return
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        print(f"\nExtracting {min(limit, len(conv_files))} sample conversation files to {output_dir}/")
        
        for i, file_info in enumerate(conv_files[:limit]):
            # Create safe filename
            safe_name = f"sample_{i+1}_{Path(file_info['path']).name}"
            output_file = output_path / safe_name
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# SOURCE: {file_info['path']}\n")
                f.write(f"# LINES: {file_info['lines']}\n")
                f.write(f"# TYPE: {file_info['type']}\n\n")
                f.write(file_info['content'])
            
            print(f"  ✓ {safe_name}")


def main():
    parser = CombinedTextParser()
    parser.parse()
    stats = parser.analyze()
    
    # Extract samples for inspection
    print("\n" + "="*60)
    response = input("\nExtract sample conversation files for inspection? (y/n): ")
    if response.lower() == 'y':
        parser.extract_sample_conversations(limit=10)
        print("\nCheck the 'samples/' directory to inspect conversation formats.")
    
    print("\nNext steps:")
    print("1. Inspect sample files to understand conversation turn formats")
    print("2. Design turn parser for different formats (User:/Coda:, **User**:, etc.)")
    print("3. Update import_combined_context.py to handle all formats")


if __name__ == "__main__":
    main()
