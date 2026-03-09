import dns from 'node:dns';

/**
 * Checks if an IP address is private or reserved.
 * Handles IPv4 and IPv6.
 *
 * @param ip - The IP address string
 * @returns true if the IP is private or reserved, false otherwise.
 */
export function isPrivateIP(ip: string): boolean {
    // IPv6 with embedded IPv4 (e.g., ::ffff:127.0.0.1)
    if (ip.includes(':') && ip.includes('.')) {
        const lowerIp = ip.toLowerCase();

        // IPv4-mapped IPv6 ::ffff:127.0.0.1
        if (lowerIp.startsWith('::ffff:')) {
            const ipv4 = lowerIp.substring(7);
             if (ipv4.includes('.')) {
                 return isPrivateIP(ipv4);
             }
        }

        // Also check for 0:0:0:0:0:ffff:127.0.0.1 style if not normalized
        // It's likely an embedded IPv4
        const parts = lowerIp.split(':');
        const lastPart = parts[parts.length - 1];
        if (lastPart.includes('.')) {
            return isPrivateIP(lastPart);
        }
    }

    // IPv4
    if (ip.includes('.')) {
        const parts = ip.split('.').map(Number);
        if (parts.length !== 4) return false;

        // 127.0.0.0/8 - Loopback
        if (parts[0] === 127) return true;
        // 10.0.0.0/8 - Private Network
        if (parts[0] === 10) return true;
        // 192.168.0.0/16 - Private Network
        if (parts[0] === 192 && parts[1] === 168) return true;
        // 172.16.0.0/12 - Private Network (172.16.x.x - 172.31.x.x)
        if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
        // 169.254.0.0/16 - Link-local
        if (parts[0] === 169 && parts[1] === 254) return true;
        // 0.0.0.0/8 - Current network (only valid as source address)
        if (parts[0] === 0) return true;

        return false;
    }
    // IPv6
    else if (ip.includes(':')) {
        const lowerIp = ip.toLowerCase();

        // ::1/128 - Loopback
        if (lowerIp === '::1' || lowerIp === '0:0:0:0:0:0:0:1') return true;

        // ::/128 - Unspecified
        if (lowerIp === '::' || lowerIp === '0:0:0:0:0:0:0:0') return true;

        // fc00::/7 - Unique Local Address
        // Check if starts with fc or fd (case insensitive)
        const firstBlock = lowerIp.split(':')[0];
        if (firstBlock.length > 0) {
            const val = parseInt(firstBlock, 16);
            // fc00::/7 covers fc00 to fdff
            if (!isNaN(val) && ((val >> 8) & 0xfe) === 0xfc) return true;
        }

        // fe80::/10 - Link-local
        if (lowerIp.startsWith('fe8') || lowerIp.startsWith('fe9') || lowerIp.startsWith('fea') || lowerIp.startsWith('feb')) return true;

        return false;
    }
    return false;
}

/**
 * Custom DNS lookup function for `got` that prevents resolving to private IP addresses.
 */
export function safeLookup(
    hostname: string,
    options: dns.LookupOptions,
    callback: (err: NodeJS.ErrnoException | null, address: string | dns.LookupAddress[], family?: number) => void
): void {
    dns.lookup(hostname, options, (err, address, family) => {
        if (err) {
            callback(err, address as any, family);
            return;
        }

        const addressesToCheck: string[] = [];

        if (Array.isArray(address)) {
            address.forEach(a => addressesToCheck.push(a.address));
        } else if (typeof address === 'string') {
            addressesToCheck.push(address);
        }

        for (const addr of addressesToCheck) {
            if (isPrivateIP(addr)) {
                const error = new Error(`DNS lookup for ${hostname} resolved to a private IP: ${addr}`);
                (error as any).code = 'ERR_SSRF_PROTECTION';
                callback(error as NodeJS.ErrnoException, address as any, family);
                return;
            }
        }

        callback(null, address as any, family);
    });
}
