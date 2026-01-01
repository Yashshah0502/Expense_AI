'use client';

import React from 'react';
import { FileSearch, Lightbulb, Target } from 'lucide-react';

export default function PolicySearchGuide() {
  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6 mb-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
          <FileSearch className="w-5 h-5 text-white" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
            Policy Search
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Search through university expense policy documents
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-start gap-3">
          <Target className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100 mb-1">What to Search For:</p>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1 list-disc list-inside">
              <li>Specific policy topics: "travel reimbursement", "meal per diem"</li>
              <li>Requirements: "business class requirements", "receipt policies"</li>
              <li>Limits: "lodging limits", "mileage rates"</li>
            </ul>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <Lightbulb className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100 mb-1">Example Searches:</p>
            <div className="space-y-2 mt-2">
              <div className="bg-white dark:bg-gray-800 rounded p-2 border border-gray-200 dark:border-gray-700">
                <p className="text-sm font-mono text-gray-700 dark:text-gray-300">"rental car insurance"</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Filter by: Organization = Stanford, Type = Travel</p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded p-2 border border-gray-200 dark:border-gray-700">
                <p className="text-sm font-mono text-gray-700 dark:text-gray-300">"alcohol policy"</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Filter by: Organization = Yale</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
