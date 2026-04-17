import React, { useState } from 'react';
import api from '../api/axios';

function QA() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');

  const handleAsk = async () => {
    if (!question.trim()) return;
    
    setLoading(true);
    setError('');
    const userQuestion = question;
    
    try {
      const response = await api.post('/books/ask/', { question: userQuestion });
      const newEntry = { question: userQuestion, answer: response.data };
      setAnswer(response.data);
      setHistory(prev => [newEntry, ...prev.slice(0, 4)]);
      setQuestion('');
    } catch (err) {
      setError('Failed to get answer: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestedQuestion = (q) => {
    setQuestion(q);
    setAnswer(null);
    setError('');
  };

  const suggestedQuestions = [
    "What are the highest rated books?",
    "Recommend a mystery novel",
    "Which books are about self-improvement?",
    "What are the most popular fiction books?"
  ];

  return (
    <div className="max-w-4xl mx-auto py-12 px-4">
      <h1 className="text-4xl font-bold text-gray-900 mb-8 text-center">Ask the Book Assistant</h1>
      
      <div className="bg-white rounded-2xl shadow-xl p-8 mb-8">
        <div className="mb-6">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask anything about the books in our collection..."
            className="w-full p-6 border-2 border-gray-200 rounded-xl resize-vertical min-h-[120px] focus:border-book-purple focus:outline-none focus:ring-2 focus:ring-book-purple/20 transition duration-200 text-lg"
            disabled={loading}
          />
        </div>
        <div className="flex flex-col sm:flex-row gap-4">
          <button
            onClick={handleAsk}
            disabled={loading || !question.trim()}
            className="flex-1 bg-book-purple text-white py-4 px-8 rounded-xl text-lg font-semibold hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5 mr-2 text-white inline" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round"/>
                  <path fill="none" stroke="currentColor" strokeWidth="4" d="M12 2v6" strokeDasharray="12 12" strokeDashoffset="0">
                    <animate attributeName="stroke-dashoffset" values="0;12" dur="1s" repeatCount="indefinite"/>
                  </path>
                </svg>
                Thinking...
              </>
            ) : (
              'Ask'
            )}
          </button>
          {error && (
            <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded-xl max-w-md">
              {error}
            </div>
          )}
        </div>
      </div>

      {answer && (
        <div className="bg-gradient-to-r from-book-purple/5 to-indigo-500/5 border border-book-purple/20 rounded-2xl p-8 mb-8 shadow-2xl">
          <h3 className="text-xl font-bold text-gray-900 mb-4">Answer</h3>
          <div className="prose max-w-none text-lg leading-relaxed">
            <p>{answer.answer}</p>
          </div>
          {answer.sources && answer.sources.length > 0 && (
            <div className="mt-6">
              <h4 className="font-semibold text-gray-800 mb-3">Sources:</h4>
              <div className="flex flex-wrap gap-2">
                {answer.sources.map((source, i) => (
                  <span key={i} className="px-3 py-1 bg-book-purple/20 text-book-purple rounded-full text-sm font-medium border border-book-purple/30">
                    {source}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {history.length > 0 && (
        <div>
          <h3 className="text-2xl font-bold text-gray-900 mb-6">Recent Questions</h3>
          {history.map((item, i) => (
            <div key={i} className="bg-white rounded-xl shadow-md p-6 mb-4 hover:shadow-lg transition duration-200 border-l-4 border-book-purple">
              <p className="font-semibold text-blue-600 mb-2 text-lg">Q: {item.question}</p>
              <p className="text-gray-700 line-clamp-3">{item.answer.answer}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-12">
        <h3 className="text-xl font-bold text-gray-900 mb-4">Try these questions:</h3>
        <div className="flex flex-wrap gap-3">
          {suggestedQuestions.map((q, i) => (
            <button
              key={i}
              onClick={() => handleSuggestedQuestion(q)}
              className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-xl font-medium transition duration-200 border border-gray-200 hover:border-gray-300"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default QA;
