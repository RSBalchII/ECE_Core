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
      if (path.includes('build/Release') && path.includes('dev_success_binary')) {
         return { dev_success: true, distance: () => 1 };
      }
      throw new Error(`Cannot find module '${path}'`);
    });
  })
}));"""

import re
text = re.sub(r'jest.unstable_mockModule\(\'module\', \(\) => \(\{[\s\S]*?\}\)\);', new_mock, text)

new_path_manager = """jest.unstable_mockModule('../../src/utils/path-manager.js', () => ({
  pathManager: {
    getNativePath: jest.fn().mockImplementation((binaryName: string) => {
       if (binaryName === 'success_binary') return '/path/to/Release/success';
       if (binaryName === 'debug_success_binary') return '/path/to/Release/debug_success_binary';
       if (binaryName === 'dev_success_binary') return '/path/to/Release/dev_success_binary'; // will fail debug due to 'Debug' mock require check and succeed dev due to 'build/Release' match
       if (binaryName === 'crash_binary') return '/path/to/Release/crash_binary';
       return '/path/to/Release/fail';
    })
  }
}));"""

text = re.sub(r'jest.unstable_mockModule\(\'\.\./\.\./src/utils/path-manager\.js\', \(\) => \(\{[\s\S]*?\}\)\);', new_path_manager, text)

with open("engine/tests/unit/native-module-manager.test.ts", "w") as f:
    f.write(text)
