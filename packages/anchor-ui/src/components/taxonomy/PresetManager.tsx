
import React, { useState } from 'react';
import { Save, RotateCcw, ChevronDown } from 'lucide-react';
import type { TaxonomyPreset } from '../../types/taxonomy';
import { Button } from '../ui/Button';

interface PresetManagerProps {
    presets: TaxonomyPreset[];
    onSave: (name: string) => void;
    onLoad: (presetId: string) => void;
}

export const PresetManager: React.FC<PresetManagerProps> = ({ presets, onSave, onLoad }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [newPresetName, setNewPresetName] = useState('');
    const [isSaveMode, setIsSaveMode] = useState(false);

    const handleSave = () => {
        if (newPresetName.trim()) {
            onSave(newPresetName);
            setNewPresetName('');
            setIsSaveMode(false);
        }
    };

    return (
        <div className="flex items-center gap-2">
            {isSaveMode ? (
                <div className="flex items-center gap-1 bg-slate-800 rounded-md p-1 animate-in fade-in slide-in-from-right-4 duration-200">
                    <input
                        type="text"
                        value={newPresetName}
                        onChange={e => setNewPresetName(e.target.value)}
                        placeholder="Preset Name..."
                        className="bg-slate-900 border-none text-sm px-2 py-1 rounded w-32 focus:ring-1 focus:ring-purple-500 text-white outline-none"
                    />
                    <Button variant="icon" onClick={handleSave} aria-label="Save preset" className="p-1 hover:text-green-400"><Save size={16} /></Button>
                    <Button variant="icon" onClick={() => setIsSaveMode(false)} aria-label="Cancel save" className="p-1 hover:text-red-400 text-slate-400">×</Button>
                </div>
            ) : (
                <Button
                    variant="ghost"
                    onClick={() => setIsSaveMode(true)}
                    className="flex items-center gap-1 text-sm bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-md text-slate-300 transition-colors"
                >
                    <Save size={14} />
                    <span>Save</span>
                </Button>
            )}

            <div className="relative">
                <Button
                    variant="ghost"
                    onClick={() => setIsOpen(!isOpen)}
                    className="flex items-center gap-1 text-sm bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-md text-slate-300 transition-colors"
                >
                    <RotateCcw size={14} />
                    <span>Load</span>
                    <ChevronDown size={12} className={`transition-transformDuration-200 ${isOpen ? 'rotate-180' : ''}`} />
                </Button>

                {isOpen && (
                    <>
                        <div
                            className="fixed inset-0 z-10"
                            onClick={() => setIsOpen(false)}
                        />
                        <div className="absolute right-0 top-full mt-2 w-48 bg-slate-900 border border-slate-700 rounded-md shadow-xl z-20 py-1">
                            {presets.length === 0 ? (
                                <div className="px-4 py-2 text-xs text-slate-500 italic">No presets found</div>
                            ) : (
                                presets.map(preset => (
                                    <Button
                                        variant="ghost"
                                        key={preset.id}
                                        onClick={() => { onLoad(preset.id); setIsOpen(false); }}
                                        className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                                    >
                                        <div className="font-medium">{preset.name}</div>
                                        <div className="text-xs text-slate-500">{new Date(preset.timestamp).toLocaleDateString()}</div>
                                    </Button>
                                ))
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
