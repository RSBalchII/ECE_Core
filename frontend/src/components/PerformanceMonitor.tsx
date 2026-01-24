import React, { useEffect, useState, useRef } from 'react';

const PerformanceMonitor: React.FC = () => {
    const [isLagging, setIsLagging] = useState(false);
    const requestRef = useRef<number | undefined>(undefined);
    const lastTimeRef = useRef<number>(performance.now());
    const frameCountRef = useRef<number>(0);
    const lastCheckRef = useRef<number>(performance.now());

    useEffect(() => {
        const animate = (time: number) => {
            frameCountRef.current++;
            const delta = time - lastCheckRef.current;

            // Check FPS every 500ms
            if (delta >= 500) {
                const fps = (frameCountRef.current / delta) * 1000;

                // Threshold: 10 FPS
                if (fps < 10) {
                    setIsLagging(true);
                } else {
                    // Add a small delay/hysteresis before hiding to prevent flickering
                    // If we were lagging, we give it a moment to settle
                    // effectively, we just turn it off if good.
                    // To make it smoother, we could use a timeout, but simpler is better first.
                    setIsLagging(false);
                }

                frameCountRef.current = 0;
                lastCheckRef.current = time;
            }

            lastTimeRef.current = time;
            requestRef.current = requestAnimationFrame(animate);
        };

        requestRef.current = requestAnimationFrame(animate);

        return () => {
            if (requestRef.current) cancelAnimationFrame(requestRef.current);
        };
    }, []);

    if (!isLagging) return null;

    return (
        <div
            className="lag-indicator glass-panel"
            style={{
                position: 'fixed',
                bottom: '1.5rem',
                right: '1.5rem',
                zIndex: 9999,
                padding: '0.5rem',
                borderRadius: '50%',
                boxShadow: '0 0 10px rgba(0,0,0,0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                pointerEvents: 'none', // Don't block clicks
                width: '40px',
                height: '40px'
            }}
            title="System Busy (Low FPS)"
        >
            <div className="hourglass-spin" style={{ fontSize: '1.2rem' }}>
                ⏳
            </div>
        </div>
    );
};

export default PerformanceMonitor;
