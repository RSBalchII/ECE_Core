import { jest } from '@jest/globals';
import dns from 'node:dns';
import { isPrivateIP, safeLookup } from '../../src/utils/safe-dns.js';

describe('safe-dns', () => {
    describe('isPrivateIP', () => {
        it('should return true for private IPv4 addresses', () => {
            // Loopback
            expect(isPrivateIP('127.0.0.1')).toBe(true);
            expect(isPrivateIP('127.255.255.255')).toBe(true);

            // Private Networks
            expect(isPrivateIP('10.0.0.1')).toBe(true);
            expect(isPrivateIP('10.255.255.255')).toBe(true);
            expect(isPrivateIP('192.168.0.1')).toBe(true);
            expect(isPrivateIP('192.168.255.255')).toBe(true);
            expect(isPrivateIP('172.16.0.1')).toBe(true);
            expect(isPrivateIP('172.31.255.255')).toBe(true);

            // Link-local
            expect(isPrivateIP('169.254.0.1')).toBe(true);
            expect(isPrivateIP('169.254.255.255')).toBe(true);

            // Current network
            expect(isPrivateIP('0.0.0.0')).toBe(true);
        });

        it('should return false for public IPv4 addresses', () => {
            expect(isPrivateIP('8.8.8.8')).toBe(false);
            expect(isPrivateIP('1.1.1.1')).toBe(false);
            expect(isPrivateIP('172.15.255.255')).toBe(false); // Just outside 172.16.x.x
            expect(isPrivateIP('172.32.0.0')).toBe(false); // Just outside 172.31.x.x
            expect(isPrivateIP('192.169.0.1')).toBe(false);
            expect(isPrivateIP('11.0.0.1')).toBe(false);
        });

        it('should return false for invalid IPv4 formats', () => {
            expect(isPrivateIP('127.1')).toBe(false);
            expect(isPrivateIP('127.0.0')).toBe(false);
            expect(isPrivateIP('not.an.ip.address')).toBe(false);
            expect(isPrivateIP('')).toBe(false);
        });

        it('should return true for private IPv6 addresses', () => {
            // Loopback
            expect(isPrivateIP('::1')).toBe(true);
            expect(isPrivateIP('0:0:0:0:0:0:0:1')).toBe(true);

            // Unspecified
            expect(isPrivateIP('::')).toBe(true);
            expect(isPrivateIP('0:0:0:0:0:0:0:0')).toBe(true);

            // Unique Local Address
            expect(isPrivateIP('fc00::1')).toBe(true);
            expect(isPrivateIP('fd00::1')).toBe(true);
            expect(isPrivateIP('fdff:ffff:ffff:ffff:ffff:ffff:ffff:ffff')).toBe(true);

            // Link-local
            expect(isPrivateIP('fe80::1')).toBe(true);
            expect(isPrivateIP('fe90::1')).toBe(true);
            expect(isPrivateIP('fea0::1')).toBe(true);
            expect(isPrivateIP('feb0::1')).toBe(true);

            // IPv4-mapped IPv6
            expect(isPrivateIP('::ffff:127.0.0.1')).toBe(true);
            expect(isPrivateIP('0:0:0:0:0:ffff:10.0.0.1')).toBe(true);
        });

        it('should return false for public IPv6 addresses', () => {
            expect(isPrivateIP('2001:4860:4860::8888')).toBe(false); // Google DNS
            expect(isPrivateIP('2606:4700:4700::1111')).toBe(false); // Cloudflare DNS
            expect(isPrivateIP('::ffff:8.8.8.8')).toBe(false); // IPv4-mapped public IP
        });

        it('should return false for invalid strings that are not IPs', () => {
             expect(isPrivateIP('hello-world')).toBe(false);
        });
    });

    describe('safeLookup', () => {
        let lookupSpy: jest.SpyInstance;

        beforeEach(() => {
            // Spy on dns.lookup and mock its implementation
            lookupSpy = jest.spyOn(dns, 'lookup');
        });

        afterEach(() => {
            // Restore original implementation
            lookupSpy.mockRestore();
        });

        it('should call callback with public IP address (string)', (done) => {
            lookupSpy.mockImplementation((hostname, options, callback) => {
                // Mock callback for dns.lookup without options usually returns (err, address, family)
                if (typeof options === 'function') {
                    options(null, '8.8.8.8', 4);
                } else {
                    (callback as Function)(null, '8.8.8.8', 4);
                }
            });

            safeLookup('public.example.com', { all: false }, (err, address, family) => {
                expect(err).toBeNull();
                expect(address).toBe('8.8.8.8');
                expect(family).toBe(4);
                done();
            });
        });

        it('should return an error for private IP address (string)', (done) => {
            lookupSpy.mockImplementation((hostname, options, callback) => {
                if (typeof options === 'function') {
                    options(null, '127.0.0.1', 4);
                } else {
                    (callback as Function)(null, '127.0.0.1', 4);
                }
            });

            safeLookup('private.example.com', { all: false }, (err, address, family) => {
                expect(err).toBeInstanceOf(Error);
                expect(err?.message).toMatch(/resolved to a private IP/);
                expect((err as any)?.code).toBe('ERR_SSRF_PROTECTION');
                done();
            });
        });

        it('should call callback with public IP addresses (array)', (done) => {
            const mockAddresses = [{ address: '8.8.8.8', family: 4 }, { address: '1.1.1.1', family: 4 }];
            lookupSpy.mockImplementation((hostname, options, callback) => {
                if (typeof options === 'function') {
                    options(null, mockAddresses as any);
                } else {
                    (callback as Function)(null, mockAddresses);
                }
            });

            safeLookup('public.example.com', { all: true }, (err, address) => {
                expect(err).toBeNull();
                expect(address).toEqual(mockAddresses);
                done();
            });
        });

        it('should return an error if any IP in array is private', (done) => {
            const mockAddresses = [{ address: '8.8.8.8', family: 4 }, { address: '10.0.0.1', family: 4 }];
            lookupSpy.mockImplementation((hostname, options, callback) => {
                if (typeof options === 'function') {
                    options(null, mockAddresses as any);
                } else {
                    (callback as Function)(null, mockAddresses);
                }
            });

            safeLookup('mixed.example.com', { all: true }, (err, address) => {
                expect(err).toBeInstanceOf(Error);
                expect(err?.message).toMatch(/resolved to a private IP/);
                expect((err as any)?.code).toBe('ERR_SSRF_PROTECTION');
                done();
            });
        });

        it('should pass through DNS lookup errors', (done) => {
            const mockError = new Error('getaddrinfo ENOTFOUND invalid.example.com');
            (mockError as any).code = 'ENOTFOUND';

            lookupSpy.mockImplementation((hostname, options, callback) => {
                if (typeof options === 'function') {
                    options(mockError, undefined);
                } else {
                    (callback as Function)(mockError, undefined);
                }
            });

            safeLookup('invalid.example.com', { all: false }, (err, address) => {
                expect(err).toBe(mockError);
                expect((err as any)?.code).toBe('ENOTFOUND');
                done();
            });
        });
    });
});
