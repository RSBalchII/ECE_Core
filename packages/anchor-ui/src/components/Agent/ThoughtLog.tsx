import React, { useState } from 'react';
import type { Message } from '../../types/chat';

interface ThoughtLogProps {
    thoughts: Message[];
    isActive?: boolean;
}

export const ThoughtLog: React.FC<ThoughtLogProps> = ({ thoughts, isActive }) => {
    const [isExpanded, setIsExpanded] = useState(isActive || false);

    // Auto-expand when active, but allow manual toggle
    React.useEffect(() => {
        if (isActive) setIsExpanded(true);
    }, [isActive]);

    if (thoughts.length === 0) return null;

    return (
        <div className={`my-2 rounded border transition-all duration-300 ${isActive
                ? 'border-cyan-500/50 bg-cyan-500/5 shadow-[0_0_15px_rgba(34,211,238,0.1)]'
                : 'border-gray-800/50 bg-gray-950/20 overflow-hidden'
            }`}>
            {/* Header */}
            <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full text-left p-3 flex justify-between items-center cursor-pointer hover:bg-white/5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
                aria-expanded={isExpanded}
                aria-label="Toggle neural thought process"
            >
                <div className="flex items-center gap-3">
                    <div className="relative">
                        {/* Brain Icon / Pulse */}
                        <div className={`w-4 h-4 text-cyan-400 ${isActive ? 'animate-pulse' : 'opacity-40'}`}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-2.5 2.5h-1A2.5 2.5 0 0 1 6 19.5v-15A2.5 2.5 0 0 1 8.5 2h1zM14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 2.5 2.5h1a2.5 2.5 0 0 0 2.5-2.5v-15A2.5 2.5 0 0 0 15.5 2h-1z" />
                            </svg>
                        </div>
                        {isActive && <div className="absolute inset-0 bg-cyan-400 blur-sm animate-pulse opacity-40" />}
                    </div>
                    <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-100 opacity-80">
                        Neural Thought Process // <span className="text-cyan-400">{thoughts.length} Cycles</span>
                    </span>
                </div>
                <div className={`text-xs text-gray-600 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}>
                    ▼
                </div>
            </button>

            {/* Expanded Content */}
            <div className={`transition-all duration-300 ease-in-out ${isExpanded ? 'max-h-[500px] opacity-100 border-t border-gray-800/50 p-4' : 'max-h-0 opacity-0'
                } overflow-y-auto custom-scrollbar`}>
                <div className="space-y-4">
                    {thoughts.map((thought, idx) => (
                        <div key={idx} className="font-mono text-[11px] leading-relaxed">
                            <div className="flex items-start gap-4">
                                <span className="text-gray-600 opacity-50 select-none shrink-0">&gt;</span>
                                <div className="space-y-2 flex-1">
                                    {renderThought(thought)}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// Helper to render different types of thoughts
function renderThought(msg: Message) {
    if (msg.role === 'thought') {
        return (
            <div className="text-gray-500 italic">
                "{msg.content}"
            </div>
        );
    } else if (msg.role === 'tool_call') {
        return (
            <div className="text-green-400 font-bold">
                <span className="text-green-600">$ </span>
                {renderToolCall(msg.content)}
            </div>
        );
    } else if (msg.role === 'tool_result') {
        return (
            <div className="text-gray-600 text-xs whitespace-pre-wrap">
                {'> ' + msg.content.substring(0, 200) + (msg.content.length > 200 ? '...' : '')}
            </div>
        );
    }
    return null; // Or handle other message roles if necessary
}

// Helper to pretty print tool calls if they are JSON
function renderToolCall(content: string) {
    try {
        const parsed = JSON.parse(content);
        return `${parsed.tool}(${JSON.stringify(parsed.params)})`;
    } catch {
        return content;
    }
}
