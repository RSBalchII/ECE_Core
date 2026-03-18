
import React from 'react';
import type { DiscoveredEntity } from '../../types/taxonomy';
import { SemanticCategory } from '../../types/taxonomy';
import { Sparkles, PlusCircle } from 'lucide-react';
import { Button } from '../ui/Button';

interface DiscoveryPanelProps {
    suggestions: DiscoveredEntity[];
    onAdd: (entity: DiscoveredEntity, targetCategory: SemanticCategory) => void;
    isLoading?: boolean;
}

export const DiscoveryPanel: React.FC<DiscoveryPanelProps> = ({ suggestions, onAdd, isLoading }) => {
    return (
        <div className="bg-slate-900/50 border-l border-slate-800 h-full p-4 overflow-y-auto">
            <div className="flex items-center gap-2 mb-6 text-purple-400">
                <Sparkles size={20} />
                <h2 className="text-lg font-semibold tracking-wide">Discovery</h2>
            </div>

            <p className="text-sm text-slate-500 mb-4">
                Found {suggestions.length} potential entities in your graph.
            </p>

            {isLoading ? (
                <div className="space-y-3 animate-pulse">
                    {[1, 2, 3].map(i => <div key={i} className="h-16 bg-slate-800 rounded-md"></div>)}
                </div>
            ) : (
                <div className="space-y-3">
                    {suggestions.map((entity, idx) => (
                        <div key={idx} className="bg-slate-950 border border-slate-800 p-3 rounded-md hover:border-purple-500/50 transition-colors group">
                            <div className="flex justify-between items-start mb-2">
                                <span className="font-medium text-slate-200">{entity.name}</span>
                                <span className="text-xs bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                                    {entity.frequency}x
                                </span>
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="text-xs text-slate-500 uppercase">{entity.suggestedCategory}</span>
                                <Button
                                    variant="icon"
                                    aria-label="Add to suggested category"
                                    onClick={() => onAdd(entity, entity.suggestedCategory)}
                                    style={{ color: '#c084fc', opacity: 0 }}
                                    className="group-hover:opacity-100 transition-opacity hover:text-purple-300"
                                    title="Add to Rules"
                                >
                                    <PlusCircle size={18} />
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
