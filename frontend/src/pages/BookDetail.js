import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/axios';

function getGenreColor(genre) {
  const colors = {
    'Fiction': 'bg-blue-500',
    'Mystery': 'bg-purple-500',
    'Romance': 'bg-pink-500',
    'Fantasy': 'bg-indigo-500',
    'Thriller': 'bg-red-500',
    'Biography': 'bg-green-500',
    'Self-Help': 'bg-yellow-500',
    'Other': 'bg-gray-500'
  };
  return colors[genre] || 'bg-gray-500';
}

function getSentimentIcon(sentiment) {
  if (sentiment === 'Positive') return '😊';
  if (sentiment === 'Negative') return '😞';
  return '😐';
}

function getStarDisplay(book) {
  if (book.star_display) return book.star_display;
  return '☆☆☆☆☆';
}

function BookDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [book, setBook] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (id) {
      fetchBook();
      fetchRecommendations();
    }
  }, [id]);

  const fetchBook = async () => {
    try {
      const response = await api.get(`/books/${id}/`);
      setBook(response.data);
    } catch (err) {
      setError('Book not found');
    }
  };

  const fetchRecommendations = async () => {
    try {
      const response = await api.get(`/books/${id}/recommend/`);
      setRecommendations(response.data);
    } catch (err) {
      console.error('Recommendations error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-book-purple"></div>
      </div>
    );
  }

  if (error || !book) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">{error || 'Book not found'}</h2>
          <button
            onClick={() => navigate('/')}
            className="bg-book-purple text-white px-6 py-3 rounded-xl font-semibold hover:bg-purple-700 transition duration-200"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-12">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <button
          onClick={() => navigate('/')}
          className="mb-8 inline-flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition duration-200 shadow-sm"
        >
          ← Back to Dashboard
        </button>

        <div className="grid lg:grid-cols-2 gap-12 items-start">
          {/* Book Cover & Basic Info */}
          <div className="lg:sticky lg:top-12">
            <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
              <div className="h-96 bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center relative">
                {book.cover_image_url ? (
                  <img src={book.cover_image_url} alt={book.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="text-6xl font-bold text-gray-400">
                    {book.title.charAt(0)}{book.author.charAt(0)}
                  </div>
                )}
              </div>
            </div>
            {book.book_url && (
              <a
                href={book.book_url}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full mt-6 bg-gradient-to-r from-book-purple to-indigo-600 text-white py-4 px-6 rounded-xl text-center font-semibold hover:from-purple-600 hover:to-indigo-700 transition duration-200 shadow-xl hover:shadow-2xl transform hover:-translate-y-1 text-lg"
              >
                View on Original Site →
              </a>
            )}
          </div>

          {/* Book Details */}
          <div>
            <h1 className="text-4xl lg:text-5xl font-bold text-gray-900 mb-6 leading-tight">{book.title}</h1>
            <div className="flex items-center mb-8">
              <span className="text-3xl mr-3">{getStarDisplay(book)}</span>
              <span className="text-2xl font-semibold text-gray-900 mr-6">{book.rating}/5</span>
              <span className="text-xl text-gray-600">({book.num_reviews} reviews)</span>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-8 max-w-md">
              <div className="bg-white p-6 rounded-xl shadow-lg">
                <div className={`inline-block px-4 py-2 rounded-full text-sm font-semibold ${getGenreColor(book.genre)} text-white`}>
                  {book.genre}
                </div>
              </div>
              <div className="bg-white p-6 rounded-xl shadow-lg flex items-center">
                <span className="text-2xl mr-3">{getSentimentIcon(book.sentiment)}</span>
                <span className="font-semibold text-xl text-gray-900">{book.sentiment}</span>
              </div>
            </div>

            <div className="bg-white rounded-2xl shadow-xl p-8 mb-8">
              <h3 className="text-2xl font-bold text-gray-900 mb-4">Author</h3>
              <p className="text-2xl text-gray-700">{book.author}</p>
            </div>

            <div className="bg-white rounded-2xl shadow-xl p-8 mb-8">
              <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
                <svg className="w-7 h-7 mr-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 10a2 2 0 00-2-2H9a2 2 0 00-2 2v3a2 2 0 002 2h5"></path>
                </svg>
                Description
              </h3>
              <p className="text-lg leading-relaxed text-gray-700 prose prose-lg max-w-none">
                {book.description}
              </p>
            </div>

            {book.summary && (
              <div className="bg-gradient-to-r from-book-purple to-indigo-600 text-white rounded-2xl p-8 mb-12 shadow-2xl">
                <h3 className="text-2xl font-bold mb-6">AI Summary</h3>
                <p className="text-xl leading-relaxed opacity-95">{book.summary}</p>
              </div>
            )}
          </div>
        </div>

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div className="mt-24">
            <h3 className="text-3xl font-bold text-gray-900 mb-12 text-center">
              If you liked this, you'll also enjoy:
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {recommendations.map((rec) => (
                <div
                  key={rec.id}
                  className="group cursor-pointer bg-white rounded-2xl shadow-lg hover:shadow-2xl transition duration-300 overflow-hidden"
                  onClick={() => navigate(`/books/${rec.id}`)}
                >
                  <div className="h-64 bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center relative overflow-hidden">
                    {rec.cover_image_url ? (
                      <img src={rec.cover_image_url} alt={rec.title} className="w-full h-full object-cover group-hover:scale-105 transition duration-300" />
                    ) : (
                      <div className="text-4xl font-bold text-gray-400">
                        {rec.title.charAt(0)}{rec.author.charAt(0)}
                      </div>
                    )}
                  </div>
                  <div className="p-6">
                    <h4 className="font-bold text-xl text-gray-900 mb-3 line-clamp-2">{rec.title}</h4>
                    <p className="text-gray-600 mb-4">{rec.author}</p>
                    <div className="flex items-center mb-4">
                      <span className="text-yellow-500 text-xl mr-2">{rec.star_display}</span>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getGenreColor(rec.genre)} text-white`}>
                      {rec.genre}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default BookDetail;

