
import React, { useState } from 'react';
import type { SemanticRule } from '../../types/taxonomy';
import { SemanticCategory } from '../../types/taxonomy';
import { X, Plus } from 'lucide-react';
import { Button } from '../ui/Button';

interface RuleCardProps {
    rule: SemanticRule;
    onUpdate: (updatedRule: SemanticRule) => void;
}

export const RuleCard: React.FC<RuleCardProps> = ({ rule, onUpdate }) => {
    const [newTrigger, setNewTrigger] = useState('');
    const [newExclusion, setNewExclusion] = useState('');

    const handleWeightChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        onUpdate({ ...rule, weight: parseFloat(e.target.value) });
    };

    const addTrigger = () => {
        if (newTrigger && !rule.triggers.includes(newTrigger)) {
            onUpdate({ ...rule, triggers: [...rule.triggers, newTrigger] });
            setNewTrigger('');
        }
    };

    const removeTrigger = (trigger: string) => {
        onUpdate({ ...rule, triggers: rule.triggers.filter(t => t !== trigger) });
    };

    const addExclusion = () => {
        if (newExclusion && !rule.exclusions.includes(newExclusion)) {
            onUpdate({ ...rule, exclusions: [...rule.exclusions, newExclusion] });
            setNewExclusion('');
        }
    };

    const removeExclusion = (exclusion: string) => {
        onUpdate({ ...rule, exclusions: rule.exclusions.filter(e => e !== exclusion) });
    };

    const handleKeyDown = (e: React.KeyboardEvent, action: () => void) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            action();
        }
    };

    // Color mapping for categories
    const getCategoryColor = (cat: SemanticCategory) => {
        switch (cat) {
            case SemanticCategory.RELATIONSHIP: return 'border-pink-500 text-pink-500';
            case SemanticCategory.NARRATIVE: return 'border-blue-500 text-blue-500';
            case SemanticCategory.TECHNICAL: return 'border-emerald-500 text-emerald-500';
            case SemanticCategory.INDUSTRY: return 'border-amber-500 text-amber-500';
            case SemanticCategory.LOCATION: return 'border-indigo-500 text-indigo-500';
            default: return 'border-slate-500 text-slate-500';
        }
    };

    return (
        <div className={`p-4 bg-slate-900 border-l-4 rounded-md mb-4 shadow-sm ${getCategoryColor(rule.category)}`}>
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-bold uppercase tracking-wider">{rule.category}</h3>
                <span className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-400">Weight: {rule.weight.toFixed(1)}</span>
            </div>

            {/* WEIGHT SLIDER */}
            <div className="mb-6">
                <label className="block text-xs uppercase text-slate-500 mb-1">Impact Weight</label>
                <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.1"
                    value={rule.weight}
                    onChange={handleWeightChange}
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-current"
                />
            </div>

            {/* TRIGGERS */}
            <div className="mb-4">
                <label className="block text-xs uppercase text-slate-500 mb-1">Triggers (Keywords)</label>
                <div className="flex flex-wrap gap-2 mb-2">
                    {rule.triggers.map((t: string) => (
                        <span key={t} className="px-2 py-1 bg-slate-800 rounded text-sm text-slate-200 flex items-center gap-1 border border-slate-700">
                            {t}
                            <Button variant="icon" onClick={() => removeTrigger(t)} aria-label="Remove trigger" style={{ color: '#f87171' }}><X size={12} /></Button>
                        </span>
                    ))}
                </div>
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={newTrigger}
                        onChange={(e) => setNewTrigger(e.target.value)}
                        onKeyDown={(e) => handleKeyDown(e, addTrigger)}
                        placeholder="Add trigger..."
                        className="flex-1 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200 focus:outline-none focus:border-slate-500"
                    />
                    <Button variant="icon" onClick={addTrigger} aria-label="Add trigger" className="bg-slate-800 rounded text-slate-400" style={{ padding: '4px' }}><Plus size={16} /></Button>
                </div>
            </div>

            {/* EXCLUSIONS */}
            <div>
                <label className="block text-xs uppercase text-slate-500 mb-1">Exclusions (Negative)</label>
                <div className="flex flex-wrap gap-2 mb-2">
                    {rule.exclusions.map((e: string) => (
                        <span key={e} className="px-2 py-1 bg-red-900/20 rounded text-sm text-red-300 flex items-center gap-1 border border-red-900/50">
                            {e}
                            <Button variant="icon" onClick={() => removeExclusion(e)} aria-label="Remove exclusion" style={{ color: '#fca5a5' }}><X size={12} /></Button>
                        </span>
                    ))}
                </div>
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={newExclusion}
                        onChange={(e) => setNewExclusion(e.target.value)}
                        onKeyDown={(e) => handleKeyDown(e, addExclusion)}
                        placeholder="Add exclusion..."
                        className="flex-1 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200 focus:outline-none focus:border-red-900/50"
                    />
                    <Button variant="icon" onClick={addExclusion} aria-label="Add exclusion" className="bg-slate-800 rounded text-slate-400" style={{ padding: '4px' }}><Plus size={16} /></Button>
                </div>
            </div>
        </div>
    );
};
