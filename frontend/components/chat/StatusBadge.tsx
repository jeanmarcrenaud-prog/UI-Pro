import React from 'react';

interface StatusBadgeProps {
  isConnected: boolean;
  mode: 'REMOTE' | 'LOCAL';
  isProcessing: boolean;
}

export default function StatusBadge({ isConnected, mode, isProcessing }: StatusBadgeProps) {
  const baseClasses = "flex items-center gap-2 px-3 py-1 rounded-full border text-[11px] font-bold uppercase tracking-wider shadow-sm transition-all duration-300";
  
  const connectionColor = isConnected 
    ? "border-emerald-500/50 bg-emerald-500/5 text-emerald-400" 
    : "border-gray-700/50 bg-gray-800/50 text-gray-500";

  const modeColor = mode === 'REMOTE'
    ? "border-blue-500/50 bg-blue-500/5 text-blue-400"
    : "border-amber-500/50 bg-amber-500/5 text-amber-400";

  return (
    <div className="flex gap-2 mb-2">
      <div className={`flex items-center gap-1.5 ${baseClasses} ${connectionColor}`}>
        <span className={`relative flex h-2 w-2 ${isConnected ? 'bg-emerald-500' : 'bg-gray-600'}`}>
          {isConnected && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />}
          <span className="relative inline-flex rounded-full h-2 w-2 bg-current" />
        </span>
        {isConnected ? 'ONLINE' : 'OFFLINE'}
      </div>
      <div className={`flex items-center gap-1.5 ${baseClasses} ${modeColor}`}>
        <span className={isProcessing ? "animate-pulse" : ""}>{mode}</span>
        {isProcessing && <span className="text-[9px] opacity-70 italic">Active</span>}
      </div>
    </div>
  );
}
