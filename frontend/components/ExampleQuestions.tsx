'use client';

import React from 'react';
import { MessageSquare, Database, FileSearch, HelpCircle } from 'lucide-react';

interface ExampleQuestion {
  question: string;
  category: 'policy' | 'expense' | 'comparison' | 'clarify';
  dataSource: string;
  icon: React.ReactNode;
  color: string;
}

const examples: ExampleQuestion[] = [
  {
    question: "What is Stanford's travel policy?",
    category: 'policy',
    dataSource: 'Policy Documents (RAG)',
    icon: <FileSearch className="w-4 h-4" />,
    color: 'blue',
  },
  {
    question: "Show me my recent expenses",
    category: 'expense',
    dataSource: 'Expense Database (SQL)',
    icon: <Database className="w-4 h-4" />,
    color: 'green',
  },
  {
    question: "Compare ASU vs Yale meal per diem",
    category: 'comparison',
    dataSource: 'Multiple Policies (RAG)',
    icon: <FileSearch className="w-4 h-4" />,
    color: 'purple',
  },
  {
    question: "Is business class allowed?",
    category: 'clarify',
    dataSource: 'Needs Clarification',
    icon: <HelpCircle className="w-4 h-4" />,
    color: 'orange',
  },
];

interface ExampleQuestionsProps {
  onSelectQuestion: (question: string) => void;
}

export default function ExampleQuestions({ onSelectQuestion }: ExampleQuestionsProps) {
  const getColorClasses = (color: string) => {
    const colors = {
      blue: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300',
      green: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300',
      purple: 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800 text-purple-700 dark:text-purple-300',
      orange: 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800 text-orange-700 dark:text-orange-300',
    };
    return colors[color as keyof typeof colors] || colors.blue;
  };

  return (
    <div className="h-full bg-gray-50 dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 p-4 overflow-y-auto">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
        Example Questions
      </h3>

      <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
        Click any question to try it, or ask similar questions.
      </p>

      <div className="space-y-3">
        {examples.map((example, idx) => (
          <button
            key={idx}
            onClick={() => onSelectQuestion(example.question)}
            className={`w-full text-left p-3 rounded-lg border transition-all hover:shadow-md ${getColorClasses(example.color)}`}
          >
            <div className="flex items-start gap-2 mb-2">
              {example.icon}
              <p className="text-sm font-medium flex-1">{example.question}</p>
            </div>
            <div className="flex items-center gap-1 ml-6">
              <Database className="w-3 h-3 opacity-60" />
              <span className="text-xs opacity-75">{example.dataSource}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-8 p-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
          How It Works
        </h4>

        <div className="space-y-3 text-xs text-gray-600 dark:text-gray-400">
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5" />
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Policy Questions</p>
              <p>Searches university policy documents</p>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5" />
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Personal Expenses</p>
              <p>Queries your expense database</p>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-purple-500 mt-1.5" />
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Comparisons</p>
              <p>Compares policies across universities</p>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-orange-500 mt-1.5" />
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Needs Info</p>
              <p>Asks for university specification</p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
        <p className="text-xs text-blue-700 dark:text-blue-300">
          <strong>Tip:</strong> Be specific! Mention a university name for faster, more accurate results.
        </p>
      </div>
    </div>
  );
}
