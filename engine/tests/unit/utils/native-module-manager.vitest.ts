import { describe, it, expect } from 'vitest';
import { NativeModuleManager, nativeModuleManager } from '../../../src/utils/native-module-manager.js';

describe('NativeModuleManager', () => {
  it('should be a singleton', () => {
    const instance1 = NativeModuleManager.getInstance();
    const instance2 = NativeModuleManager.getInstance();
    expect(instance1).toBe(instance2);
    expect(instance1).toBe(nativeModuleManager);
  });

  it('should return empty status initially or a map', () => {
    const statusMap = nativeModuleManager.getAllStatus();
    expect(statusMap).toBeInstanceOf(Map);
  });

  it('should return undefined for unknown module status', () => {
    const status = nativeModuleManager.getStatus('unknown_module');
    expect(status).toBeUndefined();
  });

  it('should return false for isUsingFallback on unknown module', () => {
    const isFallback = nativeModuleManager.isUsingFallback('unknown_module');
    expect(isFallback).toBe(false);
  });

  it('should load fallback for ece_native and update status', () => {
    // ece_native is hardcoded to use fallback in the current implementation
    const module = nativeModuleManager.loadNativeModule('ece_native', 'ece_core.node');

    expect(module).toBeDefined();
    expect(typeof module.cleanse).toBe('function');

    const status = nativeModuleManager.getStatus('ece_native');
    expect(status).toBeDefined();
    expect(status?.loaded).toBe(true);
    expect(status?.fallbackActive).toBe(true);
    expect(status?.moduleName).toBe('ece_native');

    const allStatus = nativeModuleManager.getAllStatus();
    expect(allStatus.has('ece_native')).toBe(true);
    expect(allStatus.get('ece_native')).toEqual(status);
  });

  it('should return cached module on subsequent loads', () => {
    const module1 = nativeModuleManager.loadNativeModule('ece_native', 'ece_core.node');
    const module2 = nativeModuleManager.loadNativeModule('ece_native', 'ece_core.node');

    expect(module1).toBe(module2);
  });
});
