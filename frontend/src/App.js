import React from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import QA from './pages/QA';
import BookDetail from './pages/BookDetail';

function Navbar() {
  return (
    <nav className="bg-gray-900 shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to="/" className="text-2xl font-bold text-white">📚 BookIQ</Link>
          </div>
          <div className="flex items-center space-x-8">
            <Link to="/" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition duration-200">Dashboard</Link>
            <Link to="/qa" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition duration-200">Q&A</Link>
          </div>
        </div>
      </div>
    </nav>
  );
}

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/qa" element={<QA />} />
        <Route path="/books/:id" element={<BookDetail />} />
      </Routes>
    </div>
  );
}

export default App;
