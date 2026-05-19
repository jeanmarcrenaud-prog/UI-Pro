// HistoryFilters.tsx
// Role: Search, filters, sort controls for history

'use client'

import { Search, Filter, ChevronDown, Square } from 'lucide-react'

export type SortOption = 'date_desc' | 'date_asc' | 'title'
export type DateGroup = 'today' | 'yesterday' | 'this_week' | 'older'

interface HistoryFiltersProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  showFilters: boolean
  onToggleFilters: () => void
  sortBy: SortOption
  onSortChange: (sort: SortOption) => void
  showArchived: boolean
  onToggleArchived: (show: boolean) => void
  selectMode: boolean
  onToggleSelectMode: () => void
  selectedCount: number
  totalCount: number
  onSelectAll: () => void
  allTags: string[]
  filterTag: string
  onFilterTagChange: (tag: string) => void
}

export function HistoryFilters({
  searchQuery,
  onSearchChange,
  showFilters,
  onToggleFilters,
  sortBy,
  onSortChange,
  showArchived,
  onToggleArchived,
  selectMode,
  onToggleSelectMode,
  selectedCount,
  totalCount,
  onSelectAll,
  allTags,
  filterTag,
  onFilterTagChange,
}: HistoryFiltersProps) {
  return (
    <>
      {/* Header Row */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="text-xl font-semibold text-white">History</h2>
          <p className="text-sm text-slate-500">{totalCount} chats</p>
        </div>
        <button
          onClick={onToggleSelectMode}
          className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border transition-colors ${
            selectMode ? 'bg-violet-600 border-violet-500 text-white' : 'border-slate-700 text-slate-400 hover:text-white'
          }`}
        >
          <Square className="w-4 h-4" />
          {selectMode ? 'Cancel' : 'Select'}
        </button>
      </div>
      
      {/* Batch Actions Bar */}
      {selectedCount > 0 && (
        <div className="mb-3 p-3 bg-violet-900/30 border border-violet-700/50 rounded-lg flex items-center justify-between">
          <span className="text-sm text-white">{selectedCount} selected</span>
        </div>
      )}
      
      {/* Search */}
      <div className="relative mb-3">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-10 pr-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
        />
      </div>

      {/* Filter Controls */}
      <div className="flex flex-wrap items-center gap-2">
        {selectMode && totalCount > 0 && (
          <button
            onClick={onSelectAll}
            className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg border border-slate-700 text-slate-400 hover:text-white"
          >
            <Square className="w-4 h-4" />
            {selectedCount === totalCount ? 'Deselect All' : 'Select All'}
          </button>
        )}
        
        <button
          onClick={onToggleFilters}
          className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg border transition-colors ${
            showFilters ? 'bg-violet-600 border-violet-500 text-white' : 'border-slate-700 text-slate-400 hover:text-white'
          }`}
        >
          <Filter className="w-4 h-4" />
          Filters
          <ChevronDown className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
        </button>

        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value as SortOption)}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white"
        >
          <option value="date_desc">Newest first</option>
          <option value="date_asc">Oldest first</option>
          <option value="title">Alphabetical</option>
        </select>

        <label className="flex items-center gap-2 text-sm text-slate-400">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => onToggleArchived(e.target.checked)}
            className="rounded"
          />
          Archived
        </label>
      </div>

      {/* Expanded Filters */}
      {showFilters && (
        <div className="mt-3 p-3 bg-slate-800/50 rounded-lg space-y-3">
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Tags</label>
            <div className="flex flex-wrap gap-1">
              <button
                onClick={() => onFilterTagChange('')}
                className={`text-xs px-2 py-1 rounded-full ${!filterTag ? 'bg-slate-600 text-white' : 'bg-slate-700 text-slate-400'}`}
              >
                All
              </button>
              {allTags.map(tag => (
                <button
                  key={tag}
                  onClick={() => onFilterTagChange(filterTag === tag ? '' : tag)}
                  className={`text-xs px-2 py-1 rounded-full ${
                    filterTag === tag ? 'bg-violet-500 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}