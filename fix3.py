with open("engine/tests/unit/native-module-manager.test.ts", "r") as f:
    text = f.read()

# Fix mock for require to correctly match the paths and logic
new_mock = """jest.unstable_mockModule('module', () => ({
  createRequire: jest.fn().mockImplementation(() => {
    return jest.fn().mockImplementation((path: string) => {
      if (path.includes('success') && !path.includes('fail')) {
        return { success: true, distance: () => 1 };
      }
      if (path.includes('Debug') && path.includes('fail')) {
         return { debug_success: true, distance: () => 1 };
      }
      if (path.includes('dev_success_binary')) {
         return { dev_success: true, distance: () => 1 };
      }
      throw new Error(`Cannot find module '${path}'`);
    });
  })
}));"""

import re
text = re.sub(r'jest.unstable_mockModule\(\'module\', \(\) => \(\{[\s\S]*?\}\)\);', new_mock, text)

# For test dev path, we need to fail the debug path as well
new_path_manager = """jest.unstable_mockModule('../../src/utils/path-manager.js', () => ({
  pathManager: {
    getNativePath: jest.fn().mockImplementation((binaryName: string) => {
       if (binaryName === 'success_binary') return '/path/to/Release/success';
       if (binaryName === 'debug_success_binary') return '/path/to/Release/fail';
       if (binaryName === 'dev_success_binary') return '/path/to/Release/fail_both'; // This will make Debug replace fail too since "fail_both" will replace to "fail_both" or "Debug" but our mock require handles it by throwing if not specific
       if (binaryName === 'crash_binary') return '/path/to/Release/fail';
       return '/path/to/Release/fail';
    })
  }
}));"""

text = re.sub(r'jest.unstable_mockModule\(\'\.\./\.\./src/utils/path-manager\.js\', \(\) => \(\{[\s\S]*?\}\)\);', new_path_manager, text)

with open("engine/tests/unit/native-module-manager.test.ts", "w") as f:
    f.write(text)
