'use client';

import React, { useState } from 'react';
import { Search, Loader2, FileText } from 'lucide-react';
import api from '@/lib/api';
import type { PolicySearchResult } from '@/types/api';
import { ORGANIZATIONS } from '@/types/api';

export default function PolicySearch() {
  const [query, setQuery] = useState('');
  const [org, setOrg] = useState('');
  const [policyType, setPolicyType] = useState('');
  const [results, setResults] = useState<PolicySearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await api.searchPolicy({
        q: query,
        org: org || undefined,
        policy_type: policyType as any || undefined,
        final_k: 10,
      });

      setResults(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search policies');
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-6 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-4">
          Policy Search
        </h2>

        <form onSubmit={handleSearch} className="space-y-4">
          <div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search policy documents..."
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Organization
              </label>
              <select
                value={org}
                onChange={(e) => setOrg(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
              >
                <option value="">All Organizations</option>
                {ORGANIZATIONS.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Policy Type
              </label>
              <select
                value={policyType}
                onChange={(e) => setPolicyType(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
              >
                <option value="">All Types</option>
                <option value="travel">Travel</option>
                <option value="procurement">Procurement</option>
                <option value="general">General</option>
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="w-full px-6 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white rounded-lg flex items-center justify-center gap-2 transition-colors"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Searching...</span>
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                <span>Search</span>
              </>
            )}
          </button>
        </form>

        {error && (
          <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {results.length === 0 && !isLoading && (
          <div className="text-center text-gray-500 dark:text-gray-400 mt-8">
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No results yet. Try searching for a policy topic.</p>
          </div>
        )}

        <div className="space-y-4">
          {results.map((result, idx) => (
            <div
              key={idx}
              className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-900 dark:text-gray-100">
                    {result.org || 'Unknown'}
                  </span>
                  {result.page && (
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      Page {result.page}
                    </span>
                  )}
                </div>
                {result.score && (
                  <span className="text-xs bg-primary-100 dark:bg-primary-900 text-primary-800 dark:text-primary-200 px-2 py-1 rounded">
                    Score: {(result.score * 100).toFixed(1)}%
                  </span>
                )}
              </div>

              <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">{result.doc_name}</p>

              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                {result.snippet}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
