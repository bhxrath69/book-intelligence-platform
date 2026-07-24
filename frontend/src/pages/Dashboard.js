import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';

function Dashboard() {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [stats, setStats] = useState({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetchBooks();
    fetchStats();
  }, []);

  const fetchBooks = async () => {
    try {
      const response = await api.get('/books/');
      setBooks(response.data);
    } catch (err) {
      setError('Failed to load books');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await api.get('/books/stats/');
      setStats(response.data);
    } catch (err) {
      console.error('Stats error:', err);
    }
  };

  const handleScrape = async () => {
    setScraping(true);
    setMessage('');
    try {
      const response = await api.post('/books/upload/');
      setMessage(`Success! Added ${response.data.new_books} new books. Skipped ${response.data.skipped}.`);
      fetchBooks();
      fetchStats();
    } catch (err) {
      setError('Scraping failed: ' + (err.response?.data?.error || err.message));
    } finally {
      setScraping(false);
    }
  };

  const getGenreColor = (genre) => {
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
  };

  const getInitials = (title, author) => {
    const t = title.charAt(0);
    const a = author.charAt(0);
    return t + a;
  };

  const getSentimentColor = (sentiment) => {
    if (sentiment === 'Positive') return 'bg-green-500';
    if (sentiment === 'Negative') return 'bg-red-500';
    return 'bg-gray-500';
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto py-12 px-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl shadow-md p-6 animate-pulse">
              <div className="h-48 bg-gray-200 rounded-lg mb-4"></div>
              <div className="h-6 bg-gray-200 rounded w-3/4 mb-2"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
              <div className="flex gap-2 mb-4">
                <div className="h-6 w-20 bg-gray-200 rounded-full"></div>
                <div className="h-6 w-24 bg-gray-200 rounded-full"></div>
              </div>
              <div className="h-20 bg-gray-200 rounded mb-4"></div>
              <button className="w-full h-10 bg-gray-200 rounded-lg"></button>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
      <div className="mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">Book Intelligence Platform</h1>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white p-8 rounded-xl shadow-lg">
            <h3 className="text-2xl font-bold text-gray-900">{stats.total_books || 0}</h3>
            <p className="text-gray-600">Total Books</p>
          </div>
          <div className="bg-white p-8 rounded-xl shadow-lg">
            <h3 className="text-2xl font-bold text-gray-900">{stats.processed_books || 0}</h3>
            <p className="text-gray-600">Processed</p>
          </div>
          <div className="bg-white p-8 rounded-xl shadow-lg">
            <h3 className="text-2xl font-bold text-gray-900">{stats.average_rating ? stats.average_rating.toFixed(1) : '0.0'}</h3>
            <p className="text-gray-600">Avg Rating</p>
          </div>
        </div>
        <button
          onClick={handleScrape}
          disabled={scraping}
          className="bg-book-purple text-white px-8 py-4 rounded-xl text-lg font-semibold hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-1"
        >
          {scraping ? 'Scraping...' : 'Scrape & Process Books'}
        </button>
        {message && (
          <div className="mt-4 p-4 bg-green-100 border border-green-400 text-green-700 rounded-lg">
            {message}
          </div>
        )}
        {error && (
          <div className="mt-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
            {error} <button onClick={() => setError('')} className="float-right text-red-500 hover:text-red-700">×</button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {books.map((book) => (
          <div key={book.id} className="bg-white rounded-2xl shadow-lg hover:shadow-2xl transition duration-300 overflow-hidden group">
            <div className="h-64 bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center relative overflow-hidden">
              {book.cover_image_url ? (
                <img src={book.cover_image_url} alt={book.title} className="w-full h-full object-cover group-hover:scale-105 transition duration-300" />
              ) : (
                <div className="text-4xl font-bold text-gray-500">{getInitials(book.title, book.author)}</div>
              )}
            </div>
            <div className="p-6">
              <h3 className="font-bold text-xl text-gray-900 mb-2 line-clamp-2 leading-tight">{book.title}</h3>
              <p className="text-gray-600 mb-4">{book.author}</p>
              <div className="flex items-center mb-3">
                <span className="text-yellow-500 text-xl mr-2">{book.star_display}</span>
                <span className="text-sm text-gray-500">({book.num_reviews} reviews)</span>
              </div>
              <div className="flex flex-wrap gap-2 mb-4">
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getGenreColor(book.genre)} text-white`}>
                  {book.genre}
                </span>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getSentimentColor(book.sentiment)} text-white`}>
                  {book.sentiment}
                </span>
              </div>
              <p className="text-gray-700 text-sm mb-6 line-clamp-3 leading-relaxed">{book.summary || book.description}</p>
              <Link
                to={`/books/${book.id}`}
                className="w-full block bg-book-purple text-white py-3 px-6 rounded-xl text-center font-semibold hover:bg-purple-700 transition duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
              >
                View Details →
              </Link>
            </div>
          </div>
        ))}
      </div>
      {books.length === 0 && !loading && (
        <div className="text-center py-24">
          <p className="text-xl text-gray-500 mb-8">No books yet. Click "Scrape & Process Books" to start!</p>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
