'use client';

import React, { useState } from 'react';
import { Database, Loader2 } from 'lucide-react';
import api from '@/lib/api';
import DataExplorerGuide from './DataExplorerGuide';
import type { DebugSQLResponse, SQLMode, GroupBy } from '@/types/api';
import { ORGANIZATIONS } from '@/types/api';

export default function DataExplorer() {
  const [mode, setMode] = useState<SQLMode>('expenses_sample');
  const [org, setOrg] = useState<string>('ASU');
  const [employeeId, setEmployeeId] = useState('');
  const [caseId, setCaseId] = useState('');
  const [groupBy, setGroupBy] = useState<GroupBy>('category');
  const [limit, setLimit] = useState(20);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DebugSQLResponse | null>(null);
  const [showGuide, setShowGuide] = useState(true);

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.debugSQL({
        mode,
        org,
        employee_id: employeeId || undefined,
        case_id: caseId || undefined,
        group_by: mode === 'expenses_totals' ? groupBy : undefined,
        limit,
      });

      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
      setData(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-6 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-200">
            Data Explorer
          </h2>
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="text-sm text-green-600 dark:text-green-400 hover:underline"
          >
            {showGuide ? 'Hide' : 'Show'} Guide
          </button>
        </div>

        {showGuide && <DataExplorerGuide />}

        <form onSubmit={handleQuery} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Query Mode
              </label>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as SQLMode)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
              >
                <option value="expenses_sample">Expense Samples</option>
                <option value="expenses_totals">Expense Totals</option>
                <option value="events_timeline">Event Timeline</option>
                <option value="duplicates">Duplicate Detection</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Organization
              </label>
              <select
                value={org}
                onChange={(e) => setOrg(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
              >
                {ORGANIZATIONS.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Employee ID (optional)
              </label>
              <input
                type="text"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="e.g., EMP001"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
              />
            </div>

            {mode === 'events_timeline' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Case ID (required for timeline)
                </label>
                <input
                  type="text"
                  value={caseId}
                  onChange={(e) => setCaseId(e.target.value)}
                  placeholder="e.g., CASE001"
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
                />
              </div>
            )}

            {mode === 'expenses_totals' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Group By
                </label>
                <select
                  value={groupBy}
                  onChange={(e) => setGroupBy(e.target.value as GroupBy)}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
                >
                  <option value="category">Category</option>
                  <option value="merchant">Merchant</option>
                  <option value="currency">Currency</option>
                  <option value="employee_id">Employee ID</option>
                  <option value="report_id">Report ID</option>
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Limit
              </label>
              <input
                type="number"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value))}
                min="1"
                max="200"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full px-6 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white rounded-lg flex items-center justify-center gap-2 transition-colors"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Loading...</span>
              </>
            ) : (
              <>
                <Database className="w-5 h-5" />
                <span>Query Data</span>
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
        {!data && !isLoading && (
          <div className="text-center text-gray-500 dark:text-gray-400 mt-8">
            <Database className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Select query parameters and click Query Data to explore expense data.</p>
          </div>
        )}

        {data && data.ok && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm border border-gray-200 dark:border-gray-700 rounded-lg">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {data.data.length > 0 &&
                    Object.keys(data.data[0]).map((key) => (
                      <th key={key} className="px-4 py-2 text-left font-semibold">
                        {key.replace(/_/g, ' ').toUpperCase()}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900">
                {data.data.map((row: any, idx) => (
                  <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                    {Object.values(row).map((value: any, cellIdx) => (
                      <td key={cellIdx} className="px-4 py-2">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>

            {data.data.length === 0 && (
              <p className="text-center text-gray-500 dark:text-gray-400 py-8">
                No data found for the selected filters.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
