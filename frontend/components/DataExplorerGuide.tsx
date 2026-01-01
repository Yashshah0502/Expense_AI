'use client';

import React from 'react';
import { Database, Lightbulb, Target } from 'lucide-react';

export default function DataExplorerGuide() {
  return (
    <div className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border border-green-200 dark:border-green-800 rounded-lg p-6 mb-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-full bg-green-600 flex items-center justify-center flex-shrink-0">
          <Database className="w-5 h-5 text-white" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
            Data Explorer
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Query your expense database directly
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-start gap-3">
          <Target className="w-5 h-5 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100 mb-1">Available Queries:</p>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1 list-disc list-inside">
              <li><strong>Expense Samples:</strong> View individual expense records</li>
              <li><strong>Expense Totals:</strong> See aggregated totals by category, merchant, etc.</li>
              <li><strong>Events Timeline:</strong> View expense workflow events</li>
              <li><strong>Duplicates:</strong> Find potential duplicate expenses</li>
            </ul>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <Lightbulb className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100 mb-1">Example Queries:</p>
            <div className="space-y-2 mt-2">
              <div className="bg-white dark:bg-gray-800 rounded p-2 border border-gray-200 dark:border-gray-700">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">View My Expenses</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Mode: Expense Samples → Org: ASU → Employee: EMP001
                </p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded p-2 border border-gray-200 dark:border-gray-700">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Total by Category</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Mode: Expense Totals → Org: ASU → Group By: Category
                </p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded p-2 border border-gray-200 dark:border-gray-700">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Find Duplicates</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Mode: Duplicates → Org: ASU
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
