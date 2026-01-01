import React from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot } from 'lucide-react';
import type { PolicySource, SQLResults } from '@/types/api';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  policySources?: PolicySource[];
  sqlResults?: SQLResults;
  followUp?: string | null;
  warnings?: string[];
}

export default function ChatMessage({
  role,
  content,
  policySources,
  sqlResults,
  followUp,
  warnings,
}: ChatMessageProps) {
  return (
    <div
      className={`flex gap-4 p-4 ${
        role === 'user' ? 'bg-gray-50 dark:bg-gray-800' : 'bg-white dark:bg-gray-900'
      }`}
    >
      <div className="flex-shrink-0">
        {role === 'user' ? (
          <div className="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center">
            <User className="w-5 h-5 text-white" />
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-purple-500 flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="markdown-content">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>

        {warnings && warnings.length > 0 && (
          <div className="mt-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
            <p className="text-sm text-yellow-800 dark:text-yellow-200 font-semibold mb-1">
              Warnings:
            </p>
            {warnings.map((warning, idx) => (
              <p key={idx} className="text-sm text-yellow-700 dark:text-yellow-300">
                {warning}
              </p>
            ))}
          </div>
        )}

        {followUp && (
          <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-200 font-semibold mb-1">
              Follow-up needed:
            </p>
            <p className="text-sm text-blue-700 dark:text-blue-300">{followUp}</p>
          </div>
        )}

        {policySources && policySources.length > 0 && (
          <div className="mt-4">
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Policy Sources ({policySources.length}):
            </p>
            <div className="space-y-2">
              {policySources.map((source, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-gray-900 dark:text-gray-100">
                      {source.org}
                    </span>
                    {source.page && (
                      <span className="text-gray-500 dark:text-gray-400">- Page {source.page}</span>
                    )}
                    {source.score && (
                      <span className="ml-auto text-xs bg-primary-100 dark:bg-primary-900 text-primary-800 dark:text-primary-200 px-2 py-0.5 rounded">
                        {(source.score * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                    {source.doc_name}
                  </p>
                  {source.snippet && (
                    <p className="text-gray-700 dark:text-gray-300">{source.snippet}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {sqlResults && (
          <div className="mt-4">
            {sqlResults.totals && sqlResults.totals.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Expense Totals:
                </p>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm border border-gray-200 dark:border-gray-700 rounded-lg">
                    <thead className="bg-gray-50 dark:bg-gray-800">
                      <tr>
                        <th className="px-4 py-2 text-left">Group</th>
                        <th className="px-4 py-2 text-left">Currency</th>
                        <th className="px-4 py-2 text-right">Total</th>
                        <th className="px-4 py-2 text-right">Count</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {sqlResults.totals.map((total, idx) => (
                        <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                          <td className="px-4 py-2">{total.group}</td>
                          <td className="px-4 py-2">{total.currency}</td>
                          <td className="px-4 py-2 text-right font-mono">
                            {total.total.toFixed(2)}
                          </td>
                          <td className="px-4 py-2 text-right">{total.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {sqlResults.samples && sqlResults.samples.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Sample Expenses ({sqlResults.samples.length}):
                </p>
                <div className="space-y-2">
                  {sqlResults.samples.map((expense, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
                    >
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Date:</span>{' '}
                          <span className="font-semibold">{expense.expense_date}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Amount:</span>{' '}
                          <span className="font-semibold">
                            {expense.currency} {expense.amount}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Category:</span>{' '}
                          <span className="font-semibold">{expense.category}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Merchant:</span>{' '}
                          <span className="font-semibold">{expense.merchant}</span>
                        </div>
                      </div>
                      {expense.description && (
                        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                          {expense.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sqlResults.timeline && sqlResults.timeline.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Event Timeline ({sqlResults.timeline.length}):
                </p>
                <div className="space-y-2">
                  {sqlResults.timeline.map((event, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-gray-50 dark:bg-gray-800 border-l-4 border-primary-500 rounded"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-sm">{event.activity}</span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {new Date(event.event_time).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        Case: {event.case_id} | Index: {event.event_index}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sqlResults.duplicates && sqlResults.duplicates.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Potential Duplicates ({sqlResults.duplicates.length}):
                </p>
                <div className="space-y-2">
                  {sqlResults.duplicates.map((dup, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
                    >
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Type:</span>{' '}
                          <span className="font-semibold">{dup.duplicate_type}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Count:</span>{' '}
                          <span className="font-semibold text-red-600 dark:text-red-400">
                            {dup.count}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Total:</span>{' '}
                          <span className="font-semibold">{dup.total.toFixed(2)}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 dark:text-gray-400">Range:</span>{' '}
                          <span className="text-xs">
                            {dup.first_date} to {dup.last_date}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
