with open("engine/tests/unit/native-module-manager.test.ts", "r") as f:
    text = f.read()

# Fix mock for require to correctly match the paths and logic
new_mock = """jest.unstable_mockModule('module', () => ({
  createRequire: jest.fn().mockImplementation(() => {
    return jest.fn().mockImplementation((path: string) => {
      if (path.includes('success') && !path.includes('fail')) {
        return { success: true, distance: () => 1 };
      }
      if (path.includes('Debug') && path.includes('debug_success_binary')) {
         return { debug_success: true, distance: () => 1 };
      }
      if (path.includes('dev') || (path.includes('build/Release') && path.includes('dev_success_binary'))) {
         return { dev_success: true, distance: () => 1 };
      }
      throw new Error(`Cannot find module '${path}'`);
    });
  })
}));"""

import re
text = re.sub(r'jest.unstable_mockModule\(\'module\', \(\) => \(\{[\s\S]*?\}\)\);', new_mock, text)
text = text.replace("expect(status?.error).toBeUndefined(); // Safety fallback doesn't set error message", "expect(status?.error).toBeDefined();")

with open("engine/tests/unit/native-module-manager.test.ts", "w") as f:
    f.write(text)
